"""Tests for the accessible-name form engine.

The rebuilt LinkedIn application form dropped its field-container markup, so
fields are found by ARIA role with the control's accessible name as the
question. These tests drive that path with lightweight locator stubs.
"""

from __future__ import annotations

import re

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.detector import (
    _ACCESSIBLE_NAME_JS,
    _RADIO_OPTIONS_JS,
    _SELECT_OPTIONS_JS,
    FormFieldDetector,
    split_question_and_choices,
)
from linkedin_easy_apply.forms.dom_utils import force_close_dialogs
from linkedin_easy_apply.forms.field import FieldKind


class FakeControl:
    """A single control that answers the detector's evaluate() probes."""

    def __init__(
        self,
        name: str,
        *,
        options: list[str] | None = None,
        visible: bool = True,
        question: str = "",
        text: str = "",
    ):
        self._name = name
        self._options = options or []
        self._visible = visible
        self._question = question
        self._text = text

    def is_visible(self) -> bool:
        return self._visible

    def inner_text(self) -> str:
        return self._text

    def evaluate(self, script: str):
        if "choices" in script:  # the question-recovery probe
            return self._question
        if "aria-labelledby" in script:
            return self._name
        if "el.options" in script:
            return self._options
        if "input[type=radio]" in script:
            return self._options
        raise AssertionError(f"unexpected script: {script[:40]}")

    def input_value(self) -> str:
        return ""

    def is_checked(self) -> bool:
        return False


class FakeLocator:
    def __init__(self, controls: list[FakeControl]):
        self._controls = controls

    def count(self) -> int:
        return len(self._controls)

    def nth(self, index: int) -> FakeControl:
        return self._controls[index]

    @property
    def first(self) -> FakeControl:
        return self._controls[0]


class FakeScope:
    """A scope exposing controls per ARIA role and no container markup."""

    def __init__(self, by_role: dict[str, list[FakeControl]]):
        self._by_role = by_role

    def get_by_role(self, role: str, **_kwargs) -> FakeLocator:
        return FakeLocator(self._by_role.get(role, []))

    def locator(self, _selector: str) -> FakeLocator:
        return FakeLocator([])


def _radio_scope(group: FakeControl) -> FakeScope:
    """A radio group that also exposes one radio control per option."""
    group.get_by_role = lambda role, **_k: FakeLocator(  # type: ignore[method-assign]
        [FakeControl(o) for o in group._options] if role == "radio" else []
    )
    return FakeScope({"radiogroup": [group]})


def test_detects_textbox_by_accessible_name():
    scope = FakeScope({"textbox": [FakeControl("Mobile phone number*")]})
    fields = FormFieldDetector().detect(scope)
    assert [(f.label, f.kind) for f in fields] == [("Mobile phone number", FieldKind.TEXT)]


def test_required_marker_is_read_from_the_name():
    scope = FakeScope({"textbox": [FakeControl("Email address*"), FakeControl("Website")]})
    required = {f.label: f.required for f in FormFieldDetector().detect(scope)}
    assert required == {"Email address": True, "Website": False}


def test_combobox_becomes_a_select_with_options():
    control = FakeControl("Phone country code*", options=["Select an option", "India (+91)"])
    fields = FormFieldDetector().detect(FakeScope({"combobox": [control]}))
    assert fields[0].kind is FieldKind.SELECT
    # The placeholder option is not a real answer and must not be offered.
    assert fields[0].options == ["India (+91)"]


def test_radio_group_collects_its_options():
    group = FakeControl("Are you authorised to work?*", options=["Yes", "No"])
    fields = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))
    assert fields[0].kind is FieldKind.RADIO
    assert fields[0].options == ["Yes", "No"]


def test_group_named_after_its_own_choice_recovers_the_question():
    """Observed live: groups named 'Yes' or 'AI/ML' - a choice, not a question.
    Such a label matches no answer key, so a required one stalls the form."""
    group = FakeControl(
        "AI/ML",
        options=["AI/ML", "Web", "Mobile"],
        question="Which domain have you worked in?",
    )
    fields = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))
    assert fields[0].label == "Which domain have you worked in?"
    assert fields[0].options == ["AI/ML", "Web", "Mobile"]


