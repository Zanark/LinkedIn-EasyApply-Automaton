"""Streamlit dashboard for the LinkedIn Easy Apply Automaton.

Run via ``lea dashboard`` (which sets ``LEA_CONFIG``) or directly with
``streamlit run linkedin_easy_apply/dashboard/app.py``.
"""

from __future__ import annotations

import html
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from linkedin_easy_apply.answers.resume_expectations import (
    GradedAnswer,
    ResumeProfile,
    Verdict,
    deviation_by_day,
    grade_comparison,
    load_resume_profile,
)
from linkedin_easy_apply.config import load_config
from linkedin_easy_apply.dashboard.focus import build_focus_view, has_real_categories
from linkedin_easy_apply.dashboard.reapply_launch import launch_reapply, reapply_command
from linkedin_easy_apply.database import Database


@st.cache_resource
def _get_database(config_path: str) -> Database:
    config = load_config(config_path)
    db = Database(config.database.path)
    db.initialize()
    return db


# --------------------------------------------------------------------------- #
# Chart helpers — horizontal bars + flat (never-rotated) axis labels.
# Streamlit's native st.bar_chart/st.line_chart rotate crowded x labels to
# vertical; these Altair replacements keep every label readable left-to-right:
# bar categories sit on the Y axis, and line dates use a compact horizontal
# "Jul 13" format. Altair ships with Streamlit, so this adds no dependency.
# --------------------------------------------------------------------------- #
def _chart_series(data: Any) -> pd.Series | None:
    """Coerce a Series, a one-column indexed DataFrame, or a dict into a Series."""
    if isinstance(data, pd.Series):
        series = data
    elif isinstance(data, dict):
        series = pd.Series(data)
    elif isinstance(data, pd.DataFrame) and data.shape[1] >= 1:
        series = data.iloc[:, 0]
    else:
        return None
    return series if not series.empty else None


def _hbar(data: Any, *, value_title: str | None = None, max_bars: int | None = None) -> None:
    """Render a **horizontal** bar chart so category labels read left-to-right.

    Drop-in replacement for ``st.bar_chart`` on categorical data: the category
    goes on the Y axis (labels never rotate vertical) and the value runs along X,
    bars sorted longest-first. Accepts a Series, a one-column DataFrame, or a
    ``{label: value}`` dict.
    """
    series = _chart_series(data)
    if series is None:
        return
    label = value_title or (
        series.name if isinstance(series.name, str) and series.name else "count"
    )
    frame = pd.DataFrame(
        {"category": [str(i) for i in series.index], "value": list(series.to_numpy())}
    )
    if max_bars is not None:
        frame = frame.head(max_bars)
    height = max(150, 30 * len(frame) + 30)
    chart = (
        alt.Chart(frame)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", title=label),
            y=alt.Y(
                "category:N", title=None, sort="-x", axis=alt.Axis(labelAngle=0, labelLimit=340)
            ),
            tooltip=[
                alt.Tooltip("category:N", title="category"),
                alt.Tooltip("value:Q", title=label),
            ],
        )
        .properties(height=height)
    )
    st.altair_chart(chart, width="stretch")


def _line(data: Any, *, value_title: str | None = None) -> None:
    """Render a line chart whose x-axis labels stay **horizontal**.

    Drop-in replacement for ``st.line_chart`` on day-series data. A date-like
    index is drawn on a temporal axis with a compact ``Jul 13`` format; any other
    index becomes an ordinal axis in its original order. Labels never rotate.
    """
    series = _chart_series(data)
    if series is None:
        return
    label = value_title or (
        series.name if isinstance(series.name, str) and series.name else "count"
    )
    x_label = str(series.index.name or "day")
    parsed = pd.to_datetime(pd.Index(series.index), errors="coerce")
    values = list(series.to_numpy())
    if not bool(parsed.isna().any()):
        frame = pd.DataFrame({"x": parsed, "value": values})
        x_enc = alt.X("x:T", title=None, axis=alt.Axis(labelAngle=0, format="%b %d"))
        tip_x = alt.Tooltip("x:T", title=x_label, format="%b %d")
    else:
        order = [str(i) for i in series.index]
        frame = pd.DataFrame({"x": order, "value": values})
        x_enc = alt.X("x:N", title=None, sort=order, axis=alt.Axis(labelAngle=0))
        tip_x = alt.Tooltip("x:N", title=x_label)
    chart = (
        alt.Chart(frame)
        .mark_line(point=True)
        .encode(
            x=x_enc,
            y=alt.Y("value:Q", title=label),
            tooltip=[tip_x, alt.Tooltip("value:Q", title=label)],
        )
    )
    st.altair_chart(chart, width="stretch")


