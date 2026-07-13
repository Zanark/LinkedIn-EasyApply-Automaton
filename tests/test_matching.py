from __future__ import annotations

from linkedin_easy_apply.forms.matching import best_option, boolean_option


def test_boolean_option_exact():
    assert boolean_option(True, ["Yes", "No"]) == "Yes"
    assert boolean_option(False, ["Yes", "No"]) == "No"


def test_boolean_option_prefix_fallback():
    options = ["No, I am not", "Yes, I am authorized to work"]
    assert boolean_option(True, options) == "Yes, I am authorized to work"


def test_boolean_option_absent():
    assert boolean_option(True, ["Maybe", "Unsure"]) is None


def test_best_option_exact_normalized():
    assert best_option("India", ["india", "canada"]) == "india"


def test_best_option_numeric_range():
    options = ["0-2 years", "3-5 years", "6-10 years", "10+ years"]
    assert best_option("6", options, numeric=True) == "6-10 years"


def test_best_option_numeric_closest_when_no_range():
    assert best_option("7", ["5", "8", "20"], numeric=True) == "8"


def test_best_option_fuzzy():
    options = ["India", "United States of America", "Canada"]
    assert best_option("United States", options) == "United States of America"


def test_best_option_below_threshold_returns_none():
    assert best_option("qwerty zzz", ["India", "Canada"]) is None
