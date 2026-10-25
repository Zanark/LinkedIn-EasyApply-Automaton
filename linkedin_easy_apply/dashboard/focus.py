"""Data behind the dashboard's clickable KPI cards.

Each headline KPI (applications today, total submitted, failed, skipped, jobs
discovered) is a *card*; clicking it opens a drill-down that lists the records in
that category plus category-specific charts. The pure query/aggregation logic
lives here (no Streamlit imports) so it can be unit tested; ``app.py`` only turns
the returned :class:`FocusView` into widgets.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from linkedin_easy_apply.database import Database

# Category buckets a breakdown falls back to when the underlying field was never
# captured (the COALESCE defaults in the queries below, and the fillna in
# app.py). A chart whose *every* bucket is one of these conveys nothing — e.g.
# "By experience level" when no job ever recorded one — so the dashboard skips it.
_PLACEHOLDER_CATEGORIES = frozenset({"unknown", "?", "(none)", "n/a", "na", "none", ""})


def has_real_categories(labels: Iterable[Any]) -> bool:
    """True if *labels* has at least one real (non-placeholder) category.

    Used to hide breakdown charts that would only show a single ``unknown`` bar
    because the underlying field (workplace type, experience level, …) was never
    populated.
    """
    return any(str(label).strip().lower() not in _PLACEHOLDER_CATEGORIES for label in labels)


# The five KPI cards, in header order: key -> (card label, one-line description).
FOCUS_CATEGORIES: dict[str, tuple[str, str]] = {
    "today": ("Applications today", "Applications you submitted today."),
    "submitted": ("Total submitted", "Every application that was successfully submitted."),
    "failed": ("Failed", "Applications whose Easy Apply run failed."),
    "skipped": ("Skipped", "Jobs the pipeline chose not to apply to, and why."),
    "discovered": ("Jobs discovered", "Every job the crawler has catalogued."),
}


@dataclass(slots=True)
class FocusChart:
    """One chart: ``rows`` are records with an ``x`` (index) and ``y`` (value) key."""

    title: str
    rows: list[dict[str, Any]]
    x: str
    y: str
    kind: str = "bar"  # 'bar' | 'line'
    caption: str = ""


@dataclass(slots=True)
class FocusView:
    """Everything needed to render one category's drill-down."""

    key: str
    title: str
    subtitle: str
    rows: list[dict[str, Any]]
    charts: list[FocusChart] = field(default_factory=list)
    note: str = ""


def build_focus_view(db: Database, category: str) -> FocusView | None:
    """Assemble the drill-down (table + charts) for one KPI category.

    Returns ``None`` for an unknown category so the caller can no-op.
    """
    builder = _BUILDERS.get(category)
    if builder is None:
        return None
    return builder(db)


# --------------------------------------------------------------------------- #
# Per-category builders
# --------------------------------------------------------------------------- #
def _today(db: Database) -> FocusView:
    rows = db.query("""SELECT a.started_at AS "When", j.title AS Title, j.company AS Company,
                  r.name AS "Résumé", j.url AS url
           FROM applications a JOIN jobs j ON a.job_id = j.id
           LEFT JOIN resumes r ON a.resume_id = r.id
           WHERE a.status='submitted' AND date(a.started_at)=date('now','localtime')
           ORDER BY a.started_at DESC""")
    charts = [
        FocusChart(
            "Submitted per day (last 14 days)",
            db.query("""SELECT date(started_at) AS day, COUNT(*) AS count
                   FROM applications
                   WHERE status='submitted'
                     AND date(started_at) >= date('now','localtime','-13 days')
                   GROUP BY day ORDER BY day"""),
            "day",
            "count",
            kind="line",
            caption="Today in context of the past two weeks.",
        ),
        FocusChart(
            "Top companies today",
            db.query("""SELECT j.company AS name, COUNT(*) AS count
                   FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE a.status='submitted'
                     AND date(a.started_at)=date('now','localtime')
                     AND j.company IS NOT NULL
                   GROUP BY lower(j.company) ORDER BY count DESC LIMIT 12"""),
            "name",
            "count",
        ),
        FocusChart(
            "Résumé used today",
            db.query("""SELECT COALESCE(r.name,'(none)') AS name, COUNT(*) AS count
                   FROM applications a LEFT JOIN resumes r ON a.resume_id=r.id
                   WHERE a.status='submitted'
                     AND date(a.started_at)=date('now','localtime')
                   GROUP BY name ORDER BY count DESC"""),
            "name",
            "count",
        ),
    ]
    return FocusView("today", "Applications submitted today", _count(rows), rows, charts)