# --------------------------------------------------------------------------- #
# Reports folder — a first-page corner control that opens the folders where
# exported reports are written (offline analysis reports + per-run outreach
# reports). Browsers block file:// links served from an http origin, so the
# reliable action opens the folder in the host's own file browser; a file://
# link is offered too for browsers that still allow it.
# --------------------------------------------------------------------------- #
def resolve_report_dirs(
    config_path: str | Path, outreach_report_dir: str | Path
) -> tuple[Path, Path]:
    """Resolve absolute ``(analysis, outreach)`` report directories.

    Anchored to the project root (the parent of the ``configs`` folder holding
    ``config_path``) so the folders resolve correctly regardless of the
    dashboard's working directory. A relative outreach ``report_dir`` resolves
    against that same root; an absolute one is kept as-is.
    """
    project_root = Path(config_path).resolve().parent.parent
    analysis_dir = project_root / "reports"
    outreach_dir = Path(outreach_report_dir)
    if not outreach_dir.is_absolute():
        outreach_dir = project_root / outreach_dir
    return analysis_dir, outreach_dir


def _default_opener(path: Path) -> None:
    """Open *path* in the host operating system's file browser."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]  # Windows only
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _reveal_directory(
    path: Path, *, opener: Callable[[Path], None] | None = None
) -> tuple[bool, str]:
    """Create *path* if missing and open it in the file browser.

    Returns ``(ok, message)`` so the caller can surface the result inline. The
    ``opener`` is injectable so tests never pop a real window.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Could not create folder {path}: {exc}"
    try:
        (opener or _default_opener)(path)
    except Exception as exc:  # pragma: no cover - platform specific
        return False, f"Could not open {path}: {exc}"
    return True, f"Opened {path} in your file browser."


def _reports_dir_row(label: str, path: Path, key: str) -> None:
    """Render one report folder: its path, an open button, and a file:// link."""
    st.markdown(f"**{label}**")
    st.code(str(path), language=None)
    if not path.is_dir():
        st.caption("Created when the first report is written.")
    open_col, link_col = st.columns(2)
    with open_col:
        if st.button("📂 Open folder", key=f"open_reports_{key}", width="stretch"):
            ok, message = _reveal_directory(path)
            (st.success if ok else st.error)(message)
    with link_col:
        st.link_button("🌐 In browser", f"file:///{path.as_posix()}", width="stretch")


def _reports_corner(config_path: str, config: Any) -> None:
    """First-page corner popover linking to the exported-report folders."""
    analysis_dir, outreach_dir = resolve_report_dirs(config_path, config.outreach.report_dir)
    with st.popover("📂 Reports", width="stretch"):
        st.caption(
            "Folders where exported reports are written. 'Open folder' opens it in "
            "your system file browser; 'In browser' uses a file:// link that some "
            "browsers block."
        )
        _reports_dir_row("Analysis reports", analysis_dir, "analysis")
        st.divider()
        _reports_dir_row("Outreach reports", outreach_dir, "outreach")


def main() -> None:
    st.set_page_config(page_title="Easy Apply Dashboard", page_icon="💼", layout="wide")

    config_path = os.environ.get("LEA_CONFIG", "configs/config.yaml")
    if not Path(config_path).exists():
        st.title("💼 LinkedIn Easy Apply — Dashboard")
        st.error(f"Config not found: {config_path}. Set LEA_CONFIG or run 'lea init'.")
        return

    db = _get_database(config_path)
    config = load_config(config_path)
    stats = db.stats()

    header_col, reports_col = st.columns([5, 1], vertical_alignment="center")
    with header_col:
        st.title("💼 LinkedIn Easy Apply — Dashboard")
    with reports_col:
        _reports_corner(config_path, config)

    cols = st.columns(5)
    kpis = [
        ("today", "Applications today", stats["applications_today"]),
        ("submitted", "Total submitted", stats["applications_submitted"]),
        ("failed", "Failed", stats["applications_failed"]),
        ("skipped", "Skipped", stats["jobs_skipped_total"]),
        ("discovered", "Jobs discovered", stats["total_jobs"]),
    ]
    for col, (key, label, value) in zip(cols, kpis, strict=True):
        with col, st.container(border=True):
            st.metric(label, value)
            if st.button("View details →", key=f"kpi_{key}", width="stretch"):
                st.session_state["focus_category"] = key

    _focus_panel(db)

    success_total = stats["applications_submitted"] + stats["applications_failed"]
    rate = (stats["applications_submitted"] / success_total * 100) if success_total else 0.0
    st.progress(min(rate / 100, 1.0), text=f"Success rate: {rate:.0f}%")

    # Excel-style tabs keep each category on its own page instead of one long scroll.
    (
        overview_tab,
        submitted_tab,
        details_tab,
        attention_tab,
        skipped_tab,
        match_tab,
        outreach_tab,
    ) = st.tabs(
        [
            "📊 Overview",
            "✅ Submitted",
            "🔎 Application details",
            "⚠️ Needs attention",
            "⏭️ Skipped",
            "🎯 Resume match",
            "🤝 Outreach",
        ]
    )
    with overview_tab:
        _overview_section(db, stats)
    with submitted_tab:
        _submitted_section(db)
    with details_tab:
        _application_detail_section(db)
    with attention_tab:
        _needs_attention_section(db, config_path)
    with skipped_tab:
        _skipped_section(db)
    with match_tab:
        _resume_match_section(db, load_resume_profile(config))
    with outreach_tab:
        _outreach_section(db)


