"""Branch-logic tests for the submit finalisation.

These lock in the decoupled behaviour: submission is automatic unless a confirm
handler is wired (via ``--confirm-submit``), and the confirm gate no longer
depends on ``WorkflowSettings.interactive``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import linkedin_easy_apply.forms.easy_apply as ea
from linkedin_easy_apply.forms.easy_apply import (
    ApplyStatus,
    EasyApplyWorkflow,
    WorkflowSettings,
)


def _workflow(settings: WorkflowSettings, on_confirm):
    """Build a workflow with only the attributes ``_finalize_submit`` touches,
    stubbing every method that would drive a real browser."""
    wf = object.__new__(EasyApplyWorkflow)
    wf._settings = settings
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
