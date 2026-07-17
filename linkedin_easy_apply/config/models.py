"""Pydantic configuration models.

All runtime behaviour is driven by these models so that nothing is hardcoded.
The models are intentionally permissive with sensible defaults so a minimal
YAML file still produces a valid configuration.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator


class BrowserEngine(StrEnum):
    """Supported Playwright browser channels/engines."""

    CHROME = "chrome"
    EDGE = "edge"
    CHROMIUM = "chromium"


class BrowserConfig(BaseModel):
    """Controls how the Playwright persistent context is launched."""

    engine: BrowserEngine = BrowserEngine.EDGE
    profile_path: Path | None = None
    headless: bool = False
    viewport_width: int = 1440
    viewport_height: int = 900
    slow_mo_ms: int = 0
    download_dir: Path = Path("downloads")
    default_timeout_ms: int = 30_000
    navigation_timeout_ms: int = 45_000
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    record_har: bool = False
    har_dir: Path = Path("logs/har")

    @field_validator("viewport_width", "viewport_height")
    @classmethod
    def _positive_viewport(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("viewport dimensions must be positive")
        return value


class JobsConfig(BaseModel):
    """Limits and guard-rails applied per run."""

    max_per_run: int = 25
    max_per_company: int = 5
    max_daily: int = 50
    pause_after: int = 0  # 0 disables the automatic pause
    pause_seconds: float = 15.0
    blacklist_companies: list[str] = Field(default_factory=list)
    whitelist_companies: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalise(self) -> JobsConfig:
        self.blacklist_companies = [
            c.strip().lower() for c in self.blacklist_companies if c.strip()
        ]
        self.whitelist_companies = [
            c.strip().lower() for c in self.whitelist_companies if c.strip()
        ]
        self.include_keywords = [k.strip().lower() for k in self.include_keywords if k.strip()]
        self.exclude_keywords = [k.strip().lower() for k in self.exclude_keywords if k.strip()]
        return self


class SearchEntry(BaseModel):
    """A single named LinkedIn job search."""

    name: str
    url: str
    enabled: bool = True

    @field_validator("url")
    @classmethod
    def _valid_url(cls, value: str) -> str:
        if "linkedin.com" not in value:
            raise ValueError("search url must point to linkedin.com")
        return value


class SearchConfig(BaseModel):
    """Collection of searches to iterate over."""

    searches: list[SearchEntry] = Field(default_factory=list)

    @property
    def enabled_searches(self) -> list[SearchEntry]:
        return [s for s in self.searches if s.enabled]


class AnswersConfig(BaseModel):
    """Where the user's answers live."""

    file: Path = Path("configs/answers.yaml")
    fuzzy_threshold: int = 80  # 0-100 similarity score for question matching


class ResumeConfig(BaseModel):
    """Resume selection configuration."""

    directory: Path = Path("generated/resume")
    default: str | None = None
    # role/keyword -> resume filename
    mapping: dict[str, str] = Field(default_factory=dict)


class ScoringRule(BaseModel):
    """A single weighted keyword rule."""

    keyword: str
    weight: int

    @field_validator("keyword")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class ScoringConfig(BaseModel):
    """Scoring engine configuration."""

    threshold: int = 0
    rules: list[ScoringRule] = Field(default_factory=list)
    case_sensitive: bool = False


class LoggingConfig(BaseModel):
    """Loguru configuration."""

    level: str = "INFO"
    directory: Path = Path("logs")
    rotation: str = "10 MB"
    retention: str = "14 days"
    serialize: bool = False
    console: bool = True

    @field_validator("level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class AIProviderName(StrEnum):
    """Supported AI advisory providers."""

    NONE = "none"
    OPENAI = "openai"


class AIConfig(BaseModel):
    """Optional AI advisory configuration. Advises only; never auto-submits."""

    provider: AIProviderName = AIProviderName.NONE
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.2
    max_tokens: int = 800
    enabled: bool = False


class DatabaseConfig(BaseModel):
    """SQLite database location."""

    path: Path = Path("database/easy_apply.db")


class ScreenshotConfig(BaseModel):
    """Screenshot capture behaviour."""

    enabled: bool = True
    directory: Path = Path("screenshots")
    on_error: bool = True
    each_step: bool = True


class RunConfig(BaseModel):
    """High level run behaviour toggles."""

    dry_run: bool = False
    interactive: bool = False  # prompt before final submit
    pause_on_unknown_question: bool = True


class AppConfig(BaseModel):
    """Root application configuration aggregating every section."""

    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    jobs: JobsConfig = Field(default_factory=JobsConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    answers: AnswersConfig = Field(default_factory=AnswersConfig)
    resume: ResumeConfig = Field(default_factory=ResumeConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    screenshots: ScreenshotConfig = Field(default_factory=ScreenshotConfig)
    run: RunConfig = Field(default_factory=RunConfig)

    model_config = {"extra": "forbid"}
