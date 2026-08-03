"""Compare what the automation answered against what the résumé implies.

The master résumé (``master.yaml`` in the dynamic-resume-builder — the single
source of truth for the user's experience) is parsed into a
:class:`ResumeProfile`. Given a recorded question/answer, the profile returns an
:class:`Expectation` — a verdict (match / mismatch / not-derivable), a
résumé-grounded *recommended* value, and a plain-English reason.

Design choices that keep the signal honest and low-noise:

* Only categories the résumé can actually adjudicate are graded — total years of
  experience, per-skill experience for skills the résumé mentions, and identity
  fields (name, email, phone, city, country). Everything else (salary, notice,
  relocation, sponsorship, custom screening…) is a personal **preference** the
  résumé says nothing about and is reported ``NOT_DERIVABLE`` (never counted as a
  deviation).
* A skill is only graded when it appears in the résumé; an unknown skill is
  ``NOT_DERIVABLE`` rather than a false "you don't have it".
* Skill-years are flagged only when clearly wrong (blank for a skill the résumé
  lists, or greater than total career years) — understating within reason is not
  treated as a deviation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from linkedin_easy_apply.config.models import AppConfig
from linkedin_easy_apply.parser.categories import QuestionCategory
from linkedin_easy_apply.utils.text import normalize, tokenize

# Skill sub-parts split out of a résumé skill string ("C# / .NET" -> C#, .NET).
_SKILL_SPLIT_RE = re.compile(r"[/,&()|]+")
# Digits run used to pull the first number out of a recorded answer.
_INT_RE = re.compile(r"\d+")


class Verdict(StrEnum):
    """How a recorded answer compares to the résumé."""

    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_DERIVABLE = "not_derivable"


@dataclass(slots=True)
class Expectation:
    """The résumé's opinion on a single recorded answer."""

    verdict: Verdict
    derivable: bool
    expected_display: str
    recommended: str | None
    reason: str


# Categories the résumé can actually adjudicate. Everything else is a personal
# preference and is reported NOT_DERIVABLE.
_IDENTITY_CATEGORIES = {
    QuestionCategory.FIRST_NAME,
    QuestionCategory.LAST_NAME,
    QuestionCategory.FULL_NAME,
    QuestionCategory.EMAIL,
    QuestionCategory.PHONE,
    QuestionCategory.LOCATION_CITY,
    QuestionCategory.LOCATION_COUNTRY,
}


def _first_int(text: str | None) -> int | None:
    if not text:
        return None
    match = _INT_RE.search(text)
    return int(match.group()) if match else None


_YES = {"yes", "y", "true", "1"}
_NO = {"no", "n", "false", "0"}


def _digits(text: str | None) -> str:
    return re.sub(r"\D", "", text or "")


