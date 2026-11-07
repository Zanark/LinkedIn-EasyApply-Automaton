"""Small helpers for working with candidate selector lists on Playwright scopes.

A "scope" is any object exposing ``locator(selector)`` (a Page or Locator).
These helpers try each selector in order and return the first that matches,
which is what makes the automation resilient to DOM changes.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


def first(scope: Any, selectors: list[str]) -> Any | None:
    """Return the first locator (from *selectors*) that matches at least once."""
    for selector in selectors:
        try:
            locator = scope.locator(selector)
            if locator.count() > 0:
                return locator.first
        except Exception:  # pragma: no cover - defensive
            continue
    return None


_CLOSE_DIALOGS_JS = """
() => {
  const open = [...document.querySelectorAll('dialog[open]')];
  for (const dialog of open) {
    try { dialog.close(); } catch (e) { dialog.removeAttribute('open'); }
  }
  return open.length;
}
"""


def force_close_dialogs(page: Any) -> int:
    """Close every open native ``<dialog>`` and report how many were closed.

    The application form is a real ``<dialog>``. When its buttons are blocked -
    by a toast, a validation error, or a second overlay - it stays open and
    swallows every click meant for the page behind it, which would strand the
    rest of the run. Closing the element directly always frees the page.
    """
    try:
        closed = int(page.evaluate(_CLOSE_DIALOGS_JS) or 0)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("force_close_dialogs error: {}", exc)
        return 0
    if closed:
        logger.debug("Force-closed {} leftover dialog(s)", closed)
    return closed


def first_group(scope: Any, selectors: list[str]) -> Any | None:
    """Return the locator matching *all* elements for the first selector that hits."""
    for selector in selectors:
        try:
            locator = scope.locator(selector)
            if locator.count() > 0:
                return locator
        except Exception:  # pragma: no cover - defensive
            continue
    return None


def is_visible(locator: Any) -> bool:
    try:
        return bool(locator) and locator.is_visible()
    except Exception:  # pragma: no cover - defensive
        return False


def safe_text(locator: Any) -> str:
    try:
        return (locator.inner_text() or "").strip()
    except Exception:  # pragma: no cover - defensive
        return ""
