"""Per-job dynamic resume generation via the external dynamic-resume-builder.

When ``resume.builder.enabled`` is true, the orchestrator asks this component to
render a resume tailored to the job at hand *just before applying*. Two modes:

* ``keyword`` - deterministic keyword-cluster matching, fully offline.
* ``ai`` - ask the configured AI provider to re-emphasise (never fabricate),
  with an optional fall back to keyword clusters.

Whatever the mode, tailoring only re-emphasises / reorders / hides the content
that already exists in the builder's ``master.yaml`` - it never invents skills or
experience. On no match, disabled state, or any failure the caller falls back to
the deterministic :class:`~linkedin_easy_apply.answers.resume_selector.ResumeSelector`.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from loguru import logger

from linkedin_easy_apply.ai.provider import AIProvider
from linkedin_easy_apply.answers.resume_selector import ResumeChoice
from linkedin_easy_apply.config.models import (
    ResumeBuilderConfig,
    ResumeBuilderMode,
    ResumeClusterConfig,
)
from linkedin_easy_apply.jobs.models import Job


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text).strip("_").lower() or "resume"


@lru_cache(maxsize=512)
def _compile_keyword(keyword: str) -> re.Pattern[str]:
    """Match ``keyword`` only at token boundaries so short keys like ``ai`` don't
    match inside ``email``/``training``, while still matching ``ai/ml``, ``.net``
    and ``c#`` (punctuation counts as a boundary)."""
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?![a-z0-9])", re.IGNORECASE)


def _keyword_in(keyword: str, text: str) -> bool:
    return bool(keyword) and _compile_keyword(keyword).search(text) is not None


@dataclass(slots=True)
class _Emphasis:
    """A resolved, ready-to-render emphasis for one job."""

    key: str  # cache key + filename discriminator
    title: str | None
    skills_order: list[str]
    compact: bool
    roomy: bool
    include_awards: bool | None
    condense_older: bool
    filename: str
    reason: str


