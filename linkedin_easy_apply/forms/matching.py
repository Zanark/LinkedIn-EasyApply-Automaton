"""Pure option-matching helpers used when filling select / radio controls.

These functions are deliberately free of any Playwright dependency so they can
be unit tested in isolation.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz

from linkedin_easy_apply.utils.text import normalize

_YES = {"yes", "true", "y", "agree", "i agree", "authorized", "authorised"}
_NO = {"no", "false", "n", "disagree", "decline"}
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def boolean_option(flag: bool, options: list[str]) -> str | None:
    """Return the option representing *flag* (Yes/No), if present."""
    wanted = _YES if flag else _NO
    for option in options:
        if normalize(option) in wanted:
            return option
    # Fall back to substring (e.g. "Yes, I am authorized").
    prefix = "yes" if flag else "no"
    for option in options:
        if normalize(option).startswith(prefix):
            return option
    return None


def _numbers(text: str) -> list[float]:
    return [float(m) for m in _NUMBER_RE.findall(text)]


def _numeric_option(value: float, options: list[str]) -> str | None:
    """Pick the option whose numeric range contains *value* or is closest."""
    best: str | None = None
    best_distance = float("inf")
    for option in options:
        nums = _numbers(option)
        if not nums:
            continue
        if len(nums) >= 2 and nums[0] <= value <= nums[1]:
            return option
        distance = min(abs(value - n) for n in nums)
        if distance < best_distance:
            best_distance, best = distance, option
    return best


def best_option(
    value: str,
    options: list[str],
    *,
    numeric: bool = False,
    fuzzy_threshold: int = 70,
) -> str | None:
    """Choose the option best matching *value*.

    Resolution order: exact (normalised) match, numeric proximity (when
    *numeric*), then fuzzy match above *fuzzy_threshold*.
    """
    if not options:
        return None

    target = normalize(value)
    for option in options:
        if normalize(option) == target:
            return option

    if numeric:
        nums = _numbers(value)
        if nums:
            match = _numeric_option(nums[0], options)
            if match is not None:
                return match

    best: str | None = None
    best_score = 0.0
    for option in options:
        score = fuzz.token_set_ratio(target, normalize(option))
        if score > best_score:
            best_score, best = score, option
    return best if best_score >= fuzzy_threshold else None
