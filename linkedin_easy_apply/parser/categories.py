"""Enumerations describing recognised questions and their expected answers."""

from __future__ import annotations

from enum import StrEnum


class AnswerType(StrEnum):
    """The kind of value a form field expects."""

    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    CHOICE = "choice"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    FILE = "file"


class QuestionCategory(StrEnum):
    """Semantic category of an Easy Apply question."""

    EXPERIENCE_SKILL = "experience_skill"
    EXPERIENCE_TOTAL = "experience_total"
    SALARY_EXPECTED = "salary_expected"
    SALARY_CURRENT = "salary_current"
    NOTICE_PERIOD = "notice_period"
    WORK_AUTHORIZATION = "work_authorization"
    VISA_SPONSORSHIP = "visa_sponsorship"
    RELOCATION = "relocation"
    REMOTE = "remote"
    ONSITE = "onsite"
    PHONE = "phone"
    PHONE_COUNTRY_CODE = "phone_country_code"
    EMAIL = "email"
    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    LOCATION_CITY = "location_city"
    LOCATION_COUNTRY = "location_country"
    START_DATE = "start_date"
    EDUCATION = "education"
    FULL_NAME = "full_name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    GENDER = "gender"
    DISABILITY = "disability"
    VETERAN = "veteran"
    RACE = "race"
    COVER_LETTER = "cover_letter"
    RESUME = "resume"
    UNKNOWN = "unknown"


# Default answer type per category. Skill/total experience and salary are numeric,
# yes/no style questions are boolean, contact details use their specific types.
DEFAULT_ANSWER_TYPE: dict[QuestionCategory, AnswerType] = {
    QuestionCategory.EXPERIENCE_SKILL: AnswerType.NUMBER,
    QuestionCategory.EXPERIENCE_TOTAL: AnswerType.NUMBER,
    QuestionCategory.SALARY_EXPECTED: AnswerType.NUMBER,
    QuestionCategory.SALARY_CURRENT: AnswerType.NUMBER,
    QuestionCategory.NOTICE_PERIOD: AnswerType.TEXT,
    QuestionCategory.WORK_AUTHORIZATION: AnswerType.BOOLEAN,
    QuestionCategory.VISA_SPONSORSHIP: AnswerType.BOOLEAN,
    QuestionCategory.RELOCATION: AnswerType.BOOLEAN,
    QuestionCategory.REMOTE: AnswerType.BOOLEAN,
    QuestionCategory.ONSITE: AnswerType.BOOLEAN,
    QuestionCategory.PHONE: AnswerType.PHONE,
    QuestionCategory.PHONE_COUNTRY_CODE: AnswerType.CHOICE,
    QuestionCategory.EMAIL: AnswerType.EMAIL,
    QuestionCategory.LINKEDIN: AnswerType.URL,
    QuestionCategory.GITHUB: AnswerType.URL,
    QuestionCategory.PORTFOLIO: AnswerType.URL,
    QuestionCategory.LOCATION_CITY: AnswerType.TEXT,
    QuestionCategory.LOCATION_COUNTRY: AnswerType.TEXT,
    QuestionCategory.START_DATE: AnswerType.DATE,
    QuestionCategory.EDUCATION: AnswerType.TEXT,
    QuestionCategory.FULL_NAME: AnswerType.TEXT,
    QuestionCategory.FIRST_NAME: AnswerType.TEXT,
    QuestionCategory.LAST_NAME: AnswerType.TEXT,
    QuestionCategory.GENDER: AnswerType.CHOICE,
    QuestionCategory.DISABILITY: AnswerType.CHOICE,
    QuestionCategory.VETERAN: AnswerType.CHOICE,
    QuestionCategory.RACE: AnswerType.CHOICE,
    QuestionCategory.COVER_LETTER: AnswerType.FILE,
    QuestionCategory.RESUME: AnswerType.FILE,
    QuestionCategory.UNKNOWN: AnswerType.TEXT,
}
