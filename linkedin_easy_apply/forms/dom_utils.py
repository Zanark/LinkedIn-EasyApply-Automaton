"""Small helpers for working with candidate selector lists on Playwright scopes.

A "scope" is any object exposing ``locator(selector)`` (a Page or Locator).
These helpers try each selector in order and return the first that matches,
which is what makes the automation resilient to DOM changes.
"""

from __future__ import annotations

from typing import Any


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