def _focus_panel(db: Database) -> None:
    """Drill-down rendered when a KPI card's 'View details →' button is clicked.

    The clicked card stashes its category in ``st.session_state``; this reads it
    back and renders that category's charts + record table (``✕ Close`` clears it).
    """
    category = st.session_state.get("focus_category")
    if not category:
        return
    view = build_focus_view(db, category)
    if view is None:
        st.session_state.pop("focus_category", None)
        return

    with st.container(border=True):
        head, close = st.columns([6, 1])
        head.subheader(f"🔎 {view.title}")
        if close.button("✕ Close", key="focus_close", width="stretch"):
            st.session_state.pop("focus_category", None)
            st.rerun()
        st.caption(view.subtitle)
        if view.note:
            st.info(view.note)

        charts = [
            chart
            for chart in view.charts
            if chart.rows
            and (chart.kind == "line" or has_real_categories(row[chart.x] for row in chart.rows))
        ]
        if charts:
            chart_cols = st.columns(2)
            for index, chart in enumerate(charts):
                with chart_cols[index % 2]:
                    st.markdown(f"**{chart.title}**")
                    frame = pd.DataFrame(chart.rows).set_index(chart.x)[[chart.y]]
                    if chart.kind == "line":
                        _line(frame)
                    else:
                        _hbar(frame)
                    if chart.caption:
                        st.caption(chart.caption)

        st.markdown("**Records**")
        if view.rows:
            _focus_table(view.rows)
        else:
            st.info("No records in this category yet.")


def _focus_table(rows: list[dict[str, Any]]) -> None:
    """Render a focus record list, turning any ``url`` column into a clickable link."""
    frame = pd.DataFrame(rows)
    column_config: dict[str, Any] = {}
    if "url" in frame.columns:
        frame = frame.rename(columns={"url": "Job link"})
        column_config["Job link"] = st.column_config.LinkColumn("Job link", display_text="Open ↗")
    st.dataframe(frame, width="stretch", hide_index=True, column_config=column_config or None)


def _overview_section(db: Database, stats: dict[str, Any]) -> None:
    """At-a-glance summary: top companies, common questions, recent applies, résumé usage."""
    left, right = st.columns(2)
    with left:
        st.subheader("Top companies")
        if stats["top_companies"]:
            st.dataframe(stats["top_companies"], width="stretch", hide_index=True)
        else:
            st.info("No applications yet.")

    with right:
        st.subheader("Most frequent questions")
        questions = db.query(
            "SELECT text AS question, category, seen_count FROM questions "
            "ORDER BY seen_count DESC LIMIT 15"
        )
        if questions:
            st.dataframe(questions, width="stretch", hide_index=True)
        else:
            st.info("No questions recorded yet.")

    st.subheader("Recent applications")
    applications = db.query("""SELECT a.started_at, j.title, j.company, a.status, a.reason, a.steps
           FROM applications a JOIN jobs j ON a.job_id = j.id
           ORDER BY a.started_at DESC LIMIT 50""")
    if applications:
        st.dataframe(applications, width="stretch", hide_index=True)
    else:
        st.info("No applications recorded yet. Run 'lea apply' to get started.")

    st.subheader("Resume usage")
    resumes = db.query("""SELECT r.name, COUNT(a.id) AS uses FROM resumes r
           LEFT JOIN applications a ON a.resume_id = r.id
           GROUP BY r.id ORDER BY uses DESC""")
    if resumes:
        _hbar({row["name"]: row["uses"] for row in resumes}, value_title="uses")


def _submitted_section(db: Database) -> None:
    """Every successful application as a collapsible, start-to-finish Q&A card."""
    st.subheader("✅ Submitted applications — the full story of each")
    apps = db.submitted_applications()
    if not apps:
        st.info(
            "No submitted applications yet. Once you apply, each success shows up "
            "here — expand any one to replay exactly what was asked and answered."
        )
        return

    grouped = db.answers_for_applications([int(a["id"]) for a in apps])
    st.caption(
        f"{len(apps)} successful application(s), newest first. Expand any "
        "**company — role** to see exactly what was asked and the answer "
        "submitted, from start to finish."
    )

    role_counts = Counter((app.get("title") or "—") for app in apps)
    if role_counts:
        st.markdown("**Successful submissions by job role**")
        _hbar(role_counts, value_title="submissions")

    for app in apps:
        title = app.get("title") or "—"
        company = app.get("company") or "—"
        when = str(app.get("started_at") or "")[:16].replace("T", " ")
        header = f"{company} — {title}" + (f"   ·   {when}" if when else "")
        with st.expander(header):
            meta = []
            if app.get("resume"):
                meta.append(f"**Résumé submitted:** {app['resume']}")
            if app.get("steps") is not None:
                meta.append(f"**Steps:** {app['steps']}")
            if meta:
                st.markdown("  ·  ".join(meta))
            if app.get("url"):
                st.markdown(f"[Open job posting ↗]({app['url']})")
            answers = grouped.get(int(app["id"]), [])
            if not answers:
                st.caption(
                    "No field-level answers recorded for this application "
                    "(a one-click apply with no questions, or an older run)."
                )
                continue
            frame = pd.DataFrame(answers)[["question_text", "value", "source"]]
            frame.columns = ["Question", "Answer submitted", "Source"]
            st.dataframe(frame, width="stretch", hide_index=True)
            st.caption(f"{len(answers)} field(s) submitted for this application.")


