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

from linkedin_easy_apply.gui.theme import (  # noqa: E402
    DEEP_SEA_FOAM,
    HARBOR_DAYLIGHT,
    build_stylesheet,
)
from linkedin_easy_apply.gui.widgets import Console  # noqa: E402


@pytest.fixture
def console(qt_app: QApplication):
    widget = Console(DEEP_SEA_FOAM)
    yield widget
    widget.deleteLater()


def _html(console: Console) -> str:
    return console.document().toHtml()


def test_partial_prompts_are_visible_and_completed_once(console: Console):
    console.append_text("first line\nhalf a ")
    assert console.toPlainText() == "first line\nhalf a "
    console.append_text("line\n")
    assert console.toPlainText() == "first line\nhalf a line"


def test_flush_preserves_the_visible_prompt_once(console: Console):
    console.append_text("no newline yet")
    assert console.toPlainText() == "no newline yet"
    console.flush()
    console.flush()
    assert console.toPlainText() == "no newline yet"


@pytest.mark.parametrize("chunks", [("a\r\nb\r\n",), ("a\r", "\nb\r", "\n")])
def test_carriage_returns_do_not_create_blank_lines(console: Console, chunks):
    for chunk in chunks:
        console.append_text(chunk)
    assert console.toPlainText() == "a\nb"


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


def _record(message, *, level="INFO", module="forms.easy_apply", function="_fill_field"):
    return (
        f"2026-01-01 09:12:34 | {level: <8} | "
        f"linkedin_easy_apply.{module}:{function}:123 - {message}"
    )


def test_compact_prefix_retains_source_as_tooltip_and_reversible_details(console: Console):
    raw = _record("Detected 4 fields", level="DEBUG", module="forms.detector", function="detect")
    console.append_text(raw + "\nAnswer: ")
    compact = console.toPlainText()
    assert compact == "09:12:34  [DEBUG] [DETECT]  Detected 4 fields\nAnswer: "
    tooltip = console.document().find("[DETECT]").charFormat().toolTip()
    assert "2026-01-01" in tooltip
    assert "linkedin_easy_apply.forms.detector:detect:123" in tooltip
    console.set_details(True)
    assert console.toPlainText() == raw + "\nAnswer: "
    console.apply_palette(HARBOR_DAYLIGHT)
    assert console.toPlainText() == raw + "\nAnswer: "
    console.set_details(False)
    assert console.toPlainText() == compact
    console.append_text("complete\n")
    assert console.toPlainText().endswith("\nAnswer: complete")


@pytest.mark.parametrize("palette", [DEEP_SEA_FOAM, HARBOR_DAYLIGHT])
@pytest.mark.parametrize(
    ("message", "module", "label", "role"),
    [
        ("[SCORE PASS] 42/20 | Example role", "orchestrator", "SCORE PASS", "document"),
        ("[SCORE FAIL] 12/20 | Example role", "orchestrator", "SCORE FAIL", "warning"),
        ("Skip (already_applied) - Example role", "orchestrator", "SKIP", "warning"),
        ("DRY-RUN: reached Submit without sending", "forms.easy_apply", "DRY-RUN", "warning"),
        ("Submitting the application now (2 questions)", "forms.easy_apply", "SUBMIT", "accent"),
        (
            "Application submitted successfully - LinkedIn confirmation: Example evidence",
            "forms.easy_apply",
            "SUBMITTED",
            "document",
        ),
    ],
)
def test_activity_labels_use_semantic_colors(
    console: Console, palette, message, module, label, role
):
    console.apply_palette(palette)
    console.append_text(_record(message, module=module) + "\n")
    label_cursor = console.document().find(f"[{label}]")
    assert not label_cursor.isNull()
    assert label_cursor.charFormat().foreground().color().name() == palette[role].lower()
    assert console.toPlainText().count(f"[{label}]") == 1
    assert "[INFO]" in console.toPlainText()


def test_unknown_output_and_multiline_diagnostics_preserve_spacing(console: Console):
    continuation = (
        "Traceback (most recent call last):\n"
        '  File "C:\\Demo\\example.py", line 7, in run\n'
        "    raise ValueError('<example> & details')\n"
        "ValueError: <example> & details\n"
        "\n"
        "  Column A    Column B\n"
        "  first       second"
    )
    raw = _record("Operation failed", level="ERROR") + "\n" + continuation
    for start in range(0, len(raw), 7):
        console.append_text(raw[start : start + 7])
    console.flush()
    assert console.toPlainText().endswith("\n" + continuation)
    assert "\u00a0" not in console.toPlainText()
    console.set_details(True)
    assert console.toPlainText() == raw


def test_ansi_prefix_can_arrive_in_separate_chunks(console: Console):
    console.append_text("\x1b[3")
    assert "\x1b" not in console.toPlainText()
    console.append_text("1m" + _record("<b>plain text</b>") + "\x1b[0")
    assert "[FORM]" in console.toPlainText()
    assert "<b>plain text</b>" in console.toPlainText()
    console.append_text("m\n")
    console.set_details(True)
    assert console.toPlainText() == _record("<b>plain text</b>")


@pytest.mark.parametrize("palette", [DEEP_SEA_FOAM, HARBOR_DAYLIGHT])
def test_narrow_console_wraps_at_words_and_breaks_long_tokens(console: Console, qt_app, palette):
    console.apply_palette(palette)
    console.setStyleSheet(build_stylesheet(palette))
    console.resize(360, 240)
    console.show()
    console.append_text(_record("A useful field message has normal word wrapping. " * 8) + "\n")
    qt_app.processEvents()
    block = console.document().firstBlock()
    layout = block.layout()
    assert layout.lineCount() > 2
    for number in range(layout.lineCount() - 1):
        line = layout.lineAt(number)
        end = line.textStart() + line.textLength()
        assert block.text()[end - 1].isspace() or block.text()[end].isspace()
    console.append_text("long_token_" * 80 + "\n")
    qt_app.processEvents()
    assert console.document().lastBlock().layout().lineCount() > 1
    assert console.horizontalScrollBar().maximum() == 0


def test_history_stays_bounded_across_pending_output_and_repaints(console: Console, monkeypatch):
    monkeypatch.setattr(console, "MAX_BLOCKS", 3)
    console.setMaximumBlockCount(3)
    console.append_text("one\ntwo\nthree\npending")
    console.apply_palette(HARBOR_DAYLIGHT)
    console.set_details(True)
    console.append_text(" complete\nfive\n")
    assert console.toPlainText() == "three\npending complete\nfive"
    console.apply_palette(DEEP_SEA_FOAM)
    assert console.toPlainText() == "three\npending complete\nfive"


def test_new_output_does_not_drag_a_scrolled_reader_to_the_bottom(console: Console, qt_app):
    console.resize(360, 180)
    console.show()
    console.append_text("".join(f"line {number}\n" for number in range(80)))
    qt_app.processEvents()
    scroll = console.verticalScrollBar()
    assert scroll.maximum() > 0
    scroll.setValue(0)
    selected = console.document().find("line 10")
    console.setTextCursor(selected)
    scroll.setValue(0)
    console.append_text("a new line\n")
    assert scroll.value() == 0
    assert console.textCursor().selectedText() == "line 10"
    scroll.setValue(scroll.maximum())
    console.append_text("following again\n")
    assert scroll.value() == scroll.maximum()
