"""Tests for the live-test follow-up improvements.

Covers the pure-logic parts of: phone country-code defaulting, prefilled-field
skipping, resume name matching, current-value reading, and the option matcher.
The Playwright-coupled workflow branches are validated with lightweight stubs.
"""

from __future__ import annotations

import pytest

from linkedin_easy_apply.answers.resolver import AnswerResolution, AnswerResolver
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.forms.easy_apply import _resume_matches
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.filler import FormFiller
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


# -- resume name matching ------------------------------------------------------
@pytest.mark.parametrize(
    "portal, stem, expected",
    [
        ("Debashish_Mishra_Seafoam-Light.pdf", "Debashish_Mishra_Seafoam-Light", True),
        ("Debashish_Mishra_Seafoam-Light", "Debashish_Mishra_Seafoam-Light", True),
        ("Debashish_Mishra_Seafoam-Light (1).pdf", "Debashish_Mishra_Seafoam-Light", True),
        ("Some_Other_Resume.pdf", "Debashish_Mishra_Seafoam-Light", False),
        ("", "Debashish_Mishra_Seafoam-Light", False),
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
