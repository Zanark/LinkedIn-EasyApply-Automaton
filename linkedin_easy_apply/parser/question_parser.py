"""Recognise the meaning of an Easy Apply question.

The parser combines high-precision keyword rules with a fuzzy fallback (via
``rapidfuzz``) so it does not rely on exact text matching. It never raises for
unknown input - it returns :data:`QuestionCategory.UNKNOWN` so the workflow can
fall back to asking the user.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from linkedin_easy_apply.parser.categories import (
    DEFAULT_ANSWER_TYPE,
    AnswerType,
    QuestionCategory,
)
from linkedin_easy_apply.utils.text import normalize

# A pragmatic default technical-skill vocabulary. Extended at runtime with the
# skills declared in the user's answers.yaml so custom skills are recognised too.
_DEFAULT_SKILLS: tuple[str, ...] = (
    "java",
    "core java",
    "python",
    "c#",
    "c++",
    "c",
    "go",
    "golang",
    "rust",
    "javascript",
    "typescript",
    "node",
    "node js",
    "react",
    "angular",
    "vue",
    "spring",
    "spring boot",
    "django",
    "flask",
    "dotnet",
    ".net",
    "kubernetes",
    "docker",
    "terraform",
    "ansible",
    "aws",
    "amazon web services",
    "azure",
    "gcp",
    "google cloud",
    "sql",
    "mysql",
    "postgresql",
    "postgres",
    "mongodb",
    "redis",
    "kafka",
    "rabbitmq",
    "elasticsearch",
    "linux",
    "bash",
    "powershell",
    "ci cd",
    "cicd",
    "jenkins",
    "git",
    "github",
    "graphql",
    "rest",
    "microservices",
    "distributed systems",
    "machine learning",
    "data science",
    "scala",
    "kotlin",
    "swift",
    "ruby",
    "php",
    "hadoop",
    "spark",
    "airflow",
    "selenium",
    "playwright",
)

# Representative phrases used for the fuzzy fallback.
_PHRASES: dict[QuestionCategory, tuple[str, ...]] = {
    QuestionCategory.EXPERIENCE_TOTAL: (
        "how many years of experience do you have",
        "total years of professional experience",
        "overall work experience in years",
    ),
    QuestionCategory.SALARY_EXPECTED: (
        "what is your expected salary",
        "expected annual compensation",
        "expected ctc",
        "desired salary",
    ),
    QuestionCategory.SALARY_CURRENT: (
        "what is your current salary",
        "current annual compensation",
        "current ctc",
    ),
    QuestionCategory.NOTICE_PERIOD: (
        "what is your notice period",
        "how soon can you join",
        "availability to start",
    ),
    QuestionCategory.WORK_AUTHORIZATION: (
        "are you legally authorized to work",
        "do you have work authorization",
        "are you authorised to work in this country",
    ),
    QuestionCategory.VISA_SPONSORSHIP: (
        "will you require visa sponsorship",
        "do you need sponsorship for employment",
        "require immigration sponsorship",
    ),
    QuestionCategory.RELOCATION: (
        "are you willing to relocate",
        "open to relocation",
    ),
    QuestionCategory.REMOTE: (
        "are you comfortable working remotely",
        "willing to work remote",
    ),
    QuestionCategory.ONSITE: (
        "are you willing to work onsite",
        "comfortable working from office",
    ),
    QuestionCategory.START_DATE: (
        "when can you start",
        "earliest start date",
        "available start date",
    ),
    QuestionCategory.EDUCATION: (
        "what is your highest level of education",
        "highest qualification",
        "degree obtained",
    ),
    QuestionCategory.COVER_LETTER: (
        "upload a cover letter",
        "attach cover letter",
    ),
    QuestionCategory.GENDER: ("what is your gender", "gender identity"),
    QuestionCategory.RACE: ("what is your race or ethnicity", "ethnic background"),
    QuestionCategory.VETERAN: ("are you a protected veteran", "veteran status"),
    QuestionCategory.DISABILITY: ("do you have a disability", "disability status"),
}

_EXPERIENCE_HINT = re.compile(r"\b(years?|experience|expertise|worked with|hands[- ]?on)\b")
_YEARS_HINT = re.compile(r"\byears?\b")


def _word(norm: str, *words: str) -> bool:
    """Whole-word membership test (so ``city`` does not match ``velocity``)."""
    return any(re.search(rf"\b{re.escape(w)}\b", norm) for w in words)


@dataclass(slots=True)
class ParsedQuestion:
    """The result of recognising a question."""

    text: str
    normalized: str
    category: QuestionCategory
    answer_type: AnswerType
    skill: str | None = None
    confidence: float = 0.0
    matched: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def is_known(self) -> bool:
        return self.category is not QuestionCategory.UNKNOWN


class QuestionParser:
    """Recognise question categories, skills and expected answer types."""

    def __init__(self, skills: list[str] | None = None, fuzzy_threshold: int = 80) -> None:
        vocab = {normalize(s) for s in _DEFAULT_SKILLS}
        vocab.update(normalize(s) for s in (skills or []))
        # Longest first so multi-word skills win over their substrings.
        self._skills = sorted((s for s in vocab if s), key=len, reverse=True)
        self._threshold = fuzzy_threshold

    def parse(self, text: str) -> ParsedQuestion:
        norm = normalize(text)
        if not norm:
            return ParsedQuestion(text, norm, QuestionCategory.UNKNOWN, AnswerType.TEXT)

        rule = self._apply_rules(norm)
        if rule is not None:
            category, skill, confidence = rule
            return self._build(text, norm, category, skill, confidence)

        fuzzy = self._fuzzy(norm)
        if fuzzy is not None:
            category, confidence, matched = fuzzy
            return self._build(text, norm, category, None, confidence, matched)

        return ParsedQuestion(text, norm, QuestionCategory.UNKNOWN, AnswerType.TEXT)

    # -- helpers --------------------------------------------------------------
    def _build(
        self,
        text: str,
        norm: str,
        category: QuestionCategory,
        skill: str | None,
        confidence: float,
        matched: str | None = None,
    ) -> ParsedQuestion:
        answer_type = self._infer_answer_type(category, norm)
        return ParsedQuestion(
            text=text,
            normalized=norm,
            category=category,
            answer_type=answer_type,
            skill=skill,
            confidence=confidence,
            matched=matched,
        )

    def _find_skill(self, norm: str) -> str | None:
        padded = f" {norm} "
        for skill in self._skills:
            if f" {skill} " in padded:
                return skill
        return None

    def _apply_rules(self, norm: str) -> tuple[QuestionCategory, str | None, float] | None:
        # Contact details (high precision). A "how many years ... with GitHub"
        # style question is about experience, not a profile URL - so only treat
        # linkedin/github/portfolio as URL questions when there is no experience
        # hint in the text.
        if _word(norm, "email", "e mail"):
            return QuestionCategory.EMAIL, None, 0.97
        # Country/dialling code must be checked *before* the generic phone rule,
        # since "phone country code" contains the word "phone".
        if "country code" in norm or (_word(norm, "code") and _word(norm, "country")):
            return QuestionCategory.PHONE_COUNTRY_CODE, None, 0.96
        if _word(norm, "phone", "mobile", "whatsapp") or "contact number" in norm:
            return QuestionCategory.PHONE, None, 0.97
        if not _EXPERIENCE_HINT.search(norm):
            if "linkedin" in norm:
                return QuestionCategory.LINKEDIN, None, 0.97
            if "github" in norm:
                return QuestionCategory.GITHUB, None, 0.97
            if _word(norm, "portfolio") or "personal website" in norm or "website url" in norm:
                return QuestionCategory.PORTFOLIO, None, 0.9

        # Skill-specific experience.
        skill = self._find_skill(norm)
        if skill and _EXPERIENCE_HINT.search(norm):
            return QuestionCategory.EXPERIENCE_SKILL, skill, 0.95

        # Salary.
        if _word(norm, "salary", "compensation", "ctc", "remuneration", "pay"):
            if _word(norm, "expected", "desired", "require") or "expectation" in norm:
                return QuestionCategory.SALARY_EXPECTED, None, 0.92
            if _word(norm, "current"):
                return QuestionCategory.SALARY_CURRENT, None, 0.92
            return QuestionCategory.SALARY_EXPECTED, None, 0.75

        if "notice period" in norm or (_word(norm, "notice") and _word(norm, "period")):
            return QuestionCategory.NOTICE_PERIOD, None, 0.95

        # Authorisation / visa.
        if "authoriz" in norm or "authoris" in norm:
            return QuestionCategory.WORK_AUTHORIZATION, None, 0.92
        if _word(norm, "visa") or "sponsor" in norm:
            return QuestionCategory.VISA_SPONSORSHIP, None, 0.92
        if "relocat" in norm:
            return QuestionCategory.RELOCATION, None, 0.92
        if _word(norm, "remote"):
            return QuestionCategory.REMOTE, None, 0.85
        if _word(norm, "onsite") or "on site" in norm or "from office" in norm:
            return QuestionCategory.ONSITE, None, 0.8

        # EEO / demographics.
        if _word(norm, "gender"):
            return QuestionCategory.GENDER, None, 0.9
        if _word(norm, "veteran"):
            return QuestionCategory.VETERAN, None, 0.9
        if _word(norm, "disability", "disabled"):
            return QuestionCategory.DISABILITY, None, 0.9
        if _word(norm, "race", "ethnicity", "ethnic"):
            return QuestionCategory.RACE, None, 0.9

        # Names / location.
        if "first name" in norm:
            return QuestionCategory.FIRST_NAME, None, 0.9
        if "last name" in norm or _word(norm, "surname"):
            return QuestionCategory.LAST_NAME, None, 0.9
        if "full name" in norm or norm.strip() == "name":
            return QuestionCategory.FULL_NAME, None, 0.85
        if _word(norm, "city"):
            return QuestionCategory.LOCATION_CITY, None, 0.85
        if _word(norm, "country"):
            return QuestionCategory.LOCATION_COUNTRY, None, 0.85

        # Total experience (after skill-specific check).
        if _YEARS_HINT.search(norm) and "experience" in norm:
            return QuestionCategory.EXPERIENCE_TOTAL, None, 0.85
        if "total experience" in norm or "overall experience" in norm:
            return QuestionCategory.EXPERIENCE_TOTAL, None, 0.85

        if "cover letter" in norm:
            return QuestionCategory.COVER_LETTER, None, 0.9
        if _word(norm, "resume") or norm.strip() == "cv":
            return QuestionCategory.RESUME, None, 0.85
        if _word(norm, "education", "degree", "qualification"):
            return QuestionCategory.EDUCATION, None, 0.8
        if "start date" in norm or (_word(norm, "start") and _word(norm, "join")):
            return QuestionCategory.START_DATE, None, 0.8
        return None

    def _fuzzy(self, norm: str) -> tuple[QuestionCategory, float, str] | None:
        best_category: QuestionCategory | None = None
        best_score = 0.0
        best_phrase = ""
        for category, phrases in _PHRASES.items():
            for phrase in phrases:
                score = fuzz.token_set_ratio(norm, phrase)
                if score > best_score:
                    best_score, best_category, best_phrase = score, category, phrase
        if best_category is not None and best_score >= self._threshold:
            return best_category, best_score / 100.0, best_phrase
        return None

    def _infer_answer_type(self, category: QuestionCategory, norm: str) -> AnswerType:
        base = DEFAULT_ANSWER_TYPE.get(category, AnswerType.TEXT)
        # A yes/no phrasing overrides to boolean regardless of category default.
        if base is not AnswerType.BOOLEAN and re.search(
            r"\b(are you|do you|have you|can you|will you)\b", norm
        ):
            if category in {
                QuestionCategory.EXPERIENCE_TOTAL,
                QuestionCategory.EXPERIENCE_SKILL,
                QuestionCategory.SALARY_EXPECTED,
                QuestionCategory.SALARY_CURRENT,
            }:
                return base
            return AnswerType.BOOLEAN
        return base
