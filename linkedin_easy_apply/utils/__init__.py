"""Cross-cutting utilities: text normalisation, retries, paths, screenshots."""

from __future__ import annotations

from linkedin_easy_apply.utils.paths import ensure_dir, project_root, timestamp_slug
from linkedin_easy_apply.utils.retry import RetryError, retry
from linkedin_easy_apply.utils.screenshots import ScreenshotManager
from linkedin_easy_apply.utils.text import normalize, slugify, tokenize

__all__ = [
    "normalize",
    "slugify",
    "tokenize",
    "retry",
    "RetryError",
    "ensure_dir",
    "project_root",
    "timestamp_slug",
    "ScreenshotManager",
]
