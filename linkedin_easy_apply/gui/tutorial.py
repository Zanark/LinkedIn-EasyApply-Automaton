"""Read-only guided reference, shared by desktop help and standalone startup."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from linkedin_easy_apply.gui.widgets import heading, muted
from linkedin_easy_apply.runtime import resource_root

CUSTOMIZE_TOPIC = "Customize this run"


@dataclass(frozen=True)
class TutorialTopic:
    title: str
    markdown: str


def load_tutorial(path: Path) -> tuple[TutorialTopic, ...]:
    """Use the guide's level-two headings as the ordered, named topics."""
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^## (.+)$", text, re.MULTILINE))
    topics = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        topics.append(TutorialTopic(match.group(1).strip(), text[match.end() : end].strip()))
    if not topics or any(not topic.title or not topic.markdown for topic in topics):
        raise ValueError(f"The tutorial has missing or empty topics: {path}")
    if len({topic.title for topic in topics}) != len(topics):
        raise ValueError(f"The tutorial has duplicate topic titles: {path}")
    return tuple(topics)


class TutorialDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, start_topic: str | None = None) -> None:
        topics = load_tutorial(resource_root() / "docs" / "gui-tutorial.md")
        titles = [topic.title for topic in topics]
        first = titles.index(start_topic) if start_topic is not None else 0
        super().__init__(parent)
        self._topics = topics
        self.setWindowTitle("Easy Apply Automaton - Guided tutorial")
        self.setModal(True)
        self.resize(1040, 760)
        self.setMinimumSize(760, 540)

        column = QVBoxLayout(self)
        column.setContentsMargins(20, 18, 20, 16)
        column.setSpacing(12)
        column.addWidget(heading("Learn the desktop, one topic at a time"))
        column.addWidget(
            muted("Read-only tutorial. No commands, browser, settings changes or run presets.")
        )

        content = QHBoxLayout()
        self._topic_list = QListWidget()
        self._topic_list.setAccessibleName("Tutorial topics")
        self._topic_list.setWordWrap(True)
        self._topic_list.setMinimumWidth(215)
        self._topic_list.setMaximumWidth(270)
        self._topic_list.addItems(
            [f"{index + 1}. {topic.title}" for index, topic in enumerate(topics)]
        )
        content.addWidget(self._topic_list, 1)

        explanation = QVBoxLayout()
        self._title = heading("")
        self._body = QTextBrowser()
        self._body.setAccessibleName("Tutorial explanation")
        self._body.setOpenLinks(False)
        self._body.setOpenExternalLinks(False)
        explanation.addWidget(self._title)
        explanation.addWidget(self._body, 1)
        content.addLayout(explanation, 3)
        column.addLayout(content, 1)

        navigation = QHBoxLayout()
        self._progress = QLabel()
        self._progress.setProperty("role", "badge")
        navigation.addWidget(self._progress)
        navigation.addStretch(1)
        self._back = QPushButton("Back")
        self._back.clicked.connect(
            lambda: self._topic_list.setCurrentRow(self._topic_list.currentRow() - 1)
        )
        self._next = QPushButton("Next")
        self._next.setProperty("role", "primary")
        self._next.setDefault(True)
        self._next.clicked.connect(self._advance)
        close = QPushButton("Close tutorial")
        close.clicked.connect(self.reject)
        for button in (self._back, self._next, close):
            navigation.addWidget(button)
        column.addLayout(navigation)

        self._topic_list.currentRowChanged.connect(self._show_topic)
        self._topic_list.setCurrentRow(first)

    def _show_topic(self, index: int) -> None:
        if index < 0:
            return
        topic = self._topics[index]
        self._title.setText(topic.title)
        self._body.setMarkdown(topic.markdown)
        self._body.verticalScrollBar().setValue(0)
        self._progress.setText(f"{index + 1} / {len(self._topics)}")
        self._back.setEnabled(index > 0)
        self._next.setText("Finish" if index == len(self._topics) - 1 else "Next")

    def _advance(self) -> None:
        index = self._topic_list.currentRow()
        if index == len(self._topics) - 1:
            self.accept()
        else:
            self._topic_list.setCurrentRow(index + 1)
