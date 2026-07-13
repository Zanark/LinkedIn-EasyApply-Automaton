"""Automatic resume selection.

Selection strategy, in order:

1. **Explicit mapping** - the ``resume.mapping`` in configuration maps a role or
   keyword to a resume file. The best (highest weighted) match wins.
2. **Keyword scoring** - if no mapping matches, score available resumes by how
   many of their filename tokens appear in the job text.
3. **Default** - fall back to ``resume.default``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from rapidfuzz import fuzz

from linkedin_easy_apply.config.models import ResumeConfig
from linkedin_easy_apply.utils.text import normalize, tokenize

_RESUME_SUFFIXES = {".pdf", ".doc", ".docx"}


@dataclass(slots=True)
class ResumeChoice:
    """The chosen resume plus a human-readable justification."""

    name: str
    path: Path
    reason: str
    score: float = 0.0


class ResumeSelector:
    """Choose the most appropriate resume for a job."""

    def __init__(self, config: ResumeConfig) -> None:
        self._config = config
        self._directory = Path(config.directory)

    def available_resumes(self) -> dict[str, Path]:
        """Map resume filename -> path for every resume in the directory."""
        if not self._directory.is_dir():
            return {}
        return {
            item.name: item
            for item in self._directory.iterdir()
            if item.is_file() and item.suffix.lower() in _RESUME_SUFFIXES
        }

    def _resolve_file(self, filename: str) -> Path | None:
        candidate = self._directory / filename
        if candidate.is_file():
            return candidate
        # allow mapping values given without an extension
        for existing_name, path in self.available_resumes().items():
            if normalize(Path(existing_name).stem) == normalize(Path(filename).stem):
                return path
        return None

    def select(self, job_title: str, job_description: str | None = None) -> ResumeChoice | None:
        haystack = normalize(f"{job_title} {job_description or ''}")

        best_key: str | None = None
        best_score = 0.0
        for key, filename in self._config.mapping.items():
            score = self._match_score(normalize(key), haystack)
            if score > best_score:
                best_score, best_key = score, filename
        if best_key and best_score >= 60:
            path = self._resolve_file(best_key)
            if path:
                return ResumeChoice(
                    path.name, path, f"matched mapping (score {best_score:.0f})", best_score
                )
            logger.warning("Mapped resume '{}' not found in {}", best_key, self._directory)

        keyword_choice = self._keyword_scored(haystack)
        if keyword_choice:
            return keyword_choice

        if self._config.default:
            path = self._resolve_file(self._config.default)
            if path:
                return ResumeChoice(path.name, path, "default resume", 0.0)
            logger.warning(
                "Default resume '{}' not found in {}", self._config.default, self._directory
            )

        logger.warning("No resume could be selected for '{}'", job_title)
        return None

    @staticmethod
    def _match_score(key: str, haystack: str) -> float:
        if not key:
            return 0.0
        if key in haystack:
            return 100.0
        return float(fuzz.partial_ratio(key, haystack))

    def _keyword_scored(self, haystack: str) -> ResumeChoice | None:
        best: ResumeChoice | None = None
        for name, path in self.available_resumes().items():
            tokens = tokenize(Path(name).stem)
            overlap = sum(1 for token in tokens if token in haystack)
            if tokens and overlap:
                score = overlap / len(tokens) * 100
                if best is None or score > best.score:
                    best = ResumeChoice(name, path, f"keyword overlap ({overlap} tokens)", score)
        return best