def _application_detail_section(db: Database) -> None:
    """Drill-down: pick one application and see every field asked & answered."""
    st.subheader("🔎 Application details — exactly what was asked & answered")
    apps = db.query("""SELECT a.id, a.started_at, a.status, a.reason, a.steps,
                  j.title, j.company, j.url, r.name AS resume
           FROM applications a
           JOIN jobs j ON a.job_id = j.id
           LEFT JOIN resumes r ON a.resume_id = r.id
           ORDER BY a.started_at DESC LIMIT 100""")
    if not apps:
        st.info("No applications recorded yet.")
        return

    def _label(app: dict) -> str:
        title = app["title"] or "—"
        company = app["company"] or "—"
        return f"{app['started_at']}  ·  {title} @ {company}  ·  {app['status']}"

    # Select over row indices (not labels) so identical labels never collapse.
    picked = st.selectbox(
        "Pick an application to inspect",
        range(len(apps)),
        format_func=lambda i: _label(apps[i]),
        key="app_detail_pick",
    )
    app = apps[picked]

    cols = st.columns([1, 1, 2, 1])
    cols[0].metric("Status", app["status"])
    cols[1].metric("Steps", app["steps"])
    cols[2].metric("Résumé submitted", app["resume"] or "—")
    if app["url"]:
        cols[3].link_button("Open job ↗", app["url"])
    if app["reason"]:
        st.caption(f"Reason: {app['reason']}")

    answers = db.application_answers(app["id"])
    if not answers:
        st.info(
            "No field-level answers recorded for this application "
            "(older run, or a one-click apply with no questions)."
        )
        return
    frame = pd.DataFrame(answers)[["question_text", "value", "source"]]
    frame.columns = ["Question", "Answer submitted", "Source"]
    st.dataframe(frame, width="stretch", hide_index=True)
    st.caption(f"{len(answers)} field(s) submitted for this application.")


def _needs_attention_section(db: Database, config_path: str) -> None:
    """Surface unanswered/skipped questions and the applications they blocked.

    Answers the question "what did the bot fail to fill, and where did that
    stall an application?" — the top gaps are the exact entries to add to
    ``configs/answers.yaml`` / ``custom_questions`` to stop future failures.
    """
    st.subheader("⚠️ Needs attention — unanswered questions & blocked applications")
    st.caption(
        "Questions the automation had **no answer** for (left blank / skipped), plus the "
        "applications that stalled. Most Easy Apply failures are a required question we "
        "couldn't answer — add answers for the questions below (configs/answers.yaml or a "
        "custom_questions entry) to stop the failures."
    )

    gaps = db.unanswered_questions()
    blocked = db.blocked_applications()
    no_progress = sum(
        1 for b in blocked if (b.get("reason_short") or "").lower().startswith("no progress")
    )

    metrics = st.columns(3)
    metrics[0].metric("Unanswered questions", len(gaps))
    metrics[1].metric("Blocked applications", len(blocked))
    metrics[2].metric("…stalled on a question", no_progress)

    st.markdown("**Questions to answer** — never answered in any application")
    if gaps:
        frame = pd.DataFrame(gaps)[
            ["question", "blank_in_apps", "blocked_apps", "answer_type", "category", "last_seen"]
        ]
        frame.columns = [
            "Question",
            "Times blank",
            "In blocked apps",
            "Type",
            "Category",
            "Last seen",
        ]
        st.dataframe(frame, width="stretch", hide_index=True)
        st.caption(
            f"{len(gaps)} distinct question(s) with no answer on record. Fixing the top rows "
            "(highest ‘In blocked apps’) prevents the most failures."
        )
    else:
        st.success("No unanswered questions on record — every asked question got a value. 🎉")

    with st.expander(f"Blocked / aborted applications ({len(blocked)})"):
        if not blocked:
            st.success("No blocked or aborted applications. 🎉")
        else:
            bframe = pd.DataFrame(blocked)[
                [
                    "started_at",
                    "title",
                    "company",
                    "status",
                    "reason_short",
                    "steps",
                    "unanswered_count",
                    "url",
                ]
            ]
            bframe.columns = [
                "Started",
                "Job",
                "Company",
                "Status",
                "Reason",
                "Step",
                "Unanswered",
                "Job link",
            ]
            st.dataframe(
                bframe,
                width="stretch",
                hide_index=True,
                column_config={
                    "Job link": st.column_config.LinkColumn("Job link", display_text="Open ↗")
                },
            )
            st.caption(
                "‘Unanswered’ counts distinct questions left blank in that attempt — usually the "
                "reason a step made ‘No progress’."
            )

    _reapply_controls(db, config_path)


