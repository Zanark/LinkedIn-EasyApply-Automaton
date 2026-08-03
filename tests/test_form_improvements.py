"""Tests for the live-test follow-up improvements.

Covers the pure-logic parts of: phone country-code defaulting, prefilled-field
skipping, resume name matching, current-value reading, and the option matcher.
The Playwright-coupled workflow branches are validated with lightweight stubs.
"""

from __future__ import annotations

import pytest

from linkedin_easy_apply.answers.resolver import AnswerResolution, AnswerResolver
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.forms.detector import FormFieldDetector
from linkedin_easy_apply.forms.easy_apply import _resume_matches
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.filler import FormFiller, _infer_yes_no
from linkedin_easy_apply.forms.matching import country_code_option, dial_code
from linkedin_easy_apply.forms.values import current_value_of
from linkedin_easy_apply.parser.categories import AnswerType, QuestionCategory
from linkedin_easy_apply.parser.question_parser import QuestionParser

_COUNTRY_OPTIONS = ["India (+91)", "United States (+1)", "United Kingdom (+44)"]


# -- parser: phone country code ------------------------------------------------
@pytest.mark.parametrize(
    "text",
    ["Phone country code", "Country code", "Mobile phone country code", "Phone country code*"],
)
def test_phone_country_code_category(text: str):
    parsed = QuestionParser().parse(text)
    assert parsed.category is QuestionCategory.PHONE_COUNTRY_CODE


def test_plain_phone_still_phone():
    assert QuestionParser().parse("Mobile phone number").category is QuestionCategory.PHONE


# -- resolver: country-code default -------------------------------------------
def test_resolver_country_code_default_when_absent():
    resolver = AnswerResolver(AnswerStore({}))
    parsed = QuestionParser().parse("Phone country code")
    resolution = resolver.resolve(parsed)
    assert resolution.found is True
    assert resolution.value == "+91"
    assert resolution.source == "default"


def test_resolver_country_code_from_answers():
    resolver = AnswerResolver(AnswerStore({"phone_country_code": "India (+91)"}))
    parsed = QuestionParser().parse("Phone country code")
    assert resolver.resolve(parsed).value == "India (+91)"


# -- matching: dialling code ---------------------------------------------------
@pytest.mark.parametrize(
    "value, code",
    [("India (+91)", "+91"), ("+91", "+91"), ("+91 9873824499", "+91"), ("India", None)],
)
def test_dial_code(value: str, code: str | None):
    assert dial_code(value) == code


def test_country_code_option_by_code():
    assert country_code_option("+91", _COUNTRY_OPTIONS) == "India (+91)"


def test_country_code_option_by_name():
    assert country_code_option("India", _COUNTRY_OPTIONS) == "India (+91)"


def test_country_code_option_none_when_empty():
    assert country_code_option("+91", []) is None


# -- filler: matches_current (prefilled skip) ---------------------------------
def _field(kind: FieldKind, options: list[str] | None = None) -> FormField:
    return FormField("Q", kind, control=None, options=options or [])


def test_matches_current_text_equal():
    filler = FormFiller()
    res = AnswerResolution(True, "Bengaluru", "yaml", AnswerType.TEXT)
    assert filler.matches_current(_field(FieldKind.TEXT), res, "Bengaluru") is True
    assert filler.matches_current(_field(FieldKind.TEXT), res, "Mumbai") is False


def test_matches_current_number_equivalent():
    filler = FormFiller()
    res = AnswerResolution(True, "5", "yaml", AnswerType.NUMBER)
    assert filler.matches_current(_field(FieldKind.NUMBER), res, "5.0") is True
    assert filler.matches_current(_field(FieldKind.NUMBER), res, "6") is False


def test_matches_current_select_option():
    filler = FormFiller()
    field = _field(FieldKind.SELECT, ["Yes", "No"])
    res = AnswerResolution(True, "Yes", "yaml", AnswerType.CHOICE)
    assert filler.matches_current(field, res, "Yes") is True
    assert filler.matches_current(field, res, "No") is False


def test_matches_current_checkbox():
    filler = FormFiller()
    field = _field(FieldKind.CHECKBOX)
    res = AnswerResolution(True, "Yes", "yaml", AnswerType.BOOLEAN, bool_value=True)
    assert filler.matches_current(field, res, "true") is True
    assert filler.matches_current(field, res, "false") is False


