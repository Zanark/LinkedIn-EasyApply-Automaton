"""Tests for the *skip analytics* feature: the ``skips`` table + ``record_skip``
/ ``skip_events`` DB methods, the ``jobs_skipped_total`` stat, and the
orchestrator wiring that persists a per-job reason for every skip.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.forms.easy_apply import ApplyResult, ApplyStatus
from linkedin_easy_apply.jobs.models import Job
from linkedin_easy_apply.orchestrator import Orchestrator, RunSummary


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "skips.db")
    database.initialize()
    return database


def _orchestrator(tmp_path) -> tuple[Orchestrator, Database]:
    config = AppConfig()
    config.scoring.threshold = 30
    config.screenshots.directory = tmp_path / "shots"
    config.database.path = tmp_path / "orch.db"
    database = Database(config.database.path)
    database.initialize()
    return Orchestrator(config, database, AnswerStore({})), database


# -- record_skip / skip_events ---------------------------------------------- #
def test_record_skip_persists_reason_and_join(db: Database):
    run_id = db.start_run("apply")
    job_id = db.upsert_job(
        {
            "url": "https://www.linkedin.com/jobs/view/1/",
            "title": "SWE",
            "company": "Acme",
            "workplace_type": "remote",
            "experience_level": "Mid-Senior",
        },
        run_id,
    )
    db.record_skip(run_id, job_id, "below_threshold")

    events = db.skip_events()
    assert len(events) == 1
    row = events[0]
    assert row["reason"] == "below_threshold"
    assert row["title"] == "SWE"
    assert row["company"] == "Acme"
    assert row["workplace_type"] == "remote"
    assert row["experience_level"] == "Mid-Senior"
    assert row["url"] == "https://www.linkedin.com/jobs/view/1/"


def test_record_skip_allows_null_job(db: Database):
    run_id = db.start_run("apply")
    db.record_skip(run_id, None, "reapply_open_failed")
    events = db.skip_events()
    assert len(events) == 1
    assert events[0]["reason"] == "reapply_open_failed"
    assert events[0]["title"] is None  # LEFT JOIN yields NULLs when there's no job


def test_skip_events_newest_first(db: Database):
    run_id = db.start_run("apply")
    job_id = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/2/", "title": "A"}, run_id)
    db.record_skip(run_id, job_id, "scan_only")
    db.record_skip(run_id, job_id, "below_threshold")
    reasons = [e["reason"] for e in db.skip_events()]
    # Same-second timestamps: the id DESC tiebreak keeps the latest insert first.
    assert reasons[0] == "below_threshold"


def test_skip_events_respects_limit(db: Database):
    run_id = db.start_run("apply")
    job_id = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/3/", "title": "A"}, run_id)
    for _ in range(5):
        db.record_skip(run_id, job_id, "scan_only")
    assert len(db.skip_events(limit=3)) == 3


# -- stats().jobs_skipped_total --------------------------------------------- #
def test_stats_reports_skipped_total_from_runs(db: Database):
    run_id = db.start_run("apply")
    db.finish_run(run_id, "completed", scanned=10, applied=2, skipped=7, failed=1)
    run2 = db.start_run("apply")
    db.finish_run(run2, "completed", scanned=4, applied=1, skipped=3, failed=0)
    assert db.stats()["jobs_skipped_total"] == 10


def test_stats_skipped_total_zero_without_runs(db: Database):
    assert db.stats()["jobs_skipped_total"] == 0


# -- orchestrator._note_skip ------------------------------------------------- #
def test_note_skip_counts_and_persists(tmp_path):
    orch, database = _orchestrator(tmp_path)
    run_id = database.start_run("apply")
    job_id = database.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/9/", "title": "X"}, run_id
    )
    summary = RunSummary(run_id=run_id, mode="apply")

    orch._note_skip(summary, "below_threshold", job_id)

    assert summary.skipped == 1
    assert summary.skip_reasons == {"below_threshold": 1}
    events = database.skip_events()
    assert len(events) == 1 and events[0]["reason"] == "below_threshold"


def test_note_skip_tolerates_missing_job(tmp_path):
    orch, database = _orchestrator(tmp_path)
    run_id = database.start_run("apply")
    summary = RunSummary(run_id=run_id, mode="reapply")

    orch._note_skip(summary, "reapply_open_failed")

    assert summary.skipped == 1
    assert database.skip_events()[0]["reason"] == "reapply_open_failed"


# -- orchestrator._process_job gates persist the reason ---------------------- #
def test_process_job_gate_records_skip(tmp_path):
    """A pre-apply gate (here: a blacklisted company) must write a skip row."""
    orch, database = _orchestrator(tmp_path)
    orch._config.jobs.blacklist_companies = ["acme"]
    run_id = database.start_run("apply")
    summary = RunSummary(run_id=run_id, mode="apply")
    job = Job(
        url="https://www.linkedin.com/jobs/view/7/",
        title="SWE",
        company="Acme",
        easy_apply=True,
    )

    orch._process_job(browser=None, job=job, summary=summary, mode="apply", settings=None, max_per_run=10)  # type: ignore[arg-type]

    assert summary.skip_reasons == {"blacklisted": 1}
    events = database.skip_events()
    assert len(events) == 1
    assert events[0]["reason"] == "blacklisted"
    assert events[0]["company"] == "Acme"


def test_skip_snapshot_survives_job_changes_and_deletion(db: Database):
    run = db.start_run("scan")
    original = {
        "url": "https://example.invalid/jobs/recorded",
        "title": "Fictional original role",
        "company": "Fictional Original Company",
        "location": "Fictional Remote Region",
        "description": "Original description, including the deciding keyword.",
        "search_name": "fictional-search",
    }
    job = db.upsert_job(original, run)
    score = {"score": 12, "threshold": 30, "breakdown": {"fictional": 12}}
    identifier = db.record_skip(run, job, "below_threshold", score=score, detail="12 < 30.")
    score["score"] = 99
    db.upsert_job({**original, "title": "Later role", "description": None}, run)
    db.record_score(job, 99, 10, True, {"later": 99})
    for remove in (False, True):
        if remove:
            with db.connect() as conn:
                conn.execute("DELETE FROM jobs WHERE id=?", (job,))
        event = db.skip_events()[0]
        assert event["id"] == identifier and event["captured"] is True
        assert all(event[key] == value for key, value in original.items())
        assert (event["score"], event["threshold"], event["detail"]) == (12, 30, "12 < 30.")
        assert event["score_breakdown"] == {"fictional": 12}
        assert event["run_mode"] == "scan"
        assert event["job_id"] == (None if remove else job)
    assert db.query("SELECT * FROM applications") == []


def test_explicit_observed_job_keeps_unknown_fields_unknown(db: Database):
    run = db.start_run("apply")
    url = "https://example.invalid/jobs/observed"
    job = db.upsert_job({"url": url, "title": "Other run", "location": "Other location"}, run)
    db.record_skip(
        run,
        job,
        "not_easy_apply",
        job={"url": url, "title": "Observed title", "location": None},
    )
    event = db.skip_events()[0]
    assert event["title"] == "Observed title" and event["location"] is None


def test_existing_database_migration_preserves_legacy_events(db: Database):
    run = db.start_run("apply")
    job = db.upsert_job({"url": "https://example.invalid/jobs/legacy", "title": "Before"}, run)
    with db.connect() as conn:
        conn.execute("DROP TABLE skips")
        conn.execute("""CREATE TABLE skips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER REFERENCES runs(id) ON DELETE SET NULL,
                job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
                reason TEXT NOT NULL, created_at TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO skips (run_id, job_id, reason, created_at) VALUES (?, ?, ?, ?)",
            (run, job, "historical_reason", "2020-01-02T03:04:05"),
        )
    db.initialize()
    db.initialize()
    db.upsert_job({"url": "https://example.invalid/jobs/legacy", "title": "Current record"}, run)
    db.record_score(job, 90, 10, True, {"later": 90})
    event = db.skip_events()[0]
    assert (event["id"], event["reason"], event["created_at"]) == (
        1,
        "historical_reason",
        "2020-01-02T03:04:05",
    )
    assert event["captured"] is False and event["title"] == "Current record"
    assert event["score"] is event["threshold"] is event["score_breakdown"] is None
    assert event["detail"] is None
    db.record_skip(run, job, "scan_only")
    assert db.skip_events()[0]["captured"] is True
    assert db.skip_events()[1] == event


