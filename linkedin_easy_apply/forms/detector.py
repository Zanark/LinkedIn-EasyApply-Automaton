"""Detect form fields inside an Easy Apply step by inspecting the DOM.

The detector makes no assumption that every company uses the same form. It
walks the field containers of the current step and classifies each control by
inspecting its actual DOM element.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.dom_utils import first, first_group, safe_text
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.values import current_value_of


class FormFieldDetector:
    """Discover :class:`FormField` instances within the current modal step."""

    def detect(self, modal: Any) -> list[FormField]:
        containers = first_group(modal, selectors.FIELD_CONTAINER)
        if containers is None:
            logger.debug("No field containers found in current step")
            return []

        fields: list[FormField] = []
        count = containers.count()
        for index in range(count):
            container = containers.nth(index)
            field = self._classify(container)
            if field is not None:
                field.current_value = current_value_of(field)
                fields.append(field)
        for f in fields:
            logger.debug(
                "  field: '{}' kind={} required={} current={!r} options={}",
                f.label,
                f.kind.value,
                f.required,
                f.current_value,
                f.options if f.options else "-",
            )
        logger.debug("Detected {} field(s) in current step", len(fields))
        return fields

    # -- classification -------------------------------------------------------
    def _classify(self, container: Any) -> FormField | None:
        label = self._label_of(container)

        if self._count(container, "select") > 0:
            control = container.locator("select").first
            options = self._select_options(control)
            return FormField(label, FieldKind.SELECT, control, container, options)

        if self._count(container, "textarea") > 0:
            control = container.locator("textarea").first
            return FormField(label, FieldKind.TEXTAREA, control, container)

        if self._count(container, "input[type='radio']") > 0:
            radios = container.locator("input[type='radio']")
            options, controls = self._radio_options(container, radios)
            return FormField(label, FieldKind.RADIO, radios, container, options, controls)

        if self._count(container, "input[type='checkbox']") > 0:
            control = container.locator("input[type='checkbox']").first
            return FormField(label, FieldKind.CHECKBOX, control, container)

        if self._count(container, "input[type='file']") > 0:
            control = container.locator("input[type='file']").first
            return FormField(label, FieldKind.FILE, control, container)

        text_input = first(
            container,
            [
                "input[type='text']",
                "input[type='number']",
                "input[type='tel']",
                "input[type='email']",
                "input[type='url']",
                "input[type='date']",
                "input:not([type='hidden'])",
            ],
        )
        if text_input is not None:
            kind = self._input_kind(text_input, label)
            return FormField(label, kind, text_input, container, required=self._required(label))

        if not label:
            return None
        logger.debug("Unclassified field container with label '{}'", label)
        return FormField(label, FieldKind.UNKNOWN, None, container, required=self._required(label))

    def _label_of(self, container: Any) -> str:
        for selector in ("label", "legend", "[aria-label]"):
            node = first(container, [selector])
            if node is None:
                continue
            text = safe_text(node)
            if not text and selector == "[aria-label]":
                try:
                    text = (node.get_attribute("aria-label") or "").strip()
                except Exception:  # pragma: no cover - defensive
                    text = ""
            if text:
                return self._clean_label(text)
        return self._clean_label(safe_text(container))

    @staticmethod
    def _clean_label(text: str) -> str:
        # LinkedIn frequently duplicates the visible label with an sr-only copy.
        first_line = text.splitlines()[0].strip() if text else ""
        return first_line.rstrip("*").strip()

    @staticmethod
    def _required(label: str) -> bool:
        return label.endswith("*")

    def _count(self, scope: Any, selector: str) -> int:
        try:
            return int(scope.locator(selector).count())
        except Exception:  # pragma: no cover - defensive
            return 0

    def _select_options(self, control: Any) -> list[str]:
        try:
            texts = control.locator("option").all_inner_texts()
        except Exception:  # pragma: no cover - defensive
            return []
        # Drop placeholder options such as "Select an option".
        cleaned = [t.strip() for t in texts if t.strip()]
        return [t for t in cleaned if t.lower() not in {"select an option", "select"}]

    def _radio_options(self, container: Any, radios: Any) -> tuple[list[str], list[Any]]:
        options: list[str] = []
        controls: list[Any] = []
        try:
            total = radios.count()
        except Exception:  # pragma: no cover - defensive
            return options, controls
        for i in range(total):
            radio = radios.nth(i)
            label = ""
            try:
                rid = radio.get_attribute("id")
                if rid:
                    lbl = container.locator(f"label[for='{rid}']")
                    if lbl.count() > 0:
                        label = safe_text(lbl.first)
                if not label:
                    label = radio.get_attribute("value") or ""
            except Exception:  # pragma: no cover - defensive
                label = ""
            options.append(label.strip())
            controls.append(radio)
        return options, controls

    def _input_kind(self, control: Any, label: str) -> FieldKind:
        try:
            input_type = (control.get_attribute("type") or "text").lower()
        except Exception:  # pragma: no cover - defensive
            input_type = "text"
        if input_type == "number" or "number" in label.lower():
            return FieldKind.NUMBER
        if input_type == "date":
            return FieldKind.DATE
        return FieldKind.TEXT
