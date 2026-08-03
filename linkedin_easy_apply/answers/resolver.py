"""Resolve a recognised question to a concrete answer value.

The resolver is the bridge between :class:`~linkedin_easy_apply.parser` output
and the user's :class:`~linkedin_easy_apply.answers.store.AnswerStore`. It never
invents answers for questions it cannot map - instead it returns a resolution
with ``found=False`` so the workflow can pause and ask the user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger

from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.parser.categories import AnswerType, QuestionCategory
from linkedin_easy_apply.parser.question_parser import ParsedQuestion
from linkedin_easy_apply.utils.text import normalize

# Category -> ordered list of answer-store keys to try.
_FIELD_MAP: dict[QuestionCategory, tuple[str, ...]] = {
    QuestionCategory.EXPERIENCE_TOTAL: ("years_experience", "total_experience"),
    QuestionCategory.SALARY_EXPECTED: ("expected_ctc", "expected_salary"),
    QuestionCategory.SALARY_CURRENT: ("current_ctc", "current_salary"),
    QuestionCategory.NOTICE_PERIOD: ("notice_period",),
    QuestionCategory.PHONE: ("phone",),
    QuestionCategory.PHONE_COUNTRY_CODE: ("phone_country_code",),
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

# The dialling code left in place by default. LinkedIn pre-selects the account
# country's code, so this is only used when nothing is stored and nothing is
# pre-selected. The workflow otherwise leaves an existing +91 selection alone.
_DEFAULT_PHONE_COUNTRY_CODE = "+91"

# Salary questions store an annual figure; a "monthly" phrasing divides by this.
_MONTHS_PER_YEAR = 12

# Monthly salary answers are rounded to a clean step. Expected salary (a
# negotiation figure) rounds to the nearest 100,000 (five zeros); current salary
# rounds to a finer 10,000 so it stays an accurate reflection of today's pay.
_EXPECTED_MONTHLY_STEP = 100_000
_CURRENT_MONTHLY_STEP = 10_000

_SALARY_CATEGORIES = {QuestionCategory.SALARY_EXPECTED, QuestionCategory.SALARY_CURRENT}

# Affirmative / negative tokens for a custom Yes/No answer.
_CUSTOM_YES = {"yes", "y", "true", "1", "comfortable", "agree", "ok", "okay"}
_CUSTOM_NO = {"no", "n", "false", "0", "not comfortable", "disagree"}


@dataclass(slots=True)
class AnswerResolution:
    """Outcome of resolving a question against the answer store."""

    found: bool
    value: str | None = None
    source: str = "none"
    answer_type: AnswerType = AnswerType.TEXT
    bool_value: bool | None = None
    candidates: tuple[str, ...] = ()

    @classmethod
    def missing(cls, answer_type: AnswerType = AnswerType.TEXT) -> AnswerResolution:
        return cls(found=False, answer_type=answer_type)


def _format_number(value: object) -> str:
    """Render numeric answers without a trailing ``.0``."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _parse_amount(value: object) -> float | None:
    """Coerce a stored salary/notice value to a number, ignoring commas,
    currency symbols and words (so ``"3,000,000"`` and ``3000000`` are equal)."""
    if value is None:
        return None
    if isinstance(value, bool):  # avoid True/False sneaking in as 1/0
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.]", "", str(value))
    if not cleaned or cleaned == ".":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _first_int(text: str) -> int | None:
    """Return the first run of digits in *text* as an int, else ``None``."""
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None


