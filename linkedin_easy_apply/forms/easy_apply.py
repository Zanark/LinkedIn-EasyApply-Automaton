"""The multi-step Easy Apply workflow.

This module drives a single application from the job page through every step of
the Easy Apply modal: it clicks *Easy Apply*, fills each detected field using the
parser/resolver/filler collaborators, handles unknown questions via an optional
callback, honours dry-run and interactive-approval modes, and finally submits or
discards the application.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from loguru import logger

from linkedin_easy_apply.answers.resolver import AnswerResolution, AnswerResolver
from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.detector import FormFieldDetector
from linkedin_easy_apply.forms.dom_utils import (
    first,
    first_group,
    force_close_dialogs,
    is_visible,
    safe_text,
)
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.filler import FormFiller
from linkedin_easy_apply.forms.matching import country_code_option, dial_code
from linkedin_easy_apply.forms.values import current_value_of
from linkedin_easy_apply.parser.categories import AnswerType, QuestionCategory
from linkedin_easy_apply.parser.question_parser import QuestionParser
from linkedin_easy_apply.progress import ProgressReporter
from linkedin_easy_apply.utils.screenshots import ScreenshotManager

# Marks the application form's container so field detection can be scoped to it.
_FORM_ATTR = "data-lea-form"
_TAG_FORM_JS = f"""
el => {{
  document.querySelectorAll('[{_FORM_ATTR}]').forEach(n => n.removeAttribute('{_FORM_ATTR}'));
  let node = el;
  for (let i = 0; i < 12 && node; i++) {{
    node = node.parentElement;
    if (!node) break;
    if (node.querySelector('[role="contentinfo"], footer')) {{
      node.setAttribute('{_FORM_ATTR}', '1');
      return true;
    }}
  }}
  return false;
}}
"""

# Callback types.
UnknownHandler = Callable[[str, "Path | None"], "str | None"]
ConfirmHandler = Callable[[], bool]
AnswerLookup = Callable[[str], "str | None"]

# Yes/No tokens for mapping an approved override to a boolean resolution.
_OVERRIDE_YES = {"yes", "y", "true", "1"}
_OVERRIDE_NO = {"no", "n", "false", "0"}

# Signature phrases from LinkedIn's platform-side daily Easy Apply cap notice
# ("We limit daily submissions ... Save this job and apply tomorrow"). Used as a
# text fallback when the structured SUBMIT_LIMIT_MODAL selectors don't match.
_DAILY_LIMIT_PHRASES = (
    "apply tomorrow",
    "limit daily submissions",
    "daily application limit",
)


class ApplyStatus(StrEnum):
    SUBMITTED = "submitted"
    DRY_RUN = "dry_run"
    SKIPPED = "skipped"
    FAILED = "failed"
    ABORTED = "aborted"
    LIMIT_REACHED = "limit_reached"
    UNCONFIRMED = "unconfirmed"


@dataclass(slots=True)
class AnsweredQuestion:
    """Record of a question encountered during an application."""

    question: str
    normalized: str
    category: str
    skill: str | None
    value: str | None
    source: str
    resolved: bool


@dataclass(slots=True)
class ApplyResult:
    status: ApplyStatus
    steps: int = 0
    reason: str | None = None
    screenshot: str | None = None
    answers: list[AnsweredQuestion] = field(default_factory=list)


@dataclass(slots=True)
class WorkflowSettings:
    """Behavioural toggles for a run."""

    dry_run: bool = False
    interactive: bool = False
    pause_on_unknown: bool = True
    max_steps: int = 15


class EasyApplyWorkflow:
    """Own the interaction with a single Easy Apply modal."""

    def __init__(
        self,
        page: Any,
        parser: QuestionParser,
        resolver: AnswerResolver,
        detector: FormFieldDetector,
        filler: FormFiller,
        screenshots: ScreenshotManager,
        settings: WorkflowSettings,
        *,
        on_unknown: UnknownHandler | None = None,
        on_confirm_submit: ConfirmHandler | None = None,
        answer_lookup: AnswerLookup | None = None,
        override_lookup: AnswerLookup | None = None,
        progress: ProgressReporter | None = None,
    ) -> None:
        self._page = page
        self._parser = parser
        self._resolver = resolver
        self._detector = detector
        self._filler = filler
        self._screenshots = screenshots
        self._settings = settings
        self._on_unknown = on_unknown
        self._on_confirm = on_confirm_submit
        self._answer_lookup = answer_lookup
        self._override_lookup = override_lookup
        self._progress = progress or ProgressReporter()
        self._resume_selected_done = False

    def apply(
        self,
        *,
        resume_path: str | None = None,
        cover_letter_path: str | None = None,
        cover_letter_text: str | None = None,
    ) -> ApplyResult:
        """Run the Easy Apply flow on the currently open job page."""
        answers: list[AnsweredQuestion] = []
        self._resume_selected_done = False
        logger.info(
            "Starting Easy Apply flow (dry_run={}, interactive={}, pause_on_unknown={})",
            self._settings.dry_run,
            self._settings.interactive,
            self._settings.pause_on_unknown,
        )
        self._progress.activity("opening_application")
        if not self._open_modal():
            return ApplyResult(ApplyStatus.SKIPPED, reason="Easy Apply button not available")

        for step in range(1, self._settings.max_steps + 1):
            self._page.wait_for_timeout(600)
            self._screenshot(f"step-{step}")
            logger.info("--- Easy Apply step {} ---", step)
            # Re-scope every step: the rebuilt form replaces its container as
            # it advances, so a locator captured up front goes stale.
            modal = self._form_scope()

            self._fill_step(modal, answers, resume_path, cover_letter_path, cover_letter_text)

            action = self._detect_action(modal)
            logger.debug("Step {}: next action = {}", step, action)

            if action == "submit":
                return self._finalize_submit(answers, step)
            if action in {"next", "review"}:
                self._progress.activity(
                    "reviewing_application" if action == "review" else "filling_application"
                )
                # Measure the click's own effect: comparing this step to the
                # previous one aborts whenever two steps merely look alike.
                before = self._step_signature(modal)
                self._click_action(
                    modal,
                    action,
                    selectors.BTN_REVIEW if action == "review" else selectors.BTN_NEXT,
                )
                self._page.wait_for_timeout(800)
                if not self._wait_for_step_change(before):
                    return self._abort(answers, step, "No progress between steps")
                continue
            return self._abort(answers, step, "No actionable button found")

        return self._abort(answers, self._settings.max_steps, "Exceeded max steps")

    # -- modal control --------------------------------------------------------
    def _open_modal(self) -> bool:
        # A form left open by an earlier job would otherwise be mistaken for
        # this job's, and we would "apply" to the wrong posting.
        if self._modal_is_open():
            logger.debug("A form was still open before starting - clearing it")
            force_close_dialogs(self._page)
            self._page.wait_for_timeout(400)
        button = first(self._page, selectors.EASY_APPLY_BUTTON)
        if button is None or not is_visible(button):
            logger.info("No Easy Apply button on this job (external application?) - skipping")
            return False
        try:
            label = (button.get_attribute("aria-label") or button.inner_text() or "").lower()
        except Exception:  # pragma: no cover - defensive
            label = ""
        if "applied" in label:
            logger.info("Job already shows 'Applied' - skipping")
            return False
        logger.info("Clicking 'Easy Apply' to open the application modal")
        button.click()
        self._page.wait_for_timeout(1200)
        opened = self._modal_is_open()
        if not opened:
            logger.warning("Easy Apply modal did not appear after clicking the button")
        return opened

    def _modal_is_open(self) -> bool:
        """True when the Easy Apply form is on screen.

        The rebuilt form is not a ``role=dialog`` - it is identified by its
        "Apply to <company>" heading - so the legacy CSS check alone reports a
        working modal as missing.
        """
        if first(self._page, selectors.MODAL) is not None:
            return True
        return self._modal_heading() is not None

    def _form_scope(self) -> Any:
        """A locator covering just the application form.

        Without a dialog wrapper the whole page is in scope, which would sweep
        up the job-search box and the filter checkboxes as if they were form
        questions. Tag the ancestor that holds the form's footer and scope to it.
        """
        legacy = first(self._page, selectors.MODAL)
        if legacy is not None:
            return legacy
        heading = self._modal_heading()
        if heading is None:
            return self._page
        try:
            if heading.evaluate(_TAG_FORM_JS):
                scoped = self._page.locator(f"[{_FORM_ATTR}]")
                if scoped.count() > 0:
                    return scoped.first
        except Exception:  # pragma: no cover - defensive
            pass
        return self._page

    def _modal_heading(self) -> Any | None:
        try:
            heading = self._page.get_by_role(
                "heading", name=re.compile(selectors.MODAL_HEADING_NAME)
            )
            return heading.first if heading.count() > 0 else None
        except Exception:  # pragma: no cover - defensive
            return None

    def _detect_action(self, modal: Any) -> str:
        if is_visible(first(modal, selectors.BTN_SUBMIT)):
            return "submit"
        if is_visible(first(modal, selectors.BTN_REVIEW)):
            return "review"
        if is_visible(first(modal, selectors.BTN_NEXT)):
            return "next"
        for action in ("submit", "review", "next"):
            if self._action_button(action) is not None:
                return action
        return "none"

    def _action_button(self, action: str) -> Any | None:
        """Find a step button by accessible name, preferring the form footer."""
        pattern = selectors.STEP_BUTTON_NAMES.get(action)
        if pattern is None:
            return None
        return self._named_button(pattern, self._action_scopes())

    def _named_button(self, pattern: str, scopes: list[Any] | None = None) -> Any | None:
        for scope in scopes or [self._page]:
            try:
                buttons = scope.get_by_role("button", name=re.compile(pattern, re.I))
                for index in range(buttons.count()):
                    button = buttons.nth(index)
                    if button.is_visible():
                        return button
            except Exception:  # pragma: no cover - defensive
                continue
        return None

    def _click_named_button(self, pattern: str) -> bool:
        button = self._named_button(pattern)
        if button is None:
            return False
        try:
            button.click(timeout=3000)
            return True
        except Exception:  # pragma: no cover - defensive
            try:
                button.click(force=True, timeout=2000)
                return True
            except Exception:
                return False

    def _action_scopes(self) -> list[Any]:
        scopes: list[Any] = []
        try:
            footer = self._page.get_by_role(selectors.MODAL_FOOTER_ROLE)
            if footer.count() > 0:
                scopes.append(footer.last)
        except Exception:  # pragma: no cover - defensive
            pass
        scopes.append(self._page)
        return scopes

    def _click_action(self, scope: Any, action: str, selector_list: list[str]) -> bool:
        if self._click(scope, selector_list):
            return True
        button = self._action_button(action)
        if button is None:
            return False
        button.click()
        return True

    def _click(self, scope: Any, selector_list: list[str]) -> bool:
        button = first(scope, selector_list)
        if button is None or not is_visible(button):
            return False
        button.click()
        return True

    def _step_signature(self, modal: Any) -> str:
        fields = self._detector.detect(modal)
        if fields:
            return "|".join(f"{f.label}:{f.kind.value}" for f in fields)
        return " ".join(safe_text(modal).split())

    def _wait_for_step_change(self, before: str) -> bool:
        for _ in range(20):
            if self._step_signature(self._form_scope()) != before:
                return True
            self._page.wait_for_timeout(250)
        return False

    # -- filling --------------------------------------------------------------
    def _fill_step(
        self,
        modal: Any,
        answers: list[AnsweredQuestion],
        resume_path: str | None,
        cover_letter_path: str | None,
        cover_letter_text: str | None = None,
    ) -> None:
        resume_handled = self._ensure_resume_selected(modal, resume_path)
        self._progress.activity("filling_application")
        for field_ in self._detector.detect(modal):
            self._fill_field(
                field_,
                answers,
                resume_path,
                cover_letter_path,
                cover_letter_text,
                resume_handled,
            )

    def _fill_field(
        self,
        field_: FormField,
        answers: list[AnsweredQuestion],
        resume_path: str | None,
        cover_letter_path: str | None,
        cover_letter_text: str | None = None,
        resume_handled: bool = False,
    ) -> None:
        if field_.kind is FieldKind.FILE:
            self._fill_file_field(field_, resume_path, cover_letter_path, resume_handled)
            return
        if (
            resume_handled
            and field_.kind is FieldKind.RADIO
            and field_.options
            and all(
                re.search(selectors.RESUME_RADIO_NAME, option, re.I) for option in field_.options
            )
        ):
            logger.debug("Resume radio picker already handled - leaving the verified selection")
            return

        parsed = self._parser.parse(field_.label)
        understood = parsed.category.value + (f"/{parsed.skill}" if parsed.skill else "")
        how = f"matched '{parsed.matched}'" if parsed.matched else "keyword rule"
        logger.debug(
            "Reading field '{}' [{}] -> understood as '{}' (confidence {:.0%}, {}, current={!r})",
            field_.label,
            field_.kind.value,
            understood,
            parsed.confidence,
            how,
            field_.current_value,
        )

        # Phone country/dialling code: leave the pre-selected +91 default in
        # place; only flag when a different code is already selected.
        if parsed.category is QuestionCategory.PHONE_COUNTRY_CODE:
            self._handle_country_code(field_, parsed, understood, answers)
            return

        # Inline cover-letter textarea: fill it with the letter we generated for
        # this job rather than prompting the user for free text.
        if (
            parsed.category is QuestionCategory.COVER_LETTER
            and field_.kind in {FieldKind.TEXTAREA, FieldKind.TEXT}
            and cover_letter_text
        ):
            self._fill_cover_textarea(field_, parsed, understood, cover_letter_text, answers)
            return

        resolution = self._override_resolution(parsed)
        if resolution is not None:
            logger.debug("Using an approved override for '{}' (résumé-sync)", field_.label)
        else:
            resolution = self._resolver.resolve(parsed)

        # Fall back to the learned-answer bank before bothering the user.
        if not resolution.found and self._answer_lookup is not None:
            learned = self._answer_lookup(parsed.normalized)
            if learned:
                logger.debug("Recovered a learned answer for '{}' from the bank", field_.label)
                resolution = AnswerResolution(True, learned, "learned", parsed.answer_type)

        # Skip a field that already holds the value we would fill.
        if resolution.found and self._filler.matches_current(
            field_, resolution, field_.current_value
        ):
            logger.info(
                "Field '{}' [{}] -> {}: already filled with {!r} - leaving as is",
                field_.label,
                field_.kind.value,
                understood,
                field_.current_value,
            )
            self._record(answers, field_, parsed, field_.current_value, "prefilled", True)
            return

        if resolution.found and self._filler.fill(field_, resolution):
            logger.info(
                "Field '{}' [{}] -> {}: filled with {!r} (source: {})",
                field_.label,
                field_.kind.value,
                understood,
                resolution.value,
                resolution.source,
            )
            self._record(answers, field_, parsed, resolution.value, resolution.source, True)
            return

        # Unknown or unresolved: pause for the user (terminal or on-page).
        value, source = self._resolve_interactively(field_)
        if value is not None:
            logger.info(
                "Field '{}' [{}] -> {}: no stored answer, using {!r} (source: {})",
                field_.label,
                field_.kind.value,
                understood,
                value,
                source,
            )
        else:
            reason = "no matching data in answers" if not resolution.found else "could not fill"
            logger.info(
                "Field '{}' [{}] -> {}: {} - left blank",
                field_.label,
                field_.kind.value,
                understood,
                reason,
            )
        self._record(answers, field_, parsed, value, source, value is not None)

    def _override_resolution(self, parsed: Any) -> AnswerResolution | None:
        """Return an approved-override answer for *parsed*, or ``None``.

        Approved corrections (from the dashboard's résumé-sync or the
        ``sync-answers`` CLI) take priority over answers.yaml and the learned
        bank, so this is checked first. A Yes/No override is mapped to a boolean
        resolution just like a custom Yes/No answer.
        """
        if self._override_lookup is None:
            return None
        value = self._override_lookup(parsed.normalized)
        if not value:
            return None
        token = value.strip().lower()
        if token in _OVERRIDE_YES:
            return AnswerResolution(True, "Yes", "approved", AnswerType.BOOLEAN, bool_value=True)
        if token in _OVERRIDE_NO:
            return AnswerResolution(True, "No", "approved", AnswerType.BOOLEAN, bool_value=False)
        return AnswerResolution(True, value, "approved", parsed.answer_type)

    def _handle_country_code(
        self,
        field_: FormField,
        parsed: Any,
        understood: str,
        answers: list[AnsweredQuestion],
    ) -> None:
        """Default the phone country code to +91; flag only if it differs."""
        current = field_.current_value
        resolution = self._resolver.resolve(parsed)
        desired = str(resolution.value) if resolution.value else "+91"

        if current and dial_code(current) == dial_code(desired):
            logger.info(
                "Field '{}' [select] -> phone country code already {!r} - leaving default",
                field_.label,
                current,
            )
            self._record(answers, field_, parsed, current, "prefilled", True)
            return

        if current and dial_code(current) is not None:
            logger.warning(
                "Phone country code is {!r}, not {} - pausing so you can confirm",
                current,
                desired,
            )
            value, source = self._resolve_interactively(field_)
            self._record(
                answers, field_, parsed, value or current, source if value else "prefilled", True
            )
            return

        option = country_code_option(desired, field_.options)
        if option is not None and self._filler.fill(
            field_, AnswerResolution(True, option, "default")
        ):
            logger.info(
                "Field '{}' [select] -> set phone country code to {!r} (default)",
                field_.label,
                option,
            )
            self._record(answers, field_, parsed, option, "default", True)
            return

        value, source = self._resolve_interactively(field_)
        self._record(answers, field_, parsed, value, source, value is not None)

    def _fill_cover_textarea(
        self,
        field_: FormField,
        parsed: Any,
        understood: str,
        cover_letter_text: str,
        answers: list[AnsweredQuestion],
    ) -> None:
        """Fill an inline cover-letter textarea with the generated letter."""
        resolution = AnswerResolution(True, cover_letter_text, "cover_letter", parsed.answer_type)
        if self._filler.matches_current(field_, resolution, field_.current_value):
            logger.info(
                "Field '{}' [{}] -> cover letter: already filled - leaving as is",
                field_.label,
                field_.kind.value,
            )
            self._record(answers, field_, parsed, field_.current_value, "prefilled", True)
            return
        if self._filler.fill(field_, resolution):
            logger.info(
                "Field '{}' [{}] -> cover letter: filled inline ({} chars)",
                field_.label,
                field_.kind.value,
                len(cover_letter_text),
            )
            self._record(answers, field_, parsed, cover_letter_text, "cover_letter", True)
            return
        logger.warning(
            "Field '{}' [{}] -> cover letter: could not fill inline - pausing",
            field_.label,
            field_.kind.value,
        )
        value, source = self._resolve_interactively(field_)
        self._record(answers, field_, parsed, value, source, value is not None)

    def _resolve_interactively(self, field_: FormField) -> tuple[str | None, str]:
        """Ask the user for a value, accepting a terminal answer *or* one they
        type directly on the page. Returns ``(value, source)``."""
        if not (self._settings.pause_on_unknown and self._on_unknown):
            return None, "unanswered"
        before = current_value_of(field_)
        shot = self._screenshot(f"unknown-{field_.label}")
        logger.info(
            "Pausing for '{}' - type an answer here, or fill it on the page and press Enter",
            field_.label,
        )
        self._progress.activity("awaiting_input")
        typed = self._on_unknown(field_.label, shot)
        self._progress.activity("filling_application")
        if typed:
            self._apply_manual_value(field_, typed)
            return typed, "manual"
        after = current_value_of(field_)
        if after and after != before:
            logger.info("Read {!r} straight from the page for '{}'", after, field_.label)
            return after, "portal"
        if after:
            return after, "portal"
        return None, "unanswered"

    def _record(
        self,
        answers: list[AnsweredQuestion],
        field_: FormField,
        parsed: Any,
        value: str | None,
        source: str,
        resolved: bool,
    ) -> None:
        answers.append(
            AnsweredQuestion(
                field_.label,
                parsed.normalized,
                parsed.category.value,
                parsed.skill,
                value,
                source,
                resolved,
            )
        )

    # -- resume selection / upload -------------------------------------------
    def _ensure_resume_selected(self, modal: Any, resume_path: str | None) -> bool:
        """Select the target resume from the on-page list, or upload it.

        Only act on a visible resume step, never a page-wide hidden upload input.
        Selection/upload must be verified before suppressing the file-field path.
        """
        if not resume_path:
            return False
        # The resume is chosen once, on the resume step. Later steps (notably the
        # read-only review step) re-render the resume as a summary card with no
        # upload control; re-running here would mis-detect it and spuriously try
        # to "upload" again. Once handled, skip on every subsequent step.
        if self._resume_selected_done:
            return True
        self._progress.activity("selecting_attachment")
        cards = self._resume_cards(modal)
        target = Path(resume_path).name
        target_stem = Path(resume_path).stem
        if self._reuse_resume(cards, target_stem):
            self._resume_selected_done = True
            return True

        upload_button = first(modal, selectors.RESUME_UPLOAD_BUTTON)
        if not cards and not is_visible(upload_button):
            return False
        logger.info(
            "Resume step: '{}' not in {} uploaded resume(s) {} - uploading once",
            target,
            len(cards),
            [name for name, _ in cards],
        )
        upload = first(modal, selectors.RESUME_UPLOAD_INPUT)
        self._progress.activity("uploading_document")
        if upload is not None:
            upload.set_input_files(resume_path)
        elif not self._upload_via_file_chooser(modal, resume_path):
            self._ask_manual_upload(target)

        for _ in range(20):
            uploaded_cards = self._resume_cards(modal)
            if self._reuse_resume(uploaded_cards, target_stem):
                self._resume_selected_done = True
                return True
            # A plain legacy file input can attach a document without cards.
            if not cards and not uploaded_cards and upload is not None:
                attached = upload.input_value().replace("\\", "/").rsplit("/", 1)[-1]
                if _resume_matches(attached, target_stem):
                    logger.info("Resume '{}' attached through the file input", target)
                    self._resume_selected_done = True
                    return True
            self._page.wait_for_timeout(500)
        raise RuntimeError(
            f"Could not verify that resume '{target}' was attached; not re-uploading"
        )

    def _reuse_resume(self, cards: list[tuple[str, Any]], target_stem: str) -> bool:
        matching = [(name, node) for name, node in cards if _resume_matches(name, target_stem)]
        for name, node in matching:
            if self._card_selected(node):
                logger.info(
                    "Resume '{}' already uploaded and selected - reusing it (no upload)", name
                )
                return True
        if not matching:
            return False
        name, node = matching[0]
        self._select_card(node)
        # Selection remounts the picker, so verify freshly discovered controls.
        for _ in range(10):
            for selected_name, selected_node in self._resume_cards(self._form_scope()):
                if _resume_matches(selected_name, target_stem) and self._card_selected(
                    selected_node
                ):
                    logger.info(
                        "Resume '{}' selected from your LinkedIn list (no upload)", selected_name
                    )
                    return True
            self._page.wait_for_timeout(250)
        raise RuntimeError(f"Could not select the already-uploaded resume '{name}'")

    def _upload_via_file_chooser(self, modal: Any, resume_path: str) -> bool:
        """Upload by clicking the "Upload resume" button and catching its chooser.

        Used only when no ``<input type=file>`` exists in the DOM to set files on
        directly (LinkedIn injects it on demand). Playwright intercepts the native
        file dialog, so this never blocks on an OS picker.
        """
        button = first(modal, selectors.RESUME_UPLOAD_BUTTON) or first(
            self._page, selectors.RESUME_UPLOAD_BUTTON
        )
        if button is None:
            return False
        try:
            with self._page.expect_file_chooser(timeout=5000) as chooser_info:
                button.click(force=True, timeout=2000)
            chooser_info.value.set_files(resume_path)
            self._page.wait_for_timeout(2000)
            return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("File-chooser resume upload failed: {}", exc)
            return False

    def _resume_cards(self, modal: Any) -> list[tuple[str, Any]]:
        radios = modal.get_by_role("radio", name=re.compile(selectors.RESUME_RADIO_NAME, re.I))
        if radios.count():
            return [
                (radios.nth(index).get_attribute("aria-label") or "", radios.nth(index))
                for index in range(radios.count())
            ]
        group = first_group(modal, selectors.RESUME_CARD)
        if group is None:
            return []
        cards: list[tuple[str, Any]] = []
        try:
            total = group.count()
        except Exception:  # pragma: no cover - defensive
            return []
        for index in range(total):
            container = group.nth(index)
            if not is_visible(container):
                continue
            name_node = first(container, selectors.RESUME_CARD_NAME)
            name = safe_text(name_node) if name_node is not None else ""
            if not name:
                text = safe_text(container)
                name = text.splitlines()[0] if text else ""
            cards.append((name.strip(), container))
        return cards

    def _card_selected(self, container: Any) -> bool:
        try:
            if container.is_checked():
                return True
        except Exception:  # pragma: no cover - legacy cards are not inputs
            pass
        try:
            classes = container.get_attribute("class") or ""
            if selectors.RESUME_CARD_SELECTED_FRAGMENT in classes:
                return True
        except Exception:  # pragma: no cover - defensive
            pass
        radio = first(container, ["input[type='radio']", "input[type='checkbox']"])
        try:
            return radio is not None and radio.is_checked()
        except Exception:  # pragma: no cover - defensive
            return False

    def _select_card(self, container: Any) -> bool:
        try:
            label = container.evaluate_handle("el => el.labels?.[0] ?? null").as_element()
            if label is not None:
                label.click(timeout=3000)
                return True
        except Exception as exc:  # pragma: no cover - legacy cards or hidden labels
            logger.debug("Resume label selection unavailable: {}", exc)
        try:
            container.check(force=True, timeout=2000)
            return True
        except Exception:  # pragma: no cover - legacy cards are not inputs
            pass
        button = first(container, selectors.RESUME_SELECT_BUTTON)
        for target in (button, container):
            if target is None:
                continue
            try:
                target.click(force=True, timeout=2000)
                return True
            except Exception:  # pragma: no cover - defensive
                continue
        return False

    def _ask_manual_upload(self, target: str) -> None:
        logger.warning("Could not upload '{}' automatically - please attach it on the page", target)
        if self._settings.pause_on_unknown and self._on_unknown:
            self._progress.activity("awaiting_input")
            self._on_unknown(f"Attach the resume '{target}' on the page, then press Enter", None)
            self._progress.activity("selecting_attachment")

    def _fill_file_field(
        self,
        field_: FormField,
        resume_path: str | None,
        cover_letter_path: str | None,
        resume_handled: bool = False,
    ) -> None:
        label = field_.label.lower()
        if "cover" in label and cover_letter_path:
            self._progress.activity("uploading_document")
            logger.info("Uploading cover letter to '{}': {}", field_.label, cover_letter_path)
            self._filler.fill(field_, _empty_resolution(), file_path=cover_letter_path)
        elif "cover" in label:
            logger.warning("Cover-letter file field '{}' but none configured - left empty", label)
        elif resume_handled:
            logger.debug(
                "Resume already handled via the picker - not re-uploading to '{}'", field_.label
            )
        elif resume_path:
            self._progress.activity("uploading_document")
            logger.info("Uploading resume to '{}': {}", field_.label, resume_path)
            self._filler.fill(field_, _empty_resolution(), file_path=resume_path)
        else:
            logger.warning("Resume file field '{}' but no resume configured - left empty", label)

    def _apply_manual_value(self, field_: FormField, value: str) -> None:
        resolution = AnswerResolution(True, value, "manual")
        self._filler.fill(field_, resolution)

    def discard_open(self) -> None:
        """Best-effort discard of an in-progress application (used on abort)."""
        try:
            self._discard()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("discard_open error: {}", exc)

    # -- finalisation ---------------------------------------------------------
    def _finalize_submit(self, answers: list[AnsweredQuestion], step: int) -> ApplyResult:
        if self._settings.dry_run:
            logger.info(
                "DRY-RUN: reached the Submit button at step {} - discarding WITHOUT submitting",
                step,
            )
            self._discard()
            return ApplyResult(
                ApplyStatus.DRY_RUN, step, "Dry run - not submitted", answers=answers
            )
        if self._on_confirm:
            self._progress.activity("awaiting_input")
            if not self._on_confirm():
                logger.info("You declined submission - discarding the application")
                self._discard()
                return ApplyResult(
                    ApplyStatus.ABORTED, step, "User declined submission", answers=answers
                )

        self._progress.activity("submitting_application")
        logger.info("Submitting the application now ({} question(s) answered)", len(answers))
        modal = first(self._page, selectors.MODAL)
        if not self._click_action(modal, "submit", selectors.BTN_SUBMIT):
            return self._abort(answers, step, "Submit button vanished")
        self._progress.activity("verifying_submission")
        status, evidence = self._submission_outcome()
        if status is ApplyStatus.LIMIT_REACHED:
            shot = self._screenshot("daily-limit")
            logger.error(
                "LinkedIn DAILY SUBMISSION LIMIT reached - it rejected this submit "
                "('save this job and apply tomorrow'). This application was NOT "
                "submitted; stopping the run so we don't hammer the cap. Try again "
                "later; the exact reset time is not known."
            )
            self._discard()  # clear the notice / 'save this application?' overlay
            return ApplyResult(
                ApplyStatus.LIMIT_REACHED,
                step,
                "LinkedIn daily submission limit reached",
                str(shot) if shot else None,
                answers,
            )
        if status is ApplyStatus.UNCONFIRMED:
            shot = self._screenshot("submit-unconfirmed")
            logger.error(
                "Submit was clicked, but LinkedIn did not confirm or reject it. "
                "Stopping for manual verification rather than counting a success/failure "
                "or risking a duplicate submission."
            )
            return ApplyResult(status, step, evidence, str(shot) if shot else None, answers)
        shot = self._screenshot("after-submit")
        logger.info("Application submitted successfully - LinkedIn confirmation: {}", evidence)
        return ApplyResult(
            ApplyStatus.SUBMITTED,
            step,
            reason=f"LinkedIn confirmation: {evidence}",
            screenshot=str(shot) if shot else None,
            answers=answers,
        )

    def _submission_outcome(self) -> tuple[ApplyStatus, str]:
        for _ in range(40):
            if self._hit_daily_submission_limit():
                return ApplyStatus.LIMIT_REACHED, "LinkedIn daily submission limit reached"
            for selector in selectors.POST_SUBMIT_MARKERS:
                marker = first(self._page, [selector])
                if is_visible(marker):
                    return ApplyStatus.SUBMITTED, safe_text(marker)
            self._page.wait_for_timeout(500)
        return ApplyStatus.UNCONFIRMED, "No LinkedIn submission confirmation within 20 seconds"

    def _hit_daily_submission_limit(self) -> bool:
        """True if LinkedIn rejected the submit with its daily-cap notice.

        After Submit, LinkedIn normally shows an "application sent" confirmation.
        When the account has hit LinkedIn's *own* daily Easy Apply cap it instead
        shows "We limit daily submissions ... Save this job and apply tomorrow".
        We must recognise this and stop the run rather than assume success and
        keep submitting into the cap job-after-job (which is exactly the pattern
        that escalates bot detection)."""
        if is_visible(first(self._page, selectors.SUBMIT_LIMIT_MODAL)):
            return True
        # Fallback: scan the visible modal/alert text for the signature phrases,
        # in case the notice renders inside a container we didn't anticipate.
        for scope in (selectors.MODAL, selectors.DISCARD_CONFIRMATION):
            text = safe_text(first(self._page, scope)).lower()
            if text and any(phrase in text for phrase in _DAILY_LIMIT_PHRASES):
                return True
        return False

    def _abort(self, answers: list[AnsweredQuestion], step: int, reason: str) -> ApplyResult:
        logger.warning("Aborting application at step {}: {}", step, reason)
        shot = self._screenshot("aborted")
        self._discard()
        return ApplyResult(ApplyStatus.FAILED, step, reason, str(shot) if shot else None, answers)

    def _discard(self) -> None:
        self._progress.activity("discarding_application")
        try:
            if not self._click(self._page, selectors.BTN_DISMISS):
                self._click_named_button(selectors.DISMISS_BUTTON_NAME)
            # LinkedIn shows a "Save this application?" dialog whose *secondary*
            # button is "Discard" (the primary is "Save"). Force-click Discard -
            # an error toast may otherwise intercept the click - and verify the
            # dialog closes, else its overlay blocks the next job card.
            for _ in range(10):
                self._page.wait_for_timeout(300)
                if first(self._page, selectors.DISCARD_CONFIRMATION) is not None:
                    self._force_click(selectors.BTN_DISCARD)
                    continue
                if self._click_named_button(selectors.DISCARD_BUTTON_NAME):
                    continue
                if not self._modal_is_open():
                    return
                self._page.keyboard.press("Escape")
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Discard flow error: {}", exc)
        force_close_dialogs(self._page)

    def _force_click(self, selector_list: list[str]) -> bool:
        button = first(self._page, selector_list)
        if button is None:
            return False
        try:
            button.click(force=True, timeout=2000)
            return True
        except Exception:  # pragma: no cover - defensive
            return False

    def _dismiss_confirmation(self) -> None:
        try:
            self._click(self._page, selectors.BTN_DISMISS)
        except Exception:  # pragma: no cover - defensive
            pass

    def dismiss_confirmation(self) -> None:
        """Close the post-submit 'application sent' modal.

        Called by the orchestrator *after* any hiring-team outreach has read the
        modal, so the recruiter cards it carries are still present during
        outreach. Safe to call when the modal is already gone.
        """
        self._dismiss_confirmation()

    def _screenshot(self, label: str) -> Path | None:
        if not self._screenshots.enabled:
            return None
        return self._screenshots.capture(self._page, label)


def _empty_resolution():
    from linkedin_easy_apply.answers.resolver import AnswerResolution

    return AnswerResolution(True, None, "file")


def _resume_matches(portal_name: str, target_stem: str) -> bool:
    """True when a resume card's filename refers to our target resume."""
    if not portal_name or not target_stem:
        return False
    name = portal_name.strip().casefold()
    if name.endswith(".pdf") or name.endswith(".doc") or name.endswith(".docx"):
        name = name.rsplit(".", 1)[0]
    name = re.sub(r"\s*\(\d+\)$", "", name)
    target = re.sub(r"\s*\(\d+\)$", "", target_stem.strip().casefold())
    return name == target
