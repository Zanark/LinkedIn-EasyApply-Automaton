"""Tests for the résumé-expectations engine (answers/resume_expectations.py)."""

from __future__ import annotations

import pytest

from linkedin_easy_apply.answers.resume_expectations import (
    Verdict,
    deviation_by_day,
    grade_comparison,
    parse_master_yaml,
)

MASTER = {
    "basics": {
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "+91 90000 12345",
        "location": "Bengaluru, India",
        "summary": "Platform engineer with 6+ years shipping distributed systems.",
    },
    "experience": [
        {
            "company": "Analytical Engines",
            "start": "2020-01",
            "end": "present",
            "skills": ["Python", "Kubernetes", "React.js"],
        },
        {
            "company": "Difference Co",
            "start": "2018-01",
            "end": "2020-01",
            "skills": ["Python", "C#"],
        },
    ],
    "skills": [
        {"category": "Cloud", "items": ["Azure Kubernetes (AKS)", "Docker"]},
    ],
}


@pytest.fixture
def profile():
    return parse_master_yaml(MASTER)


# -- parsing ----------------------------------------------------------------- #
def test_parse_basics(profile):
    assert profile.total_years == 6  # from the "6+ years" in the summary
    assert profile.full_name == "Ada Lovelace"
    assert profile.first_name == "Ada"
    assert profile.last_name == "Lovelace"
    assert profile.email == "ada@example.com"
    assert profile.city == "Bengaluru"
    assert profile.country == "India"


def test_skill_presence(profile):
    assert profile.has_skill("Python") is True
    assert profile.has_skill("Kubernetes") is True
    assert profile.has_skill("React") is True  # from React.js
    assert profile.has_skill("AKS") is True  # from "Azure Kubernetes (AKS)"
    assert profile.has_skill("COBOL") is False
    assert profile.has_skill(None) is False


def test_total_years_from_dates_when_no_summary():
    data = {"experience": MASTER["experience"]}  # no summary -> compute span
    prof = parse_master_yaml(data)
    # 2018-01 .. today spans well over 6y, but exact value depends on run date;
    # just assert it computed a positive number.
    assert prof.total_years >= 6


# -- total experience -------------------------------------------------------- #
def test_total_match(profile):
    exp = profile.expected("experience_total", None, "number", "6")
    assert exp.verdict is Verdict.MATCH


@pytest.mark.parametrize("recorded", ["3", "", None])
def test_total_mismatch_recommends_full(profile, recorded):
    exp = profile.expected("experience_total", None, "number", recorded)
    assert exp.verdict is Verdict.MISMATCH
    assert exp.recommended == "6"
    assert exp.derivable is True


# -- per-skill experience (numeric) ------------------------------------------ #
def test_skill_numeric_within_total_is_match(profile):
    exp = profile.expected("experience_skill", "Python", "number", "3")
    assert exp.verdict is Verdict.MATCH


def test_skill_numeric_over_total_is_mismatch(profile):
    exp = profile.expected("experience_skill", "Python", "number", "9")
    assert exp.verdict is Verdict.MISMATCH
    assert int(exp.recommended) <= profile.total_years


def test_skill_numeric_blank_is_mismatch(profile):
    exp = profile.expected("experience_skill", "Kubernetes", "number", "")
    assert exp.verdict is Verdict.MISMATCH
    assert exp.recommended is not None


def test_skill_not_in_resume_is_not_derivable(profile):
    exp = profile.expected("experience_skill", "COBOL", "number", "5")
    assert exp.verdict is Verdict.NOT_DERIVABLE
    assert exp.derivable is False


def test_skill_missing_name_is_not_derivable(profile):
    exp = profile.expected("experience_skill", None, "number", "5")
    assert exp.verdict is Verdict.NOT_DERIVABLE


# -- per-skill experience (yes/no) ------------------------------------------- #
def test_skill_yes_is_match(profile):
    exp = profile.expected("experience_skill", "Python", "boolean", "Yes")
    assert exp.verdict is Verdict.MATCH
    assert exp.recommended == "Yes"


def test_skill_no_is_mismatch_recommends_yes(profile):
    exp = profile.expected("experience_skill", "Python", "boolean", "No")
    assert exp.verdict is Verdict.MISMATCH
    assert exp.recommended == "Yes"


def test_skill_blank_boolean_recommends_yes(profile):
    exp = profile.expected("experience_skill", "Python", "boolean", "")
    assert exp.verdict is Verdict.MISMATCH
    assert exp.recommended == "Yes"


# -- identity ---------------------------------------------------------------- #
def test_email_match(profile):
    assert profile.expected("email", None, "email", "ada@example.com").verdict is Verdict.MATCH


def test_email_mismatch(profile):
    exp = profile.expected("email", None, "email", "typo@example.com")
    assert exp.verdict is Verdict.MISMATCH
    assert exp.recommended == "ada@example.com"


def test_phone_matches_on_last_ten_digits(profile):
    # Different formatting, same national number -> match.
    assert profile.expected("phone", None, "phone", "9000012345").verdict is Verdict.MATCH


def test_city_match(profile):
    assert profile.expected("location_city", None, "text", "bengaluru").verdict is Verdict.MATCH


# -- preferences are never a deviation --------------------------------------- #
@pytest.mark.parametrize("category", ["salary_current", "notice_period", "relocation", "gender"])
def test_preferences_not_derivable(profile, category):
    exp = profile.expected(category, None, "text", "whatever")
    assert exp.verdict is Verdict.NOT_DERIVABLE
    assert exp.derivable is False


def test_unknown_category_not_derivable(profile):
    assert profile.expected("nonsense", None, "text", "x").verdict is Verdict.NOT_DERIVABLE


# -- grade_comparison / deviation_by_day ------------------------------------- #
def test_grade_comparison_shape(profile):
    rows = [
        {
            "question_id": 1,
            "question": "Total experience?",
            "normalized": "total experience",
            "category": "experience_total",
            "skill": None,
            "answer_type": "number",
            "latest_value": "3",
            "apps": 2,
            "blocked_apps": 1,
            "override_value": None,
        }
    ]
    graded = grade_comparison(profile, rows)
    assert len(graded) == 1
    g = graded[0]
    assert g.verdict is Verdict.MISMATCH
    assert g.recommended == "6"
    assert g.normalized == "total experience"
    assert g.apps == 2 and g.blocked_apps == 1


def test_deviation_by_day_counts_only_derivable(profile):
    history = [
        # derivable + wrong
        {
            "day": "2026-01-01",
            "category": "experience_total",
            "skill": None,
            "answer_type": "number",
            "value": "3",
        },
        # derivable + right
        {
            "day": "2026-01-01",
            "category": "experience_total",
            "skill": None,
            "answer_type": "number",
            "value": "6",
        },
        # preference -> excluded entirely
        {
            "day": "2026-01-01",
            "category": "salary_current",
            "skill": None,
            "answer_type": "number",
            "value": "999",
        },
    ]
    days = deviation_by_day(profile, history)
    assert days["2026-01-01"]["derivable"] == 2
    assert days["2026-01-01"]["mismatch"] == 1
