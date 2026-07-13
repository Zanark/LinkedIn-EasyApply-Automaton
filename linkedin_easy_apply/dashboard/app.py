"""Streamlit dashboard for the LinkedIn Easy Apply Automaton.

Run via ``lea dashboard`` (which sets ``LEA_CONFIG``) or directly with
``streamlit run linkedin_easy_apply/dashboard/app.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

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
            st.dataframe(stats["top_companies"], use_container_width=True, hide_index=True)
        else:
            st.info("No applications yet.")

    with right:
        st.subheader("Most frequent questions")
        questions = db.query(
            "SELECT text AS question, category, seen_count FROM questions "
            "ORDER BY seen_count DESC LIMIT 15"
        )
        if questions:
            st.dataframe(questions, use_container_width=True, hide_index=True)
        else:
            st.info("No questions recorded yet.")

    st.subheader("Recent applications")
    applications = db.query("""SELECT a.started_at, j.title, j.company, a.status, a.reason, a.steps
           FROM applications a JOIN jobs j ON a.job_id = j.id
           ORDER BY a.started_at DESC LIMIT 50""")
    if applications:
        st.dataframe(applications, use_container_width=True, hide_index=True)
    else:
        st.info("No applications recorded yet. Run 'lea apply' to get started.")

    st.subheader("Resume usage")
    resumes = db.query("""SELECT r.name, COUNT(a.id) AS uses FROM resumes r
           LEFT JOIN applications a ON a.resume_id = r.id
           GROUP BY r.id ORDER BY uses DESC""")
    if resumes:
        st.bar_chart({row["name"]: row["uses"] for row in resumes})


main()
