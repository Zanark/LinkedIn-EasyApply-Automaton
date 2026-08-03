"""Streamlit dashboard for the LinkedIn Easy Apply Automaton.

Run via ``lea dashboard`` (which sets ``LEA_CONFIG``) or directly with
``streamlit run linkedin_easy_apply/dashboard/app.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from linkedin_easy_apply.config import load_config
from linkedin_easy_apply.database import Database


@st.cache_resource
def _get_database(config_path: str) -> Database:
    config = load_config(config_path)
    db = Database(config.database.path)
    db.initialize()
    return db


def main() -> None:
    st.set_page_config(page_title="Easy Apply Dashboard", page_icon="💼", layout="wide")
    st.title("💼 LinkedIn Easy Apply — Dashboard")

    config_path = os.environ.get("LEA_CONFIG", "configs/config.yaml")
    if not Path(config_path).exists():
        st.error(f"Config not found: {config_path}. Set LEA_CONFIG or run 'lea init'.")
        return

    db = _get_database(config_path)
    stats = db.stats()

    cols = st.columns(4)
    cols[0].metric("Applications today", stats["applications_today"])
    cols[1].metric("Total submitted", stats["applications_submitted"])
    cols[2].metric("Failed", stats["applications_failed"])
    cols[3].metric("Jobs discovered", stats["total_jobs"])

    success_total = stats["applications_submitted"] + stats["applications_failed"]
    rate = (stats["applications_submitted"] / success_total * 100) if success_total else 0.0
    st.progress(min(rate / 100, 1.0), text=f"Success rate: {rate:.0f}%")

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

    _application_detail_section(db)
    _needs_attention_section(db)
    _outreach_section(db)

    st.subheader("Resume usage")
    resumes = db.query("""SELECT r.name, COUNT(a.id) AS uses FROM resumes r
           LEFT JOIN applications a ON a.resume_id = r.id
           GROUP BY r.id ORDER BY uses DESC""")
    if resumes:
        st.bar_chart({row["name"]: row["uses"] for row in resumes})


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


def _needs_attention_section(db: Database) -> None:
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
            return
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

    table = pd.DataFrame(
        [
            {
                "Name": d.get("person_name") or "Unknown",
                "Profile": d.get("profile_url") or "",
                "Applied to": _job(d),
                "Résumé to attach": d.get("resume_name") or "—",
            }
            for d in drafts
        ]
    )
    st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        column_config={
            "Profile": st.column_config.LinkColumn("Profile", display_text="Open profile ↗")
        },
    )
    st.caption(
        f"{len(drafts)} contact(s). Open each profile, attach the listed résumé, "
        "and paste the drafted message below."
    )

    for index, draft in enumerate(drafts, start=1):
        name = draft.get("person_name") or "Unknown"
        job = _job(draft)
        header = f"{index}. {name}" + (f"  —  {job}" if job != "—" else "")
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
            st.markdown("**Message:**")
            st.code(draft.get("message") or "", language="text")


main()
