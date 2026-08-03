"""SQLite persistence layer.

A thin repository over ``sqlite3`` exposing intention-revealing methods for the
rest of the application. Connections are short-lived and created per operation
so the object is safe to share across the orchestrator and CLI.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

_SCHEMA_PATH = Path(__file__).resolve().parent / "sql" / "schema.sql"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _last_id(cur: sqlite3.Cursor) -> int:
    """Return the row id of the last INSERT, guarding against a missing value."""
    if cur.lastrowid is None:  # pragma: no cover - defensive
        raise RuntimeError("INSERT did not produce a rowid")
    return cur.lastrowid


class Database:
    """Repository around the SQLite database defined in ``sql/schema.sql``."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # -- connection management ------------------------------------------------
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection, committing on success."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Apply the schema. Safe to call repeatedly."""
        schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)
        logger.debug("Database initialised at {}", self.path)

    # -- runs -----------------------------------------------------------------
    def start_run(self, mode: str, searches: list[str] | None = None) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO runs (mode, searches, status, started_at) VALUES (?, ?, 'running', ?)",
                (mode, json.dumps(searches or []), _now()),
            )
            return _last_id(cur)

    def finish_run(
        self,
        run_id: int,
        status: str = "completed",
        *,
        scanned: int = 0,
        applied: int = 0,
        skipped: int = 0,
        failed: int = 0,
        notes: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE runs
                   SET status=?, jobs_scanned=?, jobs_applied=?, jobs_skipped=?,
                       jobs_failed=?, notes=?, finished_at=?
                   WHERE id=?""",
                (status, scanned, applied, skipped, failed, notes, _now(), run_id),
            )

    # -- jobs -----------------------------------------------------------------
    def upsert_job(self, job: dict[str, Any], run_id: int | None = None) -> int:
        """Insert or update a job keyed by URL; returns the job id."""
        columns = (
            "external_id title company location workplace_type employment_type "
            "experience_level applicants posting_age salary description recruiter "
            "easy_apply already_applied search_name"
        ).split()
        # These columns are NOT NULL in the schema, so coerce missing values to 0.
        not_null_defaults = {"easy_apply": False, "already_applied": False}
        values: list[Any] = []
        for col in columns:
            value = job.get(col, not_null_defaults.get(col))
            values.append(int(value) if isinstance(value, bool) else value)
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM jobs WHERE url=?", (job["url"],)).fetchone()
            if existing:
                assignments = ", ".join(f"{c}=?" for c in columns)
                conn.execute(
                    f"UPDATE jobs SET {assignments}, updated_at=? WHERE id=?",
                    (*values, _now(), existing["id"]),
                )
                return int(existing["id"])
            placeholders = ", ".join(["?"] * (len(columns) + 3))
            cur = conn.execute(
                f"INSERT INTO jobs (url, discovered_run, discovered_at, {', '.join(columns)}) "
                f"VALUES ({placeholders})",
                (job["url"], run_id, _now(), *values),
            )
            return _last_id(cur)

    def get_job_by_url(self, url: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE url=?", (url,)).fetchone()
            return dict(row) if row else None

    def has_applied_to_url(self, url: str) -> bool:
        """True if we previously *submitted* an application for this job URL."""
        with self.connect() as conn:
            row = conn.execute(
                """SELECT 1 FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE j.url=? AND a.status='submitted' LIMIT 1""",
                (url,),
            ).fetchone()
            return row is not None

    def has_applied_to_company_role(self, company: str, title: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT 1 FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE lower(j.company)=lower(?) AND lower(j.title)=lower(?)
                     AND a.status='submitted' LIMIT 1""",
                (company, title),
            ).fetchone()
            return row is not None

    # -- scores ---------------------------------------------------------------
    def record_score(
        self, job_id: int, score: int, threshold: int, passed: bool, breakdown: dict[str, int]
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO scores (job_id, score, threshold, passed, breakdown, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, score, threshold, int(passed), json.dumps(breakdown), _now()),
            )
            return _last_id(cur)

    # -- resumes --------------------------------------------------------------
    def register_resume(self, name: str, path: str) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM resumes WHERE name=?", (name,)).fetchone()
            if row:
                conn.execute("UPDATE resumes SET path=? WHERE id=?", (path, row["id"]))
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO resumes (name, path, created_at) VALUES (?, ?, ?)",
                (name, path, _now()),
            )
            return _last_id(cur)

    # -- applications ---------------------------------------------------------
    def create_application(
        self, job_id: int, run_id: int | None, resume_id: int | None, status: str = "pending"
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO applications (job_id, run_id, resume_id, status, started_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(job_id, run_id) DO UPDATE SET status=excluded.status",
                (job_id, run_id, resume_id, status, _now()),
            )
            if cur.lastrowid:
                return _last_id(cur)
            row = conn.execute(
                "SELECT id FROM applications WHERE job_id=? AND run_id IS ?", (job_id, run_id)
            ).fetchone()
            return int(row["id"])

    def update_application(
        self,
        application_id: int,
        *,
        status: str | None = None,
        reason: str | None = None,
        steps: int | None = None,
        screenshot: str | None = None,
        finished: bool = False,
    ) -> None:
        sets: list[str] = []
        params: list[Any] = []
        if status is not None:
            sets.append("status=?")
            params.append(status)
        if reason is not None:
            sets.append("reason=?")
            params.append(reason)
        if steps is not None:
            sets.append("steps=?")
            params.append(steps)
        if screenshot is not None:
            sets.append("screenshot=?")
            params.append(screenshot)
        if finished:
            sets.append("finished_at=?")
            params.append(_now())
        if not sets:
            return
        params.append(application_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE applications SET {', '.join(sets)} WHERE id=?", params)

    def count_applications_today(self, status: str = "submitted") -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM applications "
                "WHERE status=? AND date(started_at)=date('now', 'localtime')",
                (status,),
            ).fetchone()
            return int(row["n"])

    def count_applications_for_company(self, company: str, status: str = "submitted") -> int:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) AS n FROM applications a JOIN jobs j ON a.job_id=j.id
                   WHERE lower(j.company)=lower(?) AND a.status=?""",
                (company, status),
            ).fetchone()
            return int(row["n"])

    # -- questions & answers --------------------------------------------------
    def upsert_question(
        self,
        text: str,
        normalized: str,
        category: str | None = None,
        skill: str | None = None,
        answer_type: str | None = None,
    ) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id FROM questions WHERE normalized=?", (normalized,)
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE questions SET seen_count=seen_count+1, last_seen=?,"
                    " category=COALESCE(?, category), skill=COALESCE(?, skill),"
                    " answer_type=COALESCE(?, answer_type) WHERE id=?",
                    (_now(), category, skill, answer_type, row["id"]),
                )
                return int(row["id"])
            cur = conn.execute(
                "INSERT INTO questions (text, normalized, category, skill, answer_type,"
                " first_seen, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (text, normalized, category, skill, answer_type, _now(), _now()),
            )
            return _last_id(cur)

    def get_known_answer(self, normalized: str) -> str | None:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT ans.value FROM answers ans JOIN questions q ON ans.question_id=q.id
                   WHERE q.normalized=? AND ans.value IS NOT NULL""",
                (normalized,),
            ).fetchone()
            return row["value"] if row else None

    def learn_answer(self, question_id: int, value: str, source: str = "manual") -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO answers (question_id, value, source, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(question_id) DO UPDATE SET value=excluded.value,"
                " source=excluded.source, updated_at=excluded.updated_at",
                (question_id, value, source, _now(), _now()),
            )

    def record_application_answer(
        self,
        application_id: int,
        question_text: str,
        value: str | None,
        source: str,
        question_id: int | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO application_answers (application_id, question_id, question_text,"
                " value, source, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (application_id, question_id, question_text, value, source, _now()),
            )

    def application_answers(self, application_id: int) -> list[dict[str, Any]]:
        """Return every field asked & answered for one application, in order.

        Powers the dashboard drill-down: each row is the exact question text, the
        value that was submitted, and where it came from (yaml/manual/ai/...).
        """
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT question_text, value, source, created_at"
                " FROM application_answers WHERE application_id=? ORDER BY id",
                (application_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def unanswered_questions(self, limit: int = 200) -> list[dict[str, Any]]:
        """Aggregate questions the tool has *never* been able to answer.

        Powers the dashboard's "needs attention" view. A question qualifies only
        when it was left blank in an application AND never received a value in
        *any* application — a genuine gap, not merely a field LinkedIn had
        already prefilled (e.g. email / phone country code, which show up blank
        on one detection pass but carry a value on another and are therefore
        excluded). For each gap we report how many applications it was blank in,
        how many of those ended blocked (``failed``/``aborted`` — typically
        "No progress between steps"), the known category/answer type, and when
        it was last seen. Ordered by blocking impact so the costliest gaps to
        fix appear first.
        """
        sql = """
            WITH per_app AS (
                SELECT aa.application_id AS app_id,
                       lower(trim(aa.question_text)) AS qkey,
                       MAX(aa.question_text) AS question,
                       MAX(aa.question_id)   AS question_id,
                       MAX(CASE WHEN aa.value IS NOT NULL AND trim(aa.value) <> ''
                                THEN 1 ELSE 0 END) AS has_value,
                       MAX(aa.created_at) AS last_seen
                FROM application_answers aa
                WHERE aa.question_text IS NOT NULL AND trim(aa.question_text) <> ''
                GROUP BY aa.application_id, lower(trim(aa.question_text))
            )
            SELECT p.question AS question,
                   SUM(CASE WHEN p.has_value = 0 THEN 1 ELSE 0 END) AS blank_in_apps,
                   COUNT(CASE WHEN p.has_value = 0
                              AND a.status IN ('failed', 'aborted')
                              THEN 1 END) AS blocked_apps,
                   MAX(q.category)    AS category,
                   MAX(q.answer_type) AS answer_type,
                   MAX(p.last_seen)   AS last_seen
            FROM per_app p
            JOIN applications a ON p.app_id = a.id
            LEFT JOIN questions q ON p.question_id = q.id
            GROUP BY p.qkey
            HAVING SUM(p.has_value) = 0
            ORDER BY blocked_apps DESC, blank_in_apps DESC, last_seen DESC
            LIMIT ?
        """
        with self.connect() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def blocked_applications(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return applications that ended blocked (``failed``/``aborted``).

        For the dashboard's "needs attention" view: each row is a job whose Easy
        Apply run did not complete, with a *short* reason (LinkedIn/Playwright
        failure text can be thousands of characters, so it is trimmed to its
        first line via ``reason_short``), the step it stopped on, and how many
        distinct questions were left unanswered in that attempt — the usual
        culprit behind "No progress between steps".
        """
        sql = """
            SELECT a.id, a.started_at, a.status, a.reason, a.steps,
                   j.title, j.company, j.url,
                   (SELECT COUNT(*) FROM (
                        SELECT 1
                        FROM application_answers aa
                        WHERE aa.application_id = a.id
                          AND aa.question_text IS NOT NULL
                          AND trim(aa.question_text) <> ''
                        GROUP BY lower(trim(aa.question_text))
                        HAVING MAX(CASE WHEN aa.value IS NOT NULL AND trim(aa.value) <> ''
                                        THEN 1 ELSE 0 END) = 0
                   )) AS unanswered_count
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE a.status IN ('failed', 'aborted')
            ORDER BY a.started_at DESC
            LIMIT ?
        """
        with self.connect() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            reason = record.get("reason") or ""
            first_line = reason.splitlines()[0].strip() if reason else ""
            record["reason_short"] = first_line[:197] + "…" if len(first_line) > 200 else first_line
            result.append(record)
        return result

    # -- AI results -----------------------------------------------------------
    def record_ai_result(self, job_id: int, result: dict[str, Any]) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO ai_results (job_id, match_percent, missing_skills, recommendation,"
                " reasons, suggested_resume, should_apply, raw, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    result.get("match_percent"),
                    json.dumps(result.get("missing_skills", [])),
                    result.get("recommendation"),
                    json.dumps(result.get("reasons", [])),
                    result.get("suggested_resume"),
                    (
                        None
                        if result.get("should_apply") is None
                        else int(bool(result["should_apply"]))
                    ),
                    json.dumps(result.get("raw")) if result.get("raw") is not None else None,
                    _now(),
                ),
            )
            return _last_id(cur)

    # -- errors ---------------------------------------------------------------
    def log_error(
        self,
        message: str,
        *,
        context: str | None = None,
        traceback: str | None = None,
        run_id: int | None = None,
        job_id: int | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO errors (run_id, job_id, context, message, traceback, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, job_id, context, message, traceback, _now()),
            )

    # -- outreach -------------------------------------------------------------
    def has_messaged_person(self, person_key: str) -> bool:
        """True if we already sent an outreach message to this person."""
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM outreach_messages WHERE person_key=? AND status='sent' LIMIT 1",
                (person_key,),
            ).fetchone()
            return row is not None

    def outreach_drafts(self, run_id: int | None = None) -> list[dict[str, Any]]:
        """Return drafted (not-yet-sent) outreach records for the end-of-run report.

        Each row carries the recruiter's name, profile URL and drafted message,
        the job title/company (joined from ``jobs``) for context, and the résumé
        that was submitted for that job (joined via the matching application, so
        the user knows which file to attach). When *run_id* is given, only that
        run's drafts are returned; otherwise every draft on record is returned
        (newest last), ordered by insertion.
        """
        sql = (
            "SELECT o.person_name, o.profile_url, o.message, o.created_at,"
            " j.title AS job_title, j.company AS job_company,"
            " r.name AS resume_name, r.path AS resume_path"
            " FROM outreach_messages o"
            " LEFT JOIN jobs j ON o.job_id = j.id"
            " LEFT JOIN applications a ON a.job_id = o.job_id AND a.run_id IS o.run_id"
            " LEFT JOIN resumes r ON a.resume_id = r.id"
            " WHERE o.status = 'drafted'"
        )
        params: list[Any] = []
        if run_id is not None:
            sql += " AND o.run_id = ?"
            params.append(run_id)
        sql += " ORDER BY o.id"
        keys = (
            "person_name",
            "profile_url",
            "message",
            "created_at",
            "job_title",
            "job_company",
            "resume_name",
            "resume_path",
        )
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def record_outreach(
        self,
        *,
        person_key: str,
        person_name: str | None = None,
        profile_url: str | None = None,
        message: str | None = None,
        status: str = "sent",
        run_id: int | None = None,
        job_id: int | None = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO outreach_messages (run_id, job_id, person_name, person_key,"
                " profile_url, message, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (run_id, job_id, person_name, person_key, profile_url, message, status, _now()),
            )
            return _last_id(cur)

    # -- stats ----------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        """Aggregate counts used by the CLI ``stats`` command and dashboard."""
        with self.connect() as conn:

            def scalar(sql: str, params: tuple[Any, ...] = ()) -> int:
                return int(conn.execute(sql, params).fetchone()[0])

            data: dict[str, Any] = {
                "total_jobs": scalar("SELECT COUNT(*) FROM jobs"),
                "easy_apply_jobs": scalar("SELECT COUNT(*) FROM jobs WHERE easy_apply=1"),
                "applications_total": scalar("SELECT COUNT(*) FROM applications"),
                "applications_submitted": scalar(
                    "SELECT COUNT(*) FROM applications WHERE status='submitted'"
                ),
                "applications_today": scalar(
                    "SELECT COUNT(*) FROM applications "
                    "WHERE status='submitted' AND date(started_at)=date('now', 'localtime')"
                ),
                "applications_failed": scalar(
                    "SELECT COUNT(*) FROM applications WHERE status='failed'"
                ),
                "runs": scalar("SELECT COUNT(*) FROM runs"),
                "errors": scalar("SELECT COUNT(*) FROM errors"),
                "distinct_questions": scalar("SELECT COUNT(*) FROM questions"),
            }
            data["top_companies"] = [
                dict(r)
                for r in conn.execute("""SELECT j.company AS company, COUNT(*) AS applications
                       FROM applications a JOIN jobs j ON a.job_id=j.id
                       WHERE a.status='submitted' AND j.company IS NOT NULL
                       GROUP BY lower(j.company) ORDER BY applications DESC LIMIT 10""").fetchall()
            ]
            return data

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Run an arbitrary read query and return a list of dict rows."""
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
