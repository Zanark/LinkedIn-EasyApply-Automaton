"""The result of an AI job evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TailoringSuggestion:
    """A re-emphasis suggestion for a job: which existing content to surface.

    The provider chooses only from the candidate's *existing* skill categories -
    it never invents experience. ``skills_order`` is a subset/ordering of the
    category names passed to the provider; ``title`` is a headline drawn from the
    real profile. Consumed by the dynamic resume builder to render one PDF.
    """

    title: str | None = None
    skills_order: list[str] = field(default_factory=list)
    cluster: str | None = None  # short label for logging/caching
    reason: str | None = None


@dataclass(slots=True)
class AIResult:
    """Advisory output describing how well a candidate matches a job."""

    match_percent: float | None = None
    missing_skills: list[str] = field(default_factory=list)
    recommendation: str | None = None
    reasons: list[str] = field(default_factory=list)
    suggested_resume: str | None = None
    suggested_cover_letter: str | None = None
    should_apply: bool | None = None
    raw: Any = None

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "match_percent": self.match_percent,
            "missing_skills": self.missing_skills,
            "recommendation": self.recommendation,
            "reasons": self.reasons,
            "suggested_resume": self.suggested_resume,
            "should_apply": self.should_apply,
            "raw": self.raw,
        }
