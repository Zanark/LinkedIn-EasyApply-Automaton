"""Resolve a recognised question to a concrete answer value.

The resolver is the bridge between :class:`~linkedin_easy_apply.parser` output
and the user's :class:`~linkedin_easy_apply.answers.store.AnswerStore`. It never
invents answers for questions it cannot map - instead it returns a resolution
with ``found=False`` so the workflow can pause and ask the user.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

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
            source_key = f"skills.{question.skill}.years"
            if years is None:
                years = self._store.get("years_experience")
                source_key = "years_experience (skill unknown - using fallback)"
            if years is not None:
                logger.debug(
                    "Resolve EXPERIENCE_SKILL[{}] -> {} (from {})",
                    question.skill,
                    years,
                    source_key,
                )
                return AnswerResolution(True, _format_number(years), "yaml", AnswerType.NUMBER)
            logger.debug(
                "Resolve EXPERIENCE_SKILL[{}] -> MISSING "
                "(no per-skill years and no 'years_experience' fallback)",
                question.skill,
            )
            return AnswerResolution.missing(AnswerType.NUMBER)

        if category in _BOOL_MAP:
            key = _BOOL_MAP[category]
            flag = self._store.get_bool(key)
            if flag is None:
                logger.debug(
                    "Resolve {} -> MISSING (boolean key '{}' not set in answers)",
                    category.value,
                    key,
                )
                return AnswerResolution.missing(AnswerType.BOOLEAN)
            logger.debug(
                "Resolve {} -> {} (from boolean key '{}')",
                category.value,
                "Yes" if flag else "No",
                key,
            )
            return AnswerResolution(
                True, "Yes" if flag else "No", "yaml", AnswerType.BOOLEAN, bool_value=flag
            )

        keys = _FIELD_MAP.get(category, ())
        for key in keys:  # ordered fallbacks
            value = self._store.get(key)
            if value is not None and str(value).strip():
                rendered = _format_number(value) if answer_type is AnswerType.NUMBER else str(value)
                logger.debug(
                    "Resolve {} -> {!r} (from answers key '{}')",
                    category.value,
                    rendered,
                    key,
                )
                return AnswerResolution(True, rendered, "yaml", answer_type)

        if keys:
            logger.debug(
                "Resolve {} -> MISSING (none of the answer keys {} are set)",
                category.value,
                list(keys),
            )
        else:
            logger.debug(
                "Resolve {} -> MISSING (no answer-key mapping for this category)",
                category.value,
            )
        return AnswerResolution.missing(answer_type)