def _reapply_controls(db: Database, config_path: str) -> None:
    """Let the user retry every failed/aborted job with one click.

    Easy Apply needs a live Playwright browser + your logged-in session, which
    can't run inside the Streamlit process, so the button launches the ``reapply``
    CLI in a **new console window** (the browser reuses your profile there). The
    exact command is always shown as a copy-paste fallback.
    """
    st.divider()
    st.markdown("**🔁 Reapply to failed / aborted jobs**")
    targets = db.reapply_targets()
    if not targets:
        st.info(
            "Nothing to reapply — every failed/aborted job was either retried "
            "successfully or has no stored URL."
        )
        return

    st.caption(
        f"{len(targets)} job(s) that never submitted. Reapply opens a **new console window** and "
        "retries each with the normal Easy Apply flow. Tip: approve fixes in the "
        "🎯 Resume match tab (or edit answers.yaml) **first** so corrected answers are used."
    )
    rframe = pd.DataFrame(targets)[["title", "company", "attempts", "last_status", "url"]]
    rframe.columns = ["Job", "Company", "Attempts", "Last status", "Job link"]
    st.dataframe(
        rframe,
        width="stretch",
        hide_index=True,
        column_config={"Job link": st.column_config.LinkColumn("Job link", display_text="Open ↗")},
    )

    controls = st.columns([1, 2])
    answer_unknowns = controls[1].checkbox(
        "Answer unknown questions in the console (recommended)",
        value=True,
        help="If ticked, the retry pauses in the new window for you to type answers to any "
        "question it has never seen. Untick for a fully unattended run (passes --yes).",
    )
    if controls[0].button(f"🔁 Reapply all ({len(targets)})", type="primary"):
        ok, message = launch_reapply(config_path, answer_unknowns=answer_unknowns)
        (st.success if ok else st.error)(message)

    st.caption("Or run it yourself:")
    st.code(reapply_command(config_path, answer_unknowns), language="powershell")


# Plain-English meaning for every skip reason the orchestrator can emit, so the
# Skipped tab explains itself instead of showing raw codes.
_SKIP_REASON_HELP: dict[str, str] = {
    "not_easy_apply": "No Easy Apply button — external application site.",
    "already_applied": "Already applied (LinkedIn marker or a prior submit).",
    "duplicate_company_role": "Already applied to the same company + role.",
    "not_whitelisted": "Company isn't in your whitelist.",
    "blacklisted": "Company is on your blacklist.",
    "excluded_keyword": "Title/description matched one of your exclude keywords.",
    "missing_include_keyword": "None of your required include-keywords were present.",
    "company_limit": "Hit your max-applications-per-company cap.",
    "below_threshold": "Match score fell below your apply threshold.",
    "ai_advised_against": "The AI advisor recommended against applying.",
    "scan_only": "Scan mode — deliberately not applying, just cataloguing.",
    "reapply_open_failed": "Couldn't reopen the job page during a reapply run.",
    "skipped": "Easy Apply form skipped mid-flow (unsupported step).",
    "dry_run": "Dry-run mode — filled the form but didn't submit.",
    "aborted": "Application aborted (e.g., interrupted).",
}


