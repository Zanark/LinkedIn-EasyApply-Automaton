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

# The rebuilt form has no field-container classes; controls carry the question
# as their own accessible name instead.
_ACCESSIBLE_NAME_JS = """
el => {
  const direct = el.getAttribute('aria-label');
  if (direct) return direct;
  const labelled = el.getAttribute('aria-labelledby');
  if (labelled) {
    const target = document.getElementById(labelled.split(/\\s+/)[0]);
    if (target && target.innerText) return target.innerText;
  }
  if (el.labels && el.labels.length && el.labels[0].innerText) return el.labels[0].innerText;
  return el.getAttribute('placeholder') || '';
}
"""
_SELECT_OPTIONS_JS = """
el => el.tagName === 'SELECT'
  ? [...el.options].map(o => (o.label || o.textContent || '').trim()).filter(Boolean)
  : []
"""
_RADIO_OPTIONS_JS = """
el => {
  const radios = [...el.querySelectorAll('input[type=radio], [role=radio]')];
  const labels = radios.map(r =>
    r.getAttribute('aria-label')
    || (r.labels && r.labels[0] && r.labels[0].innerText)
    || r.innerText || r.getAttribute('value') || '');
  const repeated = labels.length > 1 && labels[0]
    && labels.every(label => label.trim() === labels[0].trim());
  return radios.map((radio, index) => {
    if (repeated) {
      // Some layouts label every input with the question, not its choice.
      for (let row = radio.parentElement; row && row !== el; row = row.parentElement) {
        if (row.querySelectorAll('input[type=radio], [role=radio]').length !== 1) break;
        const text = (row.innerText || '').trim();
        if (text && text !== labels[index].trim()) return text;
      }
    }
    return labels[index];
  });
}
"""
# Recover a radio group's question when its accessible name is just a choice:
# the question is a legend, or the nearest preceding text that is not a choice.
_RADIO_QUESTION_JS = """
el => {
  const choices = new Set((__RADIO_OPTIONS__)(el)
    .map(label => label.trim().toLowerCase()).filter(Boolean));
  const usable = text => {
    const t = (text || '').trim();
    return t.length > 2 && !choices.has(t.toLowerCase()) ? t : '';
  };
  let node = el;
  for (let i = 0; i < 4 && node; i++) {
    const legend = node.querySelector('legend');
    if (legend && usable(legend.innerText)) return usable(legend.innerText);
    for (let sib = node.previousElementSibling; sib; sib = sib.previousElementSibling) {
      const text = usable(sib.innerText);
      if (text) return text;
    }
    node = node.parentElement;
  }
  // Nothing preceded the group, so subtract the choices from the surrounding
  // text and keep what is left - that remainder is the question.
  node = el.parentElement;
  for (let i = 0; i < 4 && node; i++) {
    let text = (node.innerText || '').trim();
    for (const choice of choices) {
      text = text.replace(new RegExp('(^|\\\\s)' + choice.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + '(\\\\s|$)', 'gi'), ' ');
    }
    text = text.replace(/\\s+/g, ' ').trim();
    if (text.length > 2 && text.length < 300) return text;
    node = node.parentElement;
  }
  return '';
}
""".replace("__RADIO_OPTIONS__", _RADIO_OPTIONS_JS)
# role -> field kind, for controls discovered by accessible name.
_ROLE_KINDS: tuple[tuple[str, FieldKind], ...] = (
    ("textbox", FieldKind.TEXT),
    ("combobox", FieldKind.SELECT),
    ("spinbutton", FieldKind.NUMBER),
    ("checkbox", FieldKind.CHECKBOX),
)


def split_question_and_choices(raw_labels: list[str]) -> tuple[str, list[str]]:
    """Split radio labels shaped ``"<question> <choice>"`` into their parts.

    Every radio in a group repeats the question in its own accessible name and
    appends that radio's choice, and the group itself is unlabelled. The shared
    prefix is therefore the question and each remainder is a choice. Returns
    ``("", originals)`` when the labels do not share a whole-word prefix.
    """
    labels = [" ".join(raw.split()) for raw in raw_labels if raw and raw.strip()]
    if len(labels) < 2:
        return "", labels

    prefix = labels[0]
    for label in labels[1:]:
        while prefix and not label.startswith(prefix):
            prefix = prefix[:-1]
        if not prefix:
            return "", labels

    # Cut after the prompt's own punctuation when it has some, so a question
    # keeps its last word; otherwise fall back to the final word boundary,
    # which keeps shared choice text ("Yes" / "Yes, often") out of the question.
    cut = max(prefix.rfind("?"), prefix.rfind(":"))
    cut = cut + 1 if cut >= 0 else prefix.rfind(" ") + 1
    question = prefix[:cut].strip()
    # A single token is a shared filename stem or similar, not a question.
    if not question or " " not in question:
        return "", labels

    choices = [label[cut:].strip() for label in labels]
    if not all(choices) or len(set(choices)) != len(choices):
        return "", labels
    return question, choices


