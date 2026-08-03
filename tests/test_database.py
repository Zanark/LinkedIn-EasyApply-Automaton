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


def test_application_answers_records_and_reads_in_order(db: Database):
    run_id = db.start_run("apply")
    job_id = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/7/", "title": "BE"}, run_id)
    app_id = db.create_application(job_id, run_id, None, "submitted")
    db.record_application_answer(app_id, "Years of Python experience?", "5", "yaml")
    db.record_application_answer(app_id, "Are you authorised to work?", "Yes", "manual")

    rows = db.application_answers(app_id)
    assert [r["question_text"] for r in rows] == [
        "Years of Python experience?",
        "Are you authorised to work?",
    ]
    assert rows[0]["value"] == "5"
    assert rows[0]["source"] == "yaml"
    assert rows[1]["value"] == "Yes"
    # A different application shares nothing.
    assert db.application_answers(app_id + 999) == []


def test_unanswered_questions_reports_only_true_gaps(db: Database):
    run_id = db.start_run("apply")
    job_id = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/50/", "title": "BE"}, run_id)
    # App 1 (failed): one genuinely-unanswered question + one answered.
    app1 = db.create_application(job_id, run_id, None, "failed")
    db.update_application(app1, status="failed", reason="No progress between steps", steps=2)
    pf_qid = db.upsert_question("Do you have a PF account?", "do you have a pf account", "unknown")
    db.record_application_answer(app1, "Do you have a PF account?", None, "unanswered", pf_qid)
    db.record_application_answer(app1, "Years of Java?", "6", "yaml")

    # A question blank in one app but ANSWERED in another must NOT be a gap.
    run2 = db.start_run("apply")
    app2 = db.create_application(job_id, run2, None, "submitted")
    notice_qid = db.upsert_question("Notice period?", "notice period", "notice_period")
    db.record_application_answer(app2, "Notice period?", None, "unanswered", notice_qid)
    run3 = db.start_run("apply")
    app3 = db.create_application(job_id, run3, None, "submitted")
    db.record_application_answer(app3, "Notice period?", "30 days", "yaml", notice_qid)

    gaps = db.unanswered_questions()
    questions = {g["question"] for g in gaps}
    assert "Do you have a PF account?" in questions  # never answered -> gap
    assert "Years of Java?" not in questions  # had a value -> not a gap
    assert "Notice period?" not in questions  # answered in app3 -> not a gap

    pf = next(g for g in gaps if g["question"] == "Do you have a PF account?")
    assert pf["blank_in_apps"] == 1
    assert pf["blocked_apps"] == 1  # app1 was 'failed'
    assert pf["category"] == "unknown"


def test_blocked_applications_trims_reason_and_counts_unanswered(db: Database):
    run_id = db.start_run("apply")
    job_id = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/51/", "title": "SRE", "company": "Globex"},
        run_id,
    )
    app = db.create_application(job_id, run_id, None, "failed")
    huge_reason = "Locator.click: Timeout 30000ms exceeded.\n" + "x" * 5000
    db.update_application(app, status="failed", reason=huge_reason, steps=3)
    db.record_application_answer(app, "Comfortable with night shift?", None, "unanswered")
    db.record_application_answer(app, "Email address", "a@b.com", "prefilled")

    # A submitted application must never appear here.
    run2 = db.start_run("apply")
    ok_app = db.create_application(job_id, run2, None, "submitted")
    db.update_application(ok_app, status="submitted", steps=4)

    blocked = db.blocked_applications()
    assert len(blocked) == 1
    row = blocked[0]
    assert row["company"] == "Globex"
    assert row["status"] == "failed"
    # The 5 KB Playwright log is trimmed to its first line.
    assert row["reason_short"] == "Locator.click: Timeout 30000ms exceeded."
    assert len(row["reason_short"]) <= 201
    assert row["unanswered_count"] == 1  # only the blank question, not the prefilled one


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
