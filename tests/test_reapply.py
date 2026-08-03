"""Tests for the *reapply* feature: the ``reapply_targets`` DB query, the
``JobSearch.open_job`` single-job navigation, and the orchestrator wiring that
retries failed/aborted jobs without crawling a search.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.dashboard import reapply_launch
from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.jobs.models import Job
from linkedin_easy_apply.jobs.search import JobSearch
from linkedin_easy_apply.orchestrator import Orchestrator


@pytest.fixture
def db(tmp_path) -> Database:
    database = Database(tmp_path / "reapply.db")
    database.initialize()
    return database


def _failed_job(db: Database, url: str, status: str = "failed", *, title: str = "SWE") -> int:
    """Seed one job with a single failed/aborted application in its own run."""
    run_id = db.start_run("apply")
    job_id = db.upsert_job({"url": url, "title": title, "company": "Acme"}, run_id)
    db.create_application(job_id, run_id, resume_id=None, status=status)
    return job_id


# -- reapply_targets --------------------------------------------------------- #
def test_reapply_targets_includes_failed_never_submitted(db: Database):
    _failed_job(db, "https://www.linkedin.com/jobs/view/1/")
    targets = db.reapply_targets()
    assert [t["url"] for t in targets] == ["https://www.linkedin.com/jobs/view/1/"]
    only = targets[0]
    assert only["attempts"] == 1
    assert only["last_status"] == "failed"
    assert only["title"] == "SWE"


def test_reapply_targets_includes_aborted(db: Database):
    _failed_job(db, "https://www.linkedin.com/jobs/view/2/", status="aborted")
    targets = {t["url"]: t for t in db.reapply_targets()}
    assert targets["https://www.linkedin.com/jobs/view/2/"]["last_status"] == "aborted"


def test_reapply_targets_excludes_later_submitted(db: Database):
    url = "https://www.linkedin.com/jobs/view/3/"
    job_id = _failed_job(db, url)
    # A later run submits the same job -> it must drop out of the retry list.
    run2 = db.start_run("apply")
    db.create_application(job_id, run2, None, "submitted")
    assert all(t["url"] != url for t in db.reapply_targets())


def test_reapply_targets_counts_multiple_attempts(db: Database):
    url = "https://www.linkedin.com/jobs/view/4/"
    job_id = _failed_job(db, url, status="failed")
    run2 = db.start_run("apply")
    db.create_application(job_id, run2, None, "aborted")
    targets = {t["url"]: t for t in db.reapply_targets()}
    assert targets[url]["attempts"] == 2


def test_reapply_targets_excludes_pending_and_submitted_only(db: Database):
    run = db.start_run("apply")
    pending = db.upsert_job({"url": "u-pending", "title": "P"}, run)
    db.create_application(pending, run, None, "pending")
    submitted = db.upsert_job({"url": "u-submitted", "title": "S"}, run)
    db.create_application(submitted, run, None, "submitted")
    urls = {t["url"] for t in db.reapply_targets()}
    assert "u-pending" not in urls
    assert "u-submitted" not in urls


def test_reapply_targets_dedupes_and_orders_recent_first(db: Database):
    # Two distinct failed jobs; force distinct timestamps (same-second seeding
    # is otherwise ambiguous) so the recency ordering is deterministic.
    old = _failed_job(db, "u-old", title="Old")
    new = _failed_job(db, "u-new", title="New")
    with db.connect() as conn:
        conn.execute(
            "UPDATE applications SET started_at=? WHERE job_id=?", ("2026-01-01T00:00:00", old)
        )
        conn.execute(
            "UPDATE applications SET started_at=? WHERE job_id=?", ("2026-02-01T00:00:00", new)
        )
    urls = [t["url"] for t in db.reapply_targets()]
    assert set(urls) == {"u-old", "u-new"}
    assert urls[0] == "u-new"  # ordered by most-recent attempt


def test_reapply_targets_respects_limit(db: Database):
    for i in range(5):
        _failed_job(db, f"u-{i}")
    assert len(db.reapply_targets(limit=2)) == 2


# -- JobSearch.open_job ------------------------------------------------------ #
class _FakePage:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.goto_urls: list[str] = []

    def goto(self, url: str, wait_until: str | None = None) -> None:
        self.goto_urls.append(url)
        if self.fail:
            raise RuntimeError("navigation failed")

    def wait_for_timeout(self, _ms: int) -> None:
        pass


def _search(page: _FakePage) -> JobSearch:
    extractor = SimpleNamespace(
        extract=lambda _page, search_name=None: Job(
            url="https://www.linkedin.com/jobs/view/5/", title="Extracted"
        )
    )
    search = JobSearch(page, extractor)  # type: ignore[arg-type]
    # The modal-clearing helper touches real Playwright locators; stub it out.
    search._clear_blocking_modal = lambda: False  # type: ignore[method-assign]
    return search


def test_open_job_navigates_and_extracts():
    page = _FakePage()
    job = _search(page).open_job("https://www.linkedin.com/jobs/view/5/")
    assert job is not None
    assert job.title == "Extracted"
    assert page.goto_urls == ["https://www.linkedin.com/jobs/view/5/"]


def test_open_job_returns_none_on_navigation_failure():
    page = _FakePage(fail=True)
    assert _search(page).open_job("https://www.linkedin.com/jobs/view/5/") is None


# -- orchestrator reapply wiring --------------------------------------------- #
def _orchestrator(tmp_path) -> tuple[Orchestrator, Database]:
    config = AppConfig()
    config.screenshots.directory = tmp_path / "shots"
    config.database.path = tmp_path / "orch.db"
    database = Database(config.database.path)
    database.initialize()
    return Orchestrator(config, database, AnswerStore({})), database


class _FakeBrowser:
    page = object()

    def __enter__(self) -> _FakeBrowser:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def test_run_reapply_sources_targets_and_records_mode(tmp_path, monkeypatch):
    orch, db = _orchestrator(tmp_path)
    _failed_job(db, "https://www.linkedin.com/jobs/view/7/", title="Retry me")

    monkeypatch.setattr(
        "linkedin_easy_apply.orchestrator.BrowserManager", lambda _cfg: _FakeBrowser()
    )
    captured: dict[str, object] = {}

    def _fake_exec(self, _browser, targets, _summary, _dry, _interactive, max_per_run):
        captured["targets"] = targets
        captured["max_per_run"] = max_per_run

    monkeypatch.setattr(Orchestrator, "_execute_reapply", _fake_exec)

    summary = orch.run(mode="reapply")

    targets = captured["targets"]
    assert isinstance(targets, list)
    assert [t["url"] for t in targets] == ["https://www.linkedin.com/jobs/view/7/"]
    assert captured["max_per_run"] == 1  # default = all targets
    assert summary.mode == "reapply"
    recorded = db.query("SELECT mode FROM runs ORDER BY id DESC LIMIT 1")
    assert recorded[0]["mode"] == "reapply"


def test_run_reapply_dry_run_records_dry_run_mode(tmp_path, monkeypatch):
    orch, db = _orchestrator(tmp_path)
    _failed_job(db, "https://www.linkedin.com/jobs/view/8/")
    monkeypatch.setattr(
        "linkedin_easy_apply.orchestrator.BrowserManager", lambda _cfg: _FakeBrowser()
    )
    monkeypatch.setattr(Orchestrator, "_execute_reapply", lambda *a, **k: None)
    summary = orch.run(mode="reapply", dry_run=True)
    assert summary.mode == "dry_run"


# -- dashboard launch helpers ------------------------------------------------ #
def test_reapply_command_interactive_omits_yes():
    cmd = reapply_launch.reapply_command("configs/config.yaml", answer_unknowns=True)
    assert "apply.py reapply" in cmd
    assert "--config configs/config.yaml" in cmd
    assert "--yes" not in cmd


def test_reapply_command_unattended_appends_yes():
    cmd = reapply_launch.reapply_command("configs/config.yaml", answer_unknowns=False)
    assert cmd.endswith("--yes")


def test_launch_reapply_interactive_builds_args(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(reapply_launch.subprocess, "Popen", _fake_popen)
    ok, message = reapply_launch.launch_reapply("cfg.yaml", answer_unknowns=True)
    assert ok is True
    assert "interactive" in message
    args = captured["args"]
    assert "reapply" in args and "--config" in args and "cfg.yaml" in args
    assert "--yes" not in args


def test_launch_reapply_unattended_passes_yes(monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        reapply_launch.subprocess,
        "Popen",
        lambda args, **kwargs: captured.update(args=args),
    )
    ok, message = reapply_launch.launch_reapply("cfg.yaml", answer_unknowns=False)
    assert ok is True
    assert "unattended" in message
    assert "--yes" in captured["args"]


def test_launch_reapply_reports_failure(monkeypatch):
    def _boom(args, **kwargs):
        raise OSError("no console available")

    monkeypatch.setattr(reapply_launch.subprocess, "Popen", _boom)
    ok, message = reapply_launch.launch_reapply("cfg.yaml", answer_unknowns=True)
    assert ok is False
    assert "Run it yourself" in message