def test_complete_skip_history_keeps_repeated_and_missing_jobs(db: Database):
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO skips (reason, created_at) VALUES (?, ?)",
            [("below_threshold", "2020-01-01T00:00:00")] * 5001,
        )
    assert len(db.skip_events()) == 5000
    events = db.skip_events(limit=None)
    assert len(events) == 5001 and len({event["id"] for event in events}) == 5001
    assert events[0]["id"] == 5001 and events[-1]["id"] == 1
    assert all(event["job_id"] is None and event["title"] is None for event in events)


@pytest.mark.parametrize(
    ("mode", "enforce", "exclude", "expected"),
    [
        ("apply", True, [], "below_threshold"),
        ("scan", False, [], "scan_only"),
        ("apply", False, ["fictional-marker"], "excluded_keyword"),
    ],
)
def test_process_job_preserves_decision_score_and_explanation(
    tmp_path,
    monkeypatch,
    mode,
    enforce,
    exclude,
    expected,
):
    orch, database = _orchestrator(tmp_path)
    monkeypatch.setattr(
        orch,
        "_attempt_application",
        lambda *args, **kwargs: pytest.fail("This fixture must not start an application."),
    )
    orch._config.scoring.enforce = enforce
    orch._config.jobs.exclude_keywords = exclude
    job = Job(
        url="https://example.invalid/jobs/decision",
        title="Fictional role",
        company="Fictional Company",
        description="A fictional-marker in the original job description.",
        location="Fictional Region",
        search_name="fictional-search",
        easy_apply=True,
    )
    run = database.start_run(mode)
    summary = RunSummary(run_id=run, mode=mode)
    expected_score = orch._scoring.score(job.title or "", job.description)
    orch._process_job(None, job, summary, mode, None, 10)  # type: ignore[arg-type]
    event = database.skip_events()[0]
    assert event["reason"] == expected
    assert event["score"] == expected_score.score
    assert event["threshold"] == expected_score.threshold
    assert event["score_breakdown"] == expected_score.breakdown
    assert event["location"] == job.location and event["search_name"] == job.search_name
    assert event["detail"]
    if exclude:
        assert "fictional-marker" in event["detail"]
    assert summary.skipped == 1 and summary.skip_reasons == {expected: 1}
    assert database.query("SELECT * FROM applications") == []