def _parse_ym(value: Any) -> date | None:
    """Parse a résumé date (``YYYY-MM`` / ``YYYY-MM-DD`` / ``present``)."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in {"present", "current", "now"}:
        return None
    match = re.match(r"(\d{4})-(\d{1,2})", text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        return date(year, max(1, min(12, month)), 1)
    match = re.match(r"(\d{4})$", text)
    return date(int(match.group(1)), 1, 1) if match else None


def _months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def _skill_forms(raw: str) -> set[str]:
    """Return the matchable normalized forms of a résumé skill string.

    ``"Azure Kubernetes (AKS)"`` -> {"azure kubernetes aks", "azure kubernetes",
    "aks"} plus individual word tokens, so a question about "AKS" or "Kubernetes"
    still matches. Mirrors :func:`normalize` so it lines up with parsed skills.
    """
    forms: set[str] = set()
    whole = normalize(raw)
    if whole:
        forms.add(whole)
    for part in _SKILL_SPLIT_RE.split(raw):
        piece = normalize(part)
        if piece:
            forms.add(piece)
    for token in tokenize(raw):
        if len(token) >= 2:
            forms.add(token)
    return forms


@dataclass(slots=True)
class ResumeProfile:
    """Parsed view of the master résumé used to grade recorded answers."""

    total_years: int
    skill_years: dict[str, float] = field(default_factory=dict)
    skill_forms: set[str] = field(default_factory=set)
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    country: str | None = None

    # -- skill helpers --------------------------------------------------------
    def _skill_keys(self, skill: str) -> set[str]:
        keys = {normalize(skill)}
        keys.update(t for t in tokenize(skill) if len(t) >= 2)
        return {k for k in keys if k}

    def has_skill(self, skill: str | None) -> bool:
        if not skill:
            return False
        return bool(self._skill_keys(skill) & self.skill_forms)

    def skill_years_for(self, skill: str) -> float | None:
        best: float | None = None
        for key in self._skill_keys(skill):
            years = self.skill_years.get(key)
            if years is not None and (best is None or years > best):
                best = years
        return best

    # -- grading --------------------------------------------------------------
    def expected(
        self,
        category: str | None,
        skill: str | None,
        answer_type: str | None,
        recorded: str | None,
    ) -> Expectation:
        """Grade one recorded answer against the résumé."""
        try:
            cat = QuestionCategory(category) if category else QuestionCategory.UNKNOWN
        except ValueError:
            cat = QuestionCategory.UNKNOWN

        if cat is QuestionCategory.EXPERIENCE_TOTAL:
            return self._expected_total(recorded)
        if cat is QuestionCategory.EXPERIENCE_SKILL:
            return self._expected_skill(skill, recorded, answer_type)
        if cat in _IDENTITY_CATEGORIES:
            return self._expected_identity(cat, recorded)
        return Expectation(
            Verdict.NOT_DERIVABLE,
            False,
            "— (preference)",
            None,
            "Not answerable from the résumé — a personal preference/legal value.",
        )

    def _expected_total(self, recorded: str | None) -> Expectation:
        expected = str(self.total_years)
        display = f"{self.total_years} (résumé total)"
        got = _first_int(recorded)
        if got == self.total_years:
            return Expectation(Verdict.MATCH, True, display, expected, "Matches résumé total.")
        if got is None:
            return Expectation(
                Verdict.MISMATCH,
                True,
                display,
                expected,
                f"Blank — résumé shows ~{self.total_years} years total.",
            )
        return Expectation(
            Verdict.MISMATCH,
            True,
            display,
            expected,
            f"Answered {got}, but the résumé shows ~{self.total_years} years total.",
        )

    def _expected_skill(
        self, skill: str | None, recorded: str | None, answer_type: str | None
    ) -> Expectation:
        if not skill:
            return Expectation(Verdict.NOT_DERIVABLE, False, "—", None, "No specific skill parsed.")
        if not self.has_skill(skill):
            return Expectation(
                Verdict.NOT_DERIVABLE,
                False,
                "— (not in résumé)",
                None,
                f"'{skill}' is not mentioned in the résumé — can't grade it.",
            )
        # Yes/No "do you have experience with X?" — the résumé lists X, so "Yes".
        token = normalize(recorded or "")
        if token in _YES or token in _NO or (answer_type == "boolean"):
            display = "Yes (in résumé)"
            if token in _YES:
                return Expectation(Verdict.MATCH, True, display, "Yes", f"Résumé lists '{skill}'.")
            reason = (
                f"Answered No, but the résumé lists '{skill}'."
                if token in _NO
                else f"Blank, but the résumé lists '{skill}' — answer Yes."
            )
            return Expectation(Verdict.MISMATCH, True, display, "Yes", reason)
        # Numeric "how many years with X?"
        span = self.skill_years_for(skill)
        cap = max(1, min(int(round(span)) if span else self.total_years, self.total_years))
        display = f"present, ≤ {self.total_years}y"
        evidence = f" (résumé evidence ≈ {int(round(span))}y)" if span else ""
        got = _first_int(recorded)
        if got is None:
            return Expectation(
                Verdict.MISMATCH,
                True,
                display,
                str(cap),
                f"Blank, but the résumé lists '{skill}'{evidence}.",
            )
        if got > self.total_years:
            return Expectation(
                Verdict.MISMATCH,
                True,
                display,
                str(cap),
                f"Answered {got}, above the {self.total_years}-year total career length.",
            )
        return Expectation(
            Verdict.MATCH,
            True,
            display,
            str(got),
            f"{got}y is within the résumé (skill present, ≤ {self.total_years}y){evidence}.",
        )

    def _expected_identity(self, cat: QuestionCategory, recorded: str | None) -> Expectation:
        expected = {
            QuestionCategory.FIRST_NAME: self.first_name,
            QuestionCategory.LAST_NAME: self.last_name,
            QuestionCategory.FULL_NAME: self.full_name,
            QuestionCategory.EMAIL: self.email,
            QuestionCategory.PHONE: self.phone,
            QuestionCategory.LOCATION_CITY: self.city,
            QuestionCategory.LOCATION_COUNTRY: self.country,
        }.get(cat)
        if not expected:
            return Expectation(
                Verdict.NOT_DERIVABLE, False, "—", None, "Résumé has no value for this field."
            )
        if cat is QuestionCategory.PHONE:
            same = _digits(recorded).endswith(_digits(expected)[-10:]) if recorded else False
        else:
            same = normalize(recorded or "") == normalize(expected)
        if same:
            return Expectation(Verdict.MATCH, True, expected, expected, "Matches the résumé.")
        return Expectation(
            Verdict.MISMATCH,
            True,
            expected,
            expected,
            f"Answered {recorded!r}; résumé says {expected!r}.",
        )


def parse_master_yaml(data: dict[str, Any]) -> ResumeProfile:
    """Build a :class:`ResumeProfile` from parsed ``master.yaml`` content."""
    basics = data.get("basics") or {}
    experience = data.get("experience") or []

    total_years = _total_years(basics, experience)
    skill_forms, skill_years = _skill_index(experience, data.get("skills") or [])

    name = str(basics.get("name") or "").strip()
    parts = name.split()
    location = str(basics.get("location") or "")
    city, _, country = location.partition(",")

    return ResumeProfile(
        total_years=total_years,
        skill_years=skill_years,
        skill_forms=skill_forms,
        first_name=parts[0] if parts else None,
        last_name=parts[-1] if len(parts) > 1 else None,
        full_name=name or None,
        email=(str(basics.get("email")).strip() or None) if basics.get("email") else None,
        phone=(str(basics.get("phone")).strip() or None) if basics.get("phone") else None,
        city=city.strip() or None,
        country=country.strip() or None,
    )


def _total_years(basics: dict[str, Any], experience: list[Any]) -> int:
    """Prefer an explicit "N+ years" in the summary; else compute from dates."""
    summary = str(basics.get("summary") or "")
    stated = [int(m) for m in re.findall(r"(\d+)\s*\+?\s*years", summary, flags=re.IGNORECASE)]
    explicit = max(stated) if stated else 0

    starts = [
        d for d in (_parse_ym(r.get("start")) for r in experience if isinstance(r, dict)) if d
    ]
    ends = []
    for role in experience:
        if not isinstance(role, dict):
            continue
        end = _parse_ym(role.get("end")) or date.today()
        ends.append(end)
    computed = 0
    if starts and ends:
        computed = round(_months_between(min(starts), max(ends)) / 12)
    return explicit or computed or 0


def _skill_index(experience: list[Any], skills: list[Any]) -> tuple[set[str], dict[str, float]]:
    """Return (presence forms, per-form résumé-span years)."""
    forms: set[str] = set()
    years: dict[str, float] = {}

    for role in experience:
        if not isinstance(role, dict):
            continue
        start = _parse_ym(role.get("start"))
        end = _parse_ym(role.get("end")) or date.today()
        duration = _months_between(start, end) / 12 if start else 0.0
        for raw in role.get("skills") or []:
            role_forms = _skill_forms(str(raw))
            forms |= role_forms
            for form in role_forms:
                years[form] = years.get(form, 0.0) + duration

    for group in skills:
        items = group.get("items") if isinstance(group, dict) else None
        for raw in items or []:
            forms |= _skill_forms(str(raw))

    return forms, years


def resolve_master_path(config: AppConfig) -> Path | None:
    """Locate ``master.yaml``: explicit config, then builder dir, then configs/."""
    resume = config.resume
    if resume.master_path and Path(resume.master_path).is_file():
        return Path(resume.master_path)
    builder_path = resume.builder.path
    if builder_path:
        candidate = Path(builder_path) / "master.yaml"
        if candidate.is_file():
            return candidate
    fallback = Path("configs/master.yaml")
    return fallback if fallback.is_file() else None


def load_resume_profile(config: AppConfig) -> ResumeProfile | None:
    """Load and parse the master résumé, or ``None`` when it can't be found."""
    path = resolve_master_path(config)
    if not path:
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    return parse_master_yaml(data)


