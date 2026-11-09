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
from linkedin_easy_apply.gui.widgets import muted, tooltip

_FIELD_HELP: dict[str, tuple[str, str]] = {
    "jobs.max_per_company": (
        "Cap confirmed submissions to one company across this database's history.",
        "With 2 already submitted and a cap of 2, another job at that company is skipped.",
    ),
    "jobs.max_daily": (
        "Cap confirmed submissions for the local calendar day, across runs.",
        "20 allows up to 20 submissions today, including earlier runs in this database.",
    ),
    "jobs.max_search_pages": (
        "Limit result pages visited for each enabled saved search.",
        "4 visits at most four pages per search; discovery can stop sooner.",
    ),
    "jobs.search_page_size": (
        "Set the increment used for LinkedIn search-result page offsets.",
        "25 advances through start=0, 25, 50; it is not the total run target.",
    ),
    "jobs.pause_after": (
        "Take a timed break after every N confirmed submissions; 0 disables it.",
        "5 requests a break after submission 5, then 10, using Pause seconds.",
    ),
    "jobs.pause_seconds": (
        "Choose the duration of each automatic submission break.",
        "15 waits fifteen seconds when Pause every N triggers.",
    ),
    "scoring.threshold": (
        "Set the minimum job score when score enforcement is enabled.",
        "10 skips a score of 8 unless Ignore the minimum score is enabled.",
    ),
    "browser.engine": (
        "Choose the browser used with a persistent automation profile.",
        "edge uses installed Edge; chromium needs the optional browser download.",
    ),
    "browser.profile_path": (
        "Use a dedicated browser profile to preserve your LinkedIn sign-in.",
        ".browser-profile reuses its session; do not share it between running browsers.",
    ),
    "browser.headless": (
        "Run the browser without a visible window.",
        "Leave this off to sign in or inspect an unknown form manually.",
    ),
    "browser.slow_mo_ms": (
        "Delay Playwright browser actions by this many milliseconds.",
        "500 adds a half-second action delay, not a break between jobs.",
    ),
    "browser.default_timeout_ms": (
        "Limit how long ordinary browser actions wait for a target.",
        "30000 allows up to thirty seconds for a form field to become available.",
    ),
    "browser.navigation_timeout_ms": (
        "Limit how long page navigation waits before timing out.",
        "45000 allows up to forty-five seconds for navigation, not for the whole run.",
    ),
    "resume.directory": (
        "Locate static resume files; relative paths use the workspace.",
        "generated\\resume contains the PDFs referenced by saved resume mappings.",
    ),
    "resume.default": (
        "Choose the fallback PDF when no static role mapping matches.",
        "default.pdf is looked up inside the configured Resume folder.",
    ),
    "run.pause_on_unknown_question": (
        "Pause for unresolved fields when interactive answering is also enabled.",
        "Enable both controls to type an answer here or fill it in the browser.",
    ),
    "run.resume_review_pause": (
        "Wait after logging the chosen resume before attempting the application.",
        "3 gives you three seconds to read the pick; 0 disables this delay.",
    ),
    "screenshots.enabled": (
        "Allow browser screenshot capture during automation.",
        "Turn this off to stop new step and unknown-question captures.",
    ),
    "screenshots.each_step": (
        "Store the per-step preference; the current workflow does not enforce it separately.",
        "Use Capture screenshots to enable or disable actual step captures.",
    ),
    "screenshots.cleanup": (
        "Delete unreferenced PNG screenshots after runs when screenshot capture is enabled.",
        "Temporary images are removed; images referenced by application records are kept.",
    ),
    "outreach.mode": (
        "Choose draft-only recruiter outreach or approval-before-send mode.",
        "draft writes a report; send needs interactive approval or falls back to drafts.",
    ),
    "outreach.send_connection_notes": (
        "Optionally send this run's pending connection notes after Apply or Reapply.",
        "Enabled can open another browser and send real invitations after the run.",
    ),
    "outreach.connect_max_per_run": (
        "Cap pending connection invitations selected for each pass.",
        "5 processes at most five notes; Run target overrides this for Connect.",
    ),
    "resume.builder.enabled": (
        "Enable per-job resume generation using the separately configured builder.",
        "A matching job uses the builder; unmatched jobs or errors fall back to static PDFs.",
    ),
}

