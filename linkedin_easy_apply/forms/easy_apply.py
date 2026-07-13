"""The multi-step Easy Apply workflow.

This module drives a single application from the job page through every step of
the Easy Apply modal: it clicks *Easy Apply*, fills each detected field using the
parser/resolver/filler collaborators, handles unknown questions via an optional
callback, honours dry-run and interactive-approval modes, and finally submits or
discards the application.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from loguru import logger

from linkedin_easy_apply.answers.resolver import AnswerResolver
from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.detector import FormFieldDetector
from linkedin_easy_apply.forms.dom_utils import first, is_visible
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.filler import FormFiller
from linkedin_easy_apply.parser.question_parser import QuestionParser
from linkedin_easy_apply.utils.screenshots import ScreenshotManager

# Callback types.
UnknownHandler = Callable[[str, "Path | None"], "str | None"]
ConfirmHandler = Callable[[], bool]


class ApplyStatus(StrEnum):
    SUBMITTED = "submitted"
    DRY_RUN = "dry_run"
    SKIPPED = "skipped"
    FAILED = "failed"
    ABORTED = "aborted"


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

    def apply(
        self, *, resume_path: str | None = None, cover_letter_path: str | None = None
    ) -> ApplyResult:
        """Run the Easy Apply flow on the currently open job page."""
        answers: list[AnsweredQuestion] = []
        if not self._open_modal():
            return ApplyResult(ApplyStatus.SKIPPED, reason="Easy Apply button not available")

        modal = first(self._page, selectors.MODAL)
        if modal is None:
            return ApplyResult(ApplyStatus.FAILED, reason="Easy Apply modal did not open")

        last_signature: str | None = None
        for step in range(1, self._settings.max_steps + 1):
            self._page.wait_for_timeout(600)
            self._screenshot(f"step-{step}")

            self._fill_step(modal, answers, resume_path, cover_letter_path)

            action = self._detect_action(modal)
            logger.debug("Step {}: action={}", step, action)

            if action == "submit":
                return self._finalize_submit(answers, step)
            if action in {"next", "review"}:
                signature = self._step_signature(modal)
                self._click(
                    modal, selectors.BTN_REVIEW if action == "review" else selectors.BTN_NEXT
                )
                self._page.wait_for_timeout(800)
                if signature == last_signature:
                    return self._abort(answers, step, "No progress between steps")
                last_signature = signature
                continue
            return self._abort(answers, step, "No actionable button found")

        return self._abort(answers, self._settings.max_steps, "Exceeded max steps")

    # -- modal control --------------------------------------------------------
    def _open_modal(self) -> bool:
        button = first(self._page, selectors.EASY_APPLY_BUTTON)
        if button is None or not is_visible(button):
            return False
        try:
            label = (button.get_attribute("aria-label") or button.inner_text() or "").lower()
        except Exception:  # pragma: no cover - defensive
            label = ""
        if "applied" in label:
            return False
        button.click()
        self._page.wait_for_timeout(1200)
        return first(self._page, selectors.MODAL) is not None

    def _detect_action(self, modal: Any) -> str:
        if is_visible(first(modal, selectors.BTN_SUBMIT)):
            return "submit"
        if is_visible(first(modal, selectors.BTN_REVIEW)):
            return "review"
        if is_visible(first(modal, selectors.BTN_NEXT)):
            return "next"
        return "none"

    def _click(self, scope: Any, selector_list: list[str]) -> bool:
        button = first(scope, selector_list)
        if button is None or not is_visible(button):
            return False
        button.click()
        return True

    def _step_signature(self, modal: Any) -> str:
        fields = self._detector.detect(modal)
        return "|".join(f"{f.label}:{f.kind.value}" for f in fields)

    # -- filling --------------------------------------------------------------
    def _fill_step(
        self,
        modal: Any,
        answers: list[AnsweredQuestion],
        resume_path: str | None,
        cover_letter_path: str | None,
    ) -> None:
        for field_ in self._detector.detect(modal):
            self._fill_field(field_, answers, resume_path, cover_letter_path)

    def _fill_field(
        self,
        field_: FormField,
        answers: list[AnsweredQuestion],
        resume_path: str | None,
        cover_letter_path: str | None,
    ) -> None:
        if field_.kind is FieldKind.FILE:
            self._fill_file_field(field_, resume_path, cover_letter_path)
            return

        parsed = self._parser.parse(field_.label)
        resolution = self._resolver.resolve(parsed)

        if resolution.found and self._filler.fill(field_, resolution):
            answers.append(
                AnsweredQuestion(
                    field_.label,
                    parsed.normalized,
                    parsed.category.value,
                    parsed.skill,
                    resolution.value,
                    resolution.source,
                    True,
                )
            )
            return

        # Unknown or unresolved: pause for the user when allowed.
        value = self._handle_unknown(field_)
        if value is not None:
            self._apply_manual_value(field_, value)
        answers.append(
            AnsweredQuestion(
                field_.label,
                parsed.normalized,
                parsed.category.value,
                parsed.skill,
                value,
                "manual" if value is not None else "unanswered",
                value is not None,
            )
        )

    def _fill_file_field(
        self, field_: FormField, resume_path: str | None, cover_letter_path: str | None
    ) -> None:
        label = field_.label.lower()
        if "cover" in label and cover_letter_path:
            self._filler.fill(field_, _empty_resolution(), file_path=cover_letter_path)
        elif resume_path:
            self._filler.fill(field_, _empty_resolution(), file_path=resume_path)

    def _apply_manual_value(self, field_: FormField, value: str) -> None:
        from linkedin_easy_apply.answers.resolver import AnswerResolution

        resolution = AnswerResolution(True, value, "manual")
        self._filler.fill(field_, resolution)

    def _handle_unknown(self, field_: FormField) -> str | None:
        if not (self._settings.pause_on_unknown and self._on_unknown):
            logger.warning("Unresolved question (left blank): '{}'", field_.label)
            return None
        shot = self._screenshot(f"unknown-{field_.label}")
        logger.info("Pausing for manual input on: '{}'", field_.label)
        return self._on_unknown(field_.label, shot)

    # -- finalisation ---------------------------------------------------------
    def _finalize_submit(self, answers: list[AnsweredQuestion], step: int) -> ApplyResult:
        if self._settings.dry_run:
            self._discard()
            return ApplyResult(
                ApplyStatus.DRY_RUN, step, "Dry run - not submitted", answers=answers
            )
        if self._settings.interactive and self._on_confirm and not self._on_confirm():
            self._discard()
            return ApplyResult(
                ApplyStatus.ABORTED, step, "User declined submission", answers=answers
            )

        modal = first(self._page, selectors.MODAL)
        if not self._click(modal, selectors.BTN_SUBMIT):
            return self._abort(answers, step, "Submit button vanished")
        self._page.wait_for_timeout(1500)
        shot = self._screenshot("after-submit")
        self._dismiss_confirmation()
        return ApplyResult(
            ApplyStatus.SUBMITTED, step, screenshot=str(shot) if shot else None, answers=answers
        )

    def _abort(self, answers: list[AnsweredQuestion], step: int, reason: str) -> ApplyResult:
        logger.warning("Aborting application at step {}: {}", step, reason)
        shot = self._screenshot("aborted")
        self._discard()
        return ApplyResult(ApplyStatus.FAILED, step, reason, str(shot) if shot else None, answers)

    def _discard(self) -> None:
        try:
            if not self._click(self._page, selectors.BTN_DISMISS):
                return
            # LinkedIn shows a "Save this application?" dialog whose *secondary*
            # button is "Discard" (the primary is "Save"). Force-click Discard -
            # an error toast may otherwise intercept the click - and verify the
            # dialog closes, else its overlay blocks the next job card.
            for _ in range(10):
                self._page.wait_for_timeout(300)
                if first(self._page, selectors.DISCARD_CONFIRMATION) is None:
                    return
                self._force_click(selectors.BTN_DISCARD)
            # Last resort: clear any lingering overlay with Escape.
            self._page.keyboard.press("Escape")
            self._page.wait_for_timeout(300)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Discard flow error: {}", exc)

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

    def _screenshot(self, label: str) -> Path | None:
        if not self._screenshots.enabled:
            return None
        return self._screenshots.capture(self._page, label)


def _empty_resolution():
    from linkedin_easy_apply.answers.resolver import AnswerResolution

    return AnswerResolution(True, None, "file")
