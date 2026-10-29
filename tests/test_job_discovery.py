"""Tests for search-results discovery: how job ids are read off a results page.

These cover the failure mode where a LinkedIn markup change (or a signed-out
profile) made ``JobSearch`` report "Collected 0 job id(s)" with no explanation:
id parsing across URL shapes, the card-selector fallbacks, the link-level
fallback, and the diagnostics emitted when a page genuinely yields nothing.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from loguru import logger

from linkedin_easy_apply.forms import selectors
from linkedin_easy_apply.jobs.extractor import (
    extract_job_id,
    parse_card_location,
    parse_document_title,
)
from linkedin_easy_apply.jobs.search import JobSearch, job_id_from_value, paginated_url


# -- fake DOM ---------------------------------------------------------------- #
class _FakeElement:
    def __init__(self, attrs: dict[str, str] | None = None, href: str | None = None) -> None:
        self.attrs = attrs or {}
        self.href = href


class _FakeLocator:
    def __init__(self, elements: list[_FakeElement]) -> None:
        self._elements = list(elements)

    def count(self) -> int:
        return len(self._elements)

    def nth(self, index: int) -> _FakeLocator:
        return _FakeLocator([self._elements[index]])

    @property
    def first(self) -> _FakeLocator:
        return _FakeLocator(self._elements[:1])

    def get_attribute(self, name: str) -> str | None:
        if not self._elements:
            return None
        element = self._elements[0]
        return element.href if name == "href" else element.attrs.get(name)

    def locator(self, selector: str) -> _FakeLocator:
        if self._elements and selector == selectors.JOB_CARD_LINK and self._elements[0].href:
            return _FakeLocator([_FakeElement(href=self._elements[0].href)])
        return _FakeLocator([])

    def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
        return None

    def evaluate(self, _script: str) -> bool:
        return False


class _FakePage:
    """A page whose DOM is a plain ``selector -> elements`` mapping."""

    def __init__(
        self,
        matches: dict[str, list[_FakeElement]] | None = None,
        *,
        links: list[str] | None = None,
        url: str = "https://www.linkedin.com/jobs/search/?keywords=python",
        title: str = "Jobs | LinkedIn",
    ) -> None:
        self.matches = matches or {}
        self.links = links or []
        self.url = url
        self.frames = [object()]
        self.mouse = SimpleNamespace(wheel=lambda _x, _y: None)
        self._title = title

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self.matches.get(selector, []))

    def eval_on_selector_all(self, selector: str, _script: str) -> list[str]:
        return self.links if selector == selectors.JOB_CARD_LINK else []

    def wait_for_selector(self, selector: str, state: str = "", timeout: int = 0) -> object:
        if any(self.matches.get(part.strip()) for part in selector.split(",")):
            return object()
        raise RuntimeError("timeout exceeded")

    def wait_for_timeout(self, _ms: int) -> None:
        return None

    def goto(self, url: str, wait_until: str | None = None) -> None:
        self.url = url

    def title(self) -> str:
        return self._title

    def content(self) -> str:
        return "<html><body>snapshot</body></html>"

    def screenshot(self, path: str, full_page: bool = False) -> None:
        Path(path).write_bytes(b"fake-png")


def _search(page: _FakePage, tmp_path: Path) -> JobSearch:
    extractor = SimpleNamespace(extract=lambda _page, search_name=None: None)
    return JobSearch(
        page,  # type: ignore[arg-type]
        extractor,  # type: ignore[arg-type]
        results_timeout_ms=10,
        diagnostics_dir=tmp_path / "diagnostics",
    )


def _captured_logs() -> tuple[list[str], int]:
    messages: list[str] = []
    handler_id = logger.add(messages.append, level="WARNING")
    return messages, handler_id


# -- job id parsing ---------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("4123456789", "4123456789"),
        ("/jobs/view/4123456789/", "4123456789"),
        ("https://www.linkedin.com/jobs/view/4123456789/?refId=abc", "4123456789"),
        # Slugged URL served to logged-out visitors and in shared links.
        ("https://in.linkedin.com/jobs/view/senior-engineer-at-acme-4123456789", "4123456789"),
        ("urn:li:jobPosting:4123456789", "4123456789"),
        ("/jobs/search/?currentJobId=4123456789", None),
        ("", None),
        (None, None),
    ],
)
def test_job_id_from_value(value: str | None, expected: str | None):
    assert job_id_from_value(value) == expected


# -- card discovery ---------------------------------------------------------- #
def test_collect_ids_reads_current_virtualised_list(tmp_path: Path):
    """The live list exposes ids on the <li>, not on a div[data-job-id]."""
    page = _FakePage(
        {
            "li[data-occludable-job-id]": [
                _FakeElement({"data-occludable-job-id": "111"}),
                _FakeElement({"data-occludable-job-id": "222"}),
            ]
        }
    )
    assert _search(page, tmp_path)._collect_ids(2) == ["111", "222"]


def test_collect_ids_reads_legacy_cards(tmp_path: Path):
    page = _FakePage({"div.job-card-container": [_FakeElement({"data-job-id": "333"})]})
    assert _search(page, tmp_path)._collect_ids(1) == ["333"]


def test_collect_ids_falls_back_to_card_link(tmp_path: Path):
    """A card with no id attribute still resolves through its job link."""
    page = _FakePage(
        {
            "li[data-occludable-job-id]": [],
            "div.job-card-container": [_FakeElement(href="/jobs/view/444/?refId=x")],
        }
    )
    assert _search(page, tmp_path)._collect_ids(1) == ["444"]


def test_collect_ids_falls_back_to_page_links_when_no_card_matches(tmp_path: Path):
    """Unknown card markup must not mean zero jobs: scan the page's job links."""
    page = _FakePage(
        links=[
            "/jobs/view/555/?refId=a",
            "/jobs/view/555/?refId=b",  # duplicate -> collapsed
            "/jobs/view/666/",
        ]
    )
    assert _search(page, tmp_path)._collect_ids(5) == ["555", "666"]


