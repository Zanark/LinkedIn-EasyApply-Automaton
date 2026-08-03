"""Tests for approved answer overrides: DB layer, comparison queries, and the
resolver precedence that makes an approved override win at fill time.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.forms.easy_apply import EasyApplyWorkflow
from linkedin_easy_apply.parser.categories import AnswerType


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "sync.db")
    database.initialize()
    return database


# -- override CRUD ----------------------------------------------------------- #
def test_override_set_get_delete(db: Database):
    assert db.get_answer_override("total experience") is None
    db.set_answer_override("total experience", "6", note="approved via test")
    assert db.get_answer_override("total experience") == "6"

    # Upsert on the normalized key updates in place.
    db.set_answer_override("total experience", "7")
    assert db.get_answer_override("total experience") == "7"

    db.delete_answer_override("total experience")
    assert db.get_answer_override("total experience") is None


def test_answer_overrides_listing(db: Database):
    db.set_answer_override("q one", "A")
    db.set_answer_override("q two", "B")
    overrides = db.answer_overrides()
    assert {o["normalized"] for o in overrides} == {"q one", "q two"}
    assert {o["value"] for o in overrides} == {"A", "B"}


# -- comparison / history queries -------------------------------------------- #
def _seed_application(db: Database) -> int:
    run_id = db.start_run("apply")
    job_id = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/99/", "title": "SWE", "company": "Acme"},
        run_id,
    )
    return db.create_application(job_id, run_id, resume_id=None, status="submitted")


def test_answer_comparison_reports_latest_and_override(db: Database):
    app_id = _seed_application(db)
    qid = db.upsert_question(
        "What is your total experience?", "total experience", "experience_total", None, "number"
    )
    db.record_application_answer(app_id, "What is your total experience?", "3", "yaml", qid)

    rows = db.answer_comparison()
    assert len(rows) == 1
    row = rows[0]
    assert row["normalized"] == "total experience"
    assert row["latest_value"] == "3"
    assert row["apps"] == 1
    assert row["override_value"] is None

    # After approving, the same query surfaces the override joined by normalized.
    db.set_answer_override("total experience", "6", question_id=qid)
    row = db.answer_comparison()[0]
    assert row["override_value"] == "6"


def test_answer_comparison_uses_most_recent_value(db: Database):
    app_id = _seed_application(db)
    qid = db.upsert_question("Notice period?", "notice period", "notice_period", None, "number")
    db.record_application_answer(app_id, "Notice period?", "90", "yaml", qid)
    db.record_application_answer(app_id, "Notice period?", "45", "manual", qid)
    row = db.answer_comparison()[0]
    assert row["latest_value"] == "45"


def test_answered_history_skips_blanks(db: Database):
    app_id = _seed_application(db)
    qid = db.upsert_question("Total exp?", "total exp", "experience_total", None, "number")
    db.record_application_answer(app_id, "Total exp?", "3", "yaml", qid)
    db.record_application_answer(app_id, "Total exp?", "", "unanswered", qid)
    history = db.answered_history()
    assert len(history) == 1
    assert history[0]["value"] == "3"
    assert history[0]["category"] == "experience_total"
    assert history[0]["day"]  # date(started_at) is populated


# -- resolver precedence ----------------------------------------------------- #
def _parsed(normalized: str, answer_type: AnswerType = AnswerType.NUMBER):
    return SimpleNamespace(normalized=normalized, answer_type=answer_type)


def test_override_resolution_number():
    me = SimpleNamespace(_override_lookup=lambda n: "6" if n == "total exp" else None)
    res = EasyApplyWorkflow._override_resolution(me, _parsed("total exp"))
    assert res is not None
    assert res.found and res.value == "6" and res.source == "approved"
    assert res.answer_type is AnswerType.NUMBER


def test_override_resolution_yes_maps_to_bool():
    me = SimpleNamespace(_override_lookup=lambda n: "Yes")
    res = EasyApplyWorkflow._override_resolution(me, _parsed("have python", AnswerType.BOOLEAN))
    assert res.value == "Yes" and res.bool_value is True
    assert res.answer_type is AnswerType.BOOLEAN


def test_override_resolution_no_maps_to_bool():
    me = SimpleNamespace(_override_lookup=lambda n: "no")
    res = EasyApplyWorkflow._override_resolution(me, _parsed("relocate", AnswerType.BOOLEAN))
    assert res.value == "No" and res.bool_value is False


def test_override_resolution_absent_returns_none():
    me = SimpleNamespace(_override_lookup=lambda n: None)
    assert EasyApplyWorkflow._override_resolution(me, _parsed("anything")) is None


def test_override_resolution_no_lookup_returns_none():
    me = SimpleNamespace(_override_lookup=None)
    assert EasyApplyWorkflow._override_resolution(me, _parsed("anything")) is None
