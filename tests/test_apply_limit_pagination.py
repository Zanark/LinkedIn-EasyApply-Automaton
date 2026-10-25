"""``--limit`` = *successful submissions*, reached by paginating the search.

These exercise the crawl-control logic in ``Orchestrator._execute`` without a
browser: a fake search driver yields scripted pages and ``_process_job`` is
replaced with a scripted outcome sequence. They lock in the contract the user
asked for — skipped / failed / aborted jobs must NOT consume the ``--limit``
budget, and the crawler keeps paginating until that many are actually submitted
(or the jobs run out / the daily cap is hit).
"""

from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.jobs.models import Job
from linkedin_easy_apply.jobs.search import paginated_url
from linkedin_easy_apply.orchestrator import Orchestrator, RunSummary

_SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords=backend&f_AL=true"


# --------------------------------------------------------------------------- #
# paginated_url                                                               #
# --------------------------------------------------------------------------- #
def test_paginated_url_first_page_is_unchanged():
    assert paginated_url(_SEARCH_URL, 0) == _SEARCH_URL


def test_paginated_url_sets_start_offset():
    q = parse_qs(urlsplit(paginated_url(_SEARCH_URL, 25)).query)
    assert q["start"] == ["25"]
    assert q["keywords"] == ["backend"]  # other params preserved
    assert q["f_AL"] == ["true"]


def test_paginated_url_replaces_existing_start():
    q = parse_qs(urlsplit(paginated_url(_SEARCH_URL + "&start=25", 50)).query)
    assert q["start"] == ["50"]  # not two start params


# --------------------------------------------------------------------------- #
# harness                                                                     #
# --------------------------------------------------------------------------- #
def _job(i: int) -> Job:
    return Job(url=f"https://www.linkedin.com/jobs/view/{i}/", external_id=str(i))


def _run_execute(
    tmp_path,
    monkeypatch,
    *,
    pages: dict[int, list[Job]],
    outcomes: list[str],
    limit: int,
    mode: str = "apply",
    max_daily: int = 0,
    max_pages: int = 40,
    page_size: int = 25,
) -> tuple[RunSummary, list[Job]]:
    config = AppConfig()
    config.database.path = tmp_path / "test.db"
    config.jobs.max_daily = max_daily
    config.jobs.max_search_pages = max_pages
    config.jobs.search_page_size = page_size
    db = Database(config.database.path)
    db.initialize()
    orch = Orchestrator(config, db, AnswerStore({}))

    class FakeSearch:
        def __init__(self, page, extractor=None):
            pass

        def iterate(self, url, name, max_jobs):
            start = int(parse_qs(urlsplit(url).query).get("start", ["0"])[0])
            yield from pages.get(start, [])

    monkeypatch.setattr("linkedin_easy_apply.orchestrator.JobSearch", FakeSearch)

    processed: list[Job] = []
    outcome_iter = iter(outcomes)

    def fake_process(browser, job, summary, m, settings, mpr):
        processed.append(job)
        outcome = next(outcome_iter, "skip")
        if outcome == "submit":
            summary.applied += 1
        elif outcome == "fail":
            summary.failed += 1
        else:
            summary.note_skip("test")

    monkeypatch.setattr(orch, "_process_job", fake_process)

    summary = RunSummary(run_id=db.start_run(mode), mode=mode)
    searches = [SimpleNamespace(name="s", url=_SEARCH_URL)]
    orch._execute(SimpleNamespace(page=None), searches, summary, mode, False, False, limit)
    return summary, processed


