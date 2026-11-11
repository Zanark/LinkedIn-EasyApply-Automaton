"""Tests for orchestrator improvements that don't require a browser."""

from __future__ import annotations

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.orchestrator import Orchestrator


def _orchestrator(tmp_path) -> tuple[Orchestrator, Database]:
    config = AppConfig()
    config.screenshots.directory = tmp_path / "shots"
    config.database.path = tmp_path / "test.db"
    db = Database(config.database.path)
    db.initialize()
    orch = Orchestrator(config, db, AnswerStore({}))
    return orch, db


def test_cleanup_removes_orphans_keeps_referenced(tmp_path):
    orch, db = _orchestrator(tmp_path)
    shots = tmp_path / "shots"
    kept = shots / "after-submit-keep.png"
    orphan_a = shots / "step-1-orphan.png"
    orphan_b = shots / "unknown-orphan.png"
    for path in (kept, orphan_a, orphan_b):
        path.write_bytes(b"x")

    run_id = db.start_run("apply")
    job_id = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/9/", "title": "X"}, run_id)
    app_id = db.create_application(job_id, run_id, None)
    db.update_application(app_id, status="submitted", screenshot=str(kept), finished=True)

    orch._cleanup_screenshots()

    assert kept.exists()
    assert not orphan_a.exists()
    assert not orphan_b.exists()


def test_cleanup_disabled_keeps_everything(tmp_path):
    orch, _db = _orchestrator(tmp_path)
    orch._config.screenshots.cleanup = False
    shots = tmp_path / "shots"
    orphan = shots / "step-1.png"
    orphan.write_bytes(b"x")

    orch._cleanup_screenshots()

    assert orphan.exists()
