from __future__ import annotations

from linkedin_easy_apply.config.models import ScoringConfig, ScoringRule
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
