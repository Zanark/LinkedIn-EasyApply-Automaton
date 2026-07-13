from __future__ import annotations

from linkedin_easy_apply.answers.resolver import AnswerResolver
from linkedin_easy_apply.answers.store import AnswerStore
from linkedin_easy_apply.parser.categories import AnswerType
from linkedin_easy_apply.parser.question_parser import QuestionParser


def test_field_lookup_and_alias(answers_store: AnswerStore):
    assert answers_store.get("phone") == "+91-9000000000"
    assert answers_store.get("mobile") == "+91-9000000000"  # via alias
    assert answers_store.get("expected compensation") == 5000000  # via alias
    assert answers_store.get("missing", "fallback") == "fallback"


def test_defaults_used_when_field_absent(answers_store: AnswerStore):
    assert answers_store.get("onsite") is True  # only present in defaults


def test_bool_coercion(answers_store: AnswerStore):
    assert answers_store.get_bool("authorization") is True
    assert answers_store.get_bool("visa") is False
    assert answers_store.get_bool("phone") is None  # not boolean-like


def test_skill_years_with_aliases(answers_store: AnswerStore):
    assert answers_store.get_skill_years("Java") == 6.0
    assert answers_store.get_skill_years("core java") == 6.0  # alias
    assert answers_store.get_skill_years("K8s") == 4.0
    assert answers_store.get_skill_years("Python") == 5.0  # plain int form
    assert answers_store.get_skill_years("cobol") is None


def test_from_yaml(tmp_path):
    path = tmp_path / "answers.yaml"
    path.write_text("phone: '123'\nskills:\n  Go:\n    years: 3\n", encoding="utf-8")
    store = AnswerStore.from_yaml(path)
    assert store.get("phone") == "123"
    assert store.get_skill_years("go") == 3.0


# -- resolver (parser + store) -----------------------------------------------


def _resolve(parser: QuestionParser, resolver: AnswerResolver, text: str):
    return resolver.resolve(parser.parse(text))


def test_resolver_end_to_end(answers_store: AnswerStore):
    parser = QuestionParser(skills=answers_store.known_skills())
    resolver = AnswerResolver(answers_store)

    skill = _resolve(parser, resolver, "How many years of experience do you have in Java?")
    assert skill.found and skill.value == "6" and skill.answer_type is AnswerType.NUMBER

    total = _resolve(parser, resolver, "What is your total years of experience?")
    assert total.found and total.value == "8"

    salary = _resolve(parser, resolver, "What is your expected CTC?")
    assert salary.found and salary.value == "5000000"

    phone = _resolve(parser, resolver, "What is your mobile phone number?")
    assert phone.found and phone.value == "+91-9000000000"

    auth = _resolve(parser, resolver, "Are you legally authorized to work in this country?")
    assert auth.found and auth.value == "Yes" and auth.bool_value is True

    visa = _resolve(parser, resolver, "Do you require visa sponsorship?")
    assert visa.found and visa.value == "No" and visa.bool_value is False


def test_resolver_missing_answer(answers_store: AnswerStore):
    parser = QuestionParser()
    resolver = AnswerResolver(answers_store)
    result = _resolve(parser, resolver, "What is your gender?")
    assert result.found is False