def test_form_skip_keeps_actual_reason_and_pipeline_score(tmp_path, monkeypatch):
    orch, database = _orchestrator(tmp_path)
    orch._config.scoring.enforce = False
    monkeypatch.setattr(orch._resume_selector, "select", lambda *args: None)
    monkeypatch.setattr(orch, "_tailor_resume", lambda *args: None)
    monkeypatch.setattr(orch, "_maybe_cover_letter", lambda *args: None)
    workflow = MagicMock()
    workflow.apply.return_value = ApplyResult(
        ApplyStatus.SKIPPED, reason="Unsupported fictional document step.", steps=3
    )
    monkeypatch.setattr(
        "linkedin_easy_apply.orchestrator.EasyApplyWorkflow", lambda *args, **kwargs: workflow
    )
    job = Job(url="https://example.invalid/jobs/form", title="Fictional form role", easy_apply=True)
    run = database.start_run("apply")
    summary = RunSummary(run_id=run, mode="apply")
    orch._process_job(MagicMock(), job, summary, "apply", MagicMock(), 10)
    event = database.skip_events()[0]
    assert event["reason"] == "skipped"
    assert event["detail"] == "Unsupported fictional document step."
    assert event["score"] == orch._scoring.score(job.title or "", job.description).score
    assert summary.skipped == 1 and summary.applied == summary.failed == 0


def test_failed_target_retains_url_without_a_job_record(tmp_path, monkeypatch):
    orch, database = _orchestrator(tmp_path)
    search = MagicMock()
    search.open_job.return_value = None
    monkeypatch.setattr("linkedin_easy_apply.orchestrator.JobSearch", lambda *args: search)
    target = {"url": "https://example.invalid/jobs/unopened", "title": "Fictional unopened role"}
    run = database.start_run("apply")
    summary = RunSummary(run_id=run, mode="apply")
    orch._execute_reapply(
        browser=MagicMock(),
        targets=[target],
        summary=summary,
        dry_run=True,
        interactive=False,
        max_per_run=10,
    )
    event = database.skip_events()[0]
    assert event["job_id"] is None and event["captured"] is True
    assert event["url"] == target["url"] and event["title"] == target["title"]
    assert event["detail"] == "Could not open the target job page during this targeted run."
    assert database.query("SELECT * FROM applications") == []
