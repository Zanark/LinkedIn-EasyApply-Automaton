from __future__ import annotations

import pytest

from linkedin_easy_apply.database.db import Database


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "test.db")
    database.initialize()
    return database


def test_upsert_job_insert_then_update(db: Database):
    run_id = db.start_run("apply", ["backend"])
    job = {
        "url": "https://www.linkedin.com/jobs/view/1/",
        "title": "Backend Engineer",
        "company": "Acme",
        "easy_apply": True,
    }
    job_id = db.upsert_job(job, run_id)
    assert isinstance(job_id, int)

    # Same URL updates in place, returns the same id.
    job["title"] = "Senior Backend Engineer"
    assert db.upsert_job(job, run_id) == job_id
    stored = db.get_job_by_url(job["url"])
    assert stored is not None
    assert stored["title"] == "Senior Backend Engineer"
    assert stored["easy_apply"] == 1


def test_dedup_and_counts(db: Database):
    run_id = db.start_run("apply")
    url = "https://www.linkedin.com/jobs/view/2/"
    job_id = db.upsert_job({"url": url, "title": "SRE", "company": "Globex"}, run_id)

    assert db.has_applied_to_url(url) is False

    app_id = db.create_application(job_id, run_id, resume_id=None, status="pending")
    db.update_application(app_id, status="submitted", steps=3, finished=True)

    assert db.has_applied_to_url(url) is True
    assert db.has_applied_to_company_role("globex", "sre") is True
    assert db.count_applications_today() == 1
    assert db.count_applications_for_company("Globex") == 1


def test_scores_and_ai_results(db: Database):
    run_id = db.start_run("scan")
    job_id = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/3/", "title": "X"}, run_id)
    db.record_score(job_id, 50, 30, True, {"backend": 30, "java": 20})
    db.record_ai_result(
        job_id,
        {
            "match_percent": 82,
            "missing_skills": ["Go"],
            "recommendation": "apply",
            "should_apply": True,
        },
    )
    scores = db.query("SELECT * FROM scores WHERE job_id=?", (job_id,))
    assert scores[0]["score"] == 50
    ai = db.query("SELECT * FROM ai_results WHERE job_id=?", (job_id,))
    assert ai[0]["match_percent"] == 82
    assert ai[0]["should_apply"] == 1


def test_questions_learn_and_recall(db: Database):
    qid = db.upsert_question(
        "What is your notice period?", "what is your notice period", "notice_period", None, "text"
    )
    assert db.get_known_answer("what is your notice period") is None
    db.learn_answer(qid, "30 days", source="manual")
    assert db.get_known_answer("what is your notice period") == "30 days"

    # Re-learning updates the value (ON CONFLICT).
    db.learn_answer(qid, "60 days")
    assert db.get_known_answer("what is your notice period") == "60 days"

    # Seen count increments on re-upsert of same normalized text.
    db.upsert_question("Notice period?", "what is your notice period")
    rows = db.query(
        "SELECT seen_count FROM questions WHERE normalized=?", ("what is your notice period",)
    )
    assert rows[0]["seen_count"] == 2


def test_stats(db: Database):
    run_id = db.start_run("apply")
    job_id = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/4/", "company": "Acme", "easy_apply": True},
        run_id,
    )
    app_id = db.create_application(job_id, run_id, None)
    db.update_application(app_id, status="submitted", finished=True)
    db.log_error("boom", context="test")

    stats = db.stats()
    assert stats["total_jobs"] == 1
    assert stats["easy_apply_jobs"] == 1
    assert stats["applications_submitted"] == 1
    assert stats["errors"] == 1
    assert any(c["company"] == "Acme" for c in stats["top_companies"])
