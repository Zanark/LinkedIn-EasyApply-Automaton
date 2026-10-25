"""Send a free LinkedIn *connection invitation* with a custom note.

This is the DOM-facing half of the connection-note microservice: given a target
recruiter's profile URL and their <=300-char note, it drives the profile page
through **Connect -> Add a note -> Send**. It never sends the long message - only
the free connection note that can be attached to an invitation.

The class is intentionally thin so the decision flow can be unit-tested against a
fake page. :class:`~linkedin_easy_apply.connect.service.ConnectionInviteService`
owns the browser, pacing and persistence around it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from loguru import logger

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.dom_utils import first, is_visible, safe_text

# LinkedIn caps a free connection-invitation note at 300 characters.
NOTE_CHAR_LIMIT = 300


class ConnectOutcome(StrEnum):
    """The result of trying to send one connection invitation."""

    SENT = "sent"  # invitation with the note was sent
    ALREADY = "already"  # already connected, or an invite is already pending
    NO_BUTTON = "no_button"  # no Connect entry point (top-card or "More" menu)
    NOTE_UNAVAILABLE = "note_unavailable"  # the "Add a note" field never appeared
    LIMIT_REACHED = "limit_reached"  # LinkedIn's weekly invitation limit was hit
    DRY_RUN = "dry_run"  # everything but the final Send click (dry-run)
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

    ``dry_run`` performs every step except the final Send click (and backs out of
    the modal), so it can be exercised safely against real profiles.
    """

    def __init__(
        self, *, dry_run: bool = False, settle_ms: int = 2500, modal_ms: int = 1200
    ) -> None:
        self._dry_run = dry_run
        self._settle_ms = settle_ms
        self._modal_ms = modal_ms

    def send_invite(self, page: Any, target: InviteTarget) -> ConnectOutcome:
        """Open *target*'s profile and send the connection note. Never raises."""
        try:
            self._open_profile(page, target.profile_url)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Connect: could not open {} ({})", target.profile_url, exc)
            return ConnectOutcome.FAILED

        if self._already_in_network(page):
            logger.info("Connect: {} is already connected/pending - skipping", target.label)
            return ConnectOutcome.ALREADY

        if not self._click_connect(page):
            logger.info("Connect: no Connect button for {} - skipping", target.label)
            return ConnectOutcome.NO_BUTTON

        page.wait_for_timeout(self._modal_ms)
        if self._invite_limit_hit(page):
            logger.warning("Connect: weekly invitation limit reached")
            return ConnectOutcome.LIMIT_REACHED

        return self._add_note_and_send(page, target)

    # -- steps ----------------------------------------------------------------
    def _open_profile(self, page: Any, url: str) -> None:
        page.goto(url)
        try:
            page.wait_for_load_state("domcontentloaded")
        except Exception:  # pragma: no cover - defensive
            pass
        page.wait_for_timeout(self._settle_ms)

    def _already_in_network(self, page: Any) -> bool:
        pending = first(page, selectors.PROFILE_PENDING)
        return pending is not None and is_visible(pending)

    def _click_connect(self, page: Any) -> bool:
        """Click Connect from the top card, or via the "More" overflow menu."""
        button = first(page, selectors.PROFILE_CONNECT_BUTTON)
        if button is not None and is_visible(button):
            button.click()
            return True
        more = first(page, selectors.PROFILE_MORE_BUTTON)
        if more is not None and is_visible(more):
            more.click()
            page.wait_for_timeout(900)
            entry = first(page, selectors.PROFILE_MORE_CONNECT)
            if entry is not None and is_visible(entry) and self._is_plain_connect(entry):
                entry.click()
                return True
        return False

    @staticmethod
    def _is_plain_connect(entry: Any) -> bool:
        """True only when the menu entry is exactly "Connect".

        Guards against clicking "Remove Connection" on an already-connected profile
        (which would disconnect them): our ``:has-text('Connect')`` selector also
        matches that item, so we verify the visible text before ever clicking.
        """
        text = safe_text(entry).strip().lower()
        if text != "connect":
            logger.info("Connect: More menu entry was {!r}, not a plain Connect - skipping", text)
            return False
        return True

    def _invite_limit_hit(self, page: Any) -> bool:
        modal = first(page, selectors.INVITE_LIMIT_MODAL)
        return modal is not None and is_visible(modal)

    def _add_note_and_send(self, page: Any, target: InviteTarget) -> ConnectOutcome:
        add_note = first(page, selectors.INVITE_ADD_NOTE_BUTTON)
        if add_note is None or not is_visible(add_note):
            logger.warning("Connect: 'Add a note' unavailable for {} - backing out", target.label)
            self._dismiss(page)
            return ConnectOutcome.NOTE_UNAVAILABLE

        note = target.note.strip()
        if len(note) > NOTE_CHAR_LIMIT:
            logger.warning(
                "Connect: note for {} is {} chars; trimming to {}",
                target.label,
                len(note),
                NOTE_CHAR_LIMIT,
            )
            note = note[:NOTE_CHAR_LIMIT]

        try:
            add_note.click()
            page.wait_for_timeout(800)
            box = first(page, selectors.INVITE_NOTE_TEXTAREA)
            if box is None:
                logger.warning("Connect: note textarea did not open for {}", target.label)
                self._dismiss(page)
                return ConnectOutcome.NOTE_UNAVAILABLE
            box.click()
            try:
                box.fill(note)
            except Exception:  # pragma: no cover - textarea fallback
                page.keyboard.type(note)
            page.wait_for_timeout(300)

            if self._dry_run:
                logger.info(
                    "Connect: [dry-run] would send note to {} ({} chars)", target.label, len(note)
                )
                self._dismiss(page)
                return ConnectOutcome.DRY_RUN

            send = first(page, selectors.INVITE_SEND_BUTTON)
            if send is None or not is_visible(send):
                logger.warning("Connect: Send button not found for {}", target.label)
                self._dismiss(page)
                return ConnectOutcome.FAILED
            send.click()
            page.wait_for_timeout(800)
            if self._invite_limit_hit(page):
                logger.warning("Connect: weekly invitation limit reached on send")
                return ConnectOutcome.LIMIT_REACHED
            logger.success(
                "Connect: sent connection note to {} ({} chars)", target.label, len(note)
            )
            return ConnectOutcome.SENT
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Connect: error sending to {}: {}", target.label, exc)
            self._dismiss(page)
            return ConnectOutcome.FAILED

    def _dismiss(self, page: Any) -> None:
        """Close the invitation modal without sending (best-effort)."""
        try:
            btn = first(page, selectors.INVITE_DISMISS_BUTTON)
            if btn is not None and is_visible(btn):
                btn.click()
                page.wait_for_timeout(300)
        except Exception:  # pragma: no cover - defensive
            pass
