"""The application orchestrator.

Ties every module together into the end-to-end flow:

    discover -> extract -> deduplicate -> filter -> score -> select resume ->
    (AI advise) -> Easy Apply -> record

It enforces the per-run, per-company and daily limits, honours dry-run and
interactive-approval modes, and persists everything to the database.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from linkedin_easy_apply.ai import AIProvider, build_provider
from linkedin_easy_apply.answers.cover_letter import CoverLetterGenerator
from linkedin_easy_apply.answers.resolver import AnswerResolver
from linkedin_easy_apply.answers.resume_selector import ResumeChoice, ResumeSelector
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.browser import BrowserManager
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms import (
    EasyApplyWorkflow,
    FormFieldDetector,
    FormFiller,
    WorkflowSettings,
)
from linkedin_easy_apply.forms.easy_apply import AnsweredQuestion, ApplyResult, ApplyStatus
from linkedin_easy_apply.jobs import Job, JobExtractor, JobSearch
from linkedin_easy_apply.parser import QuestionParser
from linkedin_easy_apply.scoring import ScoringEngine
from linkedin_easy_apply.utils.paths import ensure_dir
from linkedin_easy_apply.utils.screenshots import ScreenshotManager

UnknownHandler = Callable[[str, "Path | None"], "str | None"]
ConfirmHandler = Callable[[Job], bool]

_COVER_DIR = Path("generated/cover_letters")


@dataclass(slots=True)
class RunSummary:
    """Aggregate outcome of an orchestrated run."""

    run_id: int
    mode: str
    scanned: int = 0
    applied: int = 0
    skipped: int = 0
    failed: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)

    def note_skip(self, reason: str) -> None:
        self.skipped += 1
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1


class Orchestrator:
    """Coordinate a full apply/scan run."""

    def __init__(
        self,
        config: AppConfig,
        database: Database,
        answers: AnswerStore,
        *,
        on_unknown: UnknownHandler | None = None,
        on_confirm_submit: ConfirmHandler | None = None,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self._config = config
        self._db = database
        self._answers = answers
        self._on_unknown = on_unknown
        self._on_confirm = on_confirm_submit

        self._parser = QuestionParser(
            skills=answers.known_skills(), fuzzy_threshold=config.answers.fuzzy_threshold
        )
        self._resolver = AnswerResolver(answers)
        self._scoring = ScoringEngine(config.scoring)
        self._resume_selector = ResumeSelector(config.resume)
        self._cover = CoverLetterGenerator()
        self._ai = ai_provider or build_provider(config.ai)
        self._screenshots = ScreenshotManager(
            config.screenshots.directory, config.screenshots.enabled
        )

    # -- public API -----------------------------------------------------------
    def run(
        self,
        *,
        mode: str = "apply",
        dry_run: bool | None = None,
        interactive: bool | None = None,
        limit: int | None = None,
    ) -> RunSummary:
        dry_run = self._config.run.dry_run if dry_run is None else dry_run
        interactive = self._config.run.interactive if interactive is None else interactive
        max_per_run = limit or self._config.jobs.max_per_run

        searches = self._config.search.enabled_searches
        if not searches:
            raise ValueError("No enabled searches configured. Add entries under 'search.searches'.")

        run_mode = "scan" if mode == "scan" else ("dry_run" if dry_run else "apply")
        run_id = self._db.start_run(run_mode, [s.name for s in searches])
        summary = RunSummary(run_id=run_id, mode=run_mode)
        logger.info(
            "Run starting: mode={} dry_run={} interactive={} max_per_run={} | "
            "{} enabled search(es): {}",
            run_mode,
            dry_run,
            interactive,
            max_per_run,
            len(searches),
            [s.name for s in searches],
        )

        try:
            with BrowserManager(self._config.browser) as browser:
                self._execute(browser, searches, summary, mode, dry_run, interactive, max_per_run)
            self._db.finish_run(
                run_id,
                "completed",
                scanned=summary.scanned,
                applied=summary.applied,
                skipped=summary.skipped,
                failed=summary.failed,
            )
        except Exception as exc:
            logger.exception("Run failed: {}", exc)
            self._db.log_error(str(exc), context="run", run_id=run_id)
            self._db.finish_run(run_id, "failed", scanned=summary.scanned, applied=summary.applied)
            raise
        return summary

    # -- execution ------------------------------------------------------------
    def _execute(
        self,
        browser: BrowserManager,
        searches: list[Any],
        summary: RunSummary,
        mode: str,
        dry_run: bool,
        interactive: bool,
        max_per_run: int,
    ) -> None:
        search_driver = JobSearch(browser.page, JobExtractor())
        settings = WorkflowSettings(
            dry_run=dry_run,
            interactive=interactive,
            pause_on_unknown=self._config.run.pause_on_unknown_question,
        )
        scan_cap = max(max_per_run * 5, 30)

        for entry in searches:
            if summary.applied >= max_per_run and mode != "scan":
                break
            logger.info("=== Search: {} ===", entry.name)
            for job in search_driver.iterate(entry.url, entry.name, scan_cap):
                summary.scanned += 1
                self._process_job(browser, job, summary, mode, settings, max_per_run)
                if mode != "scan" and summary.applied >= max_per_run:
                    logger.info("Reached max applications for this run ({})", max_per_run)
                    return
                if self._config.jobs.max_daily and (
                    self._db.count_applications_today() >= self._config.jobs.max_daily
                ):
                    logger.info("Reached daily application limit ({})", self._config.jobs.max_daily)
                    return

    def _process_job(
        self,
        browser: BrowserManager,
        job: Job,
        summary: RunSummary,
        mode: str,
        settings: WorkflowSettings,
        max_per_run: int,
    ) -> None:
        job_id = self._db.upsert_job(job.to_db_dict(), summary.run_id)
        logger.info("Job: {}", job.summary)

        gate = self._pre_apply_checks(job)
        score = self._scoring.score(job.title or "", job.description)
        self._db.record_score(job_id, score.score, score.threshold, score.passed, score.breakdown)
        logger.debug(
            "Scored '{}': {} vs threshold {} -> {} (breakdown: {})",
            job.title,
            score.score,
            score.threshold,
            "PASS" if score.passed else "FAIL",
            score.breakdown,
        )

        if gate is not None:
            summary.note_skip(gate)
            logger.info("Skip ({}) - {}", gate, job.summary)
            return
        if not score.passed:
            summary.note_skip("below_threshold")
            logger.info("Skip (score {} < {}) - {}", score.score, score.threshold, job.summary)
            return

        resume = self._resume_selector.select(job.title or "", job.description)
        if resume is not None:
            logger.debug("Selected resume '{}' for '{}'", resume.name, job.title)
        ai_advice = self._advise(job, job_id)
        if ai_advice is False:
            summary.note_skip("ai_advised_against")
            return

        if mode == "scan":
            summary.note_skip("scan_only")
            return

        self._attempt_application(browser, job, job_id, resume, summary, settings)

    def _pre_apply_checks(self, job: Job) -> str | None:
        """Return a skip reason, or ``None`` if the job passes the gates."""
        cfg = self._config.jobs
        company = (job.company or "").lower()
        title = (job.title or "").lower()

        if not job.easy_apply:
            return "not_easy_apply"
        if job.already_applied or self._db.has_applied_to_url(job.url):
            return "already_applied"
        if (
            job.company
            and job.title
            and self._db.has_applied_to_company_role(job.company, job.title)
        ):
            return "duplicate_company_role"
        if cfg.whitelist_companies and company not in cfg.whitelist_companies:
            return "not_whitelisted"
        if company and company in cfg.blacklist_companies:
            return "blacklisted"
        text = f"{title} {(job.description or '').lower()}"
        if cfg.exclude_keywords and any(k in text for k in cfg.exclude_keywords):
            return "excluded_keyword"
        if cfg.include_keywords and not any(k in text for k in cfg.include_keywords):
            return "missing_include_keyword"
        if (
            job.company
            and self._db.count_applications_for_company(job.company) >= cfg.max_per_company
        ):
            return "company_limit"
        return None

    def _advise(self, job: Job, job_id: int) -> bool | None:
        """Run the AI advisor. Returns ``False`` only when it advises against."""
        if self._ai.name == "none":
            return None
        try:
            result = self._ai.evaluate_job(
                job_title=job.title or "", job_description=job.description or ""
            )
        except Exception as exc:  # pragma: no cover - optional
            logger.warning("AI advisor error: {}", exc)
            return None
        self._db.record_ai_result(job_id, result.to_db_dict())
        if result.match_percent is not None:
            logger.info("AI match {:.0f}% - {}", result.match_percent, result.recommendation)
        return False if result.should_apply is False else None

    def _attempt_application(
        self,
        browser: BrowserManager,
        job: Job,
        job_id: int,
        resume: ResumeChoice | None,
        summary: RunSummary,
        settings: WorkflowSettings,
    ) -> None:
        resume_id = self._db.register_resume(resume.name, str(resume.path)) if resume else None
        application_id = self._db.create_application(job_id, summary.run_id, resume_id, "pending")

        cover_path = self._maybe_cover_letter(job)
        workflow = EasyApplyWorkflow(
            browser.page,
            self._parser,
            self._resolver,
            FormFieldDetector(),
            FormFiller(self._config.answers.fuzzy_threshold),
            self._screenshots,
            settings,
            on_unknown=self._on_unknown,
            on_confirm_submit=(
                functools.partial(self._on_confirm, job) if self._on_confirm else None
            ),
        )

        try:
            result = workflow.apply(
                resume_path=str(resume.path) if resume else None,
                cover_letter_path=cover_path,
            )
        except Exception as exc:
            logger.exception("Application error for {}: {}", job.summary, exc)
            self._db.log_error(str(exc), context="apply", run_id=summary.run_id, job_id=job_id)
            self._db.update_application(
                application_id, status="failed", reason=str(exc), finished=True
            )
            summary.failed += 1
            return

        self._persist_result(application_id, result, summary, job)

    def _persist_result(
        self, application_id: int, result: ApplyResult, summary: RunSummary, job: Job
    ) -> None:
        self._db.update_application(
            application_id,
            status=result.status.value,
            reason=result.reason,
            steps=result.steps,
            screenshot=result.screenshot,
            finished=True,
        )
        self._record_answers(application_id, result.answers)

        if result.status is ApplyStatus.SUBMITTED:
            summary.applied += 1
            logger.success("Applied to {}", job.summary)
            self._maybe_pause(summary)
        elif result.status is ApplyStatus.FAILED:
            summary.failed += 1
        else:
            summary.note_skip(result.status.value)

    def _record_answers(self, application_id: int, answers: list[AnsweredQuestion]) -> None:
        for answer in answers:
            question_id = self._db.upsert_question(
                answer.question, answer.normalized, answer.category, answer.skill
            )
            self._db.record_application_answer(
                application_id, answer.question, answer.value, answer.source, question_id
            )
            # Learn manually provided answers so future runs resolve them automatically.
            if answer.source == "manual" and answer.value:
                self._db.learn_answer(question_id, answer.value, "manual")

    def _maybe_cover_letter(self, job: Job) -> str | None:
        try:
            context = {
                "company": job.company or "your company",
                "role": job.title or "this role",
                "candidate_name": self._answers.get_str("full_name", ""),
                "years_experience": self._answers.get("years_experience"),
                "tech_stack": self._scoring.score(
                    job.title or "", job.description
                ).matched_keywords,
                "summary": self._answers.get_str("summary"),
            }
            ensure_dir(_COVER_DIR)
            return str(self._cover.render_to_file(context, _COVER_DIR))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Cover letter generation skipped: {}", exc)
            return None

    def _maybe_pause(self, summary: RunSummary) -> None:
        pause_after = self._config.jobs.pause_after
        if pause_after and summary.applied % pause_after == 0:
            logger.info(
                "Pausing {:.0f}s after {} applications",
                self._config.jobs.pause_seconds,
                summary.applied,
            )
            import time

            time.sleep(self._config.jobs.pause_seconds)
