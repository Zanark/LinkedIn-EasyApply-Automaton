"""Navigate a LinkedIn job-search results page and iterate its jobs.

The iterator lazily loads results (LinkedIn paginates and lazy-loads cards),
opens each job in the detail pane, and yields an extracted :class:`Job`. The
detail pane stays active after each yield so the orchestrator can immediately
run the Easy Apply workflow on the same page.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from loguru import logger

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.dom_utils import first, first_group
from linkedin_easy_apply.jobs.extractor import JobExtractor
from linkedin_easy_apply.jobs.models import Job
from linkedin_easy_apply.utils.paths import ensure_dir, timestamp_slug

_JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")
# Logged-out / shared links carry a slug before the id: /jobs/view/swe-at-acme-4123456789
_SLUG_JOB_ID_RE = re.compile(r"/jobs/view/[^/?#]*?(\d{6,})")
# Guest result cards identify the posting through an entity urn instead of a link.
_URN_JOB_ID_RE = re.compile(r"jobPosting:(\d+)")
_AUTH_WALL_URL_RE = re.compile(r"linkedin\.com/(login|authwall|checkpoint|uas/)", re.IGNORECASE)

# Walk up from a job card to the nearest scrollable ancestor and page it down.
# LinkedIn virtualises the results column, so scrolling the *window* never loads
# more cards - the inner pane is what has to move.
_SCROLL_PANE_JS = """
el => {
  let node = el;
  while (node) {
    const style = window.getComputedStyle(node);
    const scrollable = /(auto|scroll|overlay)/.test(style.overflowY);
    if (scrollable && node.scrollHeight > node.clientHeight + 16) {
      const before = node.scrollTop;
      node.scrollTop = Math.min(before + node.clientHeight, node.scrollHeight);
      return node.scrollTop !== before;
    }
    node = node.parentElement;
  }
  return false;
}
"""

_DEFAULT_RESULTS_TIMEOUT_MS = 20_000
_DEFAULT_DIAGNOSTICS_DIR = Path("logs") / "diagnostics"


def job_id_from_value(value: str | None) -> str | None:
    """Return the numeric LinkedIn job id found in *value*, if any.

    Accepts a bare id (``"4123456789"``), a canonical job URL, a slugged job URL
    and an entity urn - i.e. every form the different result-page variants use.
    """
    text = (value or "").strip()
    if not text:
        return None
    if text.isdigit():
        return text
    for pattern in (_JOB_ID_RE, _SLUG_JOB_ID_RE, _URN_JOB_ID_RE):
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def paginated_url(url: str, start: int) -> str:
    """Return *url* with LinkedIn's ``start`` pagination offset set to *start*.

    LinkedIn job-search results are paginated via a ``start`` query parameter
    (``start=25`` is the second page, ``start=50`` the third, ...). This rebuilds
    the URL with that offset, replacing any existing ``start`` and leaving every
    other query parameter untouched. ``start=0`` (the first page) is emitted
    without the parameter so the canonical first-page URL is returned unchanged.
    """
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "start"]
    if start > 0:
        query.append(("start", str(start)))
    return urlunsplit(parts._replace(query=urlencode(query)))


class JobSearch:
    """Drive discovery over a single job-search URL."""

    def __init__(
        self,
        page: Any,
        extractor: JobExtractor | None = None,
        *,
        results_timeout_ms: int = _DEFAULT_RESULTS_TIMEOUT_MS,
        diagnostics_dir: str | Path = _DEFAULT_DIAGNOSTICS_DIR,
    ) -> None:
        self._page = page
        self._extractor = extractor or JobExtractor()
        self._results_timeout_ms = results_timeout_ms
        self._diagnostics_dir = Path(diagnostics_dir)

    def open(self, url: str) -> None:
        logger.info("Opening search {}", url)
        self._page.goto(url, wait_until="domcontentloaded")
        self._wait_for_results()

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

    def open_job(self, url: str, search_name: str = "reapply") -> Job | None:
        """Navigate straight to a single job page and extract it.

        Used by the *reapply* flow, which retries specific previously-failed
        jobs by their stored ``/jobs/view/<id>/`` URL rather than crawling a
        search. Any leftover modal is cleared first, and navigation failures
        return ``None`` so the caller can skip that job.
        """
        self._clear_blocking_modal()
        try:
            self._page.goto(url, wait_until="domcontentloaded")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Could not open job {}: {}", url, exc)
            return None
        self._page.wait_for_timeout(1800)
        self._clear_blocking_modal()
        return self._extractor.extract(self._page, search_name=search_name)

    # -- internals ------------------------------------------------------------
    def _wait_for_results(self) -> bool:
        """Block until the first job card is in the DOM.

        LinkedIn renders the results list client-side after the document loads,
        so a fixed sleep raced the first paint and silently produced zero jobs.
        Returns ``False`` when nothing appeared within the timeout; the caller
        reports the reason via :meth:`_report_empty_results`.
        """
        selector = ", ".join(selectors.JOB_CARD)
        try:
            self._page.wait_for_selector(
                selector, state="attached", timeout=self._results_timeout_ms
            )
        except Exception:
            logger.debug("No job card attached within {} ms", self._results_timeout_ms)
            return False
        # Let the remaining cards of the first batch hydrate.
        self._page.wait_for_timeout(1200)
        return True

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
        if not ordered:
            self._report_empty_results()
        return ordered

    def _current_ids(self) -> list[str]:
        ids = [job_id for job_id in (self._card_id(c) for c in self._cards()) if job_id]
        return ids or self._link_ids()

    def _cards(self) -> list[Any]:
        group = first_group(self._page, selectors.JOB_CARD)
        if group is None:
            return []
        try:
            return [group.nth(i) for i in range(group.count())]
        except Exception:  # pragma: no cover - defensive
            return []

    def _link_ids(self) -> list[str]:
        """Fallback discovery: read every ``/jobs/view/`` link on the page.

        Used when no known card selector matches, which keeps discovery working
        through a LinkedIn markup change instead of reporting zero jobs.
        """
        try:
            hrefs = self._page.eval_on_selector_all(
                selectors.JOB_CARD_LINK,
                "els => els.map(el => el.getAttribute('href'))",
            )
        except Exception:  # pragma: no cover - defensive
            return []
        ordered: list[str] = []
        seen: set[str] = set()
        for href in hrefs or []:
            job_id = job_id_from_value(href)
            if job_id and job_id not in seen:
                seen.add(job_id)
                ordered.append(job_id)
        return ordered

    def _card_id(self, card: Any) -> str | None:
        try:
            for attribute in ("data-job-id", "data-occludable-job-id", "data-entity-urn"):
                job_id = job_id_from_value(card.get_attribute(attribute))
                if job_id:
                    return job_id
            link = card.locator(selectors.JOB_CARD_LINK).first
            href = link.get_attribute("href") if link.count() > 0 else None
        except Exception:  # pragma: no cover - defensive
            return None
        return job_id_from_value(href)

    def _locate_card(self, job_id: str) -> Any:
        candidates = (
            f"[data-job-id='{job_id}']",
            f"[data-occludable-job-id='{job_id}']",
            f"a[href*='/jobs/view/{job_id}']",
            f"a[href*='-{job_id}']",
        )
        for selector in candidates:
            locator = self._page.locator(selector).first
            try:
                if locator.count() > 0:
                    return locator
            except Exception:  # pragma: no cover - defensive
                continue
        return self._page.locator(candidates[0]).first

    @staticmethod
    def _clickable(card: Any) -> Any:
        """Prefer the card's job link: the list item itself is often inert."""
        try:
            link = card.locator(selectors.JOB_CARD_LINK).first
            if link.count() > 0:
                return link
        except Exception:  # pragma: no cover - defensive
            pass
        return card

    def _open_card(self, job_id: str) -> bool:
        self._clear_blocking_modal()
        try:
            card = self._locate_card(job_id)
            card.scroll_into_view_if_needed(timeout=5000)
            self._clickable(card).click(timeout=5000)
            return True
        except Exception as exc:  # pragma: no cover - defensive
            # A leftover modal overlay (e.g. a discard confirmation from the
            # previous job) can intercept the click - clear it and retry once.
            if self._clear_blocking_modal():
                try:
                    card = self._locate_card(job_id)
                    card.scroll_into_view_if_needed(timeout=5000)
                    self._clickable(card).click(timeout=5000)
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
        if not self._scroll_results_pane():
            try:
                self._page.mouse.wheel(0, 1200)
            except Exception:  # pragma: no cover - defensive
                pass
        self._page.wait_for_timeout(1200)
        return len(self._current_ids()) > current_count

    def _scroll_results_pane(self) -> bool:
        """Page down the scrollable results column. Returns True if it moved."""
        moved = False
        anchor = self._last_card()
        if anchor is not None:
            try:
                anchor.scroll_into_view_if_needed(timeout=3000)
                moved = True
            except Exception:  # pragma: no cover - defensive
                anchor = None
        target = anchor if anchor is not None else first(self._page, selectors.JOB_LIST_CONTAINER)
        if target is None:
            return moved
        try:
            return bool(target.evaluate(_SCROLL_PANE_JS)) or moved
        except Exception:  # pragma: no cover - defensive
            return moved

    def _last_card(self) -> Any | None:
        cards = self._cards()
        return cards[-1] if cards else None

    # -- diagnostics ----------------------------------------------------------
    def _report_empty_results(self) -> None:
        """Explain *why* a results page yielded no jobs instead of failing silently."""
        page_url = self._safe(lambda: self._page.url) or "<unknown>"
        title = self._safe(lambda: self._page.title()) or ""
        logger.warning("No job cards found on {} (title={!r})", page_url, title)

        if _AUTH_WALL_URL_RE.search(page_url) or first(self._page, selectors.AUTH_WALL) is not None:
            logger.error(
                "LinkedIn served a sign-in wall: the automation browser profile is not "
                "logged in (or its session expired). Run 'apply.py login', sign in in "
                "that window, then re-run. Note this profile is separate from your "
                "everyday browser, so being logged in there does not count."
            )
        elif first(self._page, selectors.NO_RESULTS) is not None:
            logger.warning(
                "LinkedIn reported no matching jobs for this search URL - widen the "
                "filters (keywords, date posted, job type) and try again."
            )
        else:
            logger.error(
                "The page loaded but no known job-card markup matched. LinkedIn most "
                "likely changed its results DOM: update JOB_CARD in "
                "linkedin_easy_apply/forms/selectors.py using the saved HTML dump."
            )

        counts = {
            selector: self._safe(lambda s=selector: self._page.locator(s).count())
            for selector in [*selectors.JOB_CARD, selectors.JOB_CARD_LINK]
        }
        logger.warning("Job-card selector match counts: {}", counts)
        logger.warning("Frames on page: {}", self._safe(lambda: len(self._page.frames)))
        self._dump_page("search-no-results")

    def _dump_page(self, label: str) -> None:
        """Save a screenshot + HTML snapshot so selectors can be fixed offline."""
        try:
            directory = ensure_dir(self._diagnostics_dir)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Could not create diagnostics directory: {}", exc)
            return
        stem = f"{timestamp_slug()}-{label}"
        try:
            self._page.screenshot(path=str(directory / f"{stem}.png"), full_page=False)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Could not capture diagnostics screenshot: {}", exc)
        try:
            (directory / f"{stem}.html").write_text(self._page.content(), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Could not save diagnostics HTML: {}", exc)
        logger.warning("Saved page diagnostics to {}", directory / f"{stem}.*")

    @staticmethod
    def _safe(call: Any) -> Any:
        try:
            return call()
        except Exception:  # pragma: no cover - defensive
            return None
