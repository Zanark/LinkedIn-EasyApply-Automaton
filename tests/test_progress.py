"""Offline metrics protocol and authoritative application-outcome boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from linkedin_easy_apply.answers.resume_selector import ResumeChoice
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms.easy_apply import ApplyResult, ApplyStatus, WorkflowSettings
from linkedin_easy_apply.jobs import Job
from linkedin_easy_apply.orchestrator import Orchestrator, RunSummary
from linkedin_easy_apply.progress import (
    ACTIVITY_ENV,
    FRAME_END,
    FRAME_START,
    MAX_FRAME,
    PROGRESS_ENV,
    ActivitySnapshot,
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


@pytest.mark.parametrize("metrics", [False, True])
@pytest.mark.parametrize("activity", [False, True])
def test_activity_requires_its_own_gui_capability(monkeypatch, capsys, metrics, activity):
    monkeypatch.setenv(PROGRESS_ENV, "1" if metrics else "0")
    monkeypatch.setenv(ACTIVITY_ENV, "1" if activity else "0")
    reporter = gui_progress()
    if reporter is not None:
        reporter.start("scan")
        reporter.activity("checking_job")
    records = list(ProgressStream().feed(capsys.readouterr().err))
    assert sum(isinstance(record, ProgressSnapshot) for record in records) == int(metrics)
    assert sum(isinstance(record, ActivitySnapshot) for record in records) == int(
        metrics and activity
    )


def test_activity_and_counter_frames_interleave_at_every_split_without_leaking_paths():
    events = []
    reporter = ProgressReporter(activity_sink=events.append)
    reporter.activity(
        "preparing_application", resume_path=Path("private") / "Example_caf\u00e9.pdf"
    )
    reporter.activity("awaiting_input")
    assert [event.resume_name for event in events] == ["Example_caf\u00e9.pdf", None]
    snapshot = ProgressSnapshot(action="apply")
    frames = encode_progress(events[0]) + encode_progress(snapshot) + encode_progress(events[1])
    assert "private" not in frames
    for split in range(len(frames) + 1):
        stream = ProgressStream()
        records = [*stream.feed(frames[:split]), *stream.feed(frames[split:]), *stream.finish()]
        assert records == [events[0], snapshot, events[1]]


@pytest.mark.parametrize(
    "change",
    [
        {"version": 2.0},
        {"activity": "invented"},
        {"resume_name": "folder/example.pdf"},
        {"resume_name": "folder\\example.pdf"},
        {"resume_name": ".."},
        {"resume_name": ""},
        {"resume_name": "example\nresume.pdf"},
        {"resume_name": "example\u2028resume.pdf"},
        {"resume_name": "example\x7fresume.pdf"},
        {"resume_name": "x" * 513},
        {"answer": "Fictional private value"},
    ],
)
def test_bad_activity_is_redacted_and_does_not_discard_subsequent_counters(change):
    payload = ActivitySnapshot(activity="filling_application").model_dump() | change
    snapshot = ProgressSnapshot(action="apply")
    records = list(
        ProgressStream().feed(
            FRAME_START + json.dumps(payload) + FRAME_END + encode_progress(snapshot)
        )
    )
    assert isinstance(records[0], ProgressError)
    assert "Fictional private value" not in records[0].message
    assert records[1:] == [snapshot]
    omitted = list(
        ProgressStream().feed(FRAME_START + '{"version":2,"activity":"awaiting_input"}' + FRAME_END)
    )
    assert isinstance(omitted[0], ProgressError)


@pytest.mark.parametrize("invalid_metadata", [False, True])
def test_activity_failure_is_explicit_and_never_disables_counters(monkeypatch, invalid_metadata):
    from linkedin_easy_apply import progress

    warnings, snapshots, attempts = [], [], []
    monkeypatch.setattr(progress.logger, "warning", lambda *args: warnings.append(args))

    def broken_sink(snapshot):
        attempts.append(snapshot)
        raise OSError("Fictional stream unavailable")

    reporter = ProgressReporter(snapshots.append, activity_sink=broken_sink)
    reporter.activity(
        "preparing_application", resume_path=Path("bad\nresume.pdf") if invalid_metadata else None
    )
    reporter.activity("checking_job")
    reporter.start("apply")
    reporter.increment({"scanned": 1})
    assert len(warnings) == 1
    assert len(attempts) == (0 if invalid_metadata else 1)
    assert snapshots[-1].counts["scanned"] == 1
    assert "bad\nresume.pdf" not in str(warnings)


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


@pytest.mark.parametrize("tailored", [False, True])
@pytest.mark.parametrize("mode", ["apply", "scan"])
def test_only_final_application_resume_choices_change_the_display(
    tmp_path, monkeypatch, tailored, mode
):
    orch, summary, job, _job_id, _reporter, snapshots, workflow = _application(
        tmp_path, monkeypatch, ApplyStatus.DRY_RUN
    )
    activity = []
    reporter = ProgressReporter(snapshots.append, activity_sink=activity.append)
    reporter.start(mode)
    orch._progress = reporter
    orch._config.scoring.enforce = False
    static = ResumeChoice("Static display label", tmp_path / "Static_backend.pdf", "mapping")
    dynamic = ResumeChoice("Tailored display label", tmp_path / "Tailored_backend.pdf", "builder")
    monkeypatch.setattr(orch, "_pre_apply_checks", lambda _job: None)
    monkeypatch.setattr(orch._resume_selector, "select", lambda *a: static)
    monkeypatch.setattr(orch, "_pause_for_resume_review", lambda: None)
    monkeypatch.setattr(orch, "_advise", lambda *a: None)
    builds = []

    def build(_job):
        builds.append(_job)
        return dynamic if tailored else None

    monkeypatch.setattr(orch, "_tailor_resume", build)
    used = []
    workflow.apply = lambda **kwargs: used.append(kwargs) or ApplyResult(ApplyStatus.DRY_RUN)
    orch._process_job(
        SimpleNamespace(page=None), job, summary, mode, WorkflowSettings(dry_run=True), 1
    )
    filenames = [event.resume_name for event in activity if event.resume_name is not None]
    if mode == "scan":
        assert not filenames and not used and not builds
    else:
        expected = dynamic if tailored else static
        assert filenames == [expected.path.name]
        assert used[0]["resume_path"] == str(expected.path)
        activity.clear()
        orch._attempt_application(
            SimpleNamespace(page=None), job, _job_id, None, summary, WorkflowSettings(dry_run=True)
        )
        assert all(event.resume_name is None for event in activity)


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
