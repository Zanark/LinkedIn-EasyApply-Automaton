"""Fill a detected :class:`FormField` with a resolved answer."""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

from linkedin_easy_apply.answers.resolver import AnswerResolution
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.matching import best_option, boolean_option
from linkedin_easy_apply.parser.categories import AnswerType
from linkedin_easy_apply.utils.text import normalize

_TRUTHY_TEXT = {"true", "yes", "y", "1", "checked", "on"}
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


class FormFiller:
    """Apply answers to form controls, tolerant of DOM quirks."""

    def __init__(self, fuzzy_threshold: int = 70) -> None:
        self._fuzzy_threshold = fuzzy_threshold

    def fill(
        self,
        field: FormField,
        resolution: AnswerResolution,
        *,
        file_path: str | None = None,
    ) -> bool:
        """Fill *field* from *resolution*; return ``True`` on success."""
        try:
            if field.kind is FieldKind.FILE:
                return self._fill_file(field, file_path)
            if field.kind is FieldKind.CHECKBOX:
                return self._fill_checkbox(field, resolution)
            if field.kind in {FieldKind.SELECT, FieldKind.RADIO}:
                return self._fill_choice(field, resolution)
            if field.kind in {FieldKind.TEXT, FieldKind.TEXTAREA, FieldKind.NUMBER, FieldKind.DATE}:
                return self._fill_text(field, resolution)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to fill field '{}': {}", field.label, exc)
            return False
        logger.debug("No filler for field kind {} ('{}')", field.kind, field.label)
        return False

    # -- pre-fill inspection --------------------------------------------------
    def matches_current(
        self, field: FormField, resolution: AnswerResolution, current: str | None
    ) -> bool:
        """True when *current* already equals what we would fill into *field*.

        Lets the workflow skip a field that is already correctly pre-filled
        instead of overwriting it with the same value.
        """
        if not current:
            return False
        try:
            if field.kind is FieldKind.CHECKBOX:
                flag = resolution.bool_value
                if flag is None:
                    flag = bool(resolution.value)
                return _is_truthy(current) == flag
            if field.kind in {FieldKind.SELECT, FieldKind.RADIO}:
                want = self._pick_option(field, resolution)
                return want is not None and normalize(want) == normalize(current)
            if resolution.value is None:
                return False
            if normalize(current) == normalize(str(resolution.value)):
                return True
            if resolution.answer_type is AnswerType.NUMBER:
                return _numbers_equal(current, str(resolution.value))
        except Exception:  # pragma: no cover - defensive
            return False
        return False

    # -- per-kind fillers -----------------------------------------------------
    def _fill_text(self, field: FormField, resolution: AnswerResolution) -> bool:
        if resolution.value is None:
            return False
        field.control.fill(str(resolution.value))
        logger.debug("Filled text field '{}' = {}", field.label, resolution.value)
        return True

    def _fill_file(self, field: FormField, file_path: str | None) -> bool:
        if not file_path:
            return False
        field.control.set_input_files(file_path)
        logger.debug("Uploaded file to '{}': {}", field.label, file_path)
        return True

    def _fill_checkbox(self, field: FormField, resolution: AnswerResolution) -> bool:
        flag = resolution.bool_value
        if flag is None:
            flag = bool(resolution.value)
        field.control.set_checked(flag)
        logger.debug("Set checkbox '{}' = {}", field.label, flag)
        return True

    def _fill_choice(self, field: FormField, resolution: AnswerResolution) -> bool:
        choice = self._pick_option(field, resolution)
        if choice is None:
            logger.debug(
                "No option on '{}' matched {!r} (available options: {})",
                field.label,
                resolution.value,
                field.options,
            )
            return False
        logger.debug(
            "Matched {} option {!r} for '{}' (from {})",
            field.kind.value,
            choice,
            field.label,
            field.options,
        )
        if field.kind is FieldKind.SELECT:
            return self._select(field.control, choice)
        return self._check_radio(field, choice)

    # -- helpers --------------------------------------------------------------
    def _pick_option(self, field: FormField, resolution: AnswerResolution) -> str | None:
        options = [o for o in field.options if o]
        if not options:
            return None
        if resolution.bool_value is not None:
            match = boolean_option(resolution.bool_value, options)
            if match is not None:
                return match
        if resolution.value is None:
            return None
        numeric = resolution.answer_type is AnswerType.NUMBER
        return best_option(
            str(resolution.value), options, numeric=numeric, fuzzy_threshold=self._fuzzy_threshold
        )

    def _select(self, control: Any, choice: str) -> bool:
        try:
            control.select_option(label=choice)
            return True
        except Exception:
            try:
                control.select_option(value=choice)
                return True
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("select_option failed for '{}': {}", choice, exc)
                return False

    def _check_radio(self, field: FormField, choice: str) -> bool:
        try:
            index = field.options.index(choice)
        except ValueError:  # pragma: no cover - defensive
            return False
        if index < len(field.option_controls):
            field.option_controls[index].check(force=True)
            return True
        return False


def _is_truthy(text: str) -> bool:
    return normalize(text) in _TRUTHY_TEXT


def _first_float(text: str) -> float | None:
    match = _NUM_RE.search(text or "")
    return float(match.group()) if match else None


def _numbers_equal(left: str, right: str) -> bool:
    a, b = _first_float(left), _first_float(right)
    return a is not None and b is not None and a == b
