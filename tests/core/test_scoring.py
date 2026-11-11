from __future__ import annotations

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.config.models import AppConfig, ScoringConfig, ScoringRule
from linkedin_easy_apply.database.db import Database
from linkedin_easy_apply.jobs.models import Job
from linkedin_easy_apply.orchestrator import Orchestrator, RunSummary
from linkedin_easy_apply.scoring.engine import ScoringEngine


def _engine(threshold: int, **rules: int) -> ScoringEngine:
    config = ScoringConfig(
        threshold=threshold,
        rules=[ScoringRule(keyword=k, weight=w) for k, w in rules.items()],
    )
    return ScoringEngine(config)


def test_weighted_score_and_threshold():
    engine = _engine(30, backend=30, java=25, senior=-20)
    result = engine.score("Senior Backend Java Engineer", "Build scalable microservices")
    assert result.score == 35  # 30 + 25 - 20
    assert result.passed is True
    assert set(result.matched_keywords) == {"backend", "java", "senior"}


def test_below_threshold_fails():
    engine = _engine(100, backend=30)
    result = engine.score("Backend Engineer")
    assert result.passed is False


def test_word_boundary_prevents_false_match():
    # "go" must not match inside "google".
    engine = _engine(0, go=40)
    result = engine.score("Google Cloud Engineer")
    assert result.score == 0
    assert "go" not in result.matched_keywords


def test_punctuation_keywords_match_by_substring():
    engine = _engine(0, **{"c++": 15})
    assert engine.score("C++ Developer").score == 15
    dotnet = _engine(0, **{".net": 10})
    assert dotnet.score("Senior ASP.NET Developer").score == 10


# -- scoring.enforce (and the --ignore-score flag that sets it) -------------- #
def _orchestrator(tmp_path, *, enforce: bool) -> tuple[Orchestrator, Database]:
    """An orchestrator whose threshold no job in these tests can reach."""
    config = AppConfig()
    config.screenshots.directory = tmp_path / "shots"
    config.database.path = tmp_path / "scoring.db"
    config.scoring.threshold = 10
    config.scoring.enforce = enforce
    database = Database(config.database.path)
    database.initialize()
    return Orchestrator(config, database, AnswerStore({})), database


def _scan_low_scoring_job(orch: Orchestrator, database: Database) -> RunSummary:
    """Run one unscoreable job through the pipeline in scan mode."""
    run_id = database.start_run("scan")
    summary = RunSummary(run_id=run_id, mode="scan")
    job = Job(
        url="https://www.linkedin.com/jobs/view/42/",
        title="Widget Polisher",
        company="Acme",
        easy_apply=True,
    )
    orch._process_job(browser=None, job=job, summary=summary, mode="scan", settings=None, max_per_run=10)  # type: ignore[arg-type]
    return summary


def test_low_score_is_skipped_when_enforced(tmp_path):
    orch, database = _orchestrator(tmp_path, enforce=True)
    summary = _scan_low_scoring_job(orch, database)
    assert summary.skip_reasons == {"below_threshold": 1}


def test_low_score_proceeds_when_not_enforced(tmp_path):
    orch, database = _orchestrator(tmp_path, enforce=False)
    summary = _scan_low_scoring_job(orch, database)
    # The job moves past the score gate; scan mode then stops it at 'scan_only'.
    assert summary.skip_reasons == {"scan_only": 1}


def test_score_is_still_recorded_when_not_enforced(tmp_path):
    """enforce: false silences the gate, it does not disable scoring."""
    orch, database = _orchestrator(tmp_path, enforce=False)
    _scan_low_scoring_job(orch, database)
    rows = database.query("SELECT score, threshold, passed FROM scores")
    assert len(rows) == 1
    assert rows[0]["score"] == 0
    assert rows[0]["threshold"] == 10
    assert not rows[0]["passed"]


def test_enforce_defaults_to_true():
    assert ScoringConfig().enforce is True