_TAB_HELP: dict[str, tuple[str, str]] = {
    "Search": (
        "Choose saved searches or an exact-job batch for this run.",
        "Uncheck a saved search to leave it out without editing the saved YAML.",
    ),
    "Limits": (
        "Adjust caps, discovery depth, pauses and the score threshold for this run.",
        "Lower Daily cap for a shorter day while keeping the saved configuration unchanged.",
    ),
    "Browser": (
        "Adjust the browser profile, timing and static resume paths for this run.",
        "Keep Headless off when you want to inspect forms in the browser.",
    ),
    "Behavior": (
        "Adjust question pauses, screenshots, outreach and the optional resume builder.",
        "Choose draft outreach to collect recruiter contacts without sending messages.",
    ),
}

_CHOICE_HELP: dict[str, dict[str, tuple[str, str]]] = {
    "browser.engine": {
        "edge": ("Use the installed Microsoft Edge browser.", "Choose this for an Edge profile."),
        "chrome": ("Use the installed Google Chrome browser.", "Choose this for a Chrome profile."),
        "chromium": (
            "Use Playwright's separately installed Chromium browser.",
            "Run Install optional Chromium in Tools before using this engine.",
        ),
    },
    "outreach.mode": {
        "draft": (
            "Collect recruiter outreach drafts without sending messages.",
            "After a confirmed application, review contacts in the end-of-run report.",
        ),
        "send": (
            "Ask for approval before sending available recruiter messages.",
            "Approve a draft interactively; without interactive approval it stays draft-only.",
        ),
    },
}


class RunSettings(QWidget):
    changed = Signal()
    help_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.customize = QCheckBox("Customize settings for this run")
        self.customize.setToolTip(
            tooltip(
                "Enable changed-only overrides for this run; saved YAML stays unchanged.",
                "Change Daily cap, then Start or Copy creates a private preset in logs\\gui-runs.",
            )
        )
        customize_row = QHBoxLayout()
        customize_row.addWidget(self.customize, 1)
        self.help_button = QPushButton("?")
        self.help_button.setFixedWidth(32)
        self.help_button.setAccessibleName("Explain per-run settings")
        self.help_button.setToolTip(
            tooltip(
                "Open the read-only tutorial at Customize this run.",
                "Read how private presets work without starting a command or saving settings.",
            )
        )
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
        searches_label = muted("Enabled saved searches")
        search_layout.addWidget(searches_label)
        self.searches = QListWidget()
        self.searches.setToolTip(
            tooltip(
                "Choose which saved searches participate in discovery for this run.",
                "Uncheck a search to skip it; Apply exact jobs or Search URL can override discovery.",
            )
        )
        searches_label.setToolTip(self.searches.toolTip())
        self.searches.setMaximumHeight(125)
        self.searches.itemChanged.connect(self.changed)
        search_layout.addWidget(self.searches)
        urls_label = muted("Exact job URLs (Apply only, one per line)")
        search_layout.addWidget(urls_label)
        self.job_urls = QPlainTextEdit()
        self.job_urls.setToolTip(
            tooltip(
                "Apply to these exact job URLs instead of crawling saved searches.",
                "Paste one jobs/view URL per line; a Run Search URL overrides this batch.",
            )
        )
        urls_label.setToolTip(self.job_urls.toolTip())
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
        for index in range(self.tabs.count()):
            self.tabs.setTabToolTip(index, tooltip(*_TAB_HELP[self.tabs.tabText(index)]))
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
        field.setToolTip(tooltip(*_FIELD_HELP[key]))
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
            form.labelForField(field).setToolTip(field.toolTip())

    def _number(self, form: QFormLayout, label: str, key: str, low: int, high: int) -> None:
        field = QSpinBox()
        field.setRange(low, high)
        self._add(form, label, key, field)

    def _text(self, form: QFormLayout, label: str, key: str) -> None:
        self._add(form, label, key, QLineEdit())

    def _choice(self, form: QFormLayout, label: str, key: str, choices: list[str]) -> None:
        field = QComboBox()
        field.addItems(choices)
        for index, choice in enumerate(choices):
            field.setItemData(
                index, tooltip(*_CHOICE_HELP[key][choice]), Qt.ItemDataRole.ToolTipRole
            )
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
            item.setToolTip(
                tooltip(
                    "Include this saved search in discovery when checked.",
                    f"Scan visits {entry['url']} when this search is enabled.",
                )
            )
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
