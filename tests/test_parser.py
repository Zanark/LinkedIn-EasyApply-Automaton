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
    ],
)
def test_categories(parser: QuestionParser, text: str, category: QuestionCategory):
    assert parser.parse(text).category is category


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
