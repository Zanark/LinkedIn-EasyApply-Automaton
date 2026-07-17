"""Provider interface and the default no-op implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from linkedin_easy_apply.ai.models import AIResult, TailoringSuggestion


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

    def suggest_tailoring(
        self,
        *,
        job_title: str,
        job_description: str,
        available_categories: list[str],
        master_title: str | None = None,
    ) -> TailoringSuggestion | None:
        """Optionally suggest how to re-emphasise an *existing* resume for a job.

        The suggestion may only reorder/select from ``available_categories`` and
        propose a headline; it must never invent content. The default returns
        ``None`` (no suggestion) so non-AI providers stay pure no-ops.
        """
        return None


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
