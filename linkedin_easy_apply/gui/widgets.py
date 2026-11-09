"""Small shared widgets for the desktop GUI."""

from __future__ import annotations

import re
from pathlib import Path
from typing import override

from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextOption,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from linkedin_easy_apply.gui.theme import Palette, log_palette

__all__ = ["Card", "Console", "PathRow", "heading", "muted", "subheading", "tooltip"]

# Matches the loguru console format: "<time> | LEVEL    | module:fn:line - message"
_LEVEL_RE = re.compile(r"\|\s*(TRACE|DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*\|")
_LOG_RE = re.compile(
    r"^(?P<stamp>\d{4}-\d{2}-\d{2} (?P<time>\d{2}:\d{2}:\d{2})(?:\.\d+)?) \|"
    r"\s*(?P<level>TRACE|DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*\| "
    r"(?P<source>(?P<module>[\w.]+):(?P<function>[^:\s]+):\d+) - (?P<message>.*)$"
)
# ANSI escapes survive when a child ignores NO_COLOR; strip them rather than
# rendering the raw control codes.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_INCOMPLETE_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*$")

_SOURCE_LABELS = {
    "orchestrator": ("RUN", "heading"),
    "logging.setup": ("SYSTEM", "muted"),
    "cli.main": ("CLI", "accent"),
    "browser.manager": ("BROWSER", "accent"),
    "jobs.search": ("SEARCH", "accent"),
    "jobs.extractor": ("JOB", "heading"),
    "scoring.engine": ("SCORE", "accent"),
    "forms.detector": ("DETECT", "muted"),
    "forms.filler": ("FILL", "accent"),
    "forms.easy_apply": ("FORM", "accent"),
    "parser.question_parser": ("PARSE", "muted"),
    "answers.resolver": ("ANSWER", "accent"),
    "answers.resume_selector": ("RESUME", "document"),
    "answers.dynamic_resume": ("RESUME", "document"),
    "answers.cover_letter": ("LETTER", "document"),
    "forms.outreach": ("OUTREACH", "accent"),
    "database.db": ("DATA", "muted"),
    "utils.retry": ("RETRY", "warning"),
}


def _log_label(match: re.Match[str]) -> tuple[str, str, str]:
    module = match["module"].removeprefix("linkedin_easy_apply.")
    message = match["message"]
    if module == "orchestrator":
        for marker, role in (("[SCORE PASS] ", "document"), ("[SCORE FAIL] ", "warning")):
            if message.startswith(marker):
                return marker.strip()[1:-1], role, message[len(marker) :]
        if message.startswith("Skip ("):
            return "SKIP", "warning", message
        if message.startswith("Best resume for "):
            return "RESUME", "document", message
        if match["function"] == "_pause_for_resume_review":
            return "WAIT", "warning", message
    elif module == "forms.easy_apply":
        if message.startswith("DRY-RUN: "):
            return "DRY-RUN", "warning", message[len("DRY-RUN: ") :]
        if message.startswith("Application submitted successfully - LinkedIn confirmation: "):
            return "SUBMITTED", "document", message
        if message.startswith("Submitting the application now "):
            return "SUBMIT", "accent", message
        if message.startswith("--- Easy Apply step "):
            return "STEP", "heading", message
        if match["function"] == "_resolve_interactively":
            return "INPUT", "warning", message
    label, role = _SOURCE_LABELS.get(module, ("LOG", "muted"))
    return label, role, message


def tooltip(purpose: str, example: str) -> str:
    """Keep option help to a purpose line and a practical-example line."""
    return f"{purpose}\nExample: {example}"


def heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "heading")
    return label


def subheading(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "subheading")
    return label


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", "muted")
    label.setWordWrap(True)
    return label


