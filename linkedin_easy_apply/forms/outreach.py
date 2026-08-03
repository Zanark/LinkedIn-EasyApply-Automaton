"""Post-apply outreach to the "Meet the hiring team" recruiters.

After a successful application the job page often shows a *Meet the hiring team*
section with recruiter cards. Each card exposes the recruiter's name and (in the
anchor around it) their LinkedIn profile URL, and sometimes a free **Message**
button. This module reads those cards and handles them in one of two modes:

* ``draft`` (default) -- read the name + profile URL, draft a personalised
  message, and record it as a *drafted* contact. It never clicks anything, so it
  is safe to run fully unattended; the orchestrator writes a plain-text report of
  every drafted contact at the end of the run for the user to send by hand.
* ``send`` -- draft, pause for the user's approval, then type and send the
  message via LinkedIn's Message button. Conservative: it skips cards without a
  free Message button (paid InMail only), de-duplicates, and honours a per-run
  cap. Needs an interactive session.

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

DRAFT_MODE = "draft"
SEND_MODE = "send"

# Draft mode only READS the page, so it just lets the post-apply "Meet the hiring
# team" section settle briefly before scanning.
_SECTION_SETTLE_MS = 1500
# Send mode must click the Message button, but LinkedIn's post-apply upsell modal
# ("Turn your resume into a profile that recruiters notice") renders a couple of
# seconds AFTER submit and overlays it. Wait this long for the modal, then
# dismiss it before messaging.
_UPSELL_SETTLE_MS = 3000
# How long to keep polling for the messaging compose box to open after clicking
# "Message" (the overlay can be slow to mount).
_COMPOSE_POLL_ATTEMPTS = 4
_COMPOSE_POLL_MS = 700


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
    """Detect hiring-team recruiters and either draft (for a report) or message them."""

    def __init__(
        self,
        messenger: HiringTeamMessenger,
        *,
        mode: str = DRAFT_MODE,
        on_approve: ApproveHandler | None = None,
        has_messaged: HasMessaged,
        record: Callable[..., Any],
        max_per_run: int = 5,
        skip_if_messaged: bool = True,
        dry_run: bool = False,
    ) -> None:
        self._messenger = messenger
        # Sending needs an approval handler; without one we can only draft.
        self._mode = SEND_MODE if (str(mode) == SEND_MODE and on_approve) else DRAFT_MODE
        self._on_approve = on_approve
        self._has_messaged = has_messaged
        self._record = record
        self._max_per_run = max_per_run
        self._skip_if_messaged = skip_if_messaged
        self._dry_run = dry_run
        self._acted_this_run = 0
        self._collected_keys: set[str] = set()

    def reach_out(
        self,
        page: Any,
        base_context: dict[str, Any],
        *,
        run_id: int | None = None,
        job_id: int | None = None,
    ) -> int:
        """Handle the hiring team for the current job page.

        Returns the number of recruiters acted on -- drafted in ``draft`` mode,
        or actually messaged in ``send`` mode.
        """
        logger.info(
            "Outreach: scanning for 'Meet the hiring team' recruiters ({} mode)...", self._mode
        )
        if self._acted_this_run >= self._max_per_run:
            logger.info("Outreach: per-run cap ({}) reached - skipping", self._max_per_run)
            return 0

        if self._mode == SEND_MODE:
            # The post-apply upsell modal overlays the page and intercepts the
            # Message button. Give it time to appear, then clear it via "Not now"
            # BEFORE messaging so the flow runs on an unobstructed, settled page.
            page.wait_for_timeout(_UPSELL_SETTLE_MS)
            self._dismiss_upsell(page)
        else:
            # Draft mode reads the DOM straight through any overlay; just let the
            # "Meet the hiring team" section render before scanning.
            page.wait_for_timeout(_SECTION_SETTLE_MS)

        section = first(page, selectors.HIRING_TEAM_SECTION)
        if section is None:
            logger.info("Outreach: no 'Meet the hiring team' section found on this page")
            return 0

        cards = first_group(section, selectors.HIRING_TEAM_CARD)
        count = cards.count() if cards is not None else 0
        if cards is None or not count:
            logger.info("Outreach: hiring-team section present but no recruiter cards found")
            return 0
        logger.info("Outreach: found {} hiring-team card(s)", count)

        handle = self._collect if self._mode == DRAFT_MODE else self._process
        done = 0
        for index in range(count):
            if self._acted_this_run >= self._max_per_run:
                logger.info("Outreach: per-run cap ({}) reached", self._max_per_run)
                break
            recruiter = self._read_card(cards.nth(index))
            if recruiter is None:
                continue
            if handle(page, recruiter, base_context, run_id=run_id, job_id=job_id):
                done += 1
        return done

    # -- draft mode (default) -------------------------------------------------
    def _collect(
        self,
        page: Any,
        recruiter: Recruiter,
        base_context: dict[str, Any],
        *,
        run_id: int | None,
        job_id: int | None,
    ) -> bool:
        """Draft a message and record the contact for the end-of-run report.

        Never clicks anything, and does not require a free Message button -- the
        user sends by hand from the recruiter's profile URL, so InMail-only cards
        are worth reporting too.
        """
        if recruiter.key in self._collected_keys:
            logger.debug("Outreach: {} already drafted this run - skipping", recruiter.name)
            return False
        if self._skip_if_messaged and self._has_messaged(recruiter.key):
            logger.info("Outreach: already messaged {} previously - skipping", recruiter.name)
            return False

        message = self._messenger.render(
            {
                **base_context,
                "recruiter_name": recruiter.name,
                "recruiter_first_name": recruiter.first_name,
            }
        )
        note = self._messenger.render_note(
            {
                **base_context,
                "recruiter_name": recruiter.name,
                "recruiter_first_name": recruiter.first_name,
            }
        )
        self._collected_keys.add(recruiter.key)
        self._acted_this_run += 1
        self._record_safe(
            person_key=recruiter.key,
            person_name=recruiter.name,
            profile_url=recruiter.profile_url,
            message=message,
            note=note,
            status="drafted",
            run_id=run_id,
            job_id=job_id,
        )
        logger.success(
            "Outreach: drafted message for {} ({} chars, note {} chars) -> {}",
            recruiter.name,
            len(message),
            len(note),
            recruiter.profile_url or "(no profile URL)",
        )
        return True

    # -- send mode (opt-in) ---------------------------------------------------
    def _process(
        self,
        page: Any,
        recruiter: Recruiter,
        base_context: dict[str, Any],
        *,
        run_id: int | None,
        job_id: int | None,
    ) -> bool:
        if recruiter.button is None or not is_visible(recruiter.button):
            logger.info(
                "Outreach: {} has no free Message button (InMail only?) - skipping", recruiter.name
            )
            return False
        if self._skip_if_messaged and self._has_messaged(recruiter.key):
            logger.info("Outreach: already messaged {} - skipping", recruiter.name)
            return False

        context = {
            **base_context,
            "recruiter_name": recruiter.name,
            "recruiter_first_name": recruiter.first_name,
        }
        message = self._messenger.render(context)
        note = self._messenger.render_note(context)
        logger.info("Outreach: drafted message for {} ({} chars)", recruiter.name, len(message))

        assert self._on_approve is not None  # send mode always has a handler
        decision = self._on_approve(recruiter.name, message)
        if decision is None:
            logger.info("Outreach: declined sending to {}", recruiter.name)
            self._record_safe(
                person_key=recruiter.key,
                person_name=recruiter.name,
                profile_url=recruiter.profile_url,
                message=message,
                note=note,
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
                note=note,
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
            note=note,
            status="sent" if ok else "failed",
            run_id=run_id,
            job_id=job_id,
        )
        if ok:
            self._acted_this_run += 1
            logger.success("Outreach: message sent to {}", recruiter.name)
        else:
            logger.warning("Outreach: failed to send to {}", recruiter.name)
        return ok

    # -- DOM helpers ----------------------------------------------------------
    def _read_card(self, card: Any) -> Recruiter | None:
        """Read a recruiter card into a :class:`Recruiter`.

        Requires only a readable name; the profile URL and Message button are
        optional (send mode enforces the button in ``_process``, draft mode does
        not need it). Returns ``None`` for an unreadable/nameless card.
        """
        name = safe_text(first(card, selectors.HIRING_TEAM_NAME))
        if not name:
            logger.debug("Outreach: skipping a card with no readable name")
            return None
        link = first(card, selectors.HIRING_TEAM_PROFILE_LINK)
        profile_url = None
        if link is not None:
            try:
                profile_url = link.get_attribute("href")
            except Exception:  # pragma: no cover - defensive
                profile_url = None
        button = first(card, selectors.HIRING_TEAM_MESSAGE_BUTTON)
        return Recruiter(name=name, profile_url=profile_url, button=button)

    def _send(self, page: Any, recruiter: Recruiter, message: str) -> bool:
        try:
            # Defensive: clear the upsell modal if it (re)appeared after scanning.
            self._dismiss_upsell(page)
            recruiter.button.click()
            # The compose overlay can be slow to mount; poll for it rather than
            # relying on a single fixed wait.
            box = None
            for _ in range(_COMPOSE_POLL_ATTEMPTS):
                page.wait_for_timeout(_COMPOSE_POLL_MS)
                box = first(page, selectors.MSG_COMPOSE_BOX)
                if box is not None:
                    break
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

    def _dismiss_upsell(self, page: Any) -> None:
        """Dismiss LinkedIn's post-apply upsell modal ("Turn your resume into a
        profile that recruiters notice") that overlays the page after submit and
        intercepts clicks on the hiring-team Message button. Clicking its "Not
        now" leaves the "Meet the hiring team" cards in place, so this is safe to
        call before scanning and before each Message click; it is a no-op when no
        such modal is present."""
        try:
            dismiss = first(page, selectors.POST_APPLY_UPSELL_DISMISS)
            if dismiss is not None and is_visible(dismiss):
                dismiss.click()
                page.wait_for_timeout(500)
                logger.info("Outreach: dismissed post-apply upsell modal ('Not now')")
        except Exception:  # pragma: no cover - defensive
            pass

    def _record_safe(self, **kwargs: Any) -> None:
        try:
            self._record(**kwargs)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Outreach: could not record message: {}", exc)
