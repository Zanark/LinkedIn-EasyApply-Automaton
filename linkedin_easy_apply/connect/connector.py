"""Send a free LinkedIn *connection invitation* with a custom note.

This is the DOM-facing half of the connection-note microservice: given a target
recruiter's profile URL and their <=300-char note, it drives the profile page
through **Connect -> note -> Send**. An explicit opt-in permits a plain invitation
only when note entry is unavailable inside an identified invitation dialog.
It never sends the long message or treats a click alone as confirmed delivery.

The class is intentionally thin so the decision flow can be unit-tested against a
fake page. :class:`~linkedin_easy_apply.connect.service.ConnectionInviteService`
owns the browser, pacing and persistence around it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from loguru import logger

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.dom_utils import is_visible, safe_text

# LinkedIn caps a free connection-invitation note at 300 characters.
NOTE_CHAR_LIMIT = 300
_POLL_MS = 100
_NO_NOTE_ACTIONS = frozenset({"send without a note", "send without note"})
_SEND_ACTIONS = frozenset({"send", "send now", "send invitation", "send invite", "connect"})
_EXPLICIT_INVITE_ACTIONS = _NO_NOTE_ACTIONS | {"send invitation", "send invite"}
_INVITE_HEADING = re.compile(r"\binvitation\b|^invite .+ to connect\b|^connect with\b")
_SENT_CONFIRMATION = re.compile(
    r"^(?:invitation sent(?: to .+)?|your invitation (?:to .+ )?has been sent)[.!]?$"
)


class ConnectOutcome(StrEnum):
    """The result of trying to send one connection invitation."""

    SENT = "sent"  # invitation with the note was sent
    SENT_WITHOUT_NOTE = "sent_without_note"
    ALREADY = "already"  # already connected, or an invite is already pending
    NO_BUTTON = "no_button"  # no Connect entry point (top-card or "More" menu)
    NOTE_UNAVAILABLE = "note_unavailable"  # the "Add a note" field never appeared
    LIMIT_REACHED = "limit_reached"  # LinkedIn's weekly invitation limit was hit
    DRY_RUN = "dry_run"  # everything but the final Send click (dry-run)
    DRY_RUN_WITHOUT_NOTE = "dry_run_without_note"
    FAILED = "failed"  # navigation error, missing Send button, or an exception


@dataclass(slots=True)
class InviteTarget:
    """One person to invite: their profile URL and the note to attach."""

    id: int
    person_name: str | None
    profile_url: str
    note: str

    @property
    def label(self) -> str:
        return self.person_name or self.profile_url


class ProfileConnector:
    """Drive a single profile page through Connect -> Add a note -> Send.

    ``allow_without_note`` permits a plain invitation only when note entry is
    unavailable. Generic Send/Connect actions require identified invitation
    context. ``dry_run`` never clicks a final action.
    """

    def __init__(
        self,
        *,
        dry_run: bool = False,
        allow_without_note: bool = False,
        settle_ms: int = 2500,
        modal_ms: int = 3000,
    ) -> None:
        self._dry_run = dry_run
        self._allow_without_note = allow_without_note
        self._settle_ms = settle_ms
        self._modal_ms = modal_ms

    def send_invite(self, page: Any, target: InviteTarget) -> ConnectOutcome:
        """Open *target*'s profile and send the connection note. Never raises."""
        try:
            self._open_profile(page, target.profile_url)
            if self._already_in_network(page):
                logger.info("Connect: {} is already connected/pending - skipping", target.label)
                return ConnectOutcome.ALREADY
            if not self._click_connect(page):
                logger.info("Connect: no Connect button for {} - skipping", target.label)
                return ConnectOutcome.NO_BUTTON
            dialog = self._wait_for(page, lambda: self._invitation_dialog(page))
            if self._invite_limit_hit(page):
                logger.warning("Connect: weekly invitation limit reached")
                return ConnectOutcome.LIMIT_REACHED
            if dialog is None:
                logger.warning(
                    "Connect: no identified invitation dialog for {} - no final action taken",
                    target.label,
                )
                return ConnectOutcome.FAILED
            return self._add_note_and_send(page, dialog, target)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Connect: error opening invitation for {}: {}", target.label, exc)
            return ConnectOutcome.FAILED

    # -- steps ----------------------------------------------------------------
    def _open_profile(self, page: Any, url: str) -> None:
        page.goto(url)
        try:
            page.wait_for_load_state("domcontentloaded")
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Connect: profile load-state wait did not complete: {}", exc)
        page.wait_for_timeout(self._settle_ms)

    def _already_in_network(self, page: Any) -> bool:
        return any(self._visible_matches(page, selectors.PROFILE_PENDING))

    def _click_connect(self, page: Any) -> bool:
        """Click Connect from the top card, or via the "More" overflow menu."""
        button = self._first_available(page, selectors.PROFILE_CONNECT_BUTTON)
        if button is not None:
            button.click()
            return True
        more = self._first_available(page, selectors.PROFILE_MORE_BUTTON)
        if more is not None:
            more.click()
            entry = self._wait_for(
                page,
                lambda: self._first_available(
                    page, selectors.PROFILE_MORE_CONNECT, labels=frozenset({"connect"})
                ),
            )
            if entry is not None:
                entry.click()
                return True
        return False

    @staticmethod
    def _normalized(text: str) -> str:
        return " ".join(text.split()).casefold()

    def _invite_limit_hit(self, page: Any) -> bool:
        return any(self._visible_matches(page, selectors.INVITE_LIMIT_MODAL))

    @staticmethod
    def _visible_matches(scope: Any, candidates: list[str]) -> Iterator[Any]:
        for selector in candidates:
            matches = scope.locator(selector)
            for index in range(matches.count()):
                control = matches.nth(index)
                if is_visible(control):
                    yield control

    @classmethod
    def _matches_action(cls, control: Any, labels: frozenset[str]) -> bool:
        text = cls._normalized(safe_text(control))
        aria = cls._normalized(control.get_attribute("aria-label") or "")
        # A generic aria-label must not veto clear text; a misleading visible
        # instruction must not become a send action just because of its aria-label.
        return text in labels or (text in {"", "send", "send now", "connect"} and aria in labels)

    @classmethod
    def _first_available(
        cls,
        scope: Any,
        candidates: list[str],
        *,
        labels: frozenset[str] | None = None,
        editable: bool = False,
    ) -> Any | None:
        for control in cls._visible_matches(scope, candidates):
            if (
                control.is_enabled()
                and (not editable or control.is_editable())
                and (labels is None or cls._matches_action(control, labels))
            ):
                return control
        return None

    def _wait_for(self, page: Any, probe: Callable[[], Any]) -> Any | None:
        remaining = max(0, self._modal_ms)
        while True:
            if self._invite_limit_hit(page):
                return None
            result = probe()
            if result:
                return result
            if remaining == 0:
                return None
            delay = min(_POLL_MS, remaining)
            page.wait_for_timeout(delay)
            remaining -= delay

    def _invitation_dialog(self, page: Any) -> Any | None:
        for dialog in self._visible_matches(page, selectors.INVITE_DIALOG):
            heading = _INVITE_HEADING.search(
                self._normalized(dialog.get_attribute("aria-label") or "")
            ) or any(
                _INVITE_HEADING.search(self._normalized(safe_text(control)))
                for control in self._visible_matches(dialog, selectors.INVITE_DIALOG_HEADING)
            )
            explicit_action = any(
                self._matches_action(control, _EXPLICIT_INVITE_ACTIONS)
                for control in self._visible_matches(
                    dialog, selectors.INVITE_SEND_WITHOUT_NOTE_BUTTON + selectors.INVITE_SEND_BUTTON
                )
            )
            if heading or explicit_action:
                return dialog
        return None

    def _note_box(self, dialog: Any) -> Any | None:
        return self._first_available(dialog, selectors.INVITE_NOTE_TEXTAREA, editable=True)

    def _add_note_and_send(self, page: Any, dialog: Any, target: InviteTarget) -> ConnectOutcome:
        try:
            self._wait_for(
                page,
                lambda: self._note_box(dialog)
                or self._first_available(
                    dialog, selectors.INVITE_ADD_NOTE_BUTTON, labels=frozenset({"add a note"})
                ),
            )
            if self._invite_limit_hit(page):
                return ConnectOutcome.LIMIT_REACHED
            box = self._note_box(dialog)
            if box is None:
                add_note = self._first_available(
                    dialog, selectors.INVITE_ADD_NOTE_BUTTON, labels=frozenset({"add a note"})
                )
                if add_note is not None:
                    add_note.click()
                    box = self._wait_for(page, lambda: self._note_box(dialog))
                if self._invite_limit_hit(page):
                    return ConnectOutcome.LIMIT_REACHED
                if box is None:
                    return self._note_unavailable(page, dialog, target)
            return self._send_note(page, dialog, box, target)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Connect: error sending to {}: {}", target.label, exc)
            if not self._has_note_draft(dialog):
                self._dismiss(dialog)
            return ConnectOutcome.FAILED

    def _send_note(self, page: Any, dialog: Any, box: Any, target: InviteTarget) -> ConnectOutcome:
        note = target.note.strip()
        if not note:
            logger.warning("Connect: note for {} is empty - not sending", target.label)
            return ConnectOutcome.FAILED
        if len(note) > NOTE_CHAR_LIMIT:
            logger.warning(
                "Connect: note for {} is {} chars; trimming to {}",
                target.label,
                len(note),
                NOTE_CHAR_LIMIT,
            )
            note = note[:NOTE_CHAR_LIMIT]
        existing = box.input_value()
        if existing.strip() and existing != note:
            logger.warning(
                "Connect: existing note draft for {} differs - leaving it untouched",
                target.label,
            )
            return ConnectOutcome.FAILED
        if existing != note:
            box.click()
            box.fill(note)
        send = self._wait_for(
            page,
            lambda: self._first_available(
                dialog, selectors.INVITE_SEND_BUTTON, labels=_SEND_ACTIONS
            ),
        )
        if self._invite_limit_hit(page):
            return ConnectOutcome.LIMIT_REACHED
        if box.input_value() != note:
            logger.warning("Connect: note fill was not retained for {}", target.label)
            return ConnectOutcome.FAILED
        if send is None:
            logger.warning(
                "Connect: Send button not found for {} - retaining the draft", target.label
            )
            return ConnectOutcome.FAILED
        return self._send(
            page, dialog, send, target, without_note=False, preserve_draft=bool(existing.strip())
        )

    @staticmethod
    def _has_note_draft(dialog: Any) -> bool:
        for selector in selectors.INVITE_NOTE_DRAFT:
            boxes = dialog.locator(selector)
            if any(boxes.nth(index).input_value().strip() for index in range(boxes.count())):
                return True
        return False

    def _draft_blocks_fallback(self, dialog: Any, target: InviteTarget) -> bool:
        if self._has_note_draft(dialog):
            logger.warning(
                "Connect: unavailable note entry contains a draft for {} "
                "- leaving it untouched, not sending a plain invitation",
                target.label,
            )
            return True
        return False

    def _note_unavailable(self, page: Any, dialog: Any, target: InviteTarget) -> ConnectOutcome:
        if self._draft_blocks_fallback(dialog, target):
            return ConnectOutcome.FAILED
        if not self._allow_without_note:
            logger.warning(
                "Connect: note entry unavailable for {} - backing out "
                "(Connect without a note is off)",
                target.label,
            )
            self._dismiss(dialog)
            return ConnectOutcome.NOTE_UNAVAILABLE

        logger.warning(
            "Connect: note entry unavailable for {} - trying the enabled no-note fallback",
            target.label,
        )

        def ready() -> tuple[str, Any] | None:
            box = self._note_box(dialog)
            if box is not None:
                return "note", box
            send = self._first_available(
                dialog, selectors.INVITE_SEND_WITHOUT_NOTE_BUTTON, labels=_NO_NOTE_ACTIONS
            ) or self._first_available(dialog, selectors.INVITE_SEND_BUTTON, labels=_SEND_ACTIONS)
            return ("send", send) if send is not None else None

        choice = self._wait_for(page, ready)
        if self._invite_limit_hit(page):
            return ConnectOutcome.LIMIT_REACHED
        if choice is None:
            logger.warning(
                "Connect: no enabled, unambiguous plain-invitation action for {} - backing out",
                target.label,
            )
            self._dismiss(dialog)
            return ConnectOutcome.FAILED
        kind, control = choice
        if kind == "note":
            return self._send_note(page, dialog, control, target)
        if self._draft_blocks_fallback(dialog, target):
            return ConnectOutcome.FAILED
        return self._send(page, dialog, control, target, without_note=True)

    def _confirmation_texts(self, page: Any) -> set[str]:
        return {
            text
            for control in self._visible_matches(page, selectors.INVITE_SENT_CONFIRMATION)
            if _SENT_CONFIRMATION.fullmatch(text := self._normalized(safe_text(control)))
        }

    def _send(
        self,
        page: Any,
        dialog: Any,
        send: Any,
        target: InviteTarget,
        *,
        without_note: bool,
        preserve_draft: bool = False,
    ) -> ConnectOutcome:
        kind = "invitation without a note" if without_note else "connection note"
        if self._dry_run:
            logger.info("Connect: [dry-run] would send {} to {}", kind, target.label)
            if not preserve_draft:
                self._dismiss(dialog)
            return ConnectOutcome.DRY_RUN_WITHOUT_NOTE if without_note else ConnectOutcome.DRY_RUN

        previous = self._confirmation_texts(page)
        send.click()
        confirmed = self._wait_for(
            page,
            lambda: self._already_in_network(page)
            or bool(self._confirmation_texts(page) - previous),
        )
        if self._invite_limit_hit(page):
            logger.warning("Connect: weekly invitation limit reached on send")
            return ConnectOutcome.LIMIT_REACHED
        if not confirmed:
            logger.warning(
                "Connect: final action clicked for {}, but delivery is unconfirmed "
                "(no Pending indicator or new invitation-sent confirmation) "
                "- not marking sent or retrying",
                target.label,
            )
            return ConnectOutcome.FAILED
        logger.success("Connect: sent {} to {}", kind, target.label)
        return ConnectOutcome.SENT_WITHOUT_NOTE if without_note else ConnectOutcome.SENT

    def _dismiss(self, dialog: Any) -> None:
        """Close the invitation modal without sending (best-effort)."""
        try:
            btn = self._first_available(dialog, selectors.INVITE_DISMISS_BUTTON)
            if btn is not None:
                btn.click()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Connect: could not dismiss the invitation dialog: {}", exc)
