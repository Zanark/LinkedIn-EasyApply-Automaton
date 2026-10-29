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
# The rebuilt results page keeps the id only in the query string.
_CURRENT_JOB_ID_RE = re.compile(r"[?&]currentJobId=(\d+)")
# "Senior Cloud Engineer | Teradata | LinkedIn"
_DOC_TITLE_RE = re.compile(r"^(?P<title>.+?)\s*\|\s*(?P<company>.+?)\s*\|\s*LinkedIn\s*$")
# Result cards end their location with the workplace type in brackets.
_WORKPLACE_PAREN_RE = re.compile(r"\((?:Remote|Hybrid|On-?site)\)", re.IGNORECASE)
_VERIFIED_MARKER = "(Verified job)"

# Climb from the "About the job" heading to the ancestor that holds the body.
_DESCRIPTION_JS = """
el => {
  let node = el;
  for (let i = 0; i < 6 && node; i++) {
    node = node.parentElement;
    if (node && node.innerText && node.innerText.length > 400) return node.innerText;
  }
  return (node && node.innerText) || '';
}
"""
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
    """Return the job id from a canonical ``/jobs/view/`` or ``currentJobId`` URL."""
    for pattern in (_JOB_ID_RE, _CURRENT_JOB_ID_RE):
        match = pattern.search(url or "")
        if match:
            return match.group(1)
    return None


def parse_card_location(
    card_text: str | None, *, title: str | None = None, company: str | None = None
) -> str | None:
    """Pull the location out of a result card's text.

    A card reads ``"<title> (Verified job)<title> <company><location> (<workplace>)..."``,
    so the location is what is left between the company and the workplace
    marker once the repeated title and the company are removed.
    """
    text = " ".join((card_text or "").split())
    if not text:
        return None
    marker = _WORKPLACE_PAREN_RE.search(text)
    if not marker:
        return None
    head = text[: marker.start()].strip()
    if _VERIFIED_MARKER in head:
        head = head.split(_VERIFIED_MARKER, 1)[1].strip()
    for prefix in (title, company):
        if prefix and head.lower().startswith(prefix.lower()):
            head = head[len(prefix) :].strip()
    head = head.strip(" -·,")
    # A sane location is a few words, not a leftover sentence.
    return head if head and len(head.split()) <= 6 else None


def parse_document_title(raw: str | None) -> tuple[str | None, str | None]:
    """Split ``"<job title> | <company> | LinkedIn"`` into its two parts.

    The rebuilt job page has no ``h1`` and only hashed class names, but the
    document title still carries both fields.
    """
    match = _DOC_TITLE_RE.match((raw or "").strip())
    if not match:
        return None, None
    return (match.group("title").strip() or None, match.group("company").strip() or None)


class JobExtractor:
    """Read the currently displayed job-detail pane into a :class:`Job`."""

    def extract(
        self, page: Any, *, search_name: str | None = None, card_text: str | None = None
    ) -> Job:
        url = self._canonical_url(page)
        job = Job(url=url, external_id=extract_job_id(url), search_name=search_name)

        job.title = self._text(page, selectors.JOB_TITLE)
        job.company = self._text(page, selectors.JOB_COMPANY)
        job.description = self._text(page, selectors.JOB_DESCRIPTION)

        # Class-based selectors return nothing on the rebuilt page; fall back to
        # the document title and the "About the job" heading, which survive.
        if not job.title or not job.company:
            doc_title, doc_company = parse_document_title(self._page_title(page))
            job.title = job.title or doc_title
            job.company = job.company or doc_company
        if not job.description:
            job.description = self._description_by_heading(page)

        metadata_text = " ".join(
            filter(
                None,
                (
                    self._text(page, selectors.JOB_PRIMARY_DESC),
                    self._insights(page),
                    # The card carries workplace type and posting signals that
                    # the rebuilt detail pane no longer exposes by class.
                    card_text,
                ),
            )
        )
        location = self._first_segment(self._text(page, selectors.JOB_PRIMARY_DESC))
        if not location:
            location = parse_card_location(card_text, title=job.title, company=job.company)
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

    @staticmethod
    def _page_title(page: Any) -> str | None:
        try:
            return page.title()
        except Exception:  # pragma: no cover - defensive
            return None

    @staticmethod
    def _description_by_heading(page: Any) -> str | None:
        """Read the posting body from the ``About the job`` section."""
        try:
            heading = page.get_by_role("heading", name=selectors.JOB_DESCRIPTION_HEADING)
            if heading.count() == 0:
                return None
            raw = heading.first.evaluate(_DESCRIPTION_JS)
        except Exception:  # pragma: no cover - defensive
            return None
        text = " ".join((raw or "").split())
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
