"""Tests for salary computation, notice-period-in-days and modifier tags."""

from __future__ import annotations

from linkedin_easy_apply.answers.resolver import AnswerResolver
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.parser.categories import AnswerType, QuestionCategory
from linkedin_easy_apply.parser.question_parser import QuestionParser


def _store() -> AnswerStore:
    return AnswerStore(
        {
            "current_ctc": 3000000,
            "expected_ctc": 4000000,
            "notice_period": "45 days",
            "notice_period_days": 45,
        }
    )


def _resolve(text: str, store: AnswerStore | None = None):
    store = store or _store()
    parser = QuestionParser()
    return parser.parse(text), AnswerResolver(store).resolve(parser.parse(text))


# -- parser modifier tags ----------------------------------------------------


def test_parser_tags_salary_monthly_and_inr():
    parsed = QuestionParser().parse("Current net salary in INR (monthly)")
    assert parsed.category is QuestionCategory.SALARY_CURRENT
    assert "monthly" in parsed.tags
    assert "inr" in parsed.tags


def test_parser_tags_salary_annual():
    parsed = QuestionParser().parse("Expected annual CTC")
    assert parsed.category is QuestionCategory.SALARY_EXPECTED
    assert "annual" in parsed.tags
    assert "monthly" not in parsed.tags


def test_parser_tags_notice_days_vs_none():
    assert "days" in QuestionParser().parse("Notice period in days").tags
    assert QuestionParser().parse("What is your notice period?").tags == []


# -- salary computation ------------------------------------------------------


def test_current_salary_monthly_divides_by_twelve():
    _parsed, res = _resolve("Current net salary in INR monthly")
    assert res.found is True
    assert res.value == "250000"  # 3,000,000 / 12 = 250,000 (already a clean 10k step)
    assert res.answer_type is AnswerType.NUMBER
    assert res.source == "computed"  # so it gets learned/saved


def test_expected_salary_monthly_rounds():
    _parsed, res = _resolve("Expected monthly salary")
    assert res.value == "300000"  # 4,000,000 / 12 = 333,333 -> nearest 100k = 300,000
    assert res.source == "tier"  # expected salary is job-specific, not learned


def test_expected_salary_annual_is_plain_number():
    _parsed, res = _resolve("Expected CTC in INR")
    assert res.value == "4000000"  # plain, no commas
    assert res.source == "tier"


def test_expected_salary_uses_tier_override_annual_and_monthly():
    store = _store()
    resolver = AnswerResolver(store)
    parser = QuestionParser()
    resolver.set_expected_ctc(3500000, 320000)  # SDE 2 band, configured monthly
    annual = resolver.resolve(parser.parse("Expected CTC in INR"))
    monthly = resolver.resolve(parser.parse("Expected monthly salary in INR"))
    assert annual.value == "3500000"
    assert monthly.value == "320000"  # exact configured monthly, not annual/12
    assert annual.source == "tier" and monthly.source == "tier"


def test_financial_expectations_uses_the_configured_monthly_tier():
    parser = QuestionParser()
    resolver = AnswerResolver(_store())
    resolver.set_expected_ctc(1200000, 100000)
    parsed = parser.parse("What are your financial expectations (monthly gross)?")

    assert parsed.category is QuestionCategory.SALARY_EXPECTED
    assert "monthly" in parsed.tags
    assert resolver.resolve(parsed).value == "100000"


def test_expected_salary_configured_monthly_per_tier():
    resolver = AnswerResolver(_store())
    parser = QuestionParser()
    resolver.set_expected_ctc(4000000, 340000)  # SDE 3
    assert resolver.resolve(parser.parse("Expected monthly CTC in INR")).value == "340000"
    resolver.set_expected_ctc(3200000, 300000)  # SDE 1
    assert resolver.resolve(parser.parse("Expected monthly CTC in INR")).value == "300000"