def _submitted(db: Database) -> FocusView:
    rows = db.query("""SELECT a.started_at AS "When", j.title AS Title, j.company AS Company,
                  r.name AS "Résumé", a.steps AS Steps, j.url AS url
           FROM applications a JOIN jobs j ON a.job_id = j.id
           LEFT JOIN resumes r ON a.resume_id = r.id
           WHERE a.status='submitted'
           ORDER BY a.started_at DESC LIMIT 200""")
    charts = [
        FocusChart(
            "Submitted per day",
            db.query("""SELECT date(started_at) AS day, COUNT(*) AS count
                   FROM applications WHERE status='submitted'
                   GROUP BY day ORDER BY day"""),
            "day",
            "count",
            kind="line",
        ),
        FocusChart(
            "Top companies",
            db.query("""SELECT j.company AS name, COUNT(*) AS count
                   FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE a.status='submitted' AND j.company IS NOT NULL
                   GROUP BY lower(j.company) ORDER BY count DESC LIMIT 12"""),
            "name",
            "count",
        ),
        FocusChart(
            "Résumé usage",
            db.query("""SELECT COALESCE(r.name,'(none)') AS name, COUNT(*) AS count
                   FROM applications a LEFT JOIN resumes r ON a.resume_id=r.id
                   WHERE a.status='submitted' GROUP BY name ORDER BY count DESC"""),
            "name",
            "count",
        ),
        FocusChart(
            "By workplace type",
            db.query("""SELECT COALESCE(j.workplace_type,'unknown') AS name, COUNT(*) AS count
                   FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE a.status='submitted' GROUP BY name ORDER BY count DESC"""),
            "name",
            "count",
        ),
        FocusChart(
            "By experience level",
            db.query("""SELECT COALESCE(j.experience_level,'unknown') AS name, COUNT(*) AS count
                   FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE a.status='submitted' GROUP BY name ORDER BY count DESC"""),
            "name",
            "count",
        ),
    ]
    return FocusView("submitted", "All submitted applications", _count(rows), rows, charts)


def _failed(db: Database) -> FocusView:
    rows = db.query("""SELECT a.started_at AS "When", j.title AS Title, j.company AS Company,
                  a.reason AS Reason, a.steps AS Steps, j.url AS url
           FROM applications a JOIN jobs j ON a.job_id = j.id
           WHERE a.status='failed'
           ORDER BY a.started_at DESC LIMIT 200""")
    charts = [
        FocusChart(
            "Failures per day",
            db.query("""SELECT date(started_at) AS day, COUNT(*) AS count
                   FROM applications WHERE status='failed'
                   GROUP BY day ORDER BY day"""),
            "day",
            "count",
            kind="line",
        ),
        FocusChart(
            "Top failure reasons",
            db.query("""SELECT substr(COALESCE(reason,'(none)'),1,40) AS name, COUNT(*) AS count
                   FROM applications WHERE status='failed'
                   GROUP BY name ORDER BY count DESC LIMIT 12"""),
            "name",
            "count",
            caption="What the run reported when it gave up.",
        ),
        FocusChart(
            "Failures by company",
            db.query("""SELECT j.company AS name, COUNT(*) AS count
                   FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE a.status='failed' AND j.company IS NOT NULL
                   GROUP BY lower(j.company) ORDER BY count DESC LIMIT 12"""),
            "name",
            "count",
        ),
    ]
    return FocusView(
        "failed",
        "Failed applications",
        _count(rows),
        rows,
        charts,
        note="Retry these from the ⚠️ Needs attention tab's **🔁 Reapply all** button.",
    )