class FormFieldDetector:
    """Discover :class:`FormField` instances within the current modal step."""

    def detect(self, modal: Any) -> list[FormField]:
        containers = first_group(modal, selectors.FIELD_CONTAINER)
        if containers is None:
            fields = self._detect_by_role(modal)
            if fields:
                logger.debug("Detected {} field(s) by accessible name", len(fields))
                return fields
            logger.debug("No field containers found in current step")
            return []

        fields = []
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

    # -- accessible-name detection -------------------------------------------
    def _detect_by_role(self, scope: Any) -> list[FormField]:
        """Find controls by ARIA role when no field container markup exists.

        The question text is the control's own accessible name, and a trailing
        ``*`` marks it required - the same convention the container markup used.
        """
        fields: list[FormField] = []
        for role, kind in _ROLE_KINDS:
            for control in self._by_role(scope, role):
                label = self._accessible_name(control)
                if not label:
                    continue
                options = self._options_of(control) if kind is FieldKind.SELECT else []
                field = FormField(
                    self._clean_label(label),
                    kind,
                    control,
                    scope,
                    options,
                    required=self._required(label.strip()),
                )
                field.current_value = current_value_of(field)
                fields.append(field)
        fields.extend(self._radio_groups(scope))
        return fields

    def _by_role(self, scope: Any, role: str, *, visible_only: bool = True) -> list[Any]:
        try:
            locator = scope.get_by_role(role)
            total = locator.count()
        except Exception:  # pragma: no cover - fake scopes in tests
            return []
        controls: list[Any] = []
        for index in range(total):
            node = locator.nth(index)
            if not visible_only:
                controls.append(node)
                continue
            try:
                if node.is_visible():
                    controls.append(node)
            except Exception:  # pragma: no cover - defensive
                continue
        return controls

    def _radio_groups(self, scope: Any) -> list[FormField]:
        groups: list[FormField] = []
        for group in self._by_role(scope, "radiogroup"):
            label = self._accessible_name(group)
            raw_options = [o for o in self._evaluate(group, _RADIO_OPTIONS_JS, []) if o]
            # Each radio is labelled "<question> <choice>", so the shared prefix
            # is the question - recovering it also strips it from the choices.
            shared_question, options = split_question_and_choices(raw_options)
            # A group whose accessible name is simply one of its own choices
            # ("Yes", "AI/ML") has lost the question, and a question like that
            # matches no answer key, so a required one stalls the whole form.
            if not label or self._is_option(label, options):
                label = shared_question or label
            if not label or self._is_option(label, options):
                # Some groups carry the question as an extra entry alongside the
                # choices; promote it and drop it from the choices.
                prompt = next((o for o in options if "?" in o and " " in o), "")
                if prompt:
                    label = prompt
                    options = [o for o in options if o != prompt]
            if not label or self._is_option(label, options):
                label = self._evaluate(group, _RADIO_QUESTION_JS, "") or ""
            if not label or self._is_option(label, options):
                # Last resort: the group's own text, minus the option labels.
                label = self._clean_label(safe_text(group))
                for option in options:
                    label = label.replace(option, " ")
            cleaned = self._clean_label(label)
            if not cleaned:
                continue
            if self._is_option(cleaned, options):
                logger.debug(
                    "Radio group still labelled with a choice ({!r}); markup: {}",
                    cleaned,
                    str(self._evaluate(group, "el => el.outerHTML", ""))[:900],
                )
            # The filler checks a radio by index into option_controls, so a
            # group without them can never be answered. A radio is often
            # visually hidden behind a styled label, so do not filter on that.
            controls = self._by_role(group, "radio", visible_only=False)
            field = FormField(
                cleaned,
                FieldKind.RADIO,
                group,
                scope,
                options,
                option_controls=controls if len(controls) == len(options) else [],
                required=self._required(label.strip()),
            )
            field.current_value = current_value_of(field)
            groups.append(field)
        return groups

    @staticmethod
    def _is_option(label: str, options: list[str]) -> bool:
        target = label.strip().strip("*").lower()
        return any(target == o.strip().strip("*").lower() for o in options if o)

    def _accessible_name(self, control: Any) -> str:
        return " ".join(str(self._evaluate(control, _ACCESSIBLE_NAME_JS, "")).split())

    def _options_of(self, control: Any) -> list[str]:
        options = self._evaluate(control, _SELECT_OPTIONS_JS, [])
        return [o for o in options if o and o.lower() not in {"select an option", "select"}]

    @staticmethod
    def _evaluate(control: Any, script: str, default: Any) -> Any:
        try:
            return control.evaluate(script)
        except Exception:  # pragma: no cover - defensive
            return default

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
            # Re-derive the label excluding the option texts so the question is
            # never mistaken for an option (e.g. "Yes"/"No").
            label = self._label_of(container, exclude=set(options))
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

    def _label_of(self, container: Any, *, exclude: set[str] | None = None) -> str:
        """Return the field's question text.

        ``exclude`` holds texts that must never be used as the label (the option
        labels of a radio group). LinkedIn wraps radio groups in a
        ``<fieldset>`` whose ``<legend>`` carries the real question while each
        option has its own ``<label>`` (Yes/No), so ``<legend>`` is tried before
        ``<label>`` and any candidate matching an option is skipped.
        """
        excluded = {e.strip().lower() for e in (exclude or set()) if e.strip()}
        for selector in ("legend", "label", "[aria-label]"):
            node = first(container, [selector])
            if node is None:
                continue
            text = safe_text(node)
            if not text and selector == "[aria-label]":
                try:
                    text = (node.get_attribute("aria-label") or "").strip()
                except Exception:  # pragma: no cover - defensive
                    text = ""
            cleaned = self._clean_label(text)
            if cleaned and cleaned.lower() not in excluded:
                return cleaned
        fallback = self._clean_label(safe_text(container))
        return "" if fallback.lower() in excluded else fallback

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
