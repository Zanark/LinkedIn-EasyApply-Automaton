"""Launch and manage a Playwright persistent browser context.

The manager reuses an existing browser profile via ``launch_persistent_context``
so the user's LinkedIn session is preserved - this project never automates login
or stores credentials. Chrome, Edge and bundled Chromium are supported in both
headed and headless modes.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING

from loguru import logger

from linkedin_easy_apply.config.models import BrowserConfig, BrowserEngine
from linkedin_easy_apply.utils.paths import ensure_dir

if TYPE_CHECKING:  # pragma: no cover - typing only
    from playwright.sync_api import BrowserContext, Page, Playwright

# Map our engine enum to Playwright channels. Chromium uses the bundled build.
_CHANNELS: dict[BrowserEngine, str | None] = {
    BrowserEngine.CHROME: "chrome",
    BrowserEngine.EDGE: "msedge",
    BrowserEngine.CHROMIUM: None,
}

_DEFAULT_PROFILE = Path(".browser-profile")


class BrowserLaunchError(RuntimeError):
    """Raised when the browser context cannot be launched."""


class BrowserManager:
    """Own the Playwright lifecycle and expose a ready-to-use page."""

    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    # -- lifecycle ------------------------------------------------------------
    def start(self) -> BrowserManager:
        """Start Playwright and launch the persistent context."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - env specific
            raise BrowserLaunchError(
                "Playwright is not installed. Run 'pip install playwright'."
            ) from exc

        profile = Path(self._config.profile_path or _DEFAULT_PROFILE)
        ensure_dir(profile)
        download_dir = ensure_dir(self._config.download_dir)

        record_har_path = None
        if self._config.record_har:
            har_dir = ensure_dir(self._config.har_dir)
            record_har_path = har_dir / "session.har"

        logger.info(
            "Launching {} (headless={}) with profile {}",
            self._config.engine.value,
            self._config.headless,
            profile,
        )
        self._playwright = sync_playwright().start()
        launcher = self._playwright.chromium
        try:
            self._context = launcher.launch_persistent_context(
                user_data_dir=str(profile),
                channel=_CHANNELS[self._config.engine],
                headless=self._config.headless,
                slow_mo=self._config.slow_mo_ms,
                viewport={
                    "width": self._config.viewport_width,
                    "height": self._config.viewport_height,
                },
                accept_downloads=True,
                downloads_path=str(download_dir),
                record_har_path=str(record_har_path) if record_har_path else None,
            )
        except Exception as exc:  # pragma: no cover - env specific
            self.stop()
            raise BrowserLaunchError(
                f"Failed to launch browser '{self._config.engine.value}'. "
                "Ensure the browser is installed (or run 'playwright install chromium') "
                f"and that no other instance is locking the profile. Original error: {exc}"
            ) from exc

        self._context.set_default_timeout(self._config.default_timeout_ms)
        self._context.set_default_navigation_timeout(self._config.navigation_timeout_ms)
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self

    def stop(self) -> None:
        """Close the context and stop Playwright, swallowing shutdown errors."""
        for closer in (self._close_context, self._stop_playwright):
            try:
                closer()
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Error during browser shutdown: {}", exc)

    def _close_context(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
            self._page = None

    def _stop_playwright(self) -> None:
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    # -- accessors ------------------------------------------------------------
    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise BrowserLaunchError("Browser context is not started. Call start() first.")
        return self._context

    @property
    def page(self) -> Page:
        if self._page is None:
            raise BrowserLaunchError("No active page. Call start() first.")
        return self._page

    def new_page(self) -> Page:
        return self.context.new_page()

    # -- context manager ------------------------------------------------------
    def __enter__(self) -> BrowserManager:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.stop()