def test_yes_no_group_recovers_the_question():
    group = FakeControl(
        "Yes",
        options=["Yes", "No"],
        question="Are you willing to relocate?*",
    )
    field = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))[0]
    assert field.label == "Are you willing to relocate?"
    assert field.required is True


def test_a_real_group_name_is_kept():
    group = FakeControl(
        "Do you have a valid passport?",
        options=["Yes", "No"],
        question="should not be used",
    )
    field = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))[0]
    assert field.label == "Do you have a valid passport?"


def test_group_falls_back_to_its_text_when_the_probe_finds_nothing():
    group = FakeControl(
        "Yes", options=["Yes", "No"], question="", text="Can you join immediately? Yes No"
    )
    field = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))[0]
    assert "Can you join immediately?" in field.label


def test_radio_group_exposes_one_control_per_option():
    """The filler checks a radio by index into option_controls, so a group
    without them resolves correctly and then silently fails to fill."""
    group = FakeControl("Are you willing to relocate?", options=["Yes", "No"])
    field = FormFieldDetector().detect(_radio_scope(group))[0]
    assert len(field.option_controls) == len(field.options) == 2


def test_radio_controls_are_dropped_when_they_do_not_line_up():
    """A mismatch would make the filler check the wrong choice."""
    group = FakeControl("Pick one", options=["Yes", "No", "Maybe"])
    group.get_by_role = lambda role, **_k: FakeLocator(  # type: ignore[method-assign]
        [FakeControl("Yes")] if role == "radio" else []
    )
    field = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))[0]
    assert field.option_controls == []


def test_invisible_controls_are_ignored():
    scope = FakeScope({"textbox": [FakeControl("Hidden", visible=False)]})
    assert FormFieldDetector().detect(scope) == []


def test_controls_without_a_name_are_ignored():
    scope = FakeScope({"textbox": [FakeControl("")]})
    assert FormFieldDetector().detect(scope) == []


def test_each_role_maps_to_its_kind():
    scope = FakeScope(
        {
            "textbox": [FakeControl("Summary")],
            "combobox": [FakeControl("Country")],
            "spinbutton": [FakeControl("Years")],
            "checkbox": [FakeControl("Agree")],
        }
    )
    kinds = {f.label: f.kind for f in FormFieldDetector().detect(scope)}
    assert kinds == {
        "Summary": FieldKind.TEXT,
        "Country": FieldKind.SELECT,
        "Years": FieldKind.NUMBER,
        "Agree": FieldKind.CHECKBOX,
    }


def test_scope_without_roles_is_handled():
    class Bare:
        def locator(self, _selector: str) -> FakeLocator:
            return FakeLocator([])

    assert FormFieldDetector().detect(Bare()) == []


def test_probe_scripts_stay_distinguishable():
    """The stubs dispatch on these tokens, so they must remain unique."""
    assert "aria-labelledby" in _ACCESSIBLE_NAME_JS
    assert "el.options" in _SELECT_OPTIONS_JS
    assert "input[type=radio]" in _RADIO_OPTIONS_JS


# -- step buttons --------------------------------------------------------------
def test_step_button_patterns_match_real_labels():
    cases = [
        ("next", "Next"),
        ("next", "Continue to next step"),
        ("review", "Review your application"),
        ("submit", "Submit application"),
    ]
    for action, label in cases:
        pattern = selectors.STEP_BUTTON_NAMES[action]
        assert re.search(pattern, label, re.I), f"{pattern!r} should match {label!r}"


def test_submit_pattern_does_not_match_next():
    assert not re.search(selectors.STEP_BUTTON_NAMES["submit"], "Next", re.I)


# -- dialog teardown -----------------------------------------------------------
class FakePage:
    def __init__(self, result):
        self._result = result
        self.calls = 0

    def evaluate(self, _script: str):
        self.calls += 1
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def test_force_close_reports_closed_dialogs():
    page = FakePage(2)
    assert force_close_dialogs(page) == 2
    assert page.calls == 1


