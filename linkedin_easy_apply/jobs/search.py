"""Navigate a LinkedIn job-search results page and iterate its jobs.

The iterator lazily loads results (LinkedIn paginates and lazy-loads cards),
opens each job in the detail pane, and yields an extracted :class:`Job`. The
detail pane stays active after each yield so the orchestrator can immediately
run the Easy Apply workflow on the same page.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from loguru import logger

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.dom_utils import first, first_group
from linkedin_easy_apply.jobs.extractor import JobExtractor
from linkedin_easy_apply.jobs.models import Job

_JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")


class JobSearch:
    """Drive discovery over a single job-search URL."""

    def __init__(self, page: Any, extractor: JobExtractor | None = None) -> None:
        self._page = page
        self._extractor = extractor or JobExtractor()

    def open(self, url: str) -> None:
        logger.info("Opening search {}", url)
        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_timeout(2500)

    def iterate(self, url: str, search_name: str, max_jobs: int) -> Iterator[Job]:
        """Yield up to *max_jobs* jobs from *url*."""
        self.open(url)
        job_ids = self._collect_ids(max_jobs)
        logger.info("Collected {} job id(s) from '{}'", len(job_ids), search_name)
        for job_id in job_ids[:max_jobs]:
            if not self._open_card(job_id):
                continue
            self._page.wait_for_timeout(1200)
            yield self._extractor.extract(self._page, search_name=search_name)

    # -- internals ------------------------------------------------------------
    def _collect_ids(self, max_jobs: int, max_scrolls: int = 15) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        stagnant = 0
        for _ in range(max_scrolls):
            for job_id in self._current_ids():
                if job_id not in seen:
                    seen.add(job_id)
                    ordered.append(job_id)
            if len(ordered) >= max_jobs:
                break
            grew = self._scroll_list(len(ordered))
            stagnant = 0 if grew else stagnant + 1
            if stagnant >= 3:
                break
        return ordered

    def _current_ids(self) -> list[str]:
        cards = first_group(self._page, selectors.JOB_CARD)
        if cards is None:
            return []
        ids: list[str] = []
        try:
            total = cards.count()
        except Exception:  # pragma: no cover - defensive
            return []
        for i in range(total):
            job_id = self._card_id(cards.nth(i))
            if job_id:
                ids.append(job_id)
        return ids

    def _card_id(self, card: Any) -> str | None:
        try:
            attr = card.get_attribute("data-job-id")
            if attr and attr.isdigit():
                return attr
            link = card.locator("a").first
            href = link.get_attribute("href") if link.count() > 0 else None
        except Exception:  # pragma: no cover - defensive
            return None
        match = _JOB_ID_RE.search(href or "")
        return match.group(1) if match else None

    def _locate_card(self, job_id: str) -> Any:
        card = self._page.locator(f"[data-job-id='{job_id}']").first
        if card.count() == 0:
            card = self._page.locator(f"a[href*='/jobs/view/{job_id}']").first
        return card

    def _open_card(self, job_id: str) -> bool:
        self._clear_blocking_modal()
        try:
            card = self._locate_card(job_id)
            card.scroll_into_view_if_needed(timeout=5000)
            card.click(timeout=5000)
            return True
        except Exception as exc:  # pragma: no cover - defensive
            # A leftover modal overlay (e.g. a discard confirmation from the
            # previous job) can intercept the click - clear it and retry once.
            if self._clear_blocking_modal():
                try:
                    card = self._locate_card(job_id)
                    card.scroll_into_view_if_needed(timeout=5000)
                    card.click(timeout=5000)
                    return True
                except Exception as exc2:  # pragma: no cover - defensive
                    logger.warning("Could not open job {}: {}", job_id, exc2)
                    return False
            logger.warning("Could not open job {}: {}", job_id, exc)
            return False

    def _force_click(self, selector_list: list[str]) -> bool:
        button = first(self._page, selector_list)
        if button is None:
            return False
        try:
            button.click(force=True, timeout=2000)
            return True
        except Exception:  # pragma: no cover - defensive
            return False

    def _clear_blocking_modal(self) -> bool:
        """Dismiss a leftover Easy Apply / discard-confirmation modal, if present."""
        try:
            if first(self._page, selectors.DISCARD_CONFIRMATION) is not None:
                self._force_click(selectors.BTN_DISCARD)
                self._page.wait_for_timeout(400)
                return True
            if self._page.locator("div.artdeco-modal-overlay").count() > 0:
                self._force_click(selectors.BTN_DISMISS)
                self._page.wait_for_timeout(300)
                self._force_click(selectors.BTN_DISCARD)
                self._page.wait_for_timeout(300)
                return True
        except Exception:  # pragma: no cover - defensive
            return False
        return False

    def _scroll_list(self, current_count: int) -> bool:
        """Scroll the results list to trigger lazy loading. Returns True if new cards appeared."""
        container = first_group(self._page, selectors.JOB_LIST_CONTAINER)
        try:
            if container is not None:
                container.first.evaluate("el => el.scrollBy(0, el.clientHeight)")
            else:
                self._page.mouse.wheel(0, 1200)
        except Exception:  # pragma: no cover - defensive
            self._page.mouse.wheel(0, 1200)
        self._page.wait_for_timeout(1200)
        return len(self._current_ids()) > current_count