class AnswerResolver:
    """Turn a :class:`ParsedQuestion` into an :class:`AnswerResolution`."""

    def __init__(self, store: AnswerStore) -> None:
        self._store = store
        self._expected_ctc_override: float | None = None
        self._expected_ctc_monthly_override: float | None = None

    def set_expected_ctc(self, annual: float | None, monthly: float | None = None) -> None:
        """Set the expected CTC for the *current* job (chosen by seniority tier).

        *annual* is the yearly figure; *monthly* is the exact value to enter for a
        "monthly" question when the user configures one per tier. Pass ``None`` for
        *annual* to clear the override and fall back to the stored value; when
        *monthly* is ``None`` a monthly question divides the annual figure by 12.
        """
        self._expected_ctc_override = annual
        self._expected_ctc_monthly_override = monthly

    def resolve(self, question: ParsedQuestion) -> AnswerResolution:
        """Resolve *question*, falling back to a user-defined custom answer.

        Category-based resolution runs first; only when it comes up empty do we
        consult the ``custom_questions`` keyword map, so built-in smart handling
        (salary tiers, notice-period, booleans...) is never shadowed.
        """
        resolution = self._resolve_core(question)
        if resolution.found:
            return resolution
        custom = self._store.custom_answer(question.normalized)
        if custom is not None:
            resolved = self._custom_resolution(custom, question.answer_type)
            logger.debug(
                "Resolve CUSTOM[{!r}] -> {!r} (matched custom_questions)",
                question.text,
                resolved.value,
            )
            return resolved
        return resolution

    def _custom_resolution(
        self, answer: str | list[str], answer_type: AnswerType
    ) -> AnswerResolution:
        """Build a resolution from a canned custom answer.

        A Yes/No answer is returned as a boolean so it fills Yes/No selects and
        radios; a list supplies ordered dropdown fallbacks (first existing option
        wins); anything else is returned verbatim with the question's own type.
        """
        if isinstance(answer, list):
            candidates = tuple(str(a) for a in answer if str(a).strip())
            first = candidates[0] if candidates else ""
            return AnswerResolution(True, first, "custom", AnswerType.CHOICE, candidates=candidates)
        token = normalize(answer)
        if token in _CUSTOM_YES:
            return AnswerResolution(True, "Yes", "custom", AnswerType.BOOLEAN, bool_value=True)
        if token in _CUSTOM_NO:
            return AnswerResolution(True, "No", "custom", AnswerType.BOOLEAN, bool_value=False)
        return AnswerResolution(True, answer, "custom", answer_type)

    def _resolve_core(self, question: ParsedQuestion) -> AnswerResolution:
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

        if category in _SALARY_CATEGORIES:
            return self._resolve_salary(category, question)

        if category is QuestionCategory.NOTICE_PERIOD:
            return self._resolve_notice_period(question)

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
        if category is QuestionCategory.PHONE_COUNTRY_CODE:
            # Never leave the dialling code unresolved - default to +91 (India).
            logger.debug(
                "Resolve {} -> {!r} (built-in default)",
                category.value,
                _DEFAULT_PHONE_COUNTRY_CODE,
            )
            return AnswerResolution(True, _DEFAULT_PHONE_COUNTRY_CODE, "default", AnswerType.CHOICE)
        return AnswerResolution.missing(answer_type)

    def _resolve_salary(
        self, category: QuestionCategory, question: ParsedQuestion
    ) -> AnswerResolution:
        """Resolve an expected/current salary. Stored figures are the *annual*
        amount as a plain integer. Expected salary is chosen per job by seniority
        tier (via :meth:`set_expected_ctc`) and is tagged source ``"tier"`` so it
        is never persisted and reused for a different-level role; current salary
        comes straight from the store.

        A monthly phrasing uses the tier's **configured monthly** value when the
        orchestrator supplied one (via :meth:`set_expected_ctc`); otherwise it
        divides by 12 and rounds to a clean step - the nearest 100,000 for
        expected salary, the nearest 10,000 for current. Values render as a plain
        number (no commas / currency), which is what LinkedIn's numeric fields and
        "amount in INR" questions expect."""
        expected = category is QuestionCategory.SALARY_EXPECTED

        amount: float | None
        used_key: str | None
        if expected and self._expected_ctc_override is not None:
            amount = self._expected_ctc_override
            used_key = "expected_ctc (seniority tier)"
        else:
            amount, used_key = self._lookup_salary(category)

        if amount is None:
            logger.debug(
                "Resolve {} -> MISSING (no salary figure from tier override or keys {})",
                category.value,
                list(_FIELD_MAP.get(category, ())),
            )
            return AnswerResolution.missing(AnswerType.NUMBER)

        annual_source = "tier" if expected else "yaml"
        monthly_source = "tier" if expected else "computed"
        step = _EXPECTED_MONTHLY_STEP if expected else _CURRENT_MONTHLY_STEP

        if "monthly" in question.tags:
            if expected and self._expected_ctc_monthly_override is not None:
                monthly = round(self._expected_ctc_monthly_override)
                logger.debug(
                    "Resolve {} -> {} (configured monthly for this seniority tier)",
                    category.value,
                    monthly,
                )
                return AnswerResolution(True, str(monthly), "tier", AnswerType.NUMBER)
            exact = amount / _MONTHS_PER_YEAR
            monthly = round(exact / step) * step
            logger.debug(
                "Resolve {} -> {} (monthly = {}/12 = {:.0f}, rounded to nearest {} from '{}')",
                category.value,
                monthly,
                _format_number(amount),
                exact,
                step,
                used_key,
            )
            # A monthly current salary is a stable derived fact -> "computed" so
            # it is learned; expected salary stays "tier" (job-specific).
            return AnswerResolution(True, str(monthly), monthly_source, AnswerType.NUMBER)

        rendered = _format_number(amount)
        logger.debug(
            "Resolve {} -> {} (annual from '{}', plain number)",
            category.value,
            rendered,
            used_key,
        )
        return AnswerResolution(True, rendered, annual_source, AnswerType.NUMBER)

    def _lookup_salary(self, category: QuestionCategory) -> tuple[float | None, str | None]:
        """Return ``(amount, key)`` for the first non-empty salary key of
        *category*, else ``(None, None)``."""
        for key in _FIELD_MAP.get(category, ()):
            value = self._store.get(key)
            if value is not None and str(value).strip():
                return _parse_amount(value), key
        return None, None

    def _resolve_notice_period(self, question: ParsedQuestion) -> AnswerResolution:
        """Resolve the notice period as a plain integer whenever possible
        (e.g. ``45``) — never with a unit suffix like ``"45 days"``. Prefers the
        numeric ``notice_period_days``; otherwise the first integer found in the
        free-text ``notice_period`` is used. Only a genuinely non-numeric
        ``notice_period`` (e.g. ``"Immediate"``) is returned as text, and only
        for a question that is not explicitly asking for a number of days."""
        days_question = "days" in question.tags

        num = _parse_amount(self._store.get("notice_period_days"))
        if num is not None:
            rendered = _format_number(num)
            logger.debug(
                "Resolve NOTICE_PERIOD -> {} (numeric days from 'notice_period_days')",
                rendered,
            )
            return AnswerResolution(True, rendered, "yaml", AnswerType.NUMBER)

        text = self._store.get("notice_period")
        if text is not None and str(text).strip():
            digits = _first_int(str(text))
            if digits is not None:
                logger.debug(
                    "Resolve NOTICE_PERIOD -> {} (integer parsed from notice_period {!r})",
                    digits,
                    text,
                )
                return AnswerResolution(True, str(digits), "yaml", AnswerType.NUMBER)
            if not days_question:
                logger.debug(
                    "Resolve NOTICE_PERIOD -> {!r} (non-numeric text from 'notice_period')",
                    str(text),
                )
                return AnswerResolution(True, str(text), "yaml", AnswerType.TEXT)

        logger.debug("Resolve NOTICE_PERIOD -> MISSING (no numeric notice period available)")
        return AnswerResolution.missing(AnswerType.NUMBER if days_question else AnswerType.TEXT)
