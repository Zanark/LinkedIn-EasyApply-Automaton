"""Resolve a recognised question to a concrete answer value.

The resolver is the bridge between :class:`~linkedin_easy_apply.parser` output
and the user's :class:`~linkedin_easy_apply.answers.store.AnswerStore`. It never
invents answers for questions it cannot map - instead it returns a resolution
with ``found=False`` so the workflow can pause and ask the user.
"""

from __future__ import annotations

from dataclasses import dataclass

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.parser.categories import AnswerType, QuestionCategory
from linkedin_easy_apply.parser.question_parser import ParsedQuestion

# Category -> ordered list of answer-store keys to try.
_FIELD_MAP: dict[QuestionCategory, tuple[str, ...]] = {
    QuestionCategory.EXPERIENCE_TOTAL: ("years_experience", "total_experience"),
    QuestionCategory.SALARY_EXPECTED: ("expected_ctc", "expected_salary"),
    QuestionCategory.SALARY_CURRENT: ("current_ctc", "current_salary"),
    QuestionCategory.NOTICE_PERIOD: ("notice_period",),
    QuestionCategory.PHONE: ("phone",),
    QuestionCategory.EMAIL: ("email",),
    QuestionCategory.LINKEDIN: ("linkedin",),
    QuestionCategory.GITHUB: ("github",),
    QuestionCategory.PORTFOLIO: ("portfolio", "website"),
    QuestionCategory.LOCATION_CITY: ("city",),
    QuestionCategory.LOCATION_COUNTRY: ("country",),
    QuestionCategory.START_DATE: ("start_date", "notice_period"),
    QuestionCategory.EDUCATION: ("education", "degree"),
    QuestionCategory.FULL_NAME: ("full_name", "name"),
    QuestionCategory.FIRST_NAME: ("first_name",),
    QuestionCategory.LAST_NAME: ("last_name",),
    QuestionCategory.GENDER: ("gender",),
    QuestionCategory.RACE: ("race", "ethnicity"),
    QuestionCategory.VETERAN: ("veteran",),
    QuestionCategory.DISABILITY: ("disability",),
}

# Category -> answer-store boolean key.
_BOOL_MAP: dict[QuestionCategory, str] = {
    QuestionCategory.WORK_AUTHORIZATION: "authorization",
    QuestionCategory.VISA_SPONSORSHIP: "visa",
    QuestionCategory.RELOCATION: "relocation",
    QuestionCategory.REMOTE: "remote",
    QuestionCategory.ONSITE: "onsite",
}


@dataclass(slots=True)
class AnswerResolution:
    """Outcome of resolving a question against the answer store."""

    found: bool
    value: str | None = None
    source: str = "none"
    answer_type: AnswerType = AnswerType.TEXT
    bool_value: bool | None = None

    @classmethod
    def missing(cls, answer_type: AnswerType = AnswerType.TEXT) -> AnswerResolution:
        return cls(found=False, answer_type=answer_type)


def _format_number(value: object) -> str:
    """Render numeric answers without a trailing ``.0``."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


class AnswerResolver:
    """Turn a :class:`ParsedQuestion` into an :class:`AnswerResolution`."""

    def __init__(self, store: AnswerStore) -> None:
        self._store = store

    def resolve(self, question: ParsedQuestion) -> AnswerResolution:
        category = question.category
        answer_type = question.answer_type

        if category is QuestionCategory.EXPERIENCE_SKILL and question.skill:
            years = self._store.get_skill_years(question.skill)
            if years is None:
                years = self._store.get("years_experience")
            if years is not None:
                return AnswerResolution(True, _format_number(years), "yaml", AnswerType.NUMBER)
            return AnswerResolution.missing(AnswerType.NUMBER)

        if category in _BOOL_MAP:
            flag = self._store.get_bool(_BOOL_MAP[category])
            if flag is None:
                return AnswerResolution.missing(AnswerType.BOOLEAN)
            return AnswerResolution(
                True, "Yes" if flag else "No", "yaml", AnswerType.BOOLEAN, bool_value=flag
            )

        for key in _FIELD_MAP.get(category, ()):  # ordered fallbacks
            value = self._store.get(key)
            if value is not None and str(value).strip():
                rendered = _format_number(value) if answer_type is AnswerType.NUMBER else str(value)
                return AnswerResolution(True, rendered, "yaml", answer_type)

        return AnswerResolution.missing(answer_type)
