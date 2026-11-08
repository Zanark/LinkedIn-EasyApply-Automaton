"""Common configuration controls for a single desktop run."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from linkedin_easy_apply.config import AppConfig
from linkedin_easy_apply.gui.widgets import muted


class RunSettings(QWidget):
    changed = Signal()
    help_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.customize = QCheckBox("Customize settings for this run")
        self.customize.setToolTip(
            "The saved YAML stays unchanged. Start or Copy creates a private preset "
            "in logs\\gui-runs, usable by the CLI."
        )
        customize_row = QHBoxLayout()
        customize_row.addWidget(self.customize, 1)
        self.help_button = QPushButton("?")
        self.help_button.setFixedWidth(32)
        self.help_button.setAccessibleName("Explain per-run settings")
        self.help_button.setToolTip("Explain this checkbox in the guided tutorial")
        self.help_button.clicked.connect(self.help_requested)
        customize_row.addWidget(self.help_button)
        layout.addLayout(customize_row)
        self.tabs = QTabWidget()
        self.tabs.setEnabled(False)
        self.tabs.setVisible(False)
        self.customize.toggled.connect(self.tabs.setEnabled)
        self.customize.toggled.connect(self.tabs.setVisible)
        self.customize.toggled.connect(self.changed)
        layout.addWidget(self.tabs)
        self._fields: dict[str, QWidget] = {}
        self._searches: list[dict[str, Any]] = []

        search = QWidget()
        search_layout = QVBoxLayout(search)
        search_layout.addWidget(muted("Enabled saved searches"))
        self.searches = QListWidget()
        self.searches.setMaximumHeight(125)
        self.searches.itemChanged.connect(self.changed)
        search_layout.addWidget(self.searches)
        search_layout.addWidget(muted("Exact job URLs (Apply only, one per line)"))
        self.job_urls = QPlainTextEdit()
        self.job_urls.setPlaceholderText("https://www.linkedin.com/jobs/view/1234567890/")
        self.job_urls.setMaximumHeight(90)
        self.job_urls.textChanged.connect(self.changed)
        search_layout.addWidget(self.job_urls)
        search_layout.addWidget(
            muted("Exact jobs replace discovery for Apply. Search URL overrides saved searches.")
        )
        self.tabs.addTab(search, "Search")

        caps = self._form_tab("Limits")
        self._number(caps, "Per company", "jobs.max_per_company", 1, 100000)
        self._number(caps, "Daily cap", "jobs.max_daily", 1, 100000)
        self._number(caps, "Search pages", "jobs.max_search_pages", 1, 10000)
        self._number(caps, "Results per page", "jobs.search_page_size", 1, 100)
        self._number(caps, "Pause every N", "jobs.pause_after", 0, 100000)
        pause = QDoubleSpinBox()
        pause.setRange(0, 86400)
        self._add(caps, "Pause seconds", "jobs.pause_seconds", pause)
        self._number(caps, "Score threshold", "scoring.threshold", -100000, 100000)

        browser = self._form_tab("Browser")
        self._choice(browser, "Browser", "browser.engine", ["edge", "chrome", "chromium"])
        self._text(browser, "Profile folder", "browser.profile_path")
        self._check(browser, "Headless browser", "browser.headless")
        self._number(browser, "Slow motion (ms)", "browser.slow_mo_ms", 0, 10000)
        self._number(browser, "Timeout (ms)", "browser.default_timeout_ms", 100, 600000)
        self._number(browser, "Navigation (ms)", "browser.navigation_timeout_ms", 100, 600000)
        self._text(browser, "Resume folder", "resume.directory")
        self._text(browser, "Default PDF", "resume.default")

        behavior = self._form_tab("Behavior")
        self._check(behavior, "Pause on unknown questions", "run.pause_on_unknown_question")
        review = QDoubleSpinBox()
        review.setRange(0, 300)
        review.setSuffix(" s")
        self._add(behavior, "Resume review", "run.resume_review_pause", review)
        self._check(behavior, "Capture screenshots", "screenshots.enabled")
        self._check(behavior, "Capture each step", "screenshots.each_step")
        self._check(behavior, "Clean unreferenced screenshots", "screenshots.cleanup")
        self._choice(behavior, "Outreach", "outreach.mode", ["draft", "send"])
        self._check(behavior, "Send connection notes after run", "outreach.send_connection_notes")
        self._number(behavior, "Connection cap", "outreach.connect_max_per_run", 1, 100000)
        self._check(behavior, "Dynamic resume builder", "resume.builder.enabled")
        self.load(AppConfig())

    def _form_tab(self, label: str) -> QFormLayout:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setSpacing(10)
        self.tabs.addTab(widget, label)
        return form

    def _add(self, form: QFormLayout, label: str, key: str, field: QWidget) -> None:
        self._fields[key] = field
        if isinstance(field, (QSpinBox, QDoubleSpinBox)):
            field.valueChanged.connect(self.changed)
        elif isinstance(field, QComboBox):
            field.currentTextChanged.connect(self.changed)
        elif isinstance(field, QLineEdit):
            field.textChanged.connect(self.changed)
        elif isinstance(field, QCheckBox):
            field.toggled.connect(self.changed)
        if isinstance(field, QCheckBox):
            form.addRow(field)
        else:
            form.addRow(label, field)

    def _number(self, form: QFormLayout, label: str, key: str, low: int, high: int) -> None:
        field = QSpinBox()
        field.setRange(low, high)
        self._add(form, label, key, field)

    def _text(self, form: QFormLayout, label: str, key: str) -> None:
        self._add(form, label, key, QLineEdit())

    def _choice(self, form: QFormLayout, label: str, key: str, choices: list[str]) -> None:
        field = QComboBox()
        field.addItems(choices)
        self._add(form, label, key, field)

    def _check(self, form: QFormLayout, label: str, key: str) -> None:
        self._add(form, label, key, QCheckBox(label))

    def load(self, config: AppConfig) -> None:
        self.customize.setChecked(False)
        data = config.model_dump(mode="json")
        for key, field in self._fields.items():
            value: Any = data
            for part in key.split("."):
                value = value[part]
            if isinstance(field, QCheckBox):
                field.setChecked(bool(value))
            elif isinstance(field, (QSpinBox, QDoubleSpinBox)):
                field.setRange(min(field.minimum(), value), max(field.maximum(), value))
                field.setValue(value)
            elif isinstance(field, QComboBox):
                field.setCurrentText(str(value))
            elif isinstance(field, QLineEdit):
                field.setText("" if value is None else str(value))
        self._searches = data["search"]["searches"]
        self.searches.clear()
        for entry in self._searches:
            item = QListWidgetItem(entry["name"])
            item.setToolTip(entry["url"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if entry["enabled"] else Qt.CheckState.Unchecked
            )
            self.searches.addItem(item)
        self.job_urls.setPlainText("\n".join(config.search.job_urls))
        self._baseline = self._values()
        self.changed.emit()

    def _values(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, field in self._fields.items():
            if isinstance(field, QCheckBox):
                values[key] = field.isChecked()
            elif isinstance(field, (QSpinBox, QDoubleSpinBox)):
                values[key] = field.value()
            elif isinstance(field, QComboBox):
                values[key] = field.currentText()
            elif isinstance(field, QLineEdit):
                values[key] = field.text().strip() or None
        values["search.searches"] = [
            {**entry, "enabled": self.searches.item(i).checkState() == Qt.CheckState.Checked}
            for i, entry in enumerate(self._searches)
        ]
        values["search.job_urls"] = self.job_urls.toPlainText().split()
        return values

    def overrides(self) -> dict[str, Any]:
        if not self.customize.isChecked():
            return {}
        return {key: value for key, value in self._values().items() if value != self._baseline[key]}