def _skipped_section(db: Database) -> None:
    """Skip analytics: how many jobs were skipped, why, and the trends behind it."""
    st.subheader("⏭️ Skipped jobs — how many & why")
    events = db.skip_events(limit=5000)
    if not events:
        st.info(
            "No per-reason skip data recorded yet. Skips are captured from this version "
            "onward — run `lea apply` or `lea scan`, then refresh. (The Overview **Skipped** "
            "metric still shows the historical total from earlier runs.)"
        )
        return

    frame = pd.DataFrame(events)
    frame["reason"] = frame["reason"].fillna("unknown")
    counts = frame["reason"].value_counts()

    cols = st.columns(3)
    cols[0].metric("Skip events", int(len(frame)))
    cols[1].metric("Distinct reasons", int(counts.size))
    cols[2].metric("Most common", f"{counts.index[0]} ({int(counts.iloc[0])})")
    st.caption(
        "Reason-level detail is recorded from this version onward; older runs only kept the "
        "aggregate count (Overview → Skipped)."
    )

    st.markdown("**Why jobs were skipped**")
    _hbar(counts)

    frame["day"] = pd.to_datetime(frame["created_at"], errors="coerce").dt.date.astype("string")
    per_day = frame.dropna(subset=["day"]).groupby("day").size()
    if per_day.size > 1:
        st.markdown("**Skips over time**")
        _line(per_day)

    breakdowns: list[tuple[str, Any]] = []
    companies = frame.loc[frame["company"].notna(), "company"].value_counts().head(12)
    if not companies.empty:
        breakdowns.append(("Top companies skipped", companies))
    workplace = frame["workplace_type"].fillna("unknown").value_counts()
    if has_real_categories(workplace.index):
        breakdowns.append(("By workplace type", workplace))
    experience = frame["experience_level"].fillna("unknown").value_counts()
    if has_real_categories(experience.index):
        breakdowns.append(("By experience level", experience))

    if breakdowns:
        grid = st.columns(2)
        for index, (title, series) in enumerate(breakdowns):
            with grid[index % 2]:
                st.markdown(f"**{title}**")
                _hbar(series)

    st.markdown("**Every skip (newest first)**")
    detail_cols = ["created_at", "reason", "title", "company"]
    detail_names = ["When", "Reason", "Title", "Company"]
    # Only surface Workplace / Level when at least one job actually recorded them
    # (they are NULL for jobs scraped before those fields were captured).
    if has_real_categories(frame["workplace_type"].dropna()):
        detail_cols.append("workplace_type")
        detail_names.append("Workplace")
    if has_real_categories(frame["experience_level"].dropna()):
        detail_cols.append("experience_level")
        detail_names.append("Level")
    detail_cols.append("url")
    detail_names.append("Job link")
    detail = frame[detail_cols].copy()
    detail.columns = detail_names
    st.dataframe(
        detail,
        width="stretch",
        hide_index=True,
        column_config={"Job link": st.column_config.LinkColumn("Job link", display_text="Open ↗")},
    )

    with st.expander("What do these reasons mean?"):
        present = [r for r in counts.index if r in _SKIP_REASON_HELP]
        st.dataframe(
            pd.DataFrame({"Reason": present, "Meaning": [_SKIP_REASON_HELP[r] for r in present]}),
            width="stretch",
            hide_index=True,
        )


def _resume_match_section(db: Database, profile: ResumeProfile | None) -> None:
    """Grade recorded answers against the résumé, chart the deviation, and let the
    user approve corrections that "sync" into a DB override the resolver reads first.
    """
    st.subheader("🎯 Resume match — what was answered vs. your résumé")
    if profile is None:
        st.info(
            "Couldn't find **master.yaml** (your résumé source of truth). Set "
            "`resume.master_path` in config.yaml, or point `resume.builder.path` at the "
            "dynamic-resume-builder folder that holds it. Then reload this page."
        )
        return

    st.caption(
        f"Graded against your résumé: **{profile.total_years} years** total experience, "
        f"**{len(profile.skill_forms)}** distinct skills. Only fields the résumé can actually "
        "judge (total & per-skill experience and identity) are graded — salary, notice, "
        "relocation and other **preferences** are shown as *not derivable*, never a deviation."
    )

    graded = grade_comparison(profile, db.answer_comparison())
    if not graded:
        st.info("No answered questions on record yet. Run 'lea apply' first.")
        return

    derivable = [g for g in graded if g.verdict is not Verdict.NOT_DERIVABLE]
    matches = [g for g in derivable if g.verdict is Verdict.MATCH]
    mismatches = [g for g in derivable if g.verdict is Verdict.MISMATCH]

    metrics = st.columns(4)
    metrics[0].metric("Gradable answers", len(derivable))
    metrics[1].metric("✅ Match résumé", len(matches))
    metrics[2].metric("❌ Differ from résumé", len(mismatches))
    metrics[3].metric("Not derivable", len(graded) - len(derivable))

    _resume_match_charts(db, profile, mismatches)
    _resume_sync_editor(db, mismatches, matches)
    _resume_overrides_view(db)


def _resume_match_charts(
    db: Database, profile: ResumeProfile, mismatches: list[GradedAnswer]
) -> None:
    """Deviation-over-time line + differences-by-category bar."""
    left, right = st.columns(2)
    with left:
        st.markdown("**Deviation from résumé over time**")
        st.caption("Share of gradable answers per day that disagreed with the résumé.")
        days = deviation_by_day(profile, db.answered_history())
        if days:
            frame = pd.DataFrame(
                [
                    {
                        "day": day,
                        "deviation %": (
                            round(100 * b["mismatch"] / b["derivable"]) if b["derivable"] else 0
                        ),
                    }
                    for day, b in sorted(days.items())
                ]
            ).set_index("day")
            _line(frame)
        else:
            st.info("Not enough dated history yet.")

    with right:
        st.markdown("**Differences by category**")
        st.caption("Which kinds of question most often disagree with the résumé.")
        if mismatches:
            counts = Counter(g.category for g in mismatches)
            frame = pd.DataFrame({"differences": dict(counts.most_common())})
            _hbar(frame)
        else:
            st.success("No differences — every gradable answer matches. 🎉")


