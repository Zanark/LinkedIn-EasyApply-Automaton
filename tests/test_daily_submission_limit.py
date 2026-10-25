"""Tests for LinkedIn's platform-side daily Easy Apply cap handling.

Two layers:

* :meth:`EasyApplyWorkflow._hit_daily_submission_limit` - recognises the
  "We limit daily submissions ... Save this job and apply tomorrow" notice that
  LinkedIn shows *instead of* the "application sent" confirmation, via the
  structured ``SUBMIT_LIMIT_MODAL`` selectors or a text fallback.
* Orchestrator wiring - a ``LIMIT_REACHED`` result flips
  ``RunSummary.platform_daily_limit_hit`` and is counted as neither an
  application, a failure, nor a skip (the crawl loop then stops the run).
"""

from __future__ import annotations

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.easy_apply import ApplyResult, ApplyStatus, EasyApplyWorkflow
from linkedin_easy_apply.jobs.models import Job
from linkedin_easy_apply.orchestrator import Orchestrator, RunSummary


# --------------------------------------------------------------------------- #
# _hit_daily_submission_limit - a tiny fake page over the selector API         #
# --------------------------------------------------------------------------- #
class _Loc:
    def __init__(self, present: bool, *, visible: bool = False, text: str = "") -> None:
        self._present = present
        self._visible = visible
        self._text = text

    def count(self) -> int:
        return 1 if self._present else 0

    @property
    def first(self) -> _Loc:
        return self

    def is_visible(self) -> bool:
        return self._visible

    def inner_text(self) -> str:
        return self._text


class _FakePage:
    """Answers ``locator(selector)`` for the two selector families the detector
    consults: the dedicated limit modal and the apply modal (text fallback)."""

    def __init__(self, *, limit_visible: bool = False, modal_text: str = "") -> None:
        self._limit = set(selectors.SUBMIT_LIMIT_MODAL)
        self._modal = set(selectors.MODAL)
        self._limit_visible = limit_visible
        self._modal_text = modal_text

    def locator(self, selector: str) -> _Loc:
        if selector in self._limit:
            return _Loc(self._limit_visible, visible=self._limit_visible)
        if selector in self._modal:
            return _Loc(bool(self._modal_text), text=self._modal_text)
        return _Loc(False)


def _detector_workflow(page: _FakePage) -> EasyApplyWorkflow:
    wf = object.__new__(EasyApplyWorkflow)
    wf._page = page
    return wf


def test_detects_limit_via_dedicated_selector():
    wf = _detector_workflow(_FakePage(limit_visible=True))
    assert wf._hit_daily_submission_limit() is True


def test_detects_limit_via_modal_text_fallback():
    page = _FakePage(modal_text="We limit daily submissions. Save this job and apply tomorrow.")
    wf = _detector_workflow(page)
    assert wf._hit_daily_submission_limit() is True


def test_no_limit_on_normal_confirmation():
    page = _FakePage(modal_text="Your application was sent to Acme Corp")
    wf = _detector_workflow(page)
    assert wf._hit_daily_submission_limit() is False


# --------------------------------------------------------------------------- #
# Orchestrator: a LIMIT_REACHED result stops the run, counts as nothing        #
# --------------------------------------------------------------------------- #
def _orchestrator(tmp_path) -> tuple[Orchestrator, Database]:
    config = AppConfig()
    config.screenshots.directory = tmp_path / "shots"
    config.database.path = tmp_path / "orch.db"
    db = Database(config.database.path)
    db.initialize()
    return Orchestrator(config, db, AnswerStore({})), db


def test_persist_limit_reached_flags_run_and_counts_nothing(tmp_path):
    orch, db = _orchestrator(tmp_path)
    run_id = db.start_run("apply")
    job = Job(url="https://www.linkedin.com/jobs/view/9/", title="SWE", company="Acme")
    job_id = db.upsert_job(job.to_db_dict(), run_id)
    application_id = db.create_application(job_id, run_id, None, "pending")

    summary = RunSummary(run_id=run_id, mode="apply")
    result = ApplyResult(
        ApplyStatus.LIMIT_REACHED, steps=4, reason="LinkedIn daily submission limit reached"
    )
    orch._persist_result(application_id, result, summary, job, job_id)

    assert summary.platform_daily_limit_hit is True
    assert summary.applied == 0
    assert summary.failed == 0
    assert summary.skipped == 0
    # The application row records the platform-cap status for history/dashboard.
    row = db.query("SELECT status FROM applications WHERE id = ?", (application_id,))[0]
    assert row["status"] == "limit_reached"
