"""Screenshot capture helper that degrades gracefully.

The helper accepts any object exposing a Playwright-style ``screenshot`` method
so it can be unit-tested with a stub and never hard-depends on Playwright.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from loguru import logger

from linkedin_easy_apply.utils.paths import ensure_dir, timestamp_slug
from linkedin_easy_apply.utils.text import slugify


class _Screenshotable(Protocol):
    def screenshot(self, *, path: str, full_page: bool = ...) -> object: ...


class ScreenshotManager:
    """Persists screenshots under a directory, organised by label + timestamp."""

    def __init__(self, directory: str | Path, enabled: bool = True) -> None:
        self._directory = Path(directory)
        self._enabled = enabled
        if enabled:
            ensure_dir(self._directory)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def capture(self, page: _Screenshotable, label: str, full_page: bool = True) -> Path | None:
        """Capture *page* into a labelled file. Returns the path or ``None``.

        Failures are logged but never raised so a screenshot problem cannot
        abort an application attempt.
        """
        if not self._enabled:
            return None
        filename = f"{timestamp_slug()}-{slugify(label) or 'screenshot'}.png"
        target = self._directory / filename
        try:
            page.screenshot(path=str(target), full_page=full_page)
            logger.debug("Captured screenshot {}", target)
            return target
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to capture screenshot '{}': {}", label, exc)
            return None