def _skipped(db: Database) -> FocusView:
    rows = [
        {
            "When": e.get("created_at"),
            "Reason": e.get("reason"),
            "Title": e.get("title"),
            "Company": e.get("company"),
            "url": e.get("url"),
        }
        for e in db.skip_events(limit=200)
    ]
    charts = [
        FocusChart(
            "Why jobs were skipped",
            db.query(
                "SELECT reason AS name, COUNT(*) AS count FROM skips "
                "GROUP BY reason ORDER BY count DESC"
            ),
            "name",
            "count",
        ),
        FocusChart(
            "Skips per day",
            db.query(
                "SELECT date(created_at) AS day, COUNT(*) AS count FROM skips "
                "GROUP BY day ORDER BY day"
            ),
            "day",
            "count",
            kind="line",
        ),
        FocusChart(
            "Skipped by company",
            db.query("""SELECT COALESCE(j.company,'unknown') AS name, COUNT(*) AS count
                   FROM skips s LEFT JOIN jobs j ON s.job_id=j.id
                   GROUP BY name ORDER BY count DESC LIMIT 12"""),
            "name",
            "count",
        ),
    ]
    return FocusView(
        "skipped",
        "Skipped jobs",
        "Jobs the pipeline chose not to apply to.",
        rows,
        charts,
        note="Per-reason detail is recorded from this version onward; the headline count "
        "also includes older runs. See the **⏭️ Skipped** tab for the full analytics.",
    )


def _discovered(db: Database) -> FocusView:
    rows = db.query("""SELECT j.discovered_at AS "When", j.title AS Title, j.company AS Company,
                  CASE j.easy_apply WHEN 1 THEN 'Easy Apply' ELSE 'External' END AS Apply,
                  COALESCE(j.workplace_type,'?') AS Workplace,
                  COALESCE(j.experience_level,'?') AS Level, j.url AS url
           FROM jobs j ORDER BY j.discovered_at DESC LIMIT 200""")
    charts = [
        FocusChart(
            "Discovered per day",
            db.query(
                "SELECT date(discovered_at) AS day, COUNT(*) AS count FROM jobs "
                "GROUP BY day ORDER BY day"
            ),
            "day",
            "count",
            kind="line",
        ),
        FocusChart(
            "Easy Apply vs external",
            db.query(
                "SELECT CASE easy_apply WHEN 1 THEN 'Easy Apply' ELSE 'External' END AS name, "
                "COUNT(*) AS count FROM jobs GROUP BY easy_apply ORDER BY count DESC"
            ),
            "name",
            "count",
        ),
        FocusChart(
            "Top companies",
            db.query("""SELECT company AS name, COUNT(*) AS count FROM jobs
                   WHERE company IS NOT NULL
                   GROUP BY lower(company) ORDER BY count DESC LIMIT 12"""),
            "name",
            "count",
        ),
        FocusChart(
            "By workplace type",
            db.query(
                "SELECT COALESCE(workplace_type,'unknown') AS name, COUNT(*) AS count "
                "FROM jobs GROUP BY name ORDER BY count DESC"
            ),
            "name",
            "count",
        ),
        FocusChart(
            "By experience level",
            db.query(
                "SELECT COALESCE(experience_level,'unknown') AS name, COUNT(*) AS count "
                "FROM jobs GROUP BY name ORDER BY count DESC"
            ),
            "name",
            "count",
        ),
    ]
    return FocusView("discovered", "Jobs discovered", _count(rows), rows, charts)


def _count(rows: list[dict[str, Any]]) -> str:
    return f"{len(rows)} record(s)" + (" (latest 200)" if len(rows) >= 200 else "")


_BUILDERS = {
    "today": _today,
    "submitted": _submitted,
    "failed": _failed,
    "skipped": _skipped,
    "discovered": _discovered,
}