def test_matches_current_blank_is_false():
    filler = FormFiller()
    res = AnswerResolution(True, "x", "yaml", AnswerType.TEXT)
    assert filler.matches_current(_field(FieldKind.TEXT), res, None) is False
    assert filler.matches_current(_field(FieldKind.TEXT), res, "") is False


# -- filler: Yes/No <select> coercion -----------------------------------------
def test_pick_option_numeric_years_to_yes():
    filler = FormFiller()
    field = _field(FieldKind.SELECT, ["Yes", "No"])
    res = AnswerResolution(True, "2", "yaml", AnswerType.NUMBER)
    assert filler._pick_option(field, res) == "Yes"


def test_pick_option_zero_years_to_no():
    filler = FormFiller()
    field = _field(FieldKind.SELECT, ["Yes", "No"])
    res = AnswerResolution(True, "0", "yaml", AnswerType.NUMBER)
    assert filler._pick_option(field, res) == "No"


def test_pick_option_degree_string_to_yes():
    filler = FormFiller()
    field = _field(FieldKind.SELECT, ["Yes", "No"])
    res = AnswerResolution(True, "Master's Degree", "yaml", AnswerType.TEXT)
    assert filler._pick_option(field, res) == "Yes"


def test_pick_option_negative_string_to_no():
    filler = FormFiller()
    field = _field(FieldKind.SELECT, ["Yes", "No"])
    res = AnswerResolution(True, "None", "yaml", AnswerType.TEXT)
    assert filler._pick_option(field, res) == "No"


def test_pick_option_multi_option_select_not_coerced():
    """A genuine multi-choice select with no match is left blank, never coerced."""
    filler = FormFiller()
    field = _field(FieldKind.SELECT, ["0-2 years", "3-5 years", "6+ years"])
    res = AnswerResolution(True, "React", "yaml", AnswerType.TEXT)
    assert filler._pick_option(field, res) is None


def test_pick_option_direct_boolean_still_matches():
    filler = FormFiller()
    field = _field(FieldKind.SELECT, ["Yes", "No"])
    res = AnswerResolution(True, "No", "yaml", AnswerType.BOOLEAN, bool_value=False)
    assert filler._pick_option(field, res) == "No"


@pytest.mark.parametrize(
    "value, answer_type, expected",
    [
        ("3", AnswerType.NUMBER, True),
        ("0", AnswerType.NUMBER, False),
        ("Bachelor of Engineering", AnswerType.TEXT, True),
        ("no", AnswerType.TEXT, False),
        ("never", AnswerType.TEXT, False),
        ("", AnswerType.TEXT, None),
        (None, AnswerType.TEXT, None),
    ],
)
def test_infer_yes_no(value, answer_type, expected):
    res = AnswerResolution(True, value, "yaml", answer_type)
    assert _infer_yes_no(res) is expected


# -- resume name matching ------------------------------------------------------
@pytest.mark.parametrize(
    "portal, stem, expected",
    [
        ("Debashish_Mishra_SeafoamTide-Light.pdf", "Debashish_Mishra_SeafoamTide-Light", True),
        ("Debashish_Mishra_SeafoamTide-Light", "Debashish_Mishra_SeafoamTide-Light", True),
        ("Debashish_Mishra_SeafoamTide-Light (1).pdf", "Debashish_Mishra_SeafoamTide-Light", True),
        ("Some_Other_Resume.pdf", "Debashish_Mishra_SeafoamTide-Light", False),
        ("", "Debashish_Mishra_SeafoamTide-Light", False),
    ],
)
def test_resume_matches(portal: str, stem: str, expected: bool):
    assert _resume_matches(portal, stem) is expected


# -- current_value_of with stub controls --------------------------------------
class _Select:
    def __init__(self, text: str) -> None:
        self._text = text

    def evaluate(self, _js: str) -> str:
        return self._text


class _Text:
    def __init__(self, value: str) -> None:
        self._value = value

    def input_value(self) -> str:
        return self._value


class _Checkbox:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def is_checked(self) -> bool:
        return self._checked


def test_current_value_select():
    field = FormField("Country", FieldKind.SELECT, control=_Select("India (+91)"))
    assert current_value_of(field) == "India (+91)"


def test_current_value_select_placeholder_is_none():
    field = FormField("Country", FieldKind.SELECT, control=_Select("Select an option"))
    assert current_value_of(field) is None


