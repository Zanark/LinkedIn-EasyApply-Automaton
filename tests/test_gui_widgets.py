"""Qt-level tests for the GUI console.

Skipped entirely when PySide6 is absent, so the suite still runs in a plain
environment. Everything here uses the offscreen platform plugin - no window is
ever shown.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6", reason="GUI extra not installed")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from linkedin_easy_apply.gui.theme import DEEP_SEA_FOAM, HARBOR_DAYLIGHT  # noqa: E402
from linkedin_easy_apply.gui.widgets import Console  # noqa: E402


@pytest.fixture(scope="module")
def qt_app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def console(qt_app: QApplication) -> Console:
    return Console(DEEP_SEA_FOAM)


def _html(console: Console) -> str:
    return console.document().toHtml()


def test_only_complete_lines_are_rendered(console: Console):
    console.append_text("first line\nhalf a ")
    assert "first line" in console.toPlainText()
    assert "half a" not in console.toPlainText()
    console.append_text("line\n")
    assert "half a line" in console.toPlainText()


def test_flush_emits_the_trailing_partial_line(console: Console):
    console.append_text("no newline yet")
    assert console.toPlainText().strip() == ""
    console.flush()
    assert "no newline yet" in console.toPlainText()


def test_carriage_returns_do_not_create_blank_lines(console: Console):
    console.append_text("a\r\nb\r\n")
    assert [line for line in console.toPlainText().splitlines() if line.strip()] == ["a", "b"]


def test_level_colours_come_from_the_palette(console: Console):
    console.append_text("2026-01-01 00:00:00 | ERROR    | mod:fn:1 - boom\n")
    assert DEEP_SEA_FOAM["error"].lower() in _html(console).lower()


def test_ansi_escapes_are_stripped(console: Console):
    console.append_text("\x1b[31mred text\x1b[0m\n")
    assert "red text" in console.toPlainText()
    assert "\x1b" not in console.toPlainText()
    assert "[31m" not in console.toPlainText()


def test_html_in_log_output_is_escaped(console: Console):
    console.append_text("<script>alert(1)</script>\n")
    assert "<script>alert(1)</script>" in console.toPlainText()


def test_theme_switch_repaints_existing_lines(console: Console):
    """A line written under one theme must not keep that theme's ink."""
    console.append_text("2026-01-01 00:00:00 | INFO     | mod:fn:1 - hello\n")
    console.note("$ python apply.py scan", "accent")
    assert DEEP_SEA_FOAM["text"].lower() in _html(console).lower()

    console.apply_palette(HARBOR_DAYLIGHT)
    html = _html(console).lower()
    assert HARBOR_DAYLIGHT["text"].lower() in html
    assert HARBOR_DAYLIGHT["accent"].lower() in html
    # DeepSeaFoam's near-white ink would sit at ~2.2:1 on Harbor Daylight paper.
    assert DEEP_SEA_FOAM["text"].lower() not in html
    assert DEEP_SEA_FOAM["accent"].lower() not in html
    # ...and the text itself survives the repaint.
    assert "hello" in console.toPlainText()
    assert "$ python apply.py scan" in console.toPlainText()


def test_clear_also_drops_the_backlog(console: Console):
    console.append_text("line\n")
    console.clear()
    console.apply_palette(HARBOR_DAYLIGHT)
    assert console.toPlainText().strip() == ""
