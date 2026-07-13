"""Extract job metadata from the LinkedIn job-detail pane.

The DOM-facing methods are heuristic and defensive. The metadata-parsing logic
is factored into the pure :func:`parse_metadata` function so it can be unit
tested without a browser.
"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.forms.dom_utils import first, is_visible, safe_text
from linkedin_easy_apply.jobs.models import Job

_APPLICANTS_RE = re.compile(r"([\d,]+)\s+applicant", re.IGNORECASE)
_JOB_ID_RE = re.compile(r"/jobs/view/(\d+)")
_WORKPLACE_RE = re.compile(r"\b(remote|hybrid|on[- ]?site)\b", re.IGNORECASE)
_EMPLOYMENT_RE = re.compile(
    r"\b(full[- ]?time|part[- ]?time|contract|temporary|internship|volunteer)\b", re.IGNORECASE
)
_AGE_RE = re.compile(
    r"(\d+\s+(?:second|minute|hour|day|week|month)s?\s+ago|just now|today|yesterday)",
    re.IGNORECASE,
)


def parse_metadata(text: str) -> dict[str, Any]:
    """Parse the free-text metadata line(s) of a job posting.

    Extracts number of applicants, posting age, workplace type and employment
    type. Returns only the keys it can confidently populate.
    """
    result: dict[str, Any] = {}
    if not text:
        return result

    applicants = _APPLICANTS_RE.search(text)
    if applicants:
        result["applicants"] = int(applicants.group(1).replace(",", ""))

    age = _AGE_RE.search(text)
    if age:
        result["posting_age"] = age.group(1).strip()

    workplace = _WORKPLACE_RE.search(text)
    if workplace:
        value = workplace.group(1).lower().replace(" ", "-")
        result["workplace_type"] = "on-site" if value.startswith("on") else value

    employment = _EMPLOYMENT_RE.search(text)
    if employment:
        result["employment_type"] = employment.group(1).lower().replace(" ", "-")

    return result


def extract_job_id(url: str) -> str | None:
    match = _JOB_ID_RE.search(url or "")
    return match.group(1) if match else None


class JobExtractor:
    """Read the currently displayed job-detail pane into a :class:`Job`."""

    def extract(self, page: Any, *, search_name: str | None = None) -> Job:
        url = self._canonical_url(page)
        job = Job(url=url, external_id=extract_job_id(url), search_name=search_name)

        job.title = self._text(page, selectors.JOB_TITLE)
        job.company = self._text(page, selectors.JOB_COMPANY)
        job.description = self._text(page, selectors.JOB_DESCRIPTION)

        metadata_text = " ".join(
            filter(None, (self._text(page, selectors.JOB_PRIMARY_DESC), self._insights(page)))
        )
        location = self._first_segment(self._text(page, selectors.JOB_PRIMARY_DESC))
        if location:
            job.location = location

        for key, value in parse_metadata(metadata_text).items():
            setattr(job, key, value)

        job.easy_apply = self._has_easy_apply(page)
        job.already_applied = self._is_applied(page)
        logger.debug(
            "Extracted job {}: {} | easy_apply={} already_applied={}",
            job.external_id,
            job.summary,
            job.easy_apply,
            job.already_applied,
        )
        return job

    # -- helpers --------------------------------------------------------------
    def _canonical_url(self, page: Any) -> str:
        try:
            url = page.url
        except Exception:  # pragma: no cover - defensive
            return ""
        job_id = extract_job_id(url)
        return f"https://www.linkedin.com/jobs/view/{job_id}/" if job_id else url

    def _text(self, page: Any, selector_list: list[str]) -> str | None:
        node = first(page, selector_list)
        text = safe_text(node) if node is not None else ""
        return text or None

    def _insights(self, page: Any) -> str | None:
        group = None
        for selector in selectors.JOB_INSIGHT_TEXT:
            try:
                candidate = page.locator(selector)
                if candidate.count() > 0:
                    group = candidate
                    break
            except Exception:  # pragma: no cover - defensive
                continue
        if group is None:
            return None
        try:
            return " ".join(t.strip() for t in group.all_inner_texts() if t.strip())
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _first_segment(text: str | None) -> str | None:
        if not text:
            return None
        # Primary description is usually "Company · Location · reposted ..."
        parts = [p.strip() for p in re.split(r"[·|]", text) if p.strip()]
        return parts[1] if len(parts) > 1 else (parts[0] if parts else None)

    def _has_easy_apply(self, page: Any) -> bool:
        button = first(page, selectors.EASY_APPLY_BUTTON)
        if button is None or not is_visible(button):
            return False
        try:
            label = (button.get_attribute("aria-label") or button.inner_text() or "").lower()
        except Exception:  # pragma: no cover - defensive
            return True
        return "easy apply" in label

    def _is_applied(self, page: Any) -> bool:
        marker = first(page, selectors.JOB_APPLIED_MARKER)
        return marker is not None and is_visible(marker)
