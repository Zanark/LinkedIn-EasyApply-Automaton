"""Tests for the custom_questions escape hatch.

A ``custom_questions`` list in answers.yaml answers bespoke per-posting screening
questions the category parser cannot recognise, so they no longer get left blank
(and abort the application under ``-y``). Category-based answers always win.
"""

from __future__ import annotations

from linkedin_easy_apply.answers.resolver import AnswerResolver
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.forms.field import FieldKind, FormField
from linkedin_easy_apply.forms.filler import FormFiller
from linkedin_easy_apply.parser.categories import AnswerType
from linkedin_easy_apply.parser.question_parser import QuestionParser

_DATA = {
    "expected_ctc": 4000000,
    "custom_questions": [
        {"match": ["shift timing", "night shift"], "answer": "Yes"},
        {"match": "which location are you applying", "answer": ["Bengaluru", "Hyderabad"]},
        {"match": "background check", "answer": "No"},
    ],
}

_SHIFT_Q = "The shift timings are 5 PM-2 AM (Cabs provided). Are you comfortable with this?"
_LOC_Q = "Which location are you applying for?"


def _resolver() -> AnswerResolver:
    return AnswerResolver(AnswerStore(_DATA))


# -- store --------------------------------------------------------------------
def test_custom_answer_matches_substring_case_insensitive():
    store = AnswerStore(_DATA)
    assert store.custom_answer(_SHIFT_Q) == "Yes"
    assert store.custom_answer("Any NIGHT SHIFT ok?") == "Yes"
    assert store.custom_answer(_LOC_Q) == ["Bengaluru", "Hyderabad"]


def test_custom_answer_none_when_no_match():
    store = AnswerStore(_DATA)
    assert store.custom_answer("What is your favourite colour?") is None


def test_no_custom_section_is_safe():
    store = AnswerStore({"phone": "123"})
    assert store.custom_answer("anything") is None


# -- resolver -----------------------------------------------------------------
def test_resolver_custom_yes_is_boolean():
    parsed = QuestionParser().parse(_SHIFT_Q)
    res = _resolver().resolve(parsed)
    assert res.found is True
    assert res.value == "Yes"
    assert res.bool_value is True
    assert res.source == "custom"


def test_resolver_custom_no_is_boolean():
    parsed = QuestionParser().parse("Are you willing to undergo a background check?")
    res = _resolver().resolve(parsed)
    assert res.value == "No"
    assert res.bool_value is False


def test_resolver_custom_list_sets_candidates():
    parsed = QuestionParser().parse(_LOC_Q)
    res = _resolver().resolve(parsed)
    assert res.found is True
    assert res.value == "Bengaluru"
    assert res.candidates == ("Bengaluru", "Hyderabad")


def test_custom_does_not_shadow_real_category():
    """A salary question is resolved by the salary logic, never by custom_questions."""
    parsed = QuestionParser().parse("What is your expected CTC?")
    res = _resolver().resolve(parsed)
    assert res.source != "custom"
    # expected_ctc is set, so it resolves via the category path
    assert res.value == "4000000"


# -- filler: candidate fallback -----------------------------------------------
def _select(options: list[str]) -> FormField:
    return FormField("Q", FieldKind.SELECT, control=None, options=options)


def test_pick_option_prefers_first_candidate():
    res = _resolver().resolve(QuestionParser().parse(_LOC_Q))
    filler = FormFiller()
    assert filler._pick_option(_select(["Bengaluru", "Hyderabad", "Pune"]), res) == "Bengaluru"


def test_pick_option_falls_back_to_second_candidate():
    res = _resolver().resolve(QuestionParser().parse(_LOC_Q))
    filler = FormFiller()
    # No Bengaluru option -> falls back to Hyderabad.
    assert filler._pick_option(_select(["Pune", "Hyderabad", "Chennai"]), res) == "Hyderabad"


def test_pick_option_blank_when_no_candidate_matches():
    res = _resolver().resolve(QuestionParser().parse(_LOC_Q))
    filler = FormFiller()
    assert filler._pick_option(_select(["Delhi", "Mumbai"]), res) is None


def test_shift_question_fills_yes_no_select():
    res = _resolver().resolve(QuestionParser().parse(_SHIFT_Q))
    filler = FormFiller()
    assert filler._pick_option(_select(["Yes", "No"]), res) == "Yes"
    assert res.answer_type is AnswerType.BOOLEAN
