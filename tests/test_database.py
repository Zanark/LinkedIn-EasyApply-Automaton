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


def test_submitted_applications_lists_only_submitted_newest_first(db: Database):
    run = db.start_run("apply")
    job1 = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/11/", "title": "BE", "company": "Acme"}, run
    )
    job2 = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/12/", "title": "FE", "company": "Globex"}, run
    )
    job3 = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/13/", "title": "SRE", "company": "Initech"}, run
    )
    resume = db.register_resume("FullStack", "generated/resume/FullStack.pdf")
    a1 = db.create_application(job1, run, resume, "submitted")
    db.create_application(job2, run, None, "failed")  # excluded — not submitted
    a3 = db.create_application(job3, run, resume, "submitted")

    apps = db.submitted_applications()
    # Newest-created first (started_at DESC with an id DESC tiebreak).
    assert [a["id"] for a in apps] == [a3, a1]
    assert all(a["status"] == "submitted" for a in apps)
    assert {a["company"] for a in apps} == {"Acme", "Initech"}
    assert apps[0]["title"] == "SRE"
    assert apps[0]["resume"] == "FullStack"
    assert apps[0]["url"].endswith("/13/")


def test_submitted_applications_respects_limit(db: Database):
    run = db.start_run("apply")
    for n in range(3):
        job = db.upsert_job(
            {"url": f"https://www.linkedin.com/jobs/view/2{n}/", "title": f"R{n}"}, run
        )
        db.create_application(job, run, None, "submitted")
    assert len(db.submitted_applications(limit=2)) == 2


def test_answers_for_applications_bulk_groups_by_app(db: Database):
    run = db.start_run("apply")
    job_a = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/31/", "title": "BE"}, run)
    job_b = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/32/", "title": "FE"}, run)
    job_c = db.upsert_job({"url": "https://www.linkedin.com/jobs/view/33/", "title": "SRE"}, run)
    a1 = db.create_application(job_a, run, None, "submitted")
    a2 = db.create_application(job_b, run, None, "submitted")
    a3 = db.create_application(job_c, run, None, "submitted")  # no answers recorded
    db.record_application_answer(a1, "Years of Python?", "5", "yaml")
    db.record_application_answer(a1, "Authorised to work?", "Yes", "manual")
    db.record_application_answer(a2, "Notice period?", "30 days", "yaml")

    grouped = db.answers_for_applications([a1, a2, a3])
    assert set(grouped) == {a1, a2, a3}
    # Insertion order preserved within each application.
    assert [r["question_text"] for r in grouped[a1]] == [
        "Years of Python?",
        "Authorised to work?",
    ]
    assert grouped[a1][0]["value"] == "5"
    assert grouped[a1][0]["source"] == "yaml"
    assert [r["question_text"] for r in grouped[a2]] == ["Notice period?"]
    assert grouped[a3] == []  # an id with no answers maps to an empty list


def test_answers_for_applications_empty_input(db: Database):
    assert db.answers_for_applications([]) == {}


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


def test_initialize_migrates_missing_note_column(tmp_path):
    """A DB created before the ``note`` column existed gains it on initialize()."""
    import sqlite3

    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE outreach_messages ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, job_id INTEGER,"
        " person_name TEXT, person_key TEXT NOT NULL, profile_url TEXT, message TEXT,"
        " status TEXT NOT NULL DEFAULT 'sent',"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    db.initialize()  # must ALTER TABLE ADD COLUMN note
    columns = {row["name"] for row in db.query("PRAGMA table_info(outreach_messages)")}
    assert "note" in columns

    # The migration is idempotent and the new column round-trips.
    db.initialize()
    db.record_outreach(person_key="in/x", message="full", note="short note", status="drafted")
    [draft] = db.outreach_drafts()
    assert draft["note"] == "short note"
