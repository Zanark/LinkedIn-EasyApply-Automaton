"""Small shared widgets for the desktop GUI."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QFont, QTextCursor
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

__all__ = ["Card", "Console", "PathRow", "heading", "muted", "subheading"]

# Matches the loguru console format: "<time> | LEVEL    | module:fn:line - message"
_LEVEL_RE = re.compile(r"\|\s*(TRACE|DEBUG|INFO|SUCCESS|WARNING|ERROR|CRITICAL)\s*\|")
# ANSI escapes survive when a child ignores NO_COLOR; strip them rather than
# rendering the raw control codes.
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


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
    """Read-only log view that colours lines by their loguru level.

    Lines are kept as ``(text, role)`` pairs rather than baked-in colours so a
    theme switch can re-render the backlog. Without that, text written under
    DeepSeaFoam would keep its near-white ink on Harbor Daylight's warm paper.
    """

    MAX_BLOCKS = 5000

    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFont(QFont("Cascadia Mono", 10))
        self._palette = palette
        self._levels = dict(log_palette(palette))
        self._lines: list[tuple[str, str | None]] = []
        self._pending = ""

    def apply_palette(self, palette: Palette) -> None:
        """Adopt *palette* and repaint every line already on screen."""
        self._palette = palette
        self._levels = dict(log_palette(palette))
        kept = list(self._lines)
        self._lines.clear()
        super().clear()
        for text, role in kept:
            self._append_line(text, role)

    def clear(self) -> None:
        self._lines.clear()
        self._pending = ""
        super().clear()

    def append_text(self, chunk: str) -> None:
        """Buffer *chunk* and render every complete line it contains."""
        self._pending += chunk.replace("\r\n", "\n").replace("\r", "\n")
        *lines, self._pending = self._pending.split("\n")
        for line in lines:
            self._append_line(line)

    def flush(self) -> None:
        if self._pending:
            self._append_line(self._pending)
            self._pending = ""

    def note(self, text: str, role: str = "text") -> None:
        """Write a GUI-generated line (command echo, status) into the log.

        *role* is a palette role name, not a colour, so the line follows a
        later theme switch.
        """
        self._append_line(text, role)

    def _colour_for(self, text: str, role: str | None) -> str:
        if role is not None:
            return self._palette[role]
        match = _LEVEL_RE.search(text)
        return self._levels.get(match.group(1), self._palette["text"]) if match else (
            self._palette["text"]
        )

    def _append_line(self, line: str, role: str | None = None) -> None:
        clean = _ANSI_RE.sub("", line)
        self._lines.append((clean, role))
        if len(self._lines) > self.MAX_BLOCKS:
            del self._lines[: len(self._lines) - self.MAX_BLOCKS]
        colour = self._colour_for(clean, role)
        self.appendHtml(f'<span style="color:{colour}; white-space:pre;">{_escape(clean)}</span>')
        self.moveCursor(QTextCursor.End)

    def contextMenuEvent(self, event) -> None:  # noqa: ANN001 - Qt signature
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        menu.addAction("Clear", self.clear)
        menu.exec(event.globalPos())


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace(" ", "&nbsp;")
    )


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
        value.setToolTip(str(path))
        value.setMinimumWidth(160)
        value.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        button = QPushButton("Open")
        button.clicked.connect(lambda: on_open(path))
        row.addWidget(name)
        row.addWidget(value, 1)
        row.addWidget(button)
