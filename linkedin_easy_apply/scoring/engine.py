"""A configurable, keyword-weighted scoring engine.

Each rule contributes its weight (positive or negative) when its keyword is
present in the job's title or description. Only jobs scoring at or above the
configured threshold are considered eligible.

Punctuation-heavy keywords such as ``c++`` or ``.net`` are matched by substring
while plain alphanumeric keywords use word-boundary matching so ``go`` does not
match ``google``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from linkedin_easy_apply.config.models import ScoringConfig

_WORD_KEYWORD = re.compile(r"^[a-z0-9 ]+$")


@dataclass(slots=True)
class ScoreResult:
    """The outcome of scoring a single job."""

    score: int
    threshold: int
    passed: bool
    breakdown: dict[str, int] = field(default_factory=dict)

    @property
    def matched_keywords(self) -> list[str]:
        return list(self.breakdown)


class ScoringEngine:
    """Score jobs against a set of weighted keyword rules."""

    def __init__(self, config: ScoringConfig) -> None:
        self._config = config
        self._threshold = config.threshold
        self._case_sensitive = config.case_sensitive

    def score(self, title: str, description: str | None = None) -> ScoreResult:
        text = f"{title}\n{description or ''}"
        haystack = text if self._case_sensitive else text.lower()

        breakdown: dict[str, int] = {}
        total = 0
        for rule in self._config.rules:
            keyword = rule.keyword if self._case_sensitive else rule.keyword.lower()
            if self._contains(keyword, haystack):
                breakdown[rule.keyword] = breakdown.get(rule.keyword, 0) + rule.weight
                total += rule.weight

        return ScoreResult(
            score=total,
            threshold=self._threshold,
            passed=total >= self._threshold,
            breakdown=breakdown,
        )

    @staticmethod
    def _contains(keyword: str, haystack: str) -> bool:
        if not keyword:
            return False
        if _WORD_KEYWORD.match(keyword):
            return re.search(rf"\b{re.escape(keyword)}\b", haystack) is not None
        return keyword in haystack