def test_expected_salary_monthly_falls_back_to_division_without_override():
    resolver = AnswerResolver(_store())
    parser = QuestionParser()
    resolver.set_expected_ctc(3200000)  # no monthly configured -> annual/12, nearest 100k
    # 3,200,000 / 12 = 266,667 -> nearest 100k = 300,000
    assert resolver.resolve(parser.parse("Expected monthly CTC")).value == "300000"
    assert resolver.resolve(parser.parse("Expected CTC")).value == "3200000"


def test_expected_salary_override_cleared_falls_back_to_store():
    resolver = AnswerResolver(_store())
    parser = QuestionParser()
    resolver.set_expected_ctc(3500000, 320000)
    resolver.set_expected_ctc(None)  # cleared -> store expected_ctc (4,000,000)
    assert resolver.resolve(parser.parse("Expected CTC")).value == "4000000"


def test_salary_value_with_commas_renders_without_them():
    store = AnswerStore({"current_ctc": "30,00,000"})
    _parsed, res = _resolve("What is your current CTC in INR?", store)
    assert res.value == "3000000"  # commas stripped
    assert "," not in res.value


def test_salary_missing_is_unresolved():
    store = AnswerStore({})
    _parsed, res = _resolve("Expected salary", store)
    assert res.found is False


# -- notice period -----------------------------------------------------------


def test_notice_period_in_days_is_numeric():
    _parsed, res = _resolve("Notice period in days")
    assert res.value == "45"
    assert res.answer_type is AnswerType.NUMBER


def test_notice_period_text_is_numeric_too():
    # Even a generic "notice period" question must submit a plain number, never
    # "45 days" - the numeric notice_period_days wins.
    _parsed, res = _resolve("What is your notice period?")
    assert res.value == "45"
    assert res.answer_type is AnswerType.NUMBER


def test_notice_period_generic_parses_int_from_text():
    # No notice_period_days set: pull the integer out of free-text notice_period.
    store = AnswerStore({"notice_period": "45 days"})
    _parsed, res = _resolve("What is your notice period?", store)
    assert res.value == "45"
    assert res.answer_type is AnswerType.NUMBER


def test_notice_period_non_numeric_text_stays_text():
    # A genuinely non-numeric value is only kept for a non-"days" question.
    store = AnswerStore({"notice_period": "Immediate"})
    _parsed, res = _resolve("What is your notice period?", store)
    assert res.value == "Immediate"
    assert res.answer_type is AnswerType.TEXT


def test_notice_period_days_falls_back_to_text_digits():
    store = AnswerStore({"notice_period": "30 days"})  # no notice_period_days
    _parsed, res = _resolve("Notice period in days", store)
    assert res.value == "30"
    assert res.answer_type is AnswerType.NUMBER


def test_notice_period_days_missing_everything():
    store = AnswerStore({})
    _parsed, res = _resolve("Notice period in days", store)
    assert res.found is False


# -- salary asked for in lakhs (LPA) -----------------------------------------


def test_parser_tags_salary_in_lakhs():
    parsed = QuestionParser().parse("What's your current salary package in LPA?")
    assert parsed.category is QuestionCategory.SALARY_CURRENT
    assert "lakhs" in parsed.tags


def test_plain_salary_question_has_no_lakhs_tag():
    assert "lakhs" not in QuestionParser().parse("Expected annual CTC").tags


def test_current_salary_in_lpa_is_converted_to_lakhs():
    _, resolution = _resolve("What's your current / last drawn salary package in LPA?")
    assert resolution.value == "30"


def test_expected_salary_in_lakhs_is_converted():
    _, resolution = _resolve("Expected salary in lakhs")
    assert resolution.value == "40"


def test_lakhs_keeps_a_meaningful_fraction():
    store = AnswerStore({"current_ctc": 3250000})
    _, resolution = _resolve("Current CTC in lakhs", store)
    assert resolution.value == "32.5"


def test_salary_without_lakhs_stays_in_rupees():
    _, resolution = _resolve("What is your current annual CTC?")
    assert resolution.value == "3000000"


def test_monthly_wins_over_lakhs_phrasing():
    """ "per month" is the stronger instruction, so the monthly branch applies."""
    _, resolution = _resolve("Current monthly salary in lakhs")
    assert resolution.value != "30"
