"""Infer a software-engineering seniority tier from a job posting.

The tier drives the *expected-salary* answer: a more senior role gets a higher
expected CTC. Detection is **title-first** (the most reliable signal on
LinkedIn), with a fallback to the coarse ``experience_level`` label, and finally
the caller's default when nothing matches.

Returned values are the tier keys ``"sde1"`` / ``"sde2"`` / ``"sde3"`` (or
``None`` when undecided). The caller maps a tier to a concrete CTC via the
``expected_ctc_<tier>`` answer keys.
"""

from __future__ import annotations

import re

from linkedin_easy_apply.utils.text import normalize

SDE1 = "sde1"
SDE2 = "sde2"
SDE3 = "sde3"

#: Tier assumed when the level cannot be inferred (conservative: the lowest band).
DEFAULT_SENIORITY = SDE1

# A "role" word that a numeric/roman level may hang off (``SDE 2``,
# ``Software Engineer III``...). ``normalize`` has already lowercased the text
# and reduced punctuation to spaces, so ``SDE-III`` arrives as ``sde iii``.
_ROLE = r"(?:sde|swe|software\s+engineer|software\s+developer|engineer|developer|programmer)"


def _level_pattern(levels: str) -> re.Pattern[str]:
    """Match ``<role> <level>`` allowing an optional space (so both ``sde 2`` and
    ``sde2`` are caught)."""
    return re.compile(rf"\b{_ROLE}\s*(?:{levels})\b")


# Ordered most-senior -> most-junior. Each tier has explicit level tokens plus
# free-standing keywords. Roman numerals use word boundaries so ``iii`` never
# satisfies the ``ii`` pattern.
_SDE3_LEVEL = _level_pattern("3|iii")
_SDE2_LEVEL = _level_pattern("2|ii")
_SDE1_LEVEL = _level_pattern("1|i")

_SDE3_WORDS = re.compile(r"\b(?:staff|principal|lead|sr)\b|(?<!mid )\bsenior\b")
_SDE2_WORDS = re.compile(r"\b(?:mid[\s-]?senior|mid|intermediate)\b")
_SDE1_WORDS = re.compile(
    r"\b(?:junior|jr|associate|entry|fresher|trainee|intern|internship|new\s+grad|graduate|grad)\b"
)

# LinkedIn "Seniority level" labels -> tier (only consulted when the title is
# inconclusive, since this field is coarse and often absent).
_EXPERIENCE_LEVEL_MAP: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:director|executive)\b"), SDE3),
    (re.compile(r"\bmid[\s-]?senior\b"), SDE2),
    (re.compile(r"\b(?:internship|intern|entry|associate)\b"), SDE1),
)


def detect_seniority(title: str | None, experience_level: str | None = None) -> str | None:
    """Return ``"sde1"`` / ``"sde2"`` / ``"sde3"`` for *title* (with
    *experience_level* as a fallback), or ``None`` when undecided."""
    norm = normalize(title or "")
    if norm:
        if _SDE3_WORDS.search(norm) or _SDE3_LEVEL.search(norm):
            return SDE3
        if _SDE2_WORDS.search(norm) or _SDE2_LEVEL.search(norm):
            return SDE2
        if _SDE1_WORDS.search(norm) or _SDE1_LEVEL.search(norm):
            return SDE1

    level = normalize(experience_level or "")
    if level:
        for pattern, tier in _EXPERIENCE_LEVEL_MAP:
            if pattern.search(level):
                return tier
    return None
