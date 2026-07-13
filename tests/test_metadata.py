from __future__ import annotations

from linkedin_easy_apply.jobs.extractor import extract_job_id, parse_metadata


def test_parse_metadata_full_line():
    text = "Over 200 applicants · 2 weeks ago · Remote · Full-time"
    meta = parse_metadata(text)
    assert meta["applicants"] == 200
    assert meta["posting_age"] == "2 weeks ago"
    assert meta["workplace_type"] == "remote"
    assert meta["employment_type"] == "full-time"


def test_parse_metadata_onsite_normalized():
    meta = parse_metadata("On-site · Contract")
    assert meta["workplace_type"] == "on-site"
    assert meta["employment_type"] == "contract"


def test_parse_metadata_empty():
    assert parse_metadata("") == {}


def test_parse_metadata_partial():
    meta = parse_metadata("Hybrid role, apply now")
    assert meta == {"workplace_type": "hybrid"}


def test_extract_job_id():
    url = "https://www.linkedin.com/jobs/view/3856789012/?refId=abc"
    assert extract_job_id(url) == "3856789012"


def test_extract_job_id_absent():
    assert extract_job_id("https://www.linkedin.com/jobs/") is None
    assert extract_job_id("") is None