@dataclass(slots=True)
class GradedAnswer:
    """A recorded question/answer paired with the résumé's verdict on it.

    The flat shape the dashboard renders as a table and the ``sync-answers`` CLI
    iterates over — combines the DB comparison row with an :class:`Expectation`.
    """

    normalized: str
    question_id: int | None
    question: str
    category: str
    skill: str | None
    answered: str | None
    verdict: Verdict
    expected_display: str
    recommended: str | None
    reason: str
    override: str | None
    apps: int
    blocked_apps: int


def grade_comparison(profile: ResumeProfile, rows: list[dict[str, Any]]) -> list[GradedAnswer]:
    """Grade :meth:`Database.answer_comparison` rows against the résumé."""
    graded: list[GradedAnswer] = []
    for row in rows:
        exp = profile.expected(
            row.get("category"),
            row.get("skill"),
            row.get("answer_type"),
            row.get("latest_value"),
        )
        graded.append(
            GradedAnswer(
                normalized=row.get("normalized") or "",
                question_id=row.get("question_id"),
                question=row.get("question") or "",
                category=row.get("category") or "",
                skill=row.get("skill"),
                answered=row.get("latest_value"),
                verdict=exp.verdict,
                expected_display=exp.expected_display,
                recommended=exp.recommended,
                reason=exp.reason,
                override=row.get("override_value"),
                apps=int(row.get("apps") or 0),
                blocked_apps=int(row.get("blocked_apps") or 0),
            )
        )
    return graded


def deviation_by_day(
    profile: ResumeProfile, history: list[dict[str, Any]]
) -> dict[str, dict[str, int]]:
    """Per-day {derivable, mismatch} counts from :meth:`Database.answered_history`.

    Only résumé-derivable answers are counted so the deviation rate stays
    meaningful (preferences never inflate or deflate it).
    """
    days: dict[str, dict[str, int]] = {}
    for entry in history:
        exp = profile.expected(
            entry.get("category"),
            entry.get("skill"),
            entry.get("answer_type"),
            entry.get("value"),
        )
        if not exp.derivable:
            continue
        day = str(entry.get("day") or "")
        if not day:
            continue
        bucket = days.setdefault(day, {"derivable": 0, "mismatch": 0})
        bucket["derivable"] += 1
        if exp.verdict is Verdict.MISMATCH:
            bucket["mismatch"] += 1
    return days