# --------------------------------------------------------------------------- #
# submission-count semantics                                                  #
# --------------------------------------------------------------------------- #
def test_limit_counts_only_submissions_across_pages(tmp_path, monkeypatch):
    """Skips and fails don't consume the budget; the run stops the instant the
    3rd *submission* lands, even mid-page, and paginates to get there."""
    pages = {
        0: [_job(0), _job(1), _job(2)],
        25: [_job(3), _job(4), _job(5)],
        50: [_job(6), _job(7), _job(8)],
    }
    outcomes = [
        "skip",
        "fail",
        "submit",  # page 0 -> applied 1
        "skip",
        "skip",
        "submit",  # page 1 -> applied 2
        "fail",
        "submit",
        "submit",  # page 2 -> applied 3 at j7, stop before j8
    ]
    summary, processed = _run_execute(
        tmp_path, monkeypatch, pages=pages, outcomes=outcomes, limit=3
    )

    assert summary.applied == 3
    assert [j.external_id for j in processed] == ["0", "1", "2", "3", "4", "5", "6", "7"]
    assert summary.failed == 2
    assert summary.skipped == 3
    assert summary.scanned == 8  # j8 never scanned/processed


def test_run_stops_when_jobs_exhausted_below_target(tmp_path, monkeypatch):
    """An empty page ends the search (no infinite loop) and the run finishes
    below target rather than hanging."""
    pages = {0: [_job(0), _job(1)], 25: []}
    outcomes = ["submit", "skip"]
    summary, processed = _run_execute(
        tmp_path, monkeypatch, pages=pages, outcomes=outcomes, limit=30
    )

    assert summary.applied == 1
    assert summary.scanned == 2
    assert len(processed) == 2


def test_seen_jobs_are_not_processed_twice(tmp_path, monkeypatch):
    """A job that reappears on a later page (LinkedIn re-ordering) is de-duped."""
    pages = {0: [_job(0)], 25: [_job(0), _job(1)], 50: []}
    outcomes = ["skip", "skip", "skip"]
    summary, processed = _run_execute(
        tmp_path, monkeypatch, pages=pages, outcomes=outcomes, limit=30
    )

    assert [j.external_id for j in processed] == ["0", "1"]  # j0 processed once
    assert summary.scanned == 2


def test_daily_cap_stops_before_processing(tmp_path, monkeypatch):
    """With the daily cap already met, the run stops immediately — the explicit
    --limit does not override the max_daily safety."""
    config = AppConfig()
    config.database.path = tmp_path / "d.db"
    config.jobs.max_daily = 2
    db = Database(config.database.path)
    db.initialize()
    run = db.start_run("apply")
    for i in range(2):  # two submissions already today
        jid = db.upsert_job({"url": f"https://x/{i}", "title": "T"}, run)
        aid = db.create_application(jid, run, None)
        db.update_application(aid, status="submitted", finished=True)
    assert db.count_applications_today() == 2

    orch = Orchestrator(config, db, AnswerStore({}))

    class FakeSearch:
        def __init__(self, page, extractor=None):
            pass

        def iterate(self, url, name, max_jobs):
            yield _job(99)

    monkeypatch.setattr("linkedin_easy_apply.orchestrator.JobSearch", FakeSearch)
    processed: list[Job] = []
    monkeypatch.setattr(orch, "_process_job", lambda *a, **k: processed.append(a[1]))

    summary = RunSummary(run_id=run, mode="apply")
    orch._execute(
        SimpleNamespace(page=None),
        [SimpleNamespace(name="s", url=_SEARCH_URL)],
        summary,
        "apply",
        False,
        False,
        30,
    )
    assert processed == []  # never even looked at a job
    assert summary.applied == 0


# --------------------------------------------------------------------------- #
# scan mode                                                                   #
# --------------------------------------------------------------------------- #
def test_scan_mode_stops_at_scanned_limit(tmp_path, monkeypatch):
    """In scan mode --limit caps *scanned* jobs (there are no submissions)."""
    pages = {0: [_job(0), _job(1), _job(2)]}
    outcomes = ["skip", "skip", "skip"]
    summary, processed = _run_execute(
        tmp_path, monkeypatch, pages=pages, outcomes=outcomes, limit=2, mode="scan"
    )

    assert summary.scanned == 2
    assert len(processed) == 2  # j2 never reached


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
