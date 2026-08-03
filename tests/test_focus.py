"""Tests for the clickable-KPI-card drill-downs (``dashboard/focus.py``): the
per-category ``build_focus_view`` query/aggregation logic behind each header card.
"""

from __future__ import annotations

import pytest

from linkedin_easy_apply.dashboard.focus import FOCUS_CATEGORIES, build_focus_view
from linkedin_easy_apply.database.db import Database


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "focus.db")
    database.initialize()
    return database


def _seed(db: Database) -> None:
    run_id = db.start_run("apply")
    a = db.upsert_job(
        {
            "url": "https://www.linkedin.com/jobs/view/1/",
            "title": "SWE",
            "company": "Acme",
            "workplace_type": "remote",
            "experience_level": "Mid-Senior",
            "easy_apply": True,
        },
        run_id,
    )
    b = db.upsert_job(
        {
            "url": "https://www.linkedin.com/jobs/view/2/",
            "title": "Dev",
            "company": "Beta",
            "workplace_type": "hybrid",
            "easy_apply": True,
        },
        run_id,
    )
    c = db.upsert_job(
        {"url": "https://www.linkedin.com/jobs/view/3/", "title": "QA", "company": "Acme"},
        run_id,
    )
    d = db.upsert_job(
        {
            "url": "https://www.linkedin.com/jobs/view/4/",
            "title": "SRE",
            "company": "Gamma",
            "easy_apply": True,
        },
        run_id,
    )
    resume = db.register_resume("res_fullstack", "/tmp/res.pdf")

    db.create_application(a, run_id, resume, "submitted")  # submitted today
    app_b = db.create_application(b, run_id, resume, "submitted")  # submitted, older
    app_d = db.create_application(d, run_id, None, "failed")
    with db.connect() as conn:
        conn.execute(
            "UPDATE applications SET started_at=? WHERE id=?", ("2026-07-01T10:00:00", app_b)
        )
        conn.execute(
            "UPDATE applications SET reason=? WHERE id=?",
            ("No progress between steps", app_d),
        )
    db.record_skip(run_id, c, "below_threshold")


def test_categories_cover_the_five_cards():
    assert set(FOCUS_CATEGORIES) == {"today", "submitted", "failed", "skipped", "discovered"}


def test_unknown_category_returns_none(db: Database):
    assert build_focus_view(db, "nope") is None


def test_submitted_lists_submitted_only(db: Database):
    _seed(db)
    view = build_focus_view(db, "submitted")
    assert view is not None and view.key == "submitted"
    companies = {r["Company"] for r in view.rows}
    assert {"Acme", "Beta"} <= companies
    assert "Gamma" not in companies  # failed job excluded
    titles = {c.title for c in view.charts}
    assert {"Submitted per day", "Top companies", "By workplace type"} <= titles


def test_today_only_todays_submissions(db: Database):
    _seed(db)
    view = build_focus_view(db, "today")
    assert view is not None
    companies = [r["Company"] for r in view.rows]
    assert "Acme" in companies  # submitted today
    assert "Beta" not in companies  # submitted on an older date


def test_failed_view_surfaces_reason(db: Database):
    _seed(db)
    view = build_focus_view(db, "failed")
    assert view is not None
    assert any(r["Company"] == "Gamma" for r in view.rows)
    reasons = next(c for c in view.charts if c.title == "Top failure reasons")
    assert any("No progress" in str(row["name"]) for row in reasons.rows)


def test_discovered_counts_all_jobs_and_apply_split(db: Database):
    _seed(db)
    view = build_focus_view(db, "discovered")
    assert view is not None
    assert len(view.rows) == 4
    ea = next(c for c in view.charts if c.title == "Easy Apply vs external")
    split = {row["name"]: row["count"] for row in ea.rows}
    assert split.get("Easy Apply") == 3
    assert split.get("External") == 1


def test_skipped_view_reads_skips(db: Database):
    _seed(db)
    view = build_focus_view(db, "skipped")
    assert view is not None
    assert any(r["Reason"] == "below_threshold" for r in view.rows)
    reason_chart = next(c for c in view.charts if c.title == "Why jobs were skipped")
    assert reason_chart.rows[0]["name"] == "below_threshold"


def test_every_chart_row_has_declared_axes(db: Database):
    _seed(db)
    for category in FOCUS_CATEGORIES:
        view = build_focus_view(db, category)
        assert view is not None
        for chart in view.charts:
            assert chart.kind in {"bar", "line"}
            for row in chart.rows:
                assert chart.x in row and chart.y in row