def _resume_sync_editor(
    db: Database, mismatches: list[GradedAnswer], matches: list[GradedAnswer]
) -> None:
    """Editable table: tick Approve (+ optionally edit the value), then Sync."""
    st.markdown("### Review & sync corrections")
    st.caption(
        "Tick **Approve** on rows whose *Approved value* is correct (edit it if the "
        "recommendation isn't quite right), then press **Sync approved**. Synced values are "
        "stored in the database and used **first** — ahead of answers.yaml and the learned "
        "bank — the next time that question is asked."
    )
    show_matches = st.checkbox("Also show answers that already match the résumé", value=False)
    candidates = mismatches + matches if show_matches else mismatches
    # Hide rows that already carry an approved override: they've been synced and
    # now live in "Approved overrides in effect" below, so they no longer need a
    # decision here. (Removing the override there brings the row back.)
    pending = [g for g in candidates if not g.override]
    approved_hidden = sum(1 for g in candidates if g.override)
    if not pending:
        if approved_hidden:
            st.success(
                f"Nothing left to review — all {approved_hidden} differing answer(s) already "
                "have an approved value. See **Approved overrides in effect** below to view "
                "or remove them."
            )
        else:
            st.success("Nothing to correct — no gradable answer differs from the résumé. 🎉")
        return
    if approved_hidden:
        st.caption(
            f"✓ {approved_hidden} already-approved answer(s) are hidden from this list — "
            "view or remove them under **Approved overrides in effect** below."
        )

    editor_rows = [
        {
            "Approve": False,
            "Question": g.question,
            "Category": g.category,
            "Answered": g.answered or "",
            "Résumé expects": g.expected_display,
            "Approved value": g.override or g.recommended or "",
            "Verdict": g.verdict.value,
            "Why": g.reason,
            "_normalized": g.normalized,
            "_question_id": g.question_id if g.question_id is not None else -1,
        }
        for g in pending
    ]
    edited = st.data_editor(
        pd.DataFrame(editor_rows),
        width="stretch",
        hide_index=True,
        key="resume_sync_editor",
        column_order=[
            "Approve",
            "Question",
            "Category",
            "Answered",
            "Résumé expects",
            "Approved value",
            "Verdict",
            "Why",
        ],
        disabled=[
            "Question",
            "Category",
            "Answered",
            "Résumé expects",
            "Verdict",
            "Why",
        ],
        column_config={
            "Approve": st.column_config.CheckboxColumn(
                "Approve", help="Tick to save this row's Approved value as the answer to use."
            ),
            "Question": st.column_config.TextColumn("Question", width="large"),
            "Approved value": st.column_config.TextColumn(
                "Approved value", help="The value to store & use. Edit if needed."
            ),
            "Why": st.column_config.TextColumn("Why", width="medium"),
        },
    )

    if st.button("💾 Sync approved answers", type="primary"):
        approved = edited[edited["Approve"] == True]  # noqa: E712 (pandas mask)
        synced = 0
        skipped = 0
        for _, row in approved.iterrows():
            value = str(row["Approved value"]).strip()
            if not value:
                skipped += 1
                continue
            qid = int(row["_question_id"])
            db.set_answer_override(
                str(row["_normalized"]),
                value,
                qid if qid >= 0 else None,
                "approved via dashboard",
            )
            synced += 1
        if synced:
            st.success(
                f"Synced {synced} approved answer(s). They'll be used the next time those "
                "questions are asked."
            )
        if skipped:
            st.warning(f"Skipped {skipped} approved row(s) with an empty value.")
        if synced or skipped:
            st.rerun()


def _resume_overrides_view(db: Database) -> None:
    """Show the approved overrides already in effect, with a way to remove one."""
    overrides = db.answer_overrides()
    with st.expander(f"Approved overrides in effect ({len(overrides)})"):
        if not overrides:
            st.caption("No approved overrides yet.")
            return
        frame = pd.DataFrame(
            [
                {
                    "Question": o.get("question") or o.get("normalized"),
                    "Approved value": o.get("value"),
                    "Category": o.get("category") or "—",
                    "Updated": o.get("updated_at"),
                }
                for o in overrides
            ]
        )
        st.dataframe(frame, width="stretch", hide_index=True)
        labels = {
            (o.get("question") or o.get("normalized") or ""): o["normalized"] for o in overrides
        }
        to_remove = st.selectbox(
            "Remove an override",
            ["—", *labels.keys()],
            key="override_remove_pick",
        )
        if st.button("Remove selected override") and to_remove != "—":
            db.delete_answer_override(labels[to_remove])
            st.success("Removed. That question will fall back to answers.yaml / learned again.")
            st.rerun()


