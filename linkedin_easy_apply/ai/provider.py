"""Provider interface and the default no-op implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from linkedin_easy_apply.ai.models import AIResult


class AIProvider(ABC):
    """Advisory provider contract.

    Implementations analyse a job against a resume and return an
    :class:`AIResult`. They must never perform side effects on the browser.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""

    @abstractmethod
    def evaluate_job(
        self,
        *,
        job_title: str,
        job_description: str,
        resume_text: str | None = None,
    ) -> AIResult:
        """Return an advisory evaluation for the given job."""


class NullAIProvider(AIProvider):
    """A provider that returns an empty, non-committal result."""

    @property
    def name(self) -> str:
        return "none"

    def evaluate_job(
        self,
        *,
        job_title: str,
        job_description: str,
        resume_text: str | None = None,
    ) -> AIResult:
        return AIResult(recommendation="AI disabled", should_apply=None)
