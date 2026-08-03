from __future__ import annotations

import pytest

from linkedin_easy_apply.parser.categories import AnswerType, QuestionCategory
from linkedin_easy_apply.parser.question_parser import QuestionParser


@pytest.fixture
def parser() -> QuestionParser:
    return QuestionParser(skills=["Java", "Kubernetes"])


@pytest.mark.parametrize(
    "text, category",
    [
        ("What is your email address?", QuestionCategory.EMAIL),
        ("Please enter your phone number", QuestionCategory.PHONE),
        ("Share your LinkedIn profile", QuestionCategory.LINKEDIN),
        ("GitHub URL", QuestionCategory.GITHUB),
        ("What is your expected CTC?", QuestionCategory.SALARY_EXPECTED),
        ("What is your current salary?", QuestionCategory.SALARY_CURRENT),
        ("What is your notice period?", QuestionCategory.NOTICE_PERIOD),
        ("Are you legally authorized to work?", QuestionCategory.WORK_AUTHORIZATION),
        ("Will you require sponsorship?", QuestionCategory.VISA_SPONSORSHIP),
        ("Are you willing to relocate?", QuestionCategory.RELOCATION),
        ("What is your gender?", QuestionCategory.GENDER),
        ("What city do you live in?", QuestionCategory.LOCATION_CITY),
        ("What is your highest level of education?", QuestionCategory.EDUCATION),
        # Salary variants must still resolve to salary.
        ("What is your current CTC?", QuestionCategory.SALARY_CURRENT),
        ("What is your expected package?", QuestionCategory.SALARY_EXPECTED),
        ("What is your current LPA?", QuestionCategory.SALARY_CURRENT),
        # The reported bug: a "current location" question is a location, NOT salary.
        ("What is your current location?", QuestionCategory.LOCATION_CITY),
        ("Where are you currently located?", QuestionCategory.LOCATION_CITY),
        ("Where are you based?", QuestionCategory.LOCATION_CITY),
    ],
)
def test_categories(parser: QuestionParser, text: str, category: QuestionCategory):
    assert parser.parse(text).category is category


@pytest.mark.parametrize(
    "text",
    [
        "What is your current location?",
        "Where are you currently located?",
        "What is your current designation?",
        "What is your current company?",
        "What is your current role?",
        "Which location are you applying for?",
    ],
)
def test_current_x_is_never_salary(parser: QuestionParser, text: str):
    # A "current <something-other-than-pay>" question shares the "what is your
    # current" tokens with the salary phrase but must NOT be filled with money.
    parsed = parser.parse(text)
    assert parsed.category is not QuestionCategory.SALARY_CURRENT
    assert parsed.category is not QuestionCategory.SALARY_EXPECTED


def test_location_preference_falls_through_to_unknown(parser: QuestionParser):
    # "Which location are you applying for?" is a preference, not the home city,
    # so it must stay UNKNOWN and be handled by a custom answer (not the city).
    parsed = parser.parse("Which location are you applying for?")
    assert parsed.category is QuestionCategory.UNKNOWN


def test_skill_experience_extraction(parser: QuestionParser):
    parsed = parser.parse("How many years of experience do you have with Kubernetes?")
    assert parsed.category is QuestionCategory.EXPERIENCE_SKILL
    assert parsed.skill == "kubernetes"
    assert parsed.answer_type is AnswerType.NUMBER


def test_word_boundary_no_false_positive(parser: QuestionParser):
    # "velocity" must not be recognised as the city question via "city".
    parsed = parser.parse("Describe your team's velocity")
    assert parsed.category is not QuestionCategory.LOCATION_CITY


def test_unknown_question_is_safe(parser: QuestionParser):
    parsed = parser.parse("Zxqw plugh foobar wibble")
    assert parsed.category is QuestionCategory.UNKNOWN
    assert parsed.is_known is False


def test_empty_question(parser: QuestionParser):
    parsed = parser.parse("   ")
    assert parsed.category is QuestionCategory.UNKNOWN


def test_fuzzy_fallback(parser: QuestionParser):
    # Not an exact rule phrase, should still fuzzy-match to notice period.
    parsed = parser.parse("How soon can you join the team?")
    assert parsed.category is QuestionCategory.NOTICE_PERIOD
    assert parsed.confidence > 0