def test_current_value_text():
    field = FormField("City", FieldKind.TEXT, control=_Text("Bengaluru"))
    assert current_value_of(field) == "Bengaluru"
    empty = FormField("City", FieldKind.TEXT, control=_Text("  "))
    assert current_value_of(empty) is None


def test_current_value_checkbox():
    on = FormField("Agree", FieldKind.CHECKBOX, control=_Checkbox(True))
    off = FormField("Agree", FieldKind.CHECKBOX, control=_Checkbox(False))
    assert current_value_of(on) == "true"
    assert current_value_of(off) == "false"


def test_current_value_radio():
    class _Radio:
        def __init__(self, checked: bool) -> None:
            self._checked = checked

        def is_checked(self) -> bool:
            return self._checked

    field = FormField(
        "Pick",
        FieldKind.RADIO,
        options=["A", "B", "C"],
        option_controls=[_Radio(False), _Radio(True), _Radio(False)],
    )
    assert current_value_of(field) == "B"


# --- detector: radio group label must be the question, never an option -------
class _Node:
    """A fake DOM element exposing only what the detector reads."""

    def __init__(self, text: str = "", attrs: dict[str, str] | None = None) -> None:
        self._text = text
        self._attrs = attrs or {}

    def inner_text(self) -> str:
        return self._text

    def get_attribute(self, name: str) -> str | None:
        return self._attrs.get(name)


class _Query:
    """The fake locator returned by ``container.locator(selector)``."""

    def __init__(self, nodes: list[_Node]) -> None:
        self._nodes = nodes

    def count(self) -> int:
        return len(self._nodes)

    @property
    def first(self) -> _Node:
        return self._nodes[0]

    def nth(self, index: int) -> _Node:
        return self._nodes[index]

    def all_inner_texts(self) -> list[str]:
        return [n.inner_text() for n in self._nodes]


class _Container:
    """A fake field container mapping CSS selectors to fake nodes."""

    def __init__(self, selmap: dict[str, list[_Node]], text: str = "") -> None:
        self._selmap = selmap
        self._text = text

    def locator(self, selector: str) -> _Query:
        return _Query(self._selmap.get(selector, []))

    def inner_text(self) -> str:
        return self._text


def _radio_container(
    *, legend: str | None, options: tuple[str, ...] = ("Yes", "No"), text: str = ""
) -> _Container:
    """Build a fake radio-group container like LinkedIn's Easy Apply DOM."""
    selmap: dict[str, list[_Node]] = {}
    if legend is not None:
        selmap["legend"] = [_Node(legend)]
    radios: list[_Node] = []
    for i, opt in enumerate(options):
        rid = f"r{i}"
        radios.append(_Node(attrs={"id": rid, "value": opt}))
        selmap[f"label[for='{rid}']"] = [_Node(opt)]
    selmap["input[type='radio']"] = radios
    # A bare "label" query returns the option labels (first == options[0]).
    selmap["label"] = [_Node(o) for o in options]
    return _Container(selmap, text=text)


def test_radio_label_uses_legend_not_option():
    # Regression: the old selector order returned the first option ("Yes").
    container = _radio_container(legend="Are you willing to relocate to Bengaluru?")
    field = FormFieldDetector()._classify(container)
    assert field is not None
    assert field.kind is FieldKind.RADIO
    assert field.label == "Are you willing to relocate to Bengaluru?"
    assert field.options == ["Yes", "No"]


def test_radio_label_falls_back_to_container_text_when_no_legend():
    # No <legend>: the guard must skip the option labels and recover the
    # question from the container's own text rather than emit "Yes".
    container = _radio_container(
        legend=None, text="Do you have a valid work authorization?\nYes\nNo"
    )
    field = FormFieldDetector()._classify(container)
    assert field is not None
    assert field.kind is FieldKind.RADIO
    assert field.label == "Do you have a valid work authorization?"
    assert field.label not in {"Yes", "No"}


def test_radio_label_blank_rather_than_option_when_only_options_present():
    # Nothing but option labels anywhere -> an empty (honest) label, never "Yes".
    container = _radio_container(legend=None, text="Yes\nNo")
    field = FormFieldDetector()._classify(container)
    assert field is not None
    assert field.kind is FieldKind.RADIO
    assert field.label == ""
