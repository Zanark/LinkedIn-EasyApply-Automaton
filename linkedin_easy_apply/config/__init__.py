"""Typed configuration models and YAML loader."""

from __future__ import annotations

from linkedin_easy_apply.config.loader import ConfigError, load_config
from linkedin_easy_apply.config.models import (
    AIConfig,
    AnswersConfig,
    AppConfig,
    BrowserConfig,
    DatabaseConfig,
    JobsConfig,
    LoggingConfig,
    ResumeConfig,
    ScoringConfig,
    ScoringRule,
    SearchConfig,
    SearchEntry,
)

__all__ = [
    "load_config",
    "ConfigError",
    "AppConfig",
    "BrowserConfig",
    "JobsConfig",
    "SearchConfig",
    "SearchEntry",
    "AnswersConfig",
    "ResumeConfig",
    "ScoringConfig",
    "ScoringRule",
    "LoggingConfig",
    "AIConfig",
    "DatabaseConfig",
]