def _outreach_section(db: Database) -> None:
    """Web view of the drafted hiring-team messages, with clickable profiles."""
    st.subheader("🤝 Hiring-team outreach — messages to send")
    drafts = db.outreach_drafts()
    if not drafts:
        st.info(
            "No drafted outreach messages yet. Enable outreach "
            "(outreach.enabled / --message-hiring-team) and apply to some jobs."
        )
        return

    def _job(draft: dict) -> str:
        parts = (draft.get("job_title"), draft.get("job_company"))
        return " @ ".join(p for p in parts if p) or "—"

    editor_rows = [
        {
            "Message sent": False,
            "Note sent": "✓" if d.get("note_sent_at") else "—",
            "Name": d.get("person_name") or "Unknown",
            "Profile": d.get("profile_url") or "",
            "Applied to": _job(d),
            "Résumé to attach": d.get("resume_name") or "—",
            "_id": int(d["id"]),
        }
        for d in drafts
    ]
    edited = st.data_editor(
        pd.DataFrame(editor_rows),
        width="stretch",
        hide_index=True,
        key="outreach_done_editor",
        column_order=[
            "Message sent",
            "Note sent",
            "Name",
            "Profile",
            "Applied to",
            "Résumé to attach",
        ],
        disabled=["Note sent", "Name", "Profile", "Applied to", "Résumé to attach"],
        column_config={
            "Message sent": st.column_config.CheckboxColumn(
                "Message sent",
                help="Tick once you've sent the full message (after they connected), then press "
                "Remove — it deletes the outreach (message, note and all).",
            ),
            "Note sent": st.column_config.TextColumn(
                "Note sent",
                help="✓ once the free connection note has been sent (mark it per contact below).",
            ),
            "Profile": st.column_config.LinkColumn("Profile", display_text="Open profile ↗"),
        },
    )
    st.caption(
        f"{len(drafts)} contact(s). **Workflow:** open a profile, send the short connection "
        "note with your invite and mark **Connection note sent** (it stays here, struck through); "
        "once they accept, send the full message and mark **Message sent** to remove it."
    )
    if st.button("🗑️ Remove message-sent outreach", type="primary"):
        done_ids = [int(row["_id"]) for _, row in edited[edited["Message sent"]].iterrows()]
        removed = db.delete_outreach(done_ids)
        if removed:
            st.success(
                f"Removed {removed} completed outreach record(s) — the message, connection "
                "note and everything related were deleted from the database."
            )
            st.rerun()
        else:
            st.info(
                "Tick **Message sent** on the outreach you've finished first, then press Remove."
            )

    for index, draft in enumerate(drafts, start=1):
        name = draft.get("person_name") or "Unknown"
        job = _job(draft)
        note_sent = bool(draft.get("note_sent_at"))
        marker = "   ✓ note sent" if note_sent else ""
        header = f"{index}. {name}" + (f"  —  {job}" if job != "—" else "") + marker
        with st.expander(header):
            url = draft.get("profile_url")
            if url:
                st.markdown(f"**Profile:** [{url}]({url})")
            else:
                st.markdown("**Profile:** _(not found — search by name on LinkedIn)_")
            resume = draft.get("resume_name")
            if resume:
                st.markdown(f"**Résumé to attach:** {resume}")
                if draft.get("resume_path"):
                    st.caption(draft["resume_path"])
            st.markdown("**Message** _(send once they connect)_:")
            st.code(draft.get("message") or "", language="text")
            note = draft.get("note") or ""
            if note:
                st.markdown(
                    f"**Connection note** — {len(note)}/300 chars, "
                    "_attach to the invite (free, no connection needed)_:"
                )
                if note_sent:
                    when = str(draft.get("note_sent_at") or "")[:16].replace("T", " ")
                    st.success("✓ Connection note sent" + (f" · {when}" if when else ""))
                    st.markdown(
                        "<pre style='text-decoration:line-through;opacity:0.55;"
                        "white-space:pre-wrap;font-family:monospace;margin:0'>"
                        f"{html.escape(note)}</pre>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.code(note, language="text")

            actions = st.columns(2)
            with actions[0]:
                if note and note_sent:
                    if st.button(
                        "↩️ Undo note sent",
                        key=f"outreach_note_undo_{draft['id']}",
                        help="Clear the 'connection note sent' mark for this contact.",
                    ):
                        db.mark_outreach_note_sent([int(draft["id"])], sent=False)
                        st.rerun()
                elif note:
                    if st.button(
                        "✉️ Connection note sent",
                        key=f"outreach_note_{draft['id']}",
                        help="Sent the free connection note with your invite? Mark it done — it "
                        "stays here (struck through); the full message is still pending.",
                    ):
                        db.mark_outreach_note_sent([int(draft["id"])])
                        st.rerun()
            with actions[1]:
                if st.button(
                    "📨 Message sent — mark done & remove",
                    key=f"outreach_done_{draft['id']}",
                    type="primary",
                    help="Sent the full message after they connected? Deletes this outreach "
                    "(message, note and all) from the database.",
                ):
                    db.delete_outreach([int(draft["id"])])
                    st.rerun()


if __name__ == "__main__":
    main()
