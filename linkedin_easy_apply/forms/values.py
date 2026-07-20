"""Read the *current* value already present in a form control.

Knowing what a control currently holds lets the workflow (a) skip fields that
are already correctly pre-filled and (b) read back a value the user typed
directly on the portal. The helpers are deliberately defensive: any DOM hiccup
yields ``None`` rather than raising, so reading a value can never abort an
application attempt.
"""

from __future__ import annotations

from typing import Any

from linkedin_easy_apply.forms.field import FieldKind, FormField

# Selected-option texts that really mean "nothing chosen yet".
_PLACEHOLDERS = {"select an option", "select", "", "-", "--"}


def current_value_of(field: FormField) -> str | None:
    """Return the value *field* currently holds, or ``None`` when empty/unknown."""
    try:
        if field.kind is FieldKind.SELECT:
            return _select_value(field.control)
        if field.kind is FieldKind.CHECKBOX:
            return _checkbox_value(field.control)
        if field.kind is FieldKind.RADIO:
            return _radio_value(field)
        if field.kind in {
            FieldKind.TEXT,
            FieldKind.TEXTAREA,
            FieldKind.NUMBER,
            FieldKind.DATE,
        }:
            return _text_value(field.control)
        if field.kind is FieldKind.FILE:
            return _file_value(field.control)
    except Exception:  # pragma: no cover - defensive
        return None
    return None


def _text_value(control: Any) -> str | None:
    if control is None:
        return None
    value = (control.input_value() or "").strip()
    return value or None


def _select_value(control: Any) -> str | None:
    if control is None:
        return None
    text = control.evaluate(
        "el => (el.selectedIndex != null && el.options[el.selectedIndex])"
        " ? el.options[el.selectedIndex].text : ''"
    )
    text = (text or "").strip()
    if text.lower() in _PLACEHOLDERS:
        return None
    return text or None


def _checkbox_value(control: Any) -> str | None:
    if control is None:
        return None
    return "true" if control.is_checked() else "false"


def _radio_value(field: FormField) -> str | None:
    for option, control in zip(field.options, field.option_controls, strict=False):
        try:
            if control.is_checked():
                return option or None
        except Exception:  # pragma: no cover - defensive
            continue
    return None


def _file_value(control: Any) -> str | None:
    if control is None:
        return None
    raw = (control.input_value() or "").strip()
    if not raw:
        return None
    # Browsers report file inputs as ``C:\fakepath\<name>``; keep just the name.
    return raw.replace("\\", "/").rsplit("/", 1)[-1] or None
