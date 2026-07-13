"""Optional LLM advisory layer.

The AI layer *advises only* - it never replaces the deterministic automation or
auto-submits. Providers implement :class:`AIProvider`; the default
:class:`NullAIProvider` is a no-op so the framework works with no AI configured.
"""

from __future__ import annotations

from linkedin_easy_apply.ai.factory import build_provider
from linkedin_easy_apply.ai.models import AIResult
from linkedin_easy_apply.ai.provider import AIProvider, NullAIProvider

__all__ = ["AIProvider", "NullAIProvider", "AIResult", "build_provider"]