class Card(QFrame):
    """A titled panel used to group related controls."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(8)
        if title:
            self._layout.addWidget(subheading(title))

    def body(self) -> QVBoxLayout:
        return self._layout

    def add(self, widget: QWidget) -> QWidget:
        self._layout.addWidget(widget)
        return widget

    def add_row(self, *widgets: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        for widget in widgets:
            row.addWidget(widget)
        self._layout.addLayout(row)
        return row


class Console(QPlainTextEdit):
    """Compact, word-wrapped logs with semantic severity and activity labels.

    Retain original lines and semantic roles, not baked-in colours. Both a
    theme switch and diagnostic view can therefore repaint the same backlog.
    """

    MAX_BLOCKS = 5000

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setFont(QFont("Cascadia Mono", 10))
        self.document().setDocumentMargin(8)
        self._palette = palette
        self._levels = dict(log_palette(palette))
        self._lines: list[tuple[str, str | None, str | None]] = []
        self._details = False
        self._rendered_lines = 0
        self._pending = ""
        self._pending_visible = False
        self._trailing_cr = False

    def apply_palette(self, palette: Palette) -> None:
        """Adopt *palette* and repaint every line already on screen."""
        self._palette = palette
        self._levels = dict(log_palette(palette))
        self._repaint()

    def set_details(self, enabled: bool) -> None:
        """Switch between compact labels and original diagnostic prefixes."""
        if self._details != enabled:
            self._details = enabled
            self._repaint()

    def _repaint(self) -> None:
        position = self._scroll_position()
        super().clear()
        self._rendered_lines = 0
        self._pending_visible = False
        for text, role, label in self._lines:
            self._insert_line(text, role, label)
        self._show_pending()
        self._restore_scroll(position)

    def clear(self) -> None:
        self._lines.clear()
        self._rendered_lines = 0
        self._pending = ""
        self._pending_visible = False
        self._trailing_cr = False
        super().clear()

    def append_text(self, chunk: str) -> None:
        """Show complete lines and unterminated prompts immediately."""
        if not chunk:
            return
        position = self._scroll_position()
        self._remove_pending()
        if self._trailing_cr and chunk.startswith("\n"):
            chunk = chunk[1:]
        self._trailing_cr = chunk.endswith("\r")
        self._pending += chunk.replace("\r\n", "\n").replace("\r", "\n")
        *lines, self._pending = self._pending.split("\n")
        for line in lines:
            self._append_line(line)
        self._show_pending()
        self._restore_scroll(position)

    def flush(self) -> None:
        if self._pending:
            self.append_text("\n")

    def note(self, text: str, role: str = "text", *, label: str | None = None) -> None:
        """Write a GUI-generated line (command echo, status) into the log.

        *role* is a palette role name, not a colour, so the line follows a
        later theme switch.
        """
        self.flush()
        position = self._scroll_position()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            self._append_line(line, role, label)
        self._restore_scroll(position)

    def _remove_pending(self) -> None:
        if not self._pending_visible:
            return
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        if cursor.blockNumber():
            cursor.deletePreviousChar()
        self._rendered_lines -= 1
        self._pending_visible = False

    def _show_pending(self) -> None:
        if self._pending:
            clean = _INCOMPLETE_ANSI_RE.sub("", _ANSI_RE.sub("", self._pending))
            self._insert_line(clean)
            self._pending_visible = True

    def _colour_for(self, text: str, role: str | None) -> str:
        if role is not None:
            return self._palette[role]
        match = _LEVEL_RE.search(text)
        return (
            self._levels.get(match.group(1), self._palette["text"])
            if match
            else (self._palette["text"])
        )

    def _append_line(self, line: str, role: str | None = None, label: str | None = None) -> None:
        clean = _ANSI_RE.sub("", line)
        self._lines.append((clean, role, label))
        if len(self._lines) > self.MAX_BLOCKS:
            del self._lines[: len(self._lines) - self.MAX_BLOCKS]
        self._insert_line(clean, role, label)

    def _insert_line(self, text: str, role: str | None = None, label: str | None = None) -> None:
        cursor = QTextCursor(self.document())
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self._rendered_lines:
            cursor.insertBlock()
        self._rendered_lines = min(self._rendered_lines + 1, self.MAX_BLOCKS)
        match = _LOG_RE.fullmatch(text) if role is None else None
        block = QTextBlockFormat()
        block.setTopMargin(5 if match or label else 0)
        block.setBottomMargin(1)
        cursor.setBlockFormat(block)
        if match and not self._details:
            tooltip = f"{match['stamp']} | {match['source']}"
            self._span(cursor, match["time"] + "  ", self._palette["muted"], tooltip=tooltip)
            self._span(
                cursor,
                f"[{match['level']}]",
                self._levels[match["level"]],
                badge=True,
                tooltip=tooltip,
            )
            label, label_role, message = _log_label(match)
            self._span(cursor, " ", self._palette["text"])
            self._span(cursor, f"[{label}]", self._palette[label_role], badge=True, tooltip=tooltip)
            message_colour = (
                self._levels[match["level"]]
                if match["level"] in {"SUCCESS", "WARNING", "ERROR", "CRITICAL"}
                else self._palette["text"]
            )
            self._span(cursor, "  " + message, message_colour, tooltip=tooltip)
        else:
            colour = self._colour_for(text, role)
            if label:
                self._span(cursor, f"[{label}]", colour, badge=True)
                self._span(cursor, "  ", colour)
            self._span(cursor, text, colour)

    def _span(
        self, cursor: QTextCursor, text: str, colour: str, *, badge: bool = False, tooltip: str = ""
    ) -> None:
        style = QTextCharFormat()
        style.setForeground(QColor(colour))
        style.setToolTip(tooltip)
        if badge:
            style.setFontWeight(QFont.Weight.DemiBold)
            style.setBackground(QColor(self._palette["surface"]))
        cursor.insertText(text, style)

    def _scroll_position(self) -> tuple[int, bool]:
        scroll = self.verticalScrollBar()
        return scroll.value(), scroll.value() == scroll.maximum()

    def _restore_scroll(self, position: tuple[int, bool]) -> None:
        value, following = position
        scroll = self.verticalScrollBar()
        scroll.setValue(scroll.maximum() if following else min(value, scroll.maximum()))

    @override
    def contextMenuEvent(self, event) -> None:  # noqa: ANN001 - Qt signature
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction("Clear", self.clear)
        menu.exec(event.globalPos())


class PathRow(QWidget):
    """A label, the path, and an 'open folder' button.

    The path is a read-only ``QLineEdit`` rather than a ``QLabel`` on purpose: a
    label's size hint is its full text, so a long absolute path would force the
    whole window wider than the screen. A line edit scrolls its content instead
    and still allows selecting and copying the path.
    """

    def __init__(
        self, label: str, path: Path, on_open, parent: QWidget | None = None
    ) -> None:  # noqa: ANN001
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        name = QLabel(label)
        name.setMinimumWidth(130)
        value = QLineEdit(str(path))
        value.setReadOnly(True)
        value.setCursorPosition(0)
        value.setToolTip(
            tooltip(
                f"Read-only location of the {label.lower()} folder.",
                "Select and copy this path, or use Open to inspect the folder.",
            )
        )
        name.setToolTip(value.toolTip())
        value.setMinimumWidth(160)
        value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        button = QPushButton("Open")
        button.setToolTip(
            tooltip(
                f"Open the {label.lower()} folder in your system file manager.",
                "Inspect files here without starting an automation command.",
            )
        )
        button.clicked.connect(lambda: on_open(path))
        row.addWidget(name)
        row.addWidget(value, 1)
        row.addWidget(button)
