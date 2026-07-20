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


class ResumeBuilderMode(StrEnum):
    """How the dynamic builder decides what to emphasise for a job."""

    KEYWORD = "keyword"  # deterministic keyword-cluster matching (offline)
    AI = "ai"  # ask the configured AI provider (needs an API key)


class ResumeClusterConfig(BaseModel):
    """A keyword-detected job cluster mapped to a resume emphasis.

    All emphasis fields map 1:1 to the builder's ``tailor`` flags. Content is
    only re-emphasised/reordered/hidden - never invented.
    """

    key: str
    keywords: list[str] = Field(default_factory=list)
    title: str | None = None  # headline override
    skills_order: list[str] = Field(default_factory=list)
    compact: bool = False
    roomy: bool = False
    include_awards: bool | None = None  # None -> leave as master default
    condense_older: bool = False
    filename: str | None = None  # output name; default derived from key

    @field_validator("keywords")
    @classmethod
    def _lower_keywords(cls, value: list[str]) -> list[str]:
        return [k.strip().lower() for k in value if k.strip()]


class ResumeBuilderConfig(BaseModel):
    """Per-job dynamic resume generation via the external dynamic-resume-builder.

    Opt-in. When enabled, the orchestrator asks the builder to render a resume
    tailored to each job just before applying, falling back to static selection
    when disabled, unmatched, or on any error.
    """

    enabled: bool = False
    path: Path | None = None  # folder holding the builder's render.py + master.yaml
    python: Path | None = None  # interpreter to run it (None -> this process's own)
    design: str = "Seafoam-Light"  # builder HTML design used for tailored resumes
    mode: ResumeBuilderMode = ResumeBuilderMode.KEYWORD
    ai_fallback_keyword: bool = True  # in AI mode, fall back to keyword clusters
    cache: bool = True  # render each cluster at most once per run
    timeout: int = 180  # subprocess timeout, seconds
    title_weight: int = 3  # keyword hit weight for the title vs the description
    min_score: int = 1  # minimum weighted hits required to tailor
    clusters: list[ResumeClusterConfig] = Field(default_factory=list)


class ResumeConfig(BaseModel):
    """Resume selection configuration."""

    directory: Path = Path("generated/resume")
    default: str | None = None
    # role/keyword -> resume filename
    mapping: dict[str, str] = Field(default_factory=dict)
    # optional per-job dynamic generation (see ResumeBuilderConfig)
    builder: ResumeBuilderConfig = Field(default_factory=ResumeBuilderConfig)


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
    cleanup: bool = True  # remove orphan (unreferenced) screenshots at end of run


class RunConfig(BaseModel):
    """High level run behaviour toggles."""

    dry_run: bool = False
    interactive: bool = False  # confirm before final submit (prompt defaults to Yes)
    pause_on_unknown_question: bool = True
    # Seconds to pause after logging the chosen resume so the pick is readable
    # in the live log before applying. Set to 0 to disable the pause.
    resume_review_pause: float = 3.0


class OutreachConfig(BaseModel):
    """Post-apply outreach to the 'Meet the hiring team' recruiters (opt-in).

    When enabled, after a successful application the tool drafts a short,
    personalised message to each messageable hiring-team member and pauses for
    the user's approval before sending. It is off by default and requires an
    interactive session (it cannot run under ``--yes``)."""

    enabled: bool = False  # opt-in
    max_per_run: int = 5  # safety cap on messages sent per run
    template: Path | None = None  # optional custom Jinja2 message template file
    skip_if_messaged: bool = True  # never message the same person twice


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
    outreach: OutreachConfig = Field(default_factory=OutreachConfig)

    model_config = {"extra": "forbid"}