class DynamicResumeBuilder:
    """Render a resume tailored to a specific job by invoking the builder tool."""

    def __init__(
        self,
        config: ResumeBuilderConfig,
        *,
        resume_dir: Path,
        ai: AIProvider | None = None,
    ) -> None:
        self._config = config
        self._resume_dir = Path(resume_dir).resolve()
        self._ai = ai
        self._cache: dict[str, ResumeChoice | None] = {}
        self._builder_path = Path(config.path).expanduser().resolve() if config.path else None
        self._python = str(config.python) if config.python else sys.executable
        self._profile: dict | None = None  # lazy {name, title, categories}
        self._warned = False

    # -- availability ---------------------------------------------------------
    @property
    def enabled(self) -> bool:
        """True only when configured *and* the builder script actually exists."""
        if not self._config.enabled:
            return False
        if self._builder_path is None or not self._render_script().is_file():
            if not self._warned:
                logger.warning(
                    "resume.builder.enabled is true but render.py was not found at "
                    "'{}'. Falling back to static resume selection.",
                    self._builder_path,
                )
                self._warned = True
            return False
        return True

    def _render_script(self) -> Path:
        assert self._builder_path is not None
        return self._builder_path / "render.py"

    # -- public API -----------------------------------------------------------
    def tailor_for(self, job: Job) -> ResumeChoice | None:
        """Return a job-tailored :class:`ResumeChoice`, or ``None`` to fall back."""
        if not self.enabled:
            return None
        emphasis = self._resolve_emphasis(job)
        if emphasis is None:
            return None
        if self._config.cache and emphasis.key in self._cache:
            cached = self._cache[emphasis.key]
            if cached is not None:
                logger.debug(
                    "Reusing cached tailored resume '{}' (cluster {})",
                    cached.name,
                    emphasis.key,
                )
            return cached
        choice = self._render(emphasis)
        if self._config.cache:
            self._cache[emphasis.key] = choice
        return choice

    # -- emphasis resolution --------------------------------------------------
    def _resolve_emphasis(self, job: Job) -> _Emphasis | None:
        if self._config.mode is ResumeBuilderMode.AI:
            ai_emphasis = self._ai_emphasis(job)
            if ai_emphasis is not None:
                return ai_emphasis
            if not self._config.ai_fallback_keyword:
                return None
        return self._keyword_emphasis(job)

    def _keyword_emphasis(self, job: Job) -> _Emphasis | None:
        match = self._detect_cluster(job)
        if match is None:
            return None
        cluster, score = match
        return self._emphasis_from_cluster(
            cluster, reason=f"keyword cluster '{cluster.key}' (score {score})"
        )

    def _detect_cluster(self, job: Job) -> tuple[ResumeClusterConfig, int] | None:
        """Score every cluster by keyword hits (title weighted higher); best wins."""
        title = (job.title or "").lower()
        desc = (job.description or "").lower()
        best: ResumeClusterConfig | None = None
        best_score = 0
        for cluster in self._config.clusters:
            score = 0
            for keyword in cluster.keywords:
                if _keyword_in(keyword, title):
                    score += self._config.title_weight
                elif _keyword_in(keyword, desc):
                    score += 1
            if score > best_score:
                best, best_score = cluster, score
        if best is None or best_score < self._config.min_score:
            return None
        return best, best_score

    def _emphasis_from_cluster(self, cluster: ResumeClusterConfig, *, reason: str) -> _Emphasis:
        filename = cluster.filename or self._default_filename(cluster.key)
        return _Emphasis(
            key=_slug(cluster.key),
            title=cluster.title,
            skills_order=list(cluster.skills_order),
            compact=cluster.compact,
            roomy=cluster.roomy,
            include_awards=cluster.include_awards,
            condense_older=cluster.condense_older,
            filename=filename,
            reason=reason,
        )

    def _ai_emphasis(self, job: Job) -> _Emphasis | None:
        if self._ai is None or self._ai.name == "none":
            return None
        categories = self._categories()
        if not categories:
            return None
        try:
            suggestion = self._ai.suggest_tailoring(
                job_title=job.title or "",
                job_description=job.description or "",
                available_categories=categories,
                master_title=self._master_title(),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("AI tailoring error: {}", exc)
            return None
        if suggestion is None or (not suggestion.title and not suggestion.skills_order):
            return None
        signature = f"{suggestion.title or ''}|{','.join(suggestion.skills_order)}"
        key = "ai_" + hashlib.sha1(signature.encode("utf-8")).hexdigest()[:8]
        return _Emphasis(
            key=key,
            title=suggestion.title,
            skills_order=list(suggestion.skills_order),
            compact=True,
            roomy=False,
            include_awards=False,
            condense_older=True,
            filename=self._default_filename(key),
            reason=suggestion.reason or "AI re-emphasis",
        )

    # -- rendering ------------------------------------------------------------
    def _render(self, emphasis: _Emphasis) -> ResumeChoice | None:
        cmd = self._build_command(emphasis)
        logger.debug("Invoking resume builder: {}", " ".join(cmd))
        ok = self._run_builder(cmd)
        dest = self._resume_dir / emphasis.filename
        if not ok or not dest.is_file():
            logger.warning(
                "Dynamic resume build did not produce '{}' (cluster {}); "
                "falling back to static selection.",
                emphasis.filename,
                emphasis.key,
            )
            return None
        return ResumeChoice(dest.name, dest, f"tailored: {emphasis.reason}", 0.0)

    def _build_command(self, emphasis: _Emphasis) -> list[str]:
        cmd = [
            self._python,
            str(self._render_script()),
            "tailor",
            "--name",
            emphasis.filename,
            "--out-dir",
            str(self._resume_dir),
        ]
        if self._config.design:
            cmd += ["--design", self._config.design]
        if emphasis.title:
            cmd += ["--title", emphasis.title]
        if emphasis.skills_order:
            cmd += ["--skills-order", ",".join(emphasis.skills_order)]
        if emphasis.compact:
            cmd.append("--compact")
        if emphasis.roomy:
            cmd.append("--roomy")
        if emphasis.include_awards is False:
            cmd.append("--no-awards")
        elif emphasis.include_awards is True:
            cmd.append("--include-awards")
        if emphasis.condense_older:
            cmd.append("--condense-older")
        return cmd

    def _run_builder(self, cmd: list[str]) -> bool:
        """Run the builder subprocess. Isolated so it is easy to stub in tests."""
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self._builder_path),
                capture_output=True,
                text=True,
                timeout=self._config.timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            logger.warning("Resume builder timed out after {}s", self._config.timeout)
            return False
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Resume builder invocation failed: {}", exc)
            return False
        if result.returncode != 0:
            logger.warning(
                "Resume builder exited {}: {}",
                result.returncode,
                (result.stderr or result.stdout or "").strip()[:500],
            )
            return False
        return True

    # -- builder profile (name + skill categories) ----------------------------
    def _profile_data(self) -> dict:
        if self._profile is not None:
            return self._profile
        profile: dict = {"name": None, "title": None, "categories": []}
        if self._builder_path is not None:
            master = self._builder_path / "master.yaml"
            if not master.exists():
                master = self._builder_path / "master.example.yaml"
            try:
                import yaml

                data = yaml.safe_load(master.read_text(encoding="utf-8")) or {}
                basics = data.get("basics") or {}
                profile = {
                    "name": basics.get("name"),
                    "title": basics.get("title"),
                    "categories": [
                        s.get("category") for s in (data.get("skills") or []) if s.get("category")
                    ],
                }
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Could not read builder master.yaml for tailoring: {}", exc)
        self._profile = profile
        return self._profile

    def _categories(self) -> list[str]:
        return list(self._profile_data()["categories"])

    def _master_name(self) -> str | None:
        return self._profile_data()["name"]

    def _master_title(self) -> str | None:
        return self._profile_data()["title"]

    def _default_filename(self, key: str) -> str:
        name = self._master_name() or "resume"
        stem = name.replace(" ", "_")
        return f"{stem}_{_slug(key)}.pdf"