# -- diagnostics ------------------------------------------------------------- #
def test_empty_results_dump_page_and_explain(tmp_path: Path):
    page = _FakePage()
    messages, handler_id = _captured_logs()
    try:
        assert _search(page, tmp_path)._collect_ids(5) == []
    finally:
        logger.remove(handler_id)

    joined = "\n".join(messages)
    assert "No job cards found" in joined
    assert "changed its results DOM" in joined
    dumps = sorted((tmp_path / "diagnostics").iterdir())
    assert [p.suffix for p in dumps] == [".html", ".png"]


def test_empty_results_reports_sign_in_wall(tmp_path: Path):
    page = _FakePage(
        {"input[name='session_key']": [_FakeElement()]},
        url="https://www.linkedin.com/login?session_redirect=%2Fjobs",
        title="Sign Up | LinkedIn",
    )
    messages, handler_id = _captured_logs()
    try:
        _search(page, tmp_path)._collect_ids(5)
    finally:
        logger.remove(handler_id)
    assert "sign-in wall" in "\n".join(messages)


def test_empty_results_reports_no_matching_jobs(tmp_path: Path):
    page = _FakePage({".jobs-search-no-results-banner": [_FakeElement()]})
    messages, handler_id = _captured_logs()
    try:
        _search(page, tmp_path)._collect_ids(5)
    finally:
        logger.remove(handler_id)
    assert "no matching jobs" in "\n".join(messages)


# -- the hashed-class rebuild ------------------------------------------------- #
# LinkedIn's 2026 jobs UI ships build-generated class names, no data-job-id and
# no <h1>. These cover the replacements: ids from the URL, title/company from
# the document title, location from the card's own text.
def test_job_id_from_current_job_id_url():
    """The rebuilt results page keeps the id only in the query string."""
    url = "https://www.linkedin.com/jobs/search-results/?currentJobId=4482505282&keywords=x"
    assert extract_job_id(url) == "4482505282"


def test_canonical_job_url_still_preferred():
    assert extract_job_id("https://www.linkedin.com/jobs/view/4123456789/") == "4123456789"


def test_job_id_absent():
    assert extract_job_id("https://www.linkedin.com/jobs/search/?keywords=python") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Full Stack Engineer | Deloitte | LinkedIn", ("Full Stack Engineer", "Deloitte")),
        ("Senior Cloud Engineer | Teradata | LinkedIn", ("Senior Cloud Engineer", "Teradata")),
        # A pipe inside the job title must not break the company field.
        ("Engineer | Data | Acme Corp | LinkedIn", ("Engineer", "Data | Acme Corp")),
        ("(99+) Jobs | LinkedIn", (None, None)),
        ("LinkedIn", (None, None)),
        ("", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_document_title(raw, expected):
    assert parse_document_title(raw) == expected


@pytest.mark.parametrize(
    ("card", "title", "company", "expected"),
    [
        (
            "Selected, Full Stack Engineer (Verified job) Full Stack Engineer Deloitte "
            "Hyderabad (Hybrid) 19 connections work here Viewed",
            "Full Stack Engineer",
            "Deloitte",
            "Hyderabad",
        ),
        (
            "CDI/CDQ Developer (Verified job) CDI/CDQ Developer Tata Consultancy Services "
            "Greater Hyderabad Area (On-site) Actively reviewing applicants",
            "CDI/CDQ Developer",
            "Tata Consultancy Services",
            "Greater Hyderabad Area",
        ),
        (
            "Backend Engineer (Verified job) Backend Engineer Globex Remote (Remote) Promoted",
            "Backend Engineer",
            "Globex",
            "Remote",
        ),
        # No workplace marker at all -> nothing to anchor on.
        ("Some Job Acme Posted 3 days ago", "Some Job", "Acme", None),
        ("", None, None, None),
        (None, None, None, None),
    ],
)
def test_parse_card_location(card, title, company, expected):
    assert parse_card_location(card, title=title, company=company) == expected


def test_parse_card_location_rejects_a_sentence():
    """A long leftover is not a location; better None than garbage."""
    card = (
        "Engineer (Verified job) Engineer Acme we are looking for someone who can "
        "do many different things (Remote)"
    )
    assert parse_card_location(card, title="Engineer", company="Acme") is None


def test_card_name_pattern_matches_a_card_and_its_dismiss_button():
    """Both match; only the Dismiss button carries that text as its aria-label."""
    pattern = re.compile(selectors.CARD_ACCESSIBLE_NAME)
    assert pattern.search("Senior Cloud Engineer ... Dismiss Senior Cloud Engineer job ...")
    assert pattern.search("Dismiss Senior Cloud Engineer job")
    assert "Dismiss Senior Cloud Engineer job".startswith(selectors.DISMISS_LABEL_PREFIX)
    assert not "Senior Cloud Engineer (Verified job)".startswith(selectors.DISMISS_LABEL_PREFIX)


# -- pagination -------------------------------------------------------------- #
def test_paginated_url_round_trip():
    url = "https://www.linkedin.com/jobs/search/?keywords=python&f_AL=true"
    assert paginated_url(url, 0) == url
    assert paginated_url(url, 25).endswith("&start=25")
    assert paginated_url(paginated_url(url, 25), 50).endswith("&start=50")

