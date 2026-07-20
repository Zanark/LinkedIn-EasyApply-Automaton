"""Post-apply outreach to the "Meet the hiring team" recruiters (opt-in).

After a successful application the job page often shows a *Meet the hiring team*
section with recruiter cards that expose a free **Message** button. This module
detects those cards, drafts a personalised message, pauses for the user's
approval, and only then types and sends it. It is deliberately conservative:

* it only ever acts when an approval handler is wired (draft-and-approve),
* it skips cards without a free Message button (e.g. paid InMail only),
* it de-duplicates against people already messaged, and
* it honours a per-run cap.

The DOM-touching parts are intentionally thin so the decision logic can be unit
tested with a fake page.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from linkedin_easy_apply.answers.hiring_message import HiringTeamMessenger
from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.dom_utils import first, first_group, is_visible, safe_text
from linkedin_easy_apply.utils.text import normalize

# Given (person_name, drafted_message) return the message to send (possibly
# edited) or ``None`` to skip this person.
ApproveHandler = Callable[[str, str], "str | None"]
HasMessaged = Callable[[str], bool]


@dataclass(slots=True)
class Recruiter:
    """A messageable hiring-team member extracted from a card."""

    name: str
    profile_url: str | None
    button: Any  # the "Message" button locator

    @property
    def key(self) -> str:
        """Stable de-dup key: the profile path, else the normalised name."""
        if self.profile_url:
            return self.profile_url.split("?")[0].rstrip("/")
        return normalize(self.name)

    @property
    def first_name(self) -> str:
        return self.name.split()[0] if self.name.strip() else "there"


class HiringTeamOutreach:
    """Detect hiring-team recruiters and send approved outreach messages."""

    def __init__(
        self,
        messenger: HiringTeamMessenger,
        *,
        on_approve: ApproveHandler,
        has_messaged: HasMessaged,
        record: Callable[..., Any],
        max_per_run: int = 5,
        skip_if_messaged: bool = True,
        dry_run: bool = False,
    ) -> None:
        self._messenger = messenger
        self._on_approve = on_approve
        self._has_messaged = has_messaged
        self._record = record
        self._max_per_run = max_per_run
        self._skip_if_messaged = skip_if_messaged
        self._dry_run = dry_run
        self._sent_this_run = 0

    def reach_out(
        self,
        page: Any,
        base_context: dict[str, Any],
        *,
        run_id: int | None = None,
        job_id: int | None = None,
    ) -> int:
        """Message the hiring team for the current job page. Returns the count
        of messages actually sent."""
        if self._sent_this_run >= self._max_per_run:
            logger.info("Outreach: per-run cap ({}) reached - skipping", self._max_per_run)
            return 0

        section = first(page, selectors.HIRING_TEAM_SECTION)
        if section is None:
            logger.debug("Outreach: no 'Meet the hiring team' section on this job")
            return 0

        cards = first_group(section, selectors.HIRING_TEAM_CARD)
        count = cards.count() if cards is not None else 0
        if cards is None or not count:
            logger.debug("Outreach: hiring-team section present but no recruiter cards")
            return 0
        logger.info("Outreach: found {} hiring-team card(s)", count)

        sent = 0
        for index in range(count):
            if self._sent_this_run >= self._max_per_run:
                logger.info("Outreach: per-run cap ({}) reached", self._max_per_run)
                break
            recruiter = self._read_card(cards.nth(index))
            if recruiter is None:
                continue
            if self._process(page, recruiter, base_context, run_id=run_id, job_id=job_id):
                sent += 1
        return sent

    # -- per-recruiter --------------------------------------------------------
    def _process(
        self,
        page: Any,
        recruiter: Recruiter,
        base_context: dict[str, Any],
        *,
        run_id: int | None,
        job_id: int | None,
    ) -> bool:
        if self._skip_if_messaged and self._has_messaged(recruiter.key):
            logger.info("Outreach: already messaged {} - skipping", recruiter.name)
            return False

        message = self._messenger.render(
            {
                **base_context,
                "recruiter_name": recruiter.name,
                "recruiter_first_name": recruiter.first_name,
            }
        )
        logger.info("Outreach: drafted message for {} ({} chars)", recruiter.name, len(message))

        decision = self._on_approve(recruiter.name, message)
        if decision is None:
            logger.info("Outreach: declined sending to {}", recruiter.name)
            self._record_safe(
                person_key=recruiter.key,
                person_name=recruiter.name,
                profile_url=recruiter.profile_url,
                message=message,
                status="declined",
                run_id=run_id,
                job_id=job_id,
            )
            return False

        message = decision
        if self._dry_run:
            logger.info("Outreach: [dry-run] would send to {}", recruiter.name)
            self._record_safe(
                person_key=recruiter.key,
                person_name=recruiter.name,
                profile_url=recruiter.profile_url,
                message=message,
                status="dry_run",
                run_id=run_id,
                job_id=job_id,
            )
            return False

        ok = self._send(page, recruiter, message)
        self._record_safe(
            person_key=recruiter.key,
            person_name=recruiter.name,
            profile_url=recruiter.profile_url,
            message=message,
            status="sent" if ok else "failed",
            run_id=run_id,
            job_id=job_id,
        )
        if ok:
            self._sent_this_run += 1
            logger.success("Outreach: message sent to {}", recruiter.name)
        else:
            logger.warning("Outreach: failed to send to {}", recruiter.name)
        return ok

    # -- DOM helpers ----------------------------------------------------------
    def _read_card(self, card: Any) -> Recruiter | None:
        name = safe_text(first(card, selectors.HIRING_TEAM_NAME))
        button = first(card, selectors.HIRING_TEAM_MESSAGE_BUTTON)
        if not name:
            logger.debug("Outreach: skipping a card with no readable name")
            return None
        if button is None or not is_visible(button):
            logger.info("Outreach: {} has no free Message button (InMail only?) - skipping", name)
            return None
        link = first(card, selectors.HIRING_TEAM_PROFILE_LINK)
        profile_url = None
        if link is not None:
            try:
                profile_url = link.get_attribute("href")
            except Exception:  # pragma: no cover - defensive
                profile_url = None
        return Recruiter(name=name, profile_url=profile_url, button=button)

    def _send(self, page: Any, recruiter: Recruiter, message: str) -> bool:
        try:
            recruiter.button.click()
            page.wait_for_timeout(1200)
            box = first(page, selectors.MSG_COMPOSE_BOX)
            if box is None:
                logger.warning("Outreach: message compose box did not open")
                self._close_overlay(page)
                return False
            box.click()
            # ``fill`` sets the text without emitting the Enter keypress that
            # would otherwise send a half-written message.
            try:
                box.fill(message)
            except Exception:  # pragma: no cover - contenteditable fallback
                page.keyboard.type(message)
            page.wait_for_timeout(400)
            send = first(page, selectors.MSG_SEND_BUTTON)
            if send is None:
                logger.warning("Outreach: Send button not found")
                self._close_overlay(page)
                return False
            send.click()
            page.wait_for_timeout(800)
            self._close_overlay(page)
            return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Outreach: send error for {}: {}", recruiter.name, exc)
            self._close_overlay(page)
            return False

    def _close_overlay(self, page: Any) -> None:
        try:
            close = first(page, selectors.MSG_OVERLAY_CLOSE)
            if close is not None and is_visible(close):
                close.click()
                page.wait_for_timeout(300)
        except Exception:  # pragma: no cover - defensive
            pass

    def _record_safe(self, **kwargs: Any) -> None:
        try:
            self._record(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Outreach: could not record message: {}", exc)