def test_force_close_survives_an_evaluate_failure():
    assert force_close_dialogs(FakePage(RuntimeError("page closed"))) == 0


def test_force_close_handles_no_dialogs():
    assert force_close_dialogs(FakePage(0)) == 0


# -- "<question> <choice>" radio labels ---------------------------------------
# Live markup: <fieldset role="radiogroup"> whose own name is empty, and each
# <input> carries aria-label="<question>\n<choice>".


def test_shared_prefix_is_the_question():
    question, choices = split_question_and_choices(
        [
            "Are you willing to relocate to Hyderabad? Yes",
            "Are you willing to relocate to Hyderabad? No",
        ]
    )
    assert question == "Are you willing to relocate to Hyderabad?"
    assert choices == ["Yes", "No"]


def test_newlines_in_the_label_are_normalised():
    question, choices = split_question_and_choices(
        ["Which domain?\nAI/ML", "Which domain?\nWeb", "Which domain?\nMobile"]
    )
    assert question == "Which domain?"
    assert choices == ["AI/ML", "Web", "Mobile"]


def test_prefix_only_splits_on_a_word_boundary():
    """ "Yes" and "Yes, remote" share "Yes" but it is not a question."""
    question, choices = split_question_and_choices(
        ["Can you travel? Yes", "Can you travel? Yes, often"]
    )
    assert question == "Can you travel?"
    assert choices == ["Yes", "Yes, often"]


def test_unrelated_labels_are_left_alone():
    labels = ["Yes", "No"]
    assert split_question_and_choices(labels) == ("", labels)


def test_a_single_radio_is_left_alone():
    assert split_question_and_choices(["Only choice"]) == ("", ["Only choice"])


def test_blank_labels_are_dropped():
    assert split_question_and_choices(["", "  "]) == ("", [])


def test_detector_uses_the_shared_prefix_for_the_label():
    group = FakeControl("", options=["Do you have a PAN card? Yes", "Do you have a PAN card? No"])
    field = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))[0]
    assert field.label == "Do you have a PAN card?"
    assert field.options == ["Yes", "No"]


def test_question_keeps_its_final_word():
    """Cutting at the last space stole "Hyderabad?" from this question."""
    question, choices = split_question_and_choices(
        [
            "Are you willing to relocate to Hyderabad?\nYes",
            "Are you willing to relocate to Hyderabad?\nNo",
        ]
    )
    assert question == "Are you willing to relocate to Hyderabad?"
    assert choices == ["Yes", "No"]


def test_resume_filenames_are_not_a_question():
    """The resume picker's radios share a filename stem, not a prompt."""
    labels = ["Example_Candidate_ai.pdf", "Example_Candidate_FullStack.pdf"]
    assert split_question_and_choices(labels) == ("", labels)


def test_a_colon_prompt_also_splits():
    question, choices = split_question_and_choices(["Select one: Alpha", "Select one: Beta"])
    assert question == "Select one:"
    assert choices == ["Alpha", "Beta"]


def test_duplicate_choices_are_rejected():
    """Identical remainders mean the prefix was cut in the wrong place."""
    labels = ["Team A lead", "Team B lead"]
    assert split_question_and_choices(labels) == ("", labels)


def test_question_carried_as_an_extra_option_is_promoted():
    """Observed live: the group is named "Yes" and the question rides along in
    the option list, so no answer key could ever match."""
    group = FakeControl(
        "Yes",
        options=["Are you comfortable working in a hybrid setting?", "Yes", "No"],
    )
    field = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))[0]
    assert field.label == "Are you comfortable working in a hybrid setting?"
    assert field.options == ["Yes", "No"]


def test_a_normally_named_group_is_not_disturbed():
    group = FakeControl("How many years with Python?", options=["0", "1", "2"])
    field = FormFieldDetector().detect(FakeScope({"radiogroup": [group]}))[0]
    assert field.label == "How many years with Python?"
    assert field.options == ["0", "1", "2"]
