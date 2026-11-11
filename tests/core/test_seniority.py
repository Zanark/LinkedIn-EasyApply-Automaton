"""Tests for :mod:`linkedin_easy_apply.jobs.seniority` tier detection."""

from __future__ import annotations

import pytest

from linkedin_easy_apply.jobs.seniority import SDE1, SDE2, SDE3, detect_seniority


@pytest.mark.parametrize(
    "title,expected",
    [
        # -- SDE 3 / senior+ --------------------------------------------------
        ("Senior Software Engineer", SDE3),
        ("Sr. SDE", SDE3),
        ("Staff Engineer", SDE3),
        ("Principal Software Engineer", SDE3),
        ("Lead Backend Engineer", SDE3),
        ("SDE III", SDE3),
        ("SDE-3", SDE3),
        ("SDE3", SDE3),
        ("Software Engineer III", SDE3),
        ("Software Engineer 3", SDE3),
        # -- SDE 2 / mid ------------------------------------------------------
        ("SDE II", SDE2),
        ("SDE 2", SDE2),
        ("Software Engineer II", SDE2),
        ("Software Engineer 2", SDE2),
        ("Mid-Senior Software Engineer", SDE2),
        ("Intermediate Developer", SDE2),
        # -- SDE 1 / junior ---------------------------------------------------
        ("SDE I", SDE1),
        ("SDE 1", SDE1),
        ("Software Engineer 1", SDE1),
        ("Junior Software Engineer", SDE1),
        ("Associate Software Engineer", SDE1),
        ("New Grad Software Engineer", SDE1),
        ("Software Engineer Intern", SDE1),
        ("Graduate Engineer Trainee", SDE1),
        # -- undecided --------------------------------------------------------
        ("Software Engineer", None),
        ("Backend Engineer", None),
        ("Data Scientist", None),
        ("", None),
    ],
)
def test_detect_from_title(title, expected):
    assert detect_seniority(title) is expected


def test_roman_three_does_not_match_two():
    # "III" must not be read as "II".
    assert detect_seniority("Software Engineer III") is SDE3


def test_senior_beats_a_trailing_number():
    # A strong "senior" signal wins over a lower numeric token.
    assert detect_seniority("Senior Software Engineer II") is SDE3


def test_none_title_is_safe():
    assert detect_seniority(None) is None


@pytest.mark.parametrize(
    "level,expected",
    [
        ("Entry level", SDE1),
        ("Internship", SDE1),
        ("Associate", SDE1),
        ("Mid-Senior level", SDE2),
        ("Director", SDE3),
        ("Executive", SDE3),
        ("Not Applicable", None),
    ],
)
def test_experience_level_fallback(level, expected):
    # Title inconclusive -> fall back to LinkedIn's seniority label.
    assert detect_seniority("Backend Engineer", level) is expected


def test_title_takes_priority_over_experience_level():
    assert detect_seniority("Senior Backend Engineer", "Entry level") is SDE3
