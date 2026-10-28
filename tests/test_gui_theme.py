"""Tests for the GUI theming layer.

The palettes are transcribed from the DeepSeaFoam project, so these tests pin
the exact published values, the role contract, and the one conversion that is
easy to get silently wrong: CSS publishes alpha **last** (``#RRGGBBAA``) while
Qt's hex form puts it **first**, which would shift every channel.

This module must import without PySide6 installed.
"""

from __future__ import annotations

import pytest

from linkedin_easy_apply.gui import theme


def test_theme_module_needs_no_qt(monkeypatch):
    """Importing the theme must not drag in PySide6."""
    import sys

    monkeypatch.setitem(sys.modules, "PySide6", None)
    import importlib

    importlib.reload(theme)
    assert theme.DEFAULT_THEME == "deepseafoam"


# -- palette contract -------------------------------------------------------- #
def test_both_themes_registered():
    assert set(theme.THEMES) == {"deepseafoam", "harbor-daylight"}
    assert theme.THEMES["deepseafoam"].is_dark
    assert not theme.THEMES["harbor-daylight"].is_dark


def test_every_theme_defines_every_role():
    for palette in theme.THEMES.values():
        for role in theme.ROLES:
            assert palette[role], f"{palette.key} is missing {role}"


def test_palette_rejects_missing_roles():
    with pytest.raises(ValueError, match="missing roles"):
        theme.Palette(key="broken", label="Broken", mode="dark", source="test", tokens={})


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("background", "#000F13"),  # base
        ("surface", "#001E26"),  # panel
        ("accent", "#00A591"),
        ("text", "#93A1A1"),
        ("muted", "#839496"),  # faintText
        ("heading", "#EEE8D5"),  # warm
        ("border", "#586E75"),
        ("document", "#45D072"),
        ("warning", "#EBE565"),
        ("error", "#E84A5F"),
        ("separator", "#586E7566"),
        ("hover", "#586E7533"),
        ("selection", "#00A59126"),
    ],
)
def test_deepseafoam_values(role: str, expected: str):
    assert theme.DEEP_SEA_FOAM[role] == expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("background", "#F3F2E9"),
        ("surface", "#E3ECE7"),
        ("raised", "#FCFAF2"),  # paper
        ("text", "#355451"),
        ("muted", "#536B66"),
        ("heading", "#173D3A"),
        ("border", "#6B857E"),
        ("accent", "#006F63"),
        ("accent_hover", "#00594F"),
        ("button_text", "#FCFAF2"),
        ("document", "#247449"),
        ("warning", "#77600E"),
        ("error", "#AD3E55"),
        ("separator", "#6B857E66"),
        ("hover", "#6B857E1A"),
        ("selection", "#006F631F"),
    ],
)
def test_harbor_daylight_values(role: str, expected: str):
    assert theme.HARBOR_DAYLIGHT[role] == expected


def test_dark_accent_hover_follows_its_documented_role():
    """DeepSeaFoam has no second accent fill: text *is* the primary-action hover."""
    assert theme.DEEP_SEA_FOAM["accent_hover"] == theme.DEEP_SEA_FOAM["text"]
    # ...so the ink on top must be the dark base, never the same light colour.
    assert theme.DEEP_SEA_FOAM["button_text"] == theme.DEEP_SEA_FOAM["background"]


def test_light_button_ink_is_paper_on_accent():
    assert theme.HARBOR_DAYLIGHT["button_text"] == theme.HARBOR_DAYLIGHT["raised"]
    assert theme.HARBOR_DAYLIGHT["accent_hover"] != theme.HARBOR_DAYLIGHT["accent"]


# -- colour conversion ------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#00A591", "#00A591"),
        ("#586E7566", "rgba(88, 110, 117, 102)"),  # 0x66 = 102 = 40%
        ("#586E7533", "rgba(88, 110, 117, 51)"),
        ("#00A59126", "rgba(0, 165, 145, 38)"),
        ("#6B857E1A", "rgba(107, 133, 126, 26)"),
        ("#006F631F", "rgba(0, 111, 99, 31)"),
        ("transparent", "transparent"),
    ],
)
def test_qt_color_moves_alpha_out_of_hex(value: str, expected: str):
    assert theme.qt_color(value) == expected


def test_qt_color_rejects_unsupported_length():
    with pytest.raises(ValueError, match="Unsupported colour token"):
        theme.qt_color("#ABCD")


# -- stylesheet -------------------------------------------------------------- #
def test_stylesheet_contains_no_eight_digit_hex():
    """Any 8-digit hex left in the QSS would be read by Qt as #AARRGGBB."""
    import re

    for palette in theme.THEMES.values():
        qss = theme.build_stylesheet(palette)
        assert not re.search(r"#[0-9A-Fa-f]{8}\b", qss), f"{palette.key} leaked alpha-last hex"


def test_stylesheet_uses_palette_values():
    qss = theme.build_stylesheet(theme.DEEP_SEA_FOAM)
    assert "#000F13" in qss
    assert "#00A591" in qss
    assert "rgba(88, 110, 117, 102)" in qss
    assert "DeepSeaFoam" in qss


def test_stylesheet_is_balanced():
    """A stray brace from the template silently voids the rest of the sheet."""
    for palette in theme.THEMES.values():
        qss = theme.build_stylesheet(palette)
        assert qss.count("{") == qss.count("}")


# -- helpers ----------------------------------------------------------------- #
def test_resolve_falls_back_to_default():
    assert theme.resolve(None).key == theme.DEFAULT_THEME
    assert theme.resolve("nonsense").key == theme.DEFAULT_THEME
    assert theme.resolve("  Harbor-Daylight ").key == "harbor-daylight"


def test_log_palette_covers_loguru_levels():
    colours = theme.log_palette(theme.HARBOR_DAYLIGHT)
    assert set(colours) == {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
    assert colours["ERROR"] == theme.HARBOR_DAYLIGHT["error"]
    assert colours["WARNING"] == theme.HARBOR_DAYLIGHT["warning"]
