"""Factory that builds an :class:`AIProvider` from configuration."""

from __future__ import annotations

from loguru import logger

from linkedin_easy_apply.ai.provider import AIProvider, NullAIProvider
from linkedin_easy_apply.config.models import AIConfig, AIProviderName


def build_provider(config: AIConfig) -> AIProvider:
    """Return the configured provider, falling back to :class:`NullAIProvider`."""
    if not config.enabled or config.provider is AIProviderName.NONE:
        return NullAIProvider()
    if config.provider is AIProviderName.OPENAI:
        from linkedin_easy_apply.ai.openai_provider import OpenAIProvider

        return OpenAIProvider(config)
    logger.warning("Unknown AI provider '{}', using null provider", config.provider)
    return NullAIProvider()
