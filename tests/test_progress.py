"""Offline metrics protocol and authoritative application-outcome boundaries."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms.easy_apply import ApplyResult, ApplyStatus, WorkflowSettings
from linkedin_easy_apply.jobs import Job
from linkedin_easy_apply.orchestrator import Orchestrator, RunSummary
from linkedin_easy_apply.progress import (
    FRAME_END,
    FRAME_START,
    MAX_FRAME,
    PROGRESS_ENV,
    ProgressError,
    ProgressReporter,
    ProgressSnapshot,
    ProgressStream,
    encode_progress,
    gui_progress,
)


def test_framed_snapshots_survive_every_split_without_delaying_a_prompt():
    snapshot = ProgressSnapshot(action="apply", run_id=7)
    frame = encode_progress(snapshot)
    for split in range(len(frame) + 1):
        stream = ProgressStream()
        assert list(stream.feed("Your answer: ")) == ["Your answer: "]
        records = [
            *stream.feed(frame[:split]),
            *stream.feed(frame[split:] + frame + "caf\u00e9\n"),
            *stream.finish(),
        ]
        assert records == [snapshot, snapshot, "caf\u00e9\n"]


@pytest.mark.parametrize(
    "change",
    [
        {"version": 2},
        {"version": True},
        {"counts": {"applied": 1}},
        {"counts": {"scanned": -1}},
        {"counts": {"applied": True}},
        {"action": "unknown"},
        {"person_name": "Fictional Example"},
    ],
)
def test_invalid_records_are_not_zero_counts_or_sensitive_console_output(change):
    payload = ProgressSnapshot(action="scan").model_dump() | change
    valid = ProgressSnapshot(action="scan", target=5)
    stream = ProgressStream()
    records = list(
        stream.feed(
            FRAME_START
            + json.dumps(payload)
            + FRAME_END
            + "Still running\n"
            + encode_progress(valid)
        )
    )
    assert isinstance(records[0], ProgressError)
    assert "Fictional Example" not in records[0].message
    assert records[1:] == ["Still running\n", valid]


def test_missing_fields_truncation_and_oversized_records_recover():
    stream = ProgressStream()
    valid = ProgressSnapshot(action="apply")
    assert isinstance(
        list(stream.feed(FRAME_START + '{"action":"apply"}' + FRAME_END))[0], ProgressError
    )
    assert list(stream.feed(FRAME_START + '{"action":')) == []
    records = list(stream.feed(encode_progress(valid)))
    assert isinstance(records[0], ProgressError)
    assert records[1] == valid
    assert isinstance(list(stream.feed(FRAME_START + "x" * (MAX_FRAME + 1)))[0], ProgressError)
    assert list(stream.feed("more discarded payload")) == []
    assert list(stream.feed(FRAME_END + "Prompt: ")) == ["Prompt: "]
    assert list(stream.feed(FRAME_START + '{"version":')) == []
    assert isinstance(list(stream.finish())[0], ProgressError)
    assert list(stream.feed("Fresh output")) == ["Fresh output"]


def test_gui_opt_in_does_not_change_terminal_output(monkeypatch, capsys):
    monkeypatch.delenv(PROGRESS_ENV, raising=False)
    assert gui_progress() is None
    assert capsys.readouterr().err == ""
    monkeypatch.setenv(PROGRESS_ENV, "1")
    reporter = gui_progress()
    assert reporter is not None
    reporter.start("connect", dry_run=True)
    reporter.increment({"connect_dry_runs": 1})
    records = list(ProgressStream().feed(capsys.readouterr().err))
    assert len(records) == 2
    assert records[-1].counts["connect_sent"] == 0
    assert records[-1].counts["connect_dry_runs"] == 1


def _application(tmp_path, monkeypatch, status):
    config = AppConfig()
    config.database.path = tmp_path / "outcomes.db"
    config.screenshots.directory = tmp_path / "shots"
    db = Database(config.database.path)
    db.initialize()
    snapshots = []
    reporter = ProgressReporter(snapshots.append)
    orch = Orchestrator(config, db, AnswerStore({}), progress=reporter)
    run_id = db.start_run("apply")
    reporter.start("apply", run_id=run_id, dry_run=status is ApplyStatus.DRY_RUN, target=3)
    summary = RunSummary(run_id=run_id, mode="apply")
    job = Job(url="https://example.test/jobs/1", title="Example engineer")
    job_id = db.upsert_job(job.to_db_dict(), run_id)
    workflow = SimpleNamespace(
        apply=lambda **kwargs: ApplyResult(status=status),
        dismiss_confirmation=lambda: None,
    )
    monkeypatch.setattr(
        "linkedin_easy_apply.orchestrator.EasyApplyWorkflow", lambda *a, **k: workflow
    )
    monkeypatch.setattr(orch, "_maybe_cover_letter", lambda _job: None)
    monkeypatch.setattr(orch, "_maybe_pause", lambda _summary: None)
    return orch, summary, job, job_id, reporter, snapshots, workflow


def test_confirmed_application_is_counted_before_outreach_and_only_once(tmp_path, monkeypatch):
    orch, summary, job, job_id, reporter, snapshots, workflow = _application(
        tmp_path, monkeypatch, ApplyStatus.SUBMITTED
    )
    order = []

    def outreach(*args, **kwargs):
        assert snapshots[-1].counts["applied"] == 1
        assert summary.applied == 0
        reporter.outreach("drafted")
        order.append("outreach")

    orch._outreach = SimpleNamespace(reach_out=outreach)
    workflow.dismiss_confirmation = lambda: order.append("dismiss")
    orch._attempt_application(
        SimpleNamespace(page=None), job, job_id, None, summary, WorkflowSettings()
    )
    assert order == ["outreach", "dismiss"]
    assert summary.applied == 1
    assert snapshots[-1].counts["applied"] == 1
    assert snapshots[-1].counts["hr_drafted"] == 1
    assert snapshots[-1].counts["hr_sent"] == 0
    assert max(snapshot.counts["applied"] for snapshot in snapshots) == 1


@pytest.mark.parametrize(
    ("status", "metric", "skipped"),
    [
        (ApplyStatus.DRY_RUN, "dry_runs", 1),
        (ApplyStatus.FAILED, "failed", 0),
        (ApplyStatus.UNCONFIRMED, "unconfirmed", 0),
        (ApplyStatus.ABORTED, "skipped", 1),
        (ApplyStatus.SKIPPED, "skipped", 1),
    ],
)
def test_application_outcomes_preserve_summary_semantics_without_claiming_sends(
    tmp_path, monkeypatch, status, metric, skipped
):
    orch, summary, job, job_id, _reporter, snapshots, _workflow = _application(
        tmp_path, monkeypatch, status
    )
    orch._attempt_application(
        SimpleNamespace(page=None), job, job_id, None, summary, WorkflowSettings()
    )
    assert snapshots[-1].counts[metric] == 1
    assert snapshots[-1].counts["skipped"] == summary.skipped == skipped
    assert snapshots[-1].counts["applied"] == summary.applied == 0
    assert snapshots[-1].counts["hr_sent"] == snapshots[-1].counts["connect_sent"] == 0


def test_application_exception_reports_a_single_failure(tmp_path, monkeypatch):
    orch, summary, job, job_id, _reporter, snapshots, workflow = _application(
        tmp_path, monkeypatch, ApplyStatus.SUBMITTED
    )

    def fail(**kwargs):
        raise RuntimeError("Fictional workflow error")

    workflow.apply = fail
    orch._attempt_application(
        SimpleNamespace(page=None), job, job_id, None, summary, WorkflowSettings()
    )
    assert snapshots[-1].counts["failed"] == summary.failed == 1
    assert snapshots[-1].counts["applied"] == 0
