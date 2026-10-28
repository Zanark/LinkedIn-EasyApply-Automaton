"""The application orchestrator.

Ties every module together into the end-to-end flow:

    discover -> extract -> deduplicate -> filter -> score -> select resume ->
    (AI advise) -> Easy Apply -> record

It enforces the per-run, per-company and daily limits, honours dry-run and
interactive-approval modes, and persists everything to the database.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from linkedin_easy_apply.ai import AIProvider, build_provider
from linkedin_easy_apply.answers.cover_letter import CoverLetterGenerator, RenderedCoverLetter
from linkedin_easy_apply.answers.dynamic_resume import DynamicResumeBuilder
from linkedin_easy_apply.answers.hiring_message import HiringTeamMessenger
from linkedin_easy_apply.answers.hiring_report import render_outreach_report
from linkedin_easy_apply.answers.resolver import AnswerResolver, _parse_amount
from linkedin_easy_apply.answers.resume_selector import ResumeChoice, ResumeSelector
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.browser import BrowserManager
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.connect.service import ConnectionInviteService, ConnectSummary
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.forms import (
    EasyApplyWorkflow,
    FormFieldDetector,
    FormFiller,
    WorkflowSettings,
)
from linkedin_easy_apply.forms.easy_apply import AnsweredQuestion, ApplyResult, ApplyStatus
from linkedin_easy_apply.forms.outreach import ApproveHandler, HiringTeamOutreach
from linkedin_easy_apply.jobs import Job, JobExtractor, JobSearch
from linkedin_easy_apply.jobs.search import paginated_url
from linkedin_easy_apply.jobs.seniority import DEFAULT_SENIORITY, detect_seniority
from linkedin_easy_apply.parser import QuestionParser
from linkedin_easy_apply.scoring import ScoringEngine
from linkedin_easy_apply.utils.paths import ensure_dir
from linkedin_easy_apply.utils.screenshots import ScreenshotManager

UnknownHandler = Callable[[str, "Path | None"], "str | None"]
ConfirmHandler = Callable[[Job], bool]

_COVER_DIR = Path("generated/coverletter")


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
    outreach_report: Path | None = None
    connection_notes_sent: int = 0
    connect_summary: ConnectSummary | None = None
    platform_daily_limit_hit: bool = False

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
        on_approve_message: ApproveHandler | None = None,
        message_hiring_team: bool | None = None,
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
        self._dynamic_resume = self._make_dynamic_resume()
        self._screenshots = ScreenshotManager(
            config.screenshots.directory, config.screenshots.enabled
        )
        self._outreach = self._make_outreach(on_approve_message, message_hiring_team)

    def _make_outreach(
        self, on_approve: ApproveHandler | None, message_flag: bool | None
    ) -> HiringTeamOutreach | None:
        """Build the post-apply hiring-team messenger, or ``None`` if disabled.

        Outreach runs whenever it is enabled -- via ``outreach.enabled`` or the
        ``--message-hiring-team`` override (``message_flag``); the flag wins when
        set. The default ``draft`` mode needs no approval handler and simply
        collects contacts for the end-of-run report, so it runs even under
        ``--yes``. Only ``mode: send`` needs a handler; without one it degrades
        to ``draft`` so the report is still produced."""
        cfg = self._config.outreach
        enabled = cfg.enabled if message_flag is None else message_flag
        if not enabled:
            return None
        mode = str(cfg.mode)
        if mode == "send" and on_approve is None:
            logger.info(
                "Outreach: 'send' mode needs interactive approval; collecting drafts "
                "for the end-of-run report instead"
            )
            mode = "draft"
        return HiringTeamOutreach(
            HiringTeamMessenger(cfg.template, note_template_path=cfg.note_template),
            mode=mode,
            on_approve=on_approve,
            has_messaged=self._db.has_messaged_person,
            record=self._db.record_outreach,
            max_per_run=cfg.max_per_run,
            skip_if_messaged=cfg.skip_if_messaged,
        )

    def _make_dynamic_resume(self) -> DynamicResumeBuilder | None:
        """Construct the optional per-job resume builder, or ``None`` if disabled."""
        cfg = self._config.resume.builder
        if not cfg.enabled:
            return None
        try:
            return DynamicResumeBuilder(
                cfg,
                resume_dir=Path(self._config.resume.directory),
                ai=self._ai,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Dynamic resume builder unavailable: {}", exc)
            return None

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

        reapply = mode == "reapply"
        targets: list[dict[str, Any]] = []
        searches: list[Any] = []
        if reapply:
            targets = self._db.reapply_targets()
            max_per_run = limit or len(targets) or 1
            search_names = ["reapply"]
            run_mode = "dry_run" if dry_run else "reapply"
        else:
            max_per_run = limit or self._config.jobs.max_per_run
            searches = self._config.search.enabled_searches
            if not searches:
                raise ValueError(
                    "No enabled searches configured. Add entries under 'search.searches'."
                )
            search_names = [s.name for s in searches]
            run_mode = "scan" if mode == "scan" else ("dry_run" if dry_run else "apply")

        run_id = self._db.start_run(run_mode, search_names)
        summary = RunSummary(run_id=run_id, mode=run_mode)
        if reapply:
            logger.info(
                "Reapply starting: dry_run={} interactive={} | {} failed/aborted job(s) to retry",
                dry_run,
                interactive,
                len(targets),
            )
        else:
            logger.info(
                "Run starting: mode={} dry_run={} interactive={} max_per_run={} | "
                "{} enabled search(es): {}",
                run_mode,
                dry_run,
                interactive,
                max_per_run,
                len(searches),
                search_names,
            )

        proceed_connect = True
        try:
            with BrowserManager(self._config.browser) as browser:
                if reapply:
                    self._execute_reapply(
                        browser, targets, summary, dry_run, interactive, max_per_run
                    )
                else:
                    self._execute(
                        browser, searches, summary, mode, dry_run, interactive, max_per_run
                    )
            self._db.finish_run(
                run_id,
                "completed",
                scanned=summary.scanned,
                applied=summary.applied,
                skipped=summary.skipped,
                failed=summary.failed,
            )
        except KeyboardInterrupt:
            proceed_connect = False
            logger.warning(
                "Interrupted by Ctrl+C - shutting down gracefully "
                "(scanned={}, applied={}, skipped={}, failed={})",
                summary.scanned,
                summary.applied,
                summary.skipped,
                summary.failed,
            )
            self._db.finish_run(
                run_id,
                "aborted",
                scanned=summary.scanned,
                applied=summary.applied,
                skipped=summary.skipped,
                failed=summary.failed,
                notes="interrupted by user (Ctrl+C)",
            )
        except Exception as exc:
            proceed_connect = False
            logger.exception("Run failed: {}", exc)
            self._db.log_error(str(exc), context="run", run_id=run_id)
            self._db.finish_run(run_id, "failed", scanned=summary.scanned, applied=summary.applied)
            raise
        finally:
            self._emit_outreach_report(run_id, summary)
            if proceed_connect and mode != "scan":
                self._maybe_send_connection_invites(run_id, summary)
            self._cleanup_screenshots()
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
        page_size = max(1, self._config.jobs.search_page_size)
        max_pages = max(1, self._config.jobs.max_search_pages)
        seen_ids: set[str] = set()

        for entry in searches:
            if self._reached_run_target(summary, mode, max_per_run):
                break
            logger.info("=== Search: {} ===", entry.name)
            # Paginate through the search's result pages (page 0, 25, 50, ...) so a
            # run can gather enough jobs to actually reach the submission target even
            # when most postings are skipped or fail. Stops early on target/daily cap
            # or when a page yields no new jobs (the search is exhausted).
            for page in range(max_pages):
                if self._reached_run_target(summary, mode, max_per_run):
                    logger.info("Reached run target ({}) for this run", max_per_run)
                    return
                if self._daily_limit_reached():
                    logger.info("Reached daily application limit ({})", self._config.jobs.max_daily)
                    return
                page_url = paginated_url(entry.url, page * page_size)
                new_jobs = 0
                for job in search_driver.iterate(page_url, entry.name, page_size):
                    key = job.external_id or job.url
                    if key and key in seen_ids:
                        continue
                    if key:
                        seen_ids.add(key)
                    new_jobs += 1
                    summary.scanned += 1
                    self._process_job(browser, job, summary, mode, settings, max_per_run)
                    if summary.platform_daily_limit_hit:
                        logger.warning(
                            "Stopping run: LinkedIn's daily submission cap was reached "
                            "(try again tomorrow)."
                        )
                        return
                    if self._reached_run_target(summary, mode, max_per_run):
                        logger.info("Reached run target ({}) for this run", max_per_run)
                        return
                    if self._daily_limit_reached():
                        logger.info(
                            "Reached daily application limit ({})",
                            self._config.jobs.max_daily,
                        )
                        return
                if new_jobs == 0:
                    logger.info(
                        "Search '{}' exhausted after {} page(s) - no more new jobs",
                        entry.name,
                        page + 1,
                    )
                    break

        if mode != "scan" and summary.applied < max_per_run:
            logger.warning(
                "Run ended with {}/{} submission(s): the searches ran out of new matching "
                "jobs{}. Broaden search.searches, raise jobs.max_search_pages, or lower "
                "--limit to reach the target.",
                summary.applied,
                max_per_run,
                " or the daily cap was hit" if self._daily_limit_reached() else "",
            )

    def _reached_run_target(self, summary: RunSummary, mode: str, max_per_run: int) -> bool:
        """The crawl's stop condition. ``--limit`` (``max_per_run``) counts
        *successful submissions* in apply/reapply mode, so skipped, failed and
        aborted jobs never consume the budget; in scan mode there are no
        submissions, so it counts jobs scanned instead."""
        if mode == "scan":
            return summary.scanned >= max_per_run
        return summary.applied >= max_per_run

    def _daily_limit_reached(self) -> bool:
        """True when today's submissions have reached the configured ``max_daily`` cap."""
        cap = self._config.jobs.max_daily
        return bool(cap) and self._db.count_applications_today() >= cap

    def _execute_reapply(
        self,
        browser: BrowserManager,
        targets: list[dict[str, Any]],
        summary: RunSummary,
        dry_run: bool,
        interactive: bool,
        max_per_run: int,
    ) -> None:
        """Retry a fixed set of previously failed/aborted jobs.

        Unlike :meth:`_execute`, this does not crawl a search: it opens each
        target job by its stored URL and runs the very same per-job pipeline
        (gates → score → resume → Easy Apply). Failed/aborted attempts never set
        the ``submitted`` status, so the ``already_applied`` gate does not fire
        and the job is genuinely retried.
        """
        if not targets:
            logger.info("No failed or aborted applications to reapply to.")
            return
        search_driver = JobSearch(browser.page, JobExtractor())
        settings = WorkflowSettings(
            dry_run=dry_run,
            interactive=interactive,
            pause_on_unknown=self._config.run.pause_on_unknown_question,
        )
        for target in targets:
            if summary.applied >= max_per_run:
                logger.info("Reached reapply limit ({})", max_per_run)
                return
            url = str(target.get("url") or "")
            label = target.get("title") or url
            if not url:
                continue
            logger.info("=== Reapply: {} ===", label)
            job = search_driver.open_job(url)
            if job is None:
                self._note_skip(summary, "reapply_open_failed", target.get("job_id"))
                logger.warning("Skip (could not open) - {}", label)
                continue
            summary.scanned += 1
            self._process_job(browser, job, summary, "apply", settings, max_per_run)
            if summary.platform_daily_limit_hit:
                logger.warning(
                    "Stopping reapply: LinkedIn's daily submission cap was reached "
                    "(try again tomorrow)."
                )
                return
            if self._config.jobs.max_daily and (
                self._db.count_applications_today() >= self._config.jobs.max_daily
            ):
                logger.info("Reached daily application limit ({})", self._config.jobs.max_daily)
                return

    def _note_skip(self, summary: RunSummary, reason: str, job_id: int | None = None) -> None:
        """Count a skip on the summary *and* persist its per-job reason."""
        summary.note_skip(reason)
        self._db.record_skip(summary.run_id, job_id, reason)

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
        logger.info(
            "[SCORE {}] {}/{} | {}",
            "PASS" if score.passed else "FAIL",
            score.score,
            score.threshold,
            job.summary,
        )
        logger.debug(
            "Scored '{}': {} vs threshold {} -> {} (breakdown: {})",
            job.title,
            score.score,
            score.threshold,
            "PASS" if score.passed else "FAIL",
            score.breakdown,
        )

        if gate is not None:
            self._note_skip(summary, gate, job_id)
            logger.info("Skip ({}) - {}", gate, job.summary)
            return
        if not score.passed:
            # scoring.enforce (or --ignore-score) keeps the score as a recorded
            # signal without letting it gate the run.
            if self._config.scoring.enforce:
                self._note_skip(summary, "below_threshold", job_id)
                logger.info("Skip (score {} < {}) - {}", score.score, score.threshold, job.summary)
                return
            logger.info(
                "Score {} < {} but scoring is not enforced - continuing with {}",
                score.score,
                score.threshold,
                job.summary,
            )

        resume = self._resume_selector.select(job.title or "", job.description)
        if resume is not None:
            logger.info(
                "Best resume for '{}': '{}' ({})",
                job.title,
                resume.name,
                resume.reason,
            )
            if mode != "scan":
                self._pause_for_resume_review()
        else:
            logger.warning(
                "No resume matched '{}' - relying on any file already attached", job.title
            )
        ai_advice = self._advise(job, job_id)
        if ai_advice is False:
            self._note_skip(summary, "ai_advised_against", job_id)
            return

        if mode == "scan":
            self._note_skip(summary, "scan_only", job_id)
            return

        tailored = self._tailor_resume(job)
        if tailored is not None:
            resume = tailored

        self._attempt_application(browser, job, job_id, resume, summary, settings)

    def _pause_for_resume_review(self) -> None:
        """Hold briefly after logging the resume pick so it is readable in the
        live log before the application starts (configurable; 0 disables)."""
        seconds = self._config.run.resume_review_pause
        if seconds and seconds > 0:
            logger.debug("Pausing {:.0f}s so the resume pick is readable", seconds)
            time.sleep(seconds)

    def _tailor_resume(self, job: Job) -> ResumeChoice | None:
        """Ask the dynamic builder for a job-tailored resume (or ``None``).

        Only runs when we are actually about to apply, so scans never pay the
        render cost. Any failure returns ``None`` and the statically selected
        resume is used instead.
        """
        if self._dynamic_resume is None or not self._dynamic_resume.enabled:
            return None
        try:
            choice = self._dynamic_resume.tailor_for(job)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Dynamic resume build failed for '{}': {}", job.title, exc)
            return None
        if choice is not None:
            logger.info("Tailored resume '{}' for '{}' ({})", choice.name, job.title, choice.reason)
        return choice

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

    def _apply_expected_ctc_tier(self, job: Job) -> None:
        """Pick the expected-CTC band for this job from its seniority tier and
        hand it to the resolver, so the expected-salary answer scales with the
        role (SDE 3 > SDE 2 > SDE 1). An optional per-tier monthly figure
        (``expected_ctc_monthly_<tier>``) overrides the annual/12 computation.
        Falls back to the default tier when the level cannot be inferred."""
        tier = detect_seniority(job.title, job.experience_level) or DEFAULT_SENIORITY
        annual = _parse_amount(self._tier_value(f"expected_ctc_{tier}", "expected_ctc"))
        monthly = _parse_amount(
            self._tier_value(f"expected_ctc_monthly_{tier}", "expected_ctc_monthly")
        )
        self._resolver.set_expected_ctc(annual, monthly)
        if annual is not None:
            note = f", monthly {int(monthly)}" if monthly is not None else ""
            logger.info(
                "Seniority tier for '{}': {} -> expected CTC {} ({:g} LPA){}",
                job.title,
                tier.upper(),
                int(annual),
                annual / 100000,
                note,
            )
        else:
            logger.warning(
                "No expected-CTC configured for tier {} ('{}') - expected-salary "
                "questions fall back to the stored value",
                tier,
                job.title,
            )

    def _tier_value(self, tier_key: str, fallback_key: str) -> object:
        """Return the tier-specific answer value, falling back to a generic key."""
        value = self._answers.get(tier_key)
        if value is None or not str(value).strip():
            value = self._answers.get(fallback_key)
        return value

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

        self._apply_expected_ctc_tier(job)
        cover = self._maybe_cover_letter(job)
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
            answer_lookup=self._db.get_known_answer,
            override_lookup=self._db.get_answer_override,
        )

        try:
            result = workflow.apply(
                resume_path=str(resume.path) if resume else None,
                cover_letter_path=str(cover.pdf_path) if cover else None,
                cover_letter_text=cover.text if cover else None,
            )
        except KeyboardInterrupt:
            logger.warning("Interrupted mid-application - discarding '{}'", job.summary)
            workflow.discard_open()
            self._db.update_application(
                application_id, status="aborted", reason="interrupted", finished=True
            )
            raise
        except Exception as exc:
            logger.exception("Application error for {}: {}", job.summary, exc)
            self._db.log_error(str(exc), context="apply", run_id=summary.run_id, job_id=job_id)
            self._db.update_application(
                application_id, status="failed", reason=str(exc), finished=True
            )
            summary.failed += 1
            return

        if result.status is ApplyStatus.SUBMITTED:
            # The post-submit "application sent" modal is what carries the "Meet
            # the hiring team" recruiter cards, so message them BEFORE closing it
            # (and before _persist_result's throttle pause could let it auto-close).
            if self._outreach is not None:
                self._reach_out_to_hiring_team(browser, job, job_id, summary.run_id)
            workflow.dismiss_confirmation()
        self._persist_result(application_id, result, summary, job, job_id)

    def _reach_out_to_hiring_team(
        self, browser: BrowserManager, job: Job, job_id: int, run_id: int | None
    ) -> None:
        """Optionally message the job's 'Meet the hiring team' recruiters."""
        if self._outreach is None:
            return
        try:
            base_context = {
                "role": job.title or "this role",
                "company": job.company or "your company",
                "candidate_name": self._answers.get_str("full_name", ""),
                "years_experience": self._answers.get("years_experience"),
                "portfolio_url": (
                    self._answers.get_str("portfolio", "") or self._answers.get_str("website", "")
                ),
                "tech_stack": self._scoring.score(
                    job.title or "", job.description
                ).matched_keywords,
            }
            self._outreach.reach_out(browser.page, base_context, run_id=run_id, job_id=job_id)
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Hiring-team outreach skipped for '{}': {}", job.summary, exc)

    def _emit_outreach_report(self, run_id: int | None, summary: RunSummary) -> None:
        """Write the end-of-run plain-text report of drafted hiring-team messages.

        In ``draft`` mode every contact is recorded but nothing is sent, so this
        turns the run's drafts into a report the user works through by hand. A
        no-op when outreach is disabled or nothing was drafted."""
        if self._outreach is None:
            return
        try:
            drafts = self._db.outreach_drafts(run_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Outreach report: could not query drafts: {}", exc)
            return
        if not drafts:
            logger.info("Outreach: no hiring-team contacts to report this run")
            return
        report = render_outreach_report(drafts, run_id=run_id)
        report_dir = Path(self._config.outreach.report_dir)
        ensure_dir(report_dir)
        path = report_dir / f"outreach_run{run_id}_{datetime.now():%Y%m%d_%H%M%S}.txt"
        try:
            path.write_text(report, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Outreach: could not write report to {}: {}", path, exc)
            return
        summary.outreach_report = path
        logger.success(
            "Outreach: {} hiring-team message(s) drafted - report written to {}",
            len(drafts),
            path,
        )

    def _maybe_send_connection_invites(self, run_id: int | None, summary: RunSummary) -> None:
        """Opt-in end-of-run pass: send this run's pending connection notes.

        Controlled by ``outreach.send_connection_notes`` (OFF by default). The
        apply run's browser has already closed by the time this runs, so
        :class:`ConnectionInviteService` opens a FRESH browser - matching the
        "close the window, then open it again just to connect" flow - and sends
        each recruiter a free connection invitation carrying their <=300-char
        note (never the long message). Never raises into the run result."""
        if not self._config.outreach.send_connection_notes:
            return
        try:
            result = ConnectionInviteService(self._config, self._db).run(run_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Connection-note pass failed: {}", exc)
            return
        summary.connect_summary = result
        summary.connection_notes_sent = result.sent
        if not result.total:
            return
        logger.success(
            "Connection notes: {} {}, {} already connected, {} skipped, {} failed{}",
            result.sent,
            "would-send [dry-run]" if result.dry_run else "sent",
            result.already,
            result.skipped,
            result.failed,
            " (weekly limit reached)" if result.limit_reached else "",
        )

    def _persist_result(
        self, application_id: int, result: ApplyResult, summary: RunSummary, job: Job, job_id: int
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
        elif result.status is ApplyStatus.LIMIT_REACHED:
            # Platform-side daily cap - neither our skip nor a failure. The row is
            # recorded as 'limit_reached'; the flag makes the crawl stop the run.
            summary.platform_daily_limit_hit = True
            logger.warning("LinkedIn daily submission cap hit - ending the run early")
        elif result.status is ApplyStatus.FAILED:
            summary.failed += 1
        else:
            self._note_skip(summary, result.status.value, job_id)

    def _record_answers(self, application_id: int, answers: list[AnsweredQuestion]) -> None:
        for answer in answers:
            question_id = self._db.upsert_question(
                answer.question, answer.normalized, answer.category, answer.skill
            )
            self._db.record_application_answer(
                application_id, answer.question, answer.value, answer.source, question_id
            )
            # Learn answers the user gave us (typed or filled on the page) plus
            # derived values (e.g. a monthly salary computed from annual CTC) so
            # future runs resolve them automatically without asking or recomputing.
            if answer.source in {"manual", "portal", "computed"} and answer.value:
                self._db.learn_answer(question_id, answer.value, answer.source)

    def _cleanup_screenshots(self) -> None:
        """Delete orphan screenshots (those not referenced by any application)."""
        cfg = self._config.screenshots
        if not (cfg.enabled and cfg.cleanup):
            return
        directory = Path(cfg.directory)
        if not directory.is_dir():
            return
        keep = {
            Path(row["screenshot"]).name
            for row in self._db.query(
                "SELECT screenshot FROM applications WHERE screenshot IS NOT NULL"
            )
            if row.get("screenshot")
        }
        removed = 0
        for shot in directory.glob("*.png"):
            if shot.name in keep:
                continue
            try:
                shot.unlink()
                removed += 1
            except OSError:  # pragma: no cover - defensive
                pass
        if removed:
            logger.info(
                "Cleaned up {} orphan screenshot(s); kept {} referenced by applications",
                removed,
                len(keep),
            )

    def _maybe_cover_letter(self, job: Job) -> RenderedCoverLetter | None:
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
            cover = self._cover.render_all(context, _COVER_DIR)
            logger.info(
                "Generated cover letter for '{}' -> {} (inline text ready, {} chars)",
                job.company or job.title or "job",
                cover.pdf_path,
                len(cover.text),
            )
            return cover
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
