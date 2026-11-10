"""Branch-logic tests for the submit finalisation.

These lock in the decoupled behaviour: submission is automatic unless a confirm
handler is wired (via ``--confirm-submit``), and the confirm gate no longer
depends on ``WorkflowSettings.interactive``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import linkedin_easy_apply.forms.easy_apply as ea
from linkedin_easy_apply.forms.easy_apply import (
    ApplyStatus,
    EasyApplyWorkflow,
    WorkflowSettings,
)
from linkedin_easy_apply.progress import ProgressReporter


def _workflow(settings: WorkflowSettings, on_confirm):
    """Build a workflow with only the attributes ``_finalize_submit`` touches,
    stubbing every method that would drive a real browser."""
    wf = object.__new__(EasyApplyWorkflow)
    wf._settings = settings
    wf._progress = ProgressReporter()
    wf._on_confirm = on_confirm
    wf._page = MagicMock()
    wf._discard = MagicMock()
    wf._click = MagicMock(return_value=True)
    wf._screenshot = MagicMock(return_value=None)
    wf._dismiss_confirmation = MagicMock()
    # Default: LinkedIn did NOT reject the submit with its daily cap. Individual
    # tests override this to exercise the limit-reached branch.
    wf._hit_daily_submission_limit = MagicMock(return_value=False)
    return wf


def test_auto_submits_when_no_confirm_handler(monkeypatch):
    monkeypatch.setattr(ea, "first", lambda *a, **k: MagicMock())
    wf = _workflow(WorkflowSettings(dry_run=False), None)
    result = wf._finalize_submit([], 3)
    assert result.status is ApplyStatus.SUBMITTED
    wf._click.assert_called_once()
    wf._discard.assert_not_called()


def test_submits_when_confirm_accepts(monkeypatch):
    monkeypatch.setattr(ea, "first", lambda *a, **k: MagicMock())
    wf = _workflow(WorkflowSettings(dry_run=False), lambda: True)
    result = wf._finalize_submit([], 3)
    assert result.status is ApplyStatus.SUBMITTED
    wf._discard.assert_not_called()


def test_discards_when_confirm_declines():
    wf = _workflow(WorkflowSettings(dry_run=False), lambda: False)
    result = wf._finalize_submit([], 3)
    assert result.status is ApplyStatus.ABORTED
    wf._discard.assert_called_once()
    wf._click.assert_not_called()


def test_confirm_gate_independent_of_interactive_flag(monkeypatch):
    # A wired confirm handler gates submission even when settings.interactive is
    # False - the two concerns are decoupled.
    monkeypatch.setattr(ea, "first", lambda *a, **k: MagicMock())
    wf = _workflow(WorkflowSettings(dry_run=False, interactive=False), lambda: True)
    assert wf._finalize_submit([], 3).status is ApplyStatus.SUBMITTED

    wf2 = _workflow(WorkflowSettings(dry_run=False, interactive=False), lambda: False)
    assert wf2._finalize_submit([], 3).status is ApplyStatus.ABORTED


def test_dry_run_never_submits():
    wf = _workflow(WorkflowSettings(dry_run=True), None)
    result = wf._finalize_submit([], 3)
    assert result.status is ApplyStatus.DRY_RUN
    wf._discard.assert_called_once()
    wf._click.assert_not_called()


@pytest.mark.parametrize(
    ("dry_run", "approval", "status", "expected"),
    [
        (True, True, ApplyStatus.DRY_RUN, ["discarding_application"]),
        (False, False, ApplyStatus.ABORTED, ["awaiting_input", "discarding_application"]),
        (
            False,
            True,
            ApplyStatus.SUBMITTED,
            ["awaiting_input", "submitting_application", "verifying_submission"],
        ),
        (
            False,
            None,
            ApplyStatus.SUBMITTED,
            ["submitting_application", "verifying_submission"],
        ),
    ],
)
def test_activity_surrounds_real_confirmation_and_submit_boundaries(
    monkeypatch, dry_run, approval, status, expected
):
    events = []

    def confirm():
        assert events[-1].activity == "awaiting_input"
        return approval

    wf = _workflow(WorkflowSettings(dry_run=dry_run), confirm if approval is not None else None)
    wf._progress = ProgressReporter(activity_sink=events.append)
    wf._discard = EasyApplyWorkflow._discard.__get__(wf)
    wf._modal_is_open = MagicMock(return_value=False)
    wf._click_named_button = MagicMock(return_value=False)
    monkeypatch.setattr(ea, "first", lambda *a, **k: None)

    def click(*args):
        assert events[-1].activity == "submitting_application"
        return True

    def outcome():
        assert events[-1].activity == "verifying_submission"
        return ApplyStatus.SUBMITTED, "Fictional confirmation"

    wf._click_action = MagicMock(side_effect=click)
    wf._submission_outcome = MagicMock(side_effect=outcome)
    result = wf._finalize_submit([], 3)
    assert result.status is status
    assert [event.activity for event in events] == expected
    assert wf._click_action.call_count == (0 if dry_run or approval is False else 1)


def test_returns_limit_reached_when_linkedin_rejects_submit(monkeypatch):
    # LinkedIn's daily-cap notice after Submit must NOT be recorded as a submit:
    # the result is LIMIT_REACHED, the modal is discarded, and success is not logged.
    monkeypatch.setattr(ea, "first", lambda *a, **k: MagicMock())
    wf = _workflow(WorkflowSettings(dry_run=False), None)
    wf._hit_daily_submission_limit = MagicMock(return_value=True)
    result = wf._finalize_submit([], 4)
    assert result.status is ApplyStatus.LIMIT_REACHED
    assert result.reason == "LinkedIn daily submission limit reached"
    wf._click.assert_called_once()  # we did click Submit
    wf._discard.assert_called_once()  # then cleaned up the notice


@pytest.mark.parametrize("confirmation", ["Your application was sent", "Application submitted"])
def test_positive_confirmation_is_required_and_preserved(monkeypatch, confirmation):
    wf = _workflow(WorkflowSettings(), None)
    marker = MagicMock()
    marker.inner_text.return_value = confirmation
    monkeypatch.setattr(ea, "first", lambda *a, **k: marker)

    result = wf._finalize_submit([], 3)

    assert result.status is ApplyStatus.SUBMITTED
    assert result.reason == f"LinkedIn confirmation: {confirmation}"


def test_absence_of_rejection_does_not_count_as_success(monkeypatch):
    wf = _workflow(WorkflowSettings(), None)
    monkeypatch.setattr(ea, "first", lambda *a, **k: None)
    wf._click_action = MagicMock(return_value=True)

    result = wf._finalize_submit([], 3)

    assert result.status is ApplyStatus.UNCONFIRMED
    assert "No LinkedIn submission confirmation" in result.reason
    wf._click_action.assert_called_once()
    wf._discard.assert_not_called()


def test_delayed_confirmation_waits_instead_of_failing(monkeypatch):
    wf = _workflow(WorkflowSettings(), None)
    marker = MagicMock()
    marker.inner_text.return_value = "Application submitted"
    found = iter([None, None, None, None, marker])
    monkeypatch.setattr(ea, "first", lambda *a, **k: next(found, marker))

    assert wf._submission_outcome() == (ApplyStatus.SUBMITTED, "Application submitted")
    wf._page.wait_for_timeout.assert_called_once_with(500)
