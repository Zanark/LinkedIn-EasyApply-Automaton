"""Tests for the *skip analytics* feature: the ``skips`` table + ``record_skip``
/ ``skip_events`` DB methods, the ``jobs_skipped_total`` stat, and the
orchestrator wiring that persists a per-job reason for every skip.
"""

from __future__ import annotations

import pytest

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.jobs.models import Job
from linkedin_easy_apply.orchestrator import Orchestrator, RunSummary


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "skips.db")
    database.initialize()
    return database


def _orchestrator(tmp_path) -> tuple[Orchestrator, Database]:
    config = AppConfig()
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
