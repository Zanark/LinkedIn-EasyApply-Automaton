"""The Easy Apply desktop window.

Five pages behind a sidebar - Run, Configuration, Answers, Data and Tools -
each of which drives the same ``apply.py`` commands the terminal uses. The
Streamlit dashboard stays a separate read-only analytics surface; this window
simply launches it (as does ``apply.py dashboard``).
"""

from __future__ import annotations

import webbrowser
from dataclasses import replace
from pathlib import Path
from typing import override

import yaml
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from linkedin_easy_apply import __version__
from linkedin_easy_apply.config import AppConfig, ConfigError, load_config
from linkedin_easy_apply.config.loader import parse_config
from linkedin_easy_apply.gui import commands
from linkedin_easy_apply.gui.activity import ResumeDisplay, RunActivity
from linkedin_easy_apply.gui.metrics import RunMetrics
from linkedin_easy_apply.gui.process import CommandRunner, start_detached
from linkedin_easy_apply.gui.settings import write_run_config
from linkedin_easy_apply.gui.settings_panel import RunSettings
from linkedin_easy_apply.gui.theme import DEFAULT_THEME, THEMES, Palette, build_stylesheet, resolve
from linkedin_easy_apply.gui.tutorial import CUSTOMIZE_TOPIC, TutorialDialog
from linkedin_easy_apply.gui.widgets import Card, Console, PathRow, heading, muted, tooltip
from linkedin_easy_apply.runtime import is_frozen, resource_root, workspace_root

__all__ = ["MainWindow", "run"]

_ORG = "LinkedInEasyApplyAutomaton"
_APP = "DesktopGUI"
_DASHBOARD_URL = "http://localhost:8501"

_ACTION_HELP: dict[str, tuple[str, str]] = {
    "scan": (
        "Discover, score and record jobs without filling or submitting applications.",
        "Use Scan to inspect available jobs before trying an Apply dry run.",
    ),
    "apply": (
        "Discover jobs or open an exact-job batch, then attempt eligible applications.",
        "Keep Dry run on to inspect forms without submitting.",
    ),
    "reapply": (
        "Retry eligible failed or aborted jobs; submitted and uncertain attempts stay excluded.",
        "Fix a saved answer, then retry; List retry targets only previews candidates.",
    ),
    "connect": (
        "Process pending free connection invitations, not job applications.",
        "Use Dry run to inspect pending notes before allowing real invitations.",
    ),
}

_LIMIT_HELP: dict[str, tuple[str, str]] = {
    "scan": (
        "Cap discovered jobs; 0 uses jobs.max_per_run from the configuration.",
        "10 scans and scores up to ten jobs without filling forms.",
    ),
    "apply": (
        "Target confirmed submissions; 0 uses jobs.max_per_run from the configuration.",
        "5 aims for five submissions; exhausted jobs or other guards can stop it sooner.",
    ),
    "reapply": (
        "Cap retry candidates; 0 considers all eligible failed or aborted jobs.",
        "3 retries up to three candidates; List retry targets only still lists all.",
    ),
    "connect": (
        "Cap pending invitations; 0 uses outreach.connect_max_per_run from the configuration.",
        "5 processes up to five pending notes, not five application submissions.",
    ),
}

_TOOL_HELP: dict[str, tuple[str, str]] = {
    "login": (
        "Open the configured browser so you can sign in to LinkedIn manually.",
        "Finish signing in in the browser, then use Send Enter to close the login command.",
    ),
    "test-browser": (
        "Briefly open the configured browser to check the saved session.",
        "Leave Optional blank for the LinkedIn feed, or supply another URL.",
    ),
    "stats": (
        "Print statistics from the configured local database.",
        "Review recorded application totals in the Run log without opening a browser.",
    ),
    "init": (
        "Scaffold example configuration and runtime folders in the workspace.",
        "Use for a new workspace; this tool does not force-overwrite existing configs.",
    ),
    "version": (
        "Print the application's installed version.",
        "Use this to identify the source version without opening a browser.",
    ),
    "install-browser": (
        "Download Playwright's optional Chromium browser.",
        "Use this for browser.engine=chromium; installed Edge or Chrome do not need it.",
    ),
    "resume-test": (
        "Preview the static resume choice for a job title without applying.",
        "Enter Senior Backend Engineer; Optional adds a job description for matching.",
    ),
    "test-form": (
        "Show how the parser and saved answers recognise a form question.",
        "Enter Years of Python experience? to inspect its category and resolved answer.",
    ),
}


def project_root() -> Path:
    return workspace_root()


class MainWindow(QMainWindow):
    def __init__(
        self, config_path: str, theme: str | None = None, *, workspace: Path | None = None
    ) -> None:
        super().__init__()
        self._settings = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, _ORG, _APP)
        stored = str(self._settings.value("theme", DEFAULT_THEME))
        self._palette: Palette = resolve(theme or stored)
        self._root = workspace or project_root()
        self._config_path = config_path
        self._runner = CommandRunner(self._root, self)
        self._dashboard_started = False
        self._loaded_config: AppConfig | None = None

        self.setWindowTitle(f"Easy Apply Automaton {__version__}")
        self.setWindowIcon(application_icon())
        self.resize(1320, 860)
        self.setMinimumSize(940, 640)
        self._build_ui()
        self._connect_runner()
        self._apply_theme(self._palette)
        self._load_config_text()
        self._load_answers_text()
        QTimer.singleShot(0, self._refresh_stats)

    # -- construction --------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._pages = QStackedWidget()
        layout.addWidget(self._build_sidebar())
        layout.addWidget(self._pages, 1)
        self.setCentralWidget(central)

        self._pages.addWidget(self._build_run_page())
        self._pages.addWidget(self._build_config_page())
        self._pages.addWidget(self._build_answers_page())
        self._pages.addWidget(self._build_data_page())
        self._pages.addWidget(self._build_tools_page())
        self._nav_buttons[0].setChecked(True)

        self._build_toolbar()
        self.statusBar().showMessage("Ready")

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(180)
        column = QVBoxLayout(sidebar)
        column.setContentsMargins(12, 16, 12, 16)
        column.setSpacing(6)

        title = QLabel("Easy Apply")
        title.setProperty("role", "heading")
        column.addWidget(title)
        column.addWidget(muted(f"AUTOMATON  /  {__version__}"))
        column.addSpacing(14)

        self._nav_buttons: list[QPushButton] = []
        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, (label, purpose, example) in enumerate(
            [
                (
                    "Run",
                    "Choose and monitor an automation command.",
                    "Start with a Scan or Apply dry run.",
                ),
                (
                    "Configuration",
                    "Edit and validate the selected configuration YAML.",
                    "Save a changed daily cap for future runs.",
                ),
                (
                    "Answers",
                    "Edit the saved answers used by the form filler.",
                    "Save an answer before retrying a failed form.",
                ),
                (
                    "Data",
                    "Inspect database totals, exports and optional analytics.",
                    "Export recorded applications as CSV.",
                ),
                (
                    "Tools",
                    "Run one-shot setup and inspection commands.",
                    "Verify a browser session or preview a resume choice.",
                ),
            ]
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setToolTip(tooltip(purpose, example))
            button.clicked.connect(lambda _checked, i=index: self._pages.setCurrentIndex(i))
            group.addButton(button)
            column.addWidget(button)
            self._nav_buttons.append(button)

        column.addStretch(1)
        column.addWidget(muted("Your browser.\nYour answers.\nOne automation engine."))
        column.addSpacing(12)
        self._theme_button = QPushButton()
        self._theme_button.clicked.connect(self._toggle_theme)
        column.addWidget(self._theme_button)
        return sidebar

    def _build_toolbar(self) -> None:
        bar = self.addToolBar("Main")
        bar.setMovable(False)

        self._config_field = QLineEdit(self._config_path)
        self._config_field.setToolTip(
            tooltip(
                "Select the configuration YAML; relative paths use this workspace.",
                "Change this path and finish editing to load another setup.",
            )
        )
        # Bounded so a long path cannot stretch the whole window.
        self._config_field.setMinimumWidth(220)
        self._config_field.setMaximumWidth(460)
        self._config_field.editingFinished.connect(self._on_config_path_changed)
        browse = QPushButton("Browse…")
        browse.setToolTip(
            tooltip(
                "Choose a configuration file in a native file picker.",
                "Select another config.yaml to load its configuration, answers and data snapshot.",
            )
        )
        browse.clicked.connect(self._browse_config)

        config_label = QLabel("Config ")
        config_label.setToolTip(self._config_field.toolTip())
        bar.addWidget(config_label)
        bar.addWidget(self._config_field)
        bar.addWidget(browse)

        self._tutorial_action = QAction("Tutorial", self)
        self._tutorial_action.setShortcut(QKeySequence.StandardKey.HelpContents)
        self._tutorial_action.setToolTip(
            tooltip(
                "Open the read-only guided tutorial; F1 does the same.",
                "Read about run options without starting a command or saving settings.",
            )
        )
        self._tutorial_action.triggered.connect(self._show_tutorial)
        bar.addAction(self._tutorial_action)

        dashboard_action = QAction("Open dashboard", self)
        dashboard_action.setToolTip(self._dashboard_help())
        dashboard_action.setShortcut(QKeySequence("Ctrl+D"))
        dashboard_action.triggered.connect(self._open_dashboard)
        bar.addAction(dashboard_action)
        if is_frozen():
            dashboard_action.setEnabled(False)

        quit_action = QAction("Quit", self)
        quit_action.setToolTip(
            tooltip(
                "Close the desktop window, asking first if its CLI command is running.",
                "A separately launched dashboard can keep running after the window closes.",
            )
        )
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

    @override
    def createPopupMenu(self) -> None:
        """Do not offer Qt's hide action for the essential top toolbar."""
        return None

    # -- pages ---------------------------------------------------------------
    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(20, 18, 20, 16)
        column.setSpacing(12)
        column.addWidget(heading(title))
        column.addWidget(muted(subtitle))
        return page, column

    def _build_run_page(self) -> QWidget:
        page, column = self._page(
            "Run workspace",
            "Set up a run on the left. Follow every decision and answer prompts on the right.",
        )
        self._run_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._run_splitter.setChildrenCollapsible(False)
        setup_scroll = QScrollArea()
        setup_scroll.setWidgetResizable(True)
        setup_scroll.setMinimumWidth(330)
        setup_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        setup = QWidget()
        setup_layout = QVBoxLayout(setup)
        setup_layout.setContentsMargins(0, 0, 8, 0)
        setup_layout.setSpacing(12)

        controls = Card("1  Choose an action")
        self._action_box = QComboBox()
        for label, action in commands.RUN_ACTIONS.items():
            self._action_box.addItem(label)
            self._action_box.setItemData(
                self._action_box.count() - 1,
                tooltip(*_ACTION_HELP[action]),
                Qt.ItemDataRole.ToolTipRole,
            )
        self._action_box.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self._action_box.currentTextChanged.connect(self._on_action_changed)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 100000)
        self._limit_spin.setSpecialValueText("Command default")
        self._url_field = QLineEdit()
        self._url_field.setToolTip(
            tooltip(
                "Use a search URL for Scan or Apply instead of saved searches or an exact-job batch.",
                "Paste a filtered LinkedIn jobs/search URL; Reapply and Connect do not use it.",
            )
        )
        self._url_field.setPlaceholderText("Optional LinkedIn search URL")
        self._connect_run = QSpinBox()
        self._connect_run.setRange(0, 2147483647)
        self._connect_run.setSpecialValueText("All pending runs")
        self._connect_run.setToolTip(
            tooltip(
                "Restrict Connect to notes drafted by one run; 0 includes all pending runs.",
                "42 processes pending notes from run 42 only, not every stored draft.",
            )
        )
        self._list_only = QCheckBox("List retry targets only (no browser)")
        self._list_only.setToolTip(
            tooltip(
                "List all eligible retry candidates and exit without opening a browser.",
                "Review failed jobs first; this list ignores the Run target cap.",
            )
        )

        form = QFormLayout()
        form.setSpacing(10)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Action", self._action_box)
        form.addRow("Run target", self._limit_spin)
        form.addRow("Search URL", self._url_field)
        form.addRow("Draft run ID", self._connect_run)
        self._action_form = form
        controls.body().addLayout(form)
        controls.add(self._list_only)
        self._action_hint = muted("")
        controls.add(self._action_hint)
        setup_layout.addWidget(controls)

        safety = Card("2  Review run behavior")
        self._dry_run = QCheckBox("Dry run - never submit or send")
        self._dry_run.setToolTip(
            tooltip(
                "Inspect or fill without submitting applications or sending invitations.",
                "Apply stops before Submit; Scan never fills forms regardless of this control.",
            )
        )
        self._dry_run.setChecked(True)
        self._ignore_score = QCheckBox("Ignore the minimum score")
        self._ignore_score.setToolTip(
            tooltip(
                "Bypass the score threshold for Apply or Reapply; other guards still apply.",
                "A low-scoring job can be attempted, but submitted-job deduplication remains active.",
            )
        )
        self._confirm_submit = QCheckBox("Confirm before every application")
        self._confirm_submit.setToolTip(
            tooltip(
                "Ask before each real submission; this keeps interactive CLI input enabled.",
                "Send Enter accepts the displayed Yes default and submits when Dry run is off.",
            )
        )
        self._interactive = QCheckBox("Answer unknown questions in this window")
        self._interactive.setChecked(True)
        self._interactive.setToolTip(
            tooltip(
                "Allow unknown-answer input when Pause on unknown questions is also enabled.",
                "Off adds --yes, unless Confirm before every application keeps prompting active.",
            )
        )
        self._outreach = QCheckBox("Hiring-team outreach (mixed = config)")
        self._outreach.setTristate(True)
        self._outreach.setCheckState(Qt.CheckState.PartiallyChecked)
        self._outreach.setToolTip(
            tooltip(
                "Override hiring-team outreach: mixed uses config, checked enables, empty disables.",
                "Check this with Outreach=draft to collect contacts after confirmed applications.",
            )
        )
        self._verbose = QCheckBox("Verbose (DEBUG logging)")
        self._verbose.setToolTip(
            tooltip(
                "Request DEBUG-level decision details for the command.",
                "Enable to inspect matching decisions; logs may contain sensitive form values.",
            )
        )
        for box in (
            self._dry_run,
            self._ignore_score,
            self._confirm_submit,
            self._interactive,
            self._outreach,
            self._verbose,
        ):
            safety.add(box)
        safety.add(muted("Live Apply, Reapply and Connect always ask before starting."))
        setup_layout.addWidget(safety)
        advanced = Card("3  Tune this run")
        self._run_settings = RunSettings()
        self._run_settings.help_requested.connect(
            lambda: self._show_tutorial(topic=CUSTOMIZE_TOPIC)
        )
        advanced.add(self._run_settings)
        setup_layout.addWidget(advanced)
        setup_layout.addStretch(1)
        setup_scroll.setWidget(setup)
        self._run_splitter.addWidget(setup_scroll)

        execution = QWidget()
        execution.setMinimumWidth(300)
        execution_layout = QVBoxLayout(execution)
        execution_layout.setContentsMargins(8, 0, 0, 0)
        execution_layout.setSpacing(6)
        state_row = QHBoxLayout()
        self._run_state = QLabel("READY")
        self._run_state.setToolTip(
            tooltip(
                "Show the child command's process state, not application confirmation.",
                "DONE means exit code zero; SUBMITTED logs confirm individual applications.",
            )
        )
        self._run_state.setProperty("role", "badge")
        state_row.addWidget(self._run_state)
        self._metrics = RunMetrics()
        state_row.addWidget(self._metrics.caption, 1)
        self._log_details = QCheckBox("Details")
        self._log_details.setToolTip(
            tooltip(
                "Switch compact log labels to original prefixes without changing file logs.",
                "Enable to see dates, modules, functions and line numbers, then turn off to compact.",
            )
        )
        state_row.addWidget(self._log_details)
        clear_button = QPushButton("Clear log")
        clear_button.setToolTip(
            tooltip(
                "Clear only the visible console and its in-window history.",
                "Start a fresh view without deleting log files or database records.",
            )
        )
        state_row.addWidget(clear_button)
        execution_layout.addLayout(state_row)
        self._activity = RunActivity(self._palette)
        live_status = QHBoxLayout()
        live_status.setContentsMargins(0, 0, 0, 0)
        live_status.setSpacing(8)
        live_status.addWidget(self._activity, 0, Qt.AlignmentFlag.AlignTop)
        live_status.addWidget(self._metrics, 1)
        execution_layout.addLayout(live_status)
        self._command_preview = QPlainTextEdit()
        self._command_preview.setReadOnly(True)
        self._command_preview.setToolTip(
            tooltip(
                "Read-only preview of the selected CLI command; viewing it creates no preset.",
                "A private-preset placeholder becomes a real path only on Start or Copy command.",
            )
        )
        self._command_preview.setObjectName("CommandPreview")
        self._command_preview.setMaximumHeight(32)
        execution_layout.addWidget(self._command_preview)
        button_panel = QWidget()
        buttons = QHBoxLayout(button_panel)
        buttons.setContentsMargins(0, 0, 0, 0)
        self._start_button = QPushButton("Start scan")
        self._start_button.setToolTip(
            tooltip(
                "Start the selected action with these options; save or reload edited YAML first.",
                "Live Apply, Reapply and Connect require a separate start confirmation.",
            )
        )
        self._start_button.setProperty("role", "primary")
        self._start_button.clicked.connect(self._start_run)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setToolTip(
            tooltip(
                "Terminate the CLI process; cleanup and browser closure are not guaranteed.",
                "Use for a stuck command; this is not the CLI's graceful Ctrl+C shutdown.",
            )
        )
        self._stop_button.setProperty("role", "danger")
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self._runner.stop)
        copy_button = QPushButton("Copy command")
        copy_button.setToolTip(
            tooltip(
                "Copy an executable CLI command; changed run settings create a private preset.",
                "Change Daily cap, then Copy to use that preset in a terminal; saved YAML stays intact.",
            )
        )
        copy_button.clicked.connect(self._copy_command)
        buttons.addWidget(self._start_button)
        buttons.addWidget(self._stop_button)
        buttons.addWidget(copy_button)
        self._resume_display = ResumeDisplay()
        command_controls = QFormLayout()
        command_controls.setContentsMargins(0, 0, 0, 0)
        command_controls.setSpacing(6)
        command_controls.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        command_controls.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        command_controls.addRow(button_panel, self._resume_display)
        execution_layout.addLayout(command_controls)

        self._console = Console(self._palette)
        self._console.setMinimumHeight(82)
        self._log_details.toggled.connect(self._console.set_details)
        clear_button.clicked.connect(self._console.clear)
        execution_layout.addWidget(self._console, 1)
        execution_layout.addWidget(
            muted("Answer below. Enter uses the prompt's displayed default.")
        )
        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setToolTip(
            tooltip(
                "Send text to the running command's current prompt, not to the browser directly.",
                "Type an answer or n, then Send; it is disabled when no command is running.",
            )
        )
        self._input.setPlaceholderText("Answer the current CLI prompt...")
        self._input.returnPressed.connect(self._send_input)
        self._send_button = QPushButton("Send")
        self._send_button.setToolTip(
            tooltip(
                "Send the prompt input followed by Enter to the running command.",
                "Type n and Send to decline a CLI approval prompt.",
            )
        )
        self._send_button.clicked.connect(self._send_input)
        self._enter_button = QPushButton("Send Enter")
        self._enter_button.setToolTip(
            tooltip(
                "Send a blank Enter to accept the current prompt's displayed default.",
                "At a submit confirmation the default is Yes, so Enter can submit an application.",
            )
        )
        self._enter_button.clicked.connect(lambda: self._send_input(empty=True))
        input_row.addWidget(self._input, 1)
        input_row.addWidget(self._send_button)
        input_row.addWidget(self._enter_button)
        execution_layout.addLayout(input_row)
        for field in (self._input, self._send_button, self._enter_button):
            field.setEnabled(False)
        self._run_splitter.addWidget(execution)
        self._run_splitter.setSizes([330, 750])
        self._run_splitter.setStretchFactor(0, 0)
        self._run_splitter.setStretchFactor(1, 1)
        column.addWidget(self._run_splitter, 1)
        self._run_settings.changed.connect(self._update_command_preview)
        for box in (
            self._dry_run,
            self._ignore_score,
            self._confirm_submit,
            self._interactive,
            self._outreach,
            self._verbose,
            self._list_only,
        ):
            box.stateChanged.connect(self._update_command_preview)
        self._limit_spin.valueChanged.connect(self._update_command_preview)
        self._connect_run.valueChanged.connect(self._update_command_preview)
        self._url_field.textChanged.connect(self._update_command_preview)
        self._on_action_changed(self._action_box.currentText())
        return page

    def _build_config_page(self) -> QWidget:
        page, column = self._page(
            "Configuration",
            "Edit configs/config.yaml. Validate parses the file through the same "
            "loader the CLI uses, so a mistake is caught here rather than mid-run.",
        )
        self._config_editor = QPlainTextEdit()
        self._config_editor.setToolTip(
            tooltip(
                "Edit the selected configuration YAML; changes are not saved automatically.",
                "Adjust jobs.max_daily, then Validate and Save before starting a command.",
            )
        )
        self._config_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        column.addWidget(self._config_editor, 1)

        row = QHBoxLayout()
        validate = QPushButton("Validate")
        validate.setToolTip(
            tooltip(
                "Check this editor's YAML syntax and configuration model without saving.",
                "Catch an invalid daily cap before writing the configuration file.",
            )
        )
        validate.clicked.connect(lambda: self._validate_yaml(self._config_editor, strict=True))
        save = QPushButton("Save")
        save.setToolTip(
            tooltip(
                "Validate and write this configuration editor to the selected YAML file.",
                "Save an edited daily cap to use it in later commands.",
            )
        )
        save.setProperty("role", "primary")
        save.clicked.connect(self._save_config_text)
        reload_button = QPushButton("Reload")
        reload_button.setToolTip(
            tooltip(
                "Replace this editor and per-run settings with the configuration on disk.",
                "Discard an unsaved experiment and restore the saved YAML values.",
            )
        )
        reload_button.clicked.connect(self._load_config_text)
        row.addWidget(validate)
        row.addWidget(save)
        row.addWidget(reload_button)
        row.addStretch(1)
        self._config_status = QLabel("")
        row.addWidget(self._config_status)
        column.addLayout(row)
        return page

    def _build_answers_page(self) -> QWidget:
        page, column = self._page(
            "Answers",
            "Edit the answers file the form filler draws on. Validation here checks "
            "YAML syntax only; sync-answers on the Tools page checks the content.",
        )
        self._answers_editor = QPlainTextEdit()
        self._answers_editor.setToolTip(
            tooltip(
                "Edit the answers YAML used by the form filler; changes stay unsaved until Save.",
                "Correct a saved answer, save it, then retry the affected application.",
            )
        )
        self._answers_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        column.addWidget(self._answers_editor, 1)

        row = QHBoxLayout()
        validate = QPushButton("Validate")
        validate.setToolTip(
            tooltip(
                "Check answers YAML syntax only; this does not verify answer content.",
                "Catch malformed indentation; use sync-answers for its separate content checks.",
            )
        )
        validate.clicked.connect(lambda: self._validate_yaml(self._answers_editor, strict=False))
        save = QPushButton("Save")
        save.setToolTip(
            tooltip(
                "Write syntactically valid answers YAML from this editor to its configured file.",
                "Save a corrected answer before starting a retry.",
            )
        )
        save.setProperty("role", "primary")
        save.clicked.connect(self._save_answers_text)
        reload_button = QPushButton("Reload")
        reload_button.setToolTip(
            tooltip(
                "Replace unsaved answers in this editor with the answers file on disk.",
                "Discard an accidental edit and restore the last saved answer values.",
            )
        )
        reload_button.clicked.connect(self._load_answers_text)
        sync = QPushButton("Run sync-answers")
        sync.setToolTip(
            tooltip(
                "Run the sync-answers preview against saved files and show its output in Run.",
                "Save edits first; this button does not add --apply to write synchronization changes.",
            )
        )
        sync.clicked.connect(
            lambda: self._run(commands.sync_answers_args(self._config_path), page_index=0)
        )
        row.addWidget(validate)
        row.addWidget(save)
        row.addWidget(reload_button)
        row.addWidget(sync)
        row.addStretch(1)
        self._answers_status = QLabel("")
        row.addWidget(self._answers_status)
        column.addLayout(row)
        return page

    def _build_data_page(self) -> QWidget:
        page, column = self._page(
            "Data",
            "Database snapshot, exports, and the Streamlit dashboard "
            "(the same one apply.py dashboard opens).",
        )

        self._stats_table = QTableWidget(0, 2)
        self._stats_table.setToolTip(
            tooltip(
                "Read a snapshot of the configured local database; cells are not editable.",
                "Use Refresh to update totals after a run.",
            )
        )
        self._stats_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._stats_table.horizontalHeader().setStretchLastSection(True)
        self._stats_table.verticalHeader().setVisible(False)
        self._stats_table.setAlternatingRowColors(True)
        self._stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        stats_card = Card("Database")
        stats_card.add(self._stats_table)
        refresh = QPushButton("Refresh")
        refresh.setToolTip(
            tooltip(
                "Reload the configured database snapshot into this page.",
                "Update totals after a completed command without opening a browser.",
            )
        )
        refresh.clicked.connect(self._refresh_stats)
        stats_card.add(refresh)
        column.addWidget(stats_card, 1)

        dashboard_card = Card("Dashboard")
        dashboard_card.add(
            muted(
                "Analytics live in the Streamlit dashboard. It starts as its own process "
                "and keeps running if this window closes."
            )
        )
        open_dashboard = QPushButton("Open dashboard")
        open_dashboard.setToolTip(self._dashboard_help())
        open_dashboard.setProperty("role", "primary")
        open_dashboard.clicked.connect(self._open_dashboard)
        if is_frozen():
            open_dashboard.setEnabled(False)
            dashboard_card.add(
                muted(
                    "The portable desktop build excludes Streamlit to keep the download smaller. "
                    "Use the database snapshot/export here, or install the dashboard source extra."
                )
            )
        browser = QPushButton("Open in browser")
        browser.setToolTip(
            tooltip(
                "Open the local dashboard URL in your default web browser without starting its server.",
                "Use after Open dashboard; otherwise localhost:8501 may not be available.",
            )
        )
        browser.clicked.connect(lambda: webbrowser.open(_DASHBOARD_URL))
        dashboard_card.add_row(open_dashboard, browser)
        column.addWidget(dashboard_card)

        export_card = Card("Export")
        self._export_format = QComboBox()
        self._export_format.setToolTip(
            tooltip(
                "Choose the applications export file format.",
                "csv opens as text or in a spreadsheet; xlsx creates an Excel workbook.",
            )
        )
        self._export_format.addItems(["csv", "xlsx"])
        for index, (purpose, example) in enumerate(
            [
                (
                    "Export application records as comma-separated text.",
                    "Choose csv for a plain-text spreadsheet import.",
                ),
                (
                    "Export application records as an Excel workbook.",
                    "Choose xlsx for an .xlsx file with spreadsheet columns.",
                ),
            ]
        ):
            self._export_format.setItemData(
                index, tooltip(purpose, example), Qt.ItemDataRole.ToolTipRole
            )
        export_button = QPushButton("Export applications…")
        export_button.setToolTip(
            tooltip(
                "Choose a destination and export recorded applications in the selected format.",
                "Save a private CSV report; exported records can contain personal data.",
            )
        )
        export_button.clicked.connect(self._export)
        format_label = QLabel("Format")
        format_label.setToolTip(self._export_format.toolTip())
        export_card.add_row(format_label, self._export_format, export_button)
        column.addWidget(export_card)
        return page

    def _build_tools_page(self) -> QWidget:
        page, column = self._page(
            "Tools",
            "One-shot commands. Output goes to the Run page log.",
        )
        card = Card("Command")
        self._tool_box = QComboBox()
        self._tool_box.setToolTip(
            tooltip(
                "Choose a one-shot command; accepted inputs change with the selected tool.",
                "Choose Preview resume choice to inspect static selection without applying.",
            )
        )
        self._tool_box.addItems(list(commands.TOOLS))
        for index, spec in enumerate(commands.TOOLS.values()):
            self._tool_box.setItemData(
                index, tooltip(*_TOOL_HELP[spec.command]), Qt.ItemDataRole.ToolTipRole
            )
        self._tool_box.currentTextChanged.connect(self._on_tool_changed)
        self._tool_value = QLineEdit()
        self._tool_option = QLineEdit()

        form = QFormLayout()
        form.addRow("Tool", self._tool_box)
        form.addRow("Value", self._tool_value)
        form.addRow("Optional", self._tool_option)
        self._tool_form = form
        form.labelForField(self._tool_box).setToolTip(self._tool_box.toolTip())
        card.body().addLayout(form)

        run_button = QPushButton("Run")
        run_button.setToolTip(
            tooltip(
                "Execute the selected tool with its accepted inputs; output appears on Run.",
                "Sign in opens a browser; Install optional Chromium downloads browser files.",
            )
        )
        run_button.setProperty("role", "primary")
        run_button.clicked.connect(self._run_tool)
        card.add(run_button)
        column.addWidget(card)

        paths = Card("Locations")
        for label, relative in (
            ("Workspace", "."),
            ("Logs", "logs"),
            ("Screenshots", "screenshots"),
            ("Generated résumés", "generated/resume"),
            ("Outreach reports", "generated/outreach"),
            ("Search diagnostics", "logs/diagnostics"),
        ):
            paths.add(PathRow(label, self._root / relative, self._open_path))
        column.addWidget(paths)
        column.addStretch(1)
        self._on_tool_changed(self._tool_box.currentText())
        return page

    @staticmethod
    def _dashboard_help() -> str:
        if is_frozen():
            return tooltip(
                "The portable build does not bundle the optional Streamlit dashboard.",
                "Use Data totals/exports here, or launch analytics from a source installation.",
            )
        return tooltip(
            "Start the optional Streamlit analytics server in a separate process.",
            "Install the dashboard source extra first; analytics opens at localhost:8501.",
        )

    # -- theme ---------------------------------------------------------------
    def _apply_theme(self, palette: Palette) -> None:
        self._palette = palette
        application = QApplication.instance()
        if isinstance(application, QApplication):
            application.setStyleSheet(build_stylesheet(palette))
        self._console.apply_palette(palette)
        self._activity.apply_palette(palette)
        other = self._other_theme().label
        self._theme_button.setText("Light mode" if palette.is_dark else "Dark mode")
        self._theme_button.setIcon(theme_icon(palette))
        self._theme_button.setToolTip(
            tooltip(
                f"Switch the desktop to {other}; the theme choice is saved locally.",
                "Change the appearance without changing run options or log history.",
            )
        )
        self._settings.setValue("theme", palette.key)

    def _other_theme(self) -> Palette:
        keys = list(THEMES)
        index = (keys.index(self._palette.key) + 1) % len(keys)
        return THEMES[keys[index]]

    def _toggle_theme(self) -> None:
        self._apply_theme(self._other_theme())

    # -- run page behaviour --------------------------------------------------
    def _current_options(self) -> commands.RunOptions:
        action = commands.RUN_ACTIONS[self._action_box.currentText()]
        outreach_state = self._outreach.checkState()
        return commands.RunOptions(
            action=action,
            config=self._config_path,
            limit=self._limit_spin.value() or None,
            url=self._url_field.text().strip() or None,
            dry_run=action != "scan" and self._dry_run.isChecked(),
            ignore_score=self._ignore_score.isChecked(),
            confirm_submit=self._confirm_submit.isChecked(),
            message_hiring_team=(
                None
                if outreach_state == Qt.CheckState.PartiallyChecked
                else outreach_state == Qt.CheckState.Checked
            ),
            assume_yes=not self._interactive.isChecked(),
            verbose=self._verbose.isChecked(),
            connect_run_id=self._connect_run.value() or None,
            list_only=self._list_only.isChecked(),
        )

    def _on_action_changed(self, label: str) -> None:
        action = commands.RUN_ACTIONS.get(label, "scan")
        self._action_box.setToolTip(tooltip(*_ACTION_HELP[action]))
        self._limit_spin.setToolTip(tooltip(*_LIMIT_HELP[action]))
        for field in (self._action_box, self._limit_spin, self._url_field, self._connect_run):
            self._action_form.labelForField(field).setToolTip(field.toolTip())
        self._url_field.setEnabled(action in {"scan", "apply"})
        self._ignore_score.setEnabled(action in {"apply", "reapply"})
        self._outreach.setEnabled(action in {"apply", "reapply"})
        self._confirm_submit.setEnabled(action in {"apply", "reapply"})
        self._interactive.setEnabled(action != "scan")
        self._dry_run.setEnabled(action != "scan")
        self._connect_run.setVisible(action == "connect")
        self._action_form.labelForField(self._connect_run).setVisible(action == "connect")
        self._list_only.setVisible(action == "reapply")
        self._action_hint.setText(
            {
                "scan": "Discover and score jobs. Never fills or submits an application.",
                "apply": "Target confirmed submissions; skips and failures do not count toward the target.",
                "reapply": "Retry failed or aborted jobs. Already submitted and uncertain submits stay excluded.",
                "connect": "Send pending free connection invitations. This does not apply to jobs.",
            }[action]
        )
        self._update_command_preview()

    def _update_command_preview(self) -> None:
        if not hasattr(self, "_command_preview"):
            return
        options = self._current_options()
        if self._run_settings.overrides():
            options = replace(options, config="<private run preset created on Start or Copy>")
        elif (
            self._loaded_config is not None
            and options.action in {"apply", "reapply"}
            and options.dry_run != self._loaded_config.run.dry_run
        ):
            options = replace(options, config="<private run preset created on Start or Copy>")
        argv = commands.full_argv(commands.run_args(options))
        self._command_preview.setPlainText(commands.describe(argv))
        labels = {
            "scan": "scan",
            "apply": "applications",
            "reapply": "retry",
            "connect": "connections",
        }
        self._start_button.setText(f"Start {labels[options.action]}")

    def _prepared_options(self) -> commands.RunOptions:
        if (
            self._config_editor.document().isModified()
            or self._answers_editor.document().isModified()
        ):
            raise ConfigError(
                "Save or reload the edited Configuration/Answers before starting a run."
            )
        options = self._current_options()
        config = load_config(self._config_file())
        overrides = self._run_settings.overrides()
        if options.action in {"apply", "reapply"} and config.run.dry_run != options.dry_run:
            overrides["run.dry_run"] = options.dry_run
        if overrides:
            path = write_run_config(self._config_file(), overrides, self._root)
            options = replace(options, config=str(path))
            self._console.note(f"Private run settings saved to {path}", "muted", label="CONFIG")
        return options

    def _start_run(self) -> None:
        if self._runner.busy:
            return
        try:
            options = self._prepared_options()
        except (ConfigError, OSError) as exc:
            QMessageBox.warning(self, "Run not started", str(exc))
            return
        live = options.action != "scan" and not options.dry_run
        if options.action == "reapply" and options.list_only:
            live = False
        if live:
            confirmation = QMessageBox.question(
                self,
                "Start a live LinkedIn action?",
                f"Action: {options.action}\n\n"
                "This can submit real applications or send real invitations/messages "
                "according to the selected settings.\n"
                "Review your answers, resume, limits and outreach settings first.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return
        self._run(
            commands.run_args(options),
            metrics_action=None if options.list_only else options.action,
        )

    def _copy_command(self) -> None:
        try:
            options = self._prepared_options()
        except (ConfigError, OSError) as exc:
            QMessageBox.warning(self, "Command not copied", str(exc))
            return
        argv = commands.full_argv(commands.run_args(options))
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(commands.describe(argv))
        self.statusBar().showMessage("Command copied to the clipboard", 4000)

    def _send_input(self, _checked: bool = False, *, empty: bool = False) -> None:
        text = "" if empty else self._input.text()
        if not self._runner.send_input(text):
            self._console.note("No running command accepted this input.", "warning", label="INPUT")
            return
        self._console.note("Answer sent." if text else "Enter sent.", "accent", label="INPUT")
        self._input.clear()

    def _run_tool(self) -> None:
        tool = self._tool_box.currentText()
        try:
            args = commands.tool_args(
                tool,
                self._config_path,
                self._tool_value.text(),
                option_value=self._tool_option.text(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Missing value", str(exc))
            return
        self._run(args)

    def _on_tool_changed(self, label: str) -> None:
        spec = commands.TOOLS.get(label)
        needs_value = bool(spec and spec.needs_value)
        self._tool_value.setEnabled(needs_value)
        self._tool_value.setPlaceholderText(spec.hint if spec else "")
        if not needs_value:
            self._tool_value.clear()
        self._tool_option.setEnabled(bool(spec and spec.optional_flag))
        self._tool_option.setPlaceholderText(spec.optional_hint if spec else "")
        self._tool_option.clear()
        command = spec.command if spec else ""
        value_help = {
            "resume-test": (
                "Enter the job title used to preview static resume matching.",
                "Senior Backend Engineer checks the saved mappings without applying.",
            ),
            "test-form": (
                "Enter a form question to inspect recognition and saved-answer resolution.",
                "Years of Python experience? shows how that question is interpreted.",
            ),
        }.get(
            command,
            (
                "This tool does not use a required Value input.",
                "Choose Recognise a question to enter a form question here.",
            ),
        )
        option_help = {
            "test-browser": (
                "Optionally choose the URL opened by the browser-session check.",
                "Leave blank for the LinkedIn feed, or enter https://www.linkedin.com/jobs/.",
            ),
            "resume-test": (
                "Optionally include a job description in the static resume match.",
                "Python and SQL backend work adds context beyond the job title.",
            ),
        }.get(
            command,
            (
                "This tool does not use an Optional input.",
                "Choose Preview resume choice to supply a job description here.",
            ),
        )
        self._tool_value.setToolTip(tooltip(*value_help))
        self._tool_option.setToolTip(tooltip(*option_help))
        for field in (self._tool_value, self._tool_option):
            self._tool_form.labelForField(field).setToolTip(field.toolTip())

    def _run(
        self, args: list[str], page_index: int = 0, *, metrics_action: str | None = None
    ) -> None:
        if self._runner.busy:
            QMessageBox.information(
                self, "Already running", "Stop the current command before starting another."
            )
            return
        self._pages.setCurrentIndex(page_index)
        self._nav_buttons[page_index].setChecked(True)
        argv = commands.full_argv(args)
        self._metrics.prepare(metrics_action)
        self._activity.set_state("starting")
        self._console.note(f"$ {commands.describe(argv)}", "accent", label="COMMAND")
        if not self._runner.start(argv):
            self._activity.set_state("error")
            self._console.note("Could not start the command.", "error", label="ERROR")

    def _connect_runner(self) -> None:
        self._runner.output.connect(self._console.append_text)
        self._runner.progress.connect(self._metrics.update_progress)
        self._runner.activity.connect(self._activity.update_activity)
        self._runner.activity.connect(self._resume_display.update_activity)
        self._runner.progress_error.connect(self._metrics.warn)
        self._runner.progress_error.connect(self._activity.warn)
        self._runner.progress_error.connect(
            lambda message: self._console.note(message, "warning", label="STATUS")
        )
        self._runner.finished.connect(self._on_finished)
        self._runner.started_command.connect(lambda _cmd: self._set_running(True))  # noqa: ARG005
        self._runner.started_command.connect(lambda _cmd: self._metrics.begin())  # noqa: ARG005
        self._runner.started_command.connect(
            lambda _cmd: self._activity.set_state("running")  # noqa: ARG005
        )

    def _set_running(self, running: bool) -> None:
        self._start_button.setEnabled(not running)
        self._stop_button.setEnabled(running)
        self._tutorial_action.setEnabled(not running)
        self._run_settings.help_button.setEnabled(not running)
        self.statusBar().showMessage("Running…" if running else "Ready")
        self._run_state.setText("RUNNING" if running else "READY")
        for field in (self._input, self._send_button, self._enter_button):
            field.setEnabled(running)

    def _on_finished(self, exit_code: int, message: str) -> None:
        self._console.flush()
        if message == "Stopped.":
            self._activity.set_state("stopped")
            self._metrics.finish("Stopped")
            self._console.note(message, "warning", label="STOPPED")
        elif exit_code == 0:
            self._activity.set_state("finished")
            self._metrics.finish("Finished")
            self._console.note(message, "document", label="DONE")
        else:
            self._activity.set_state("error")
            self._metrics.finish("Error")
            self._console.note(message, "error", label="ERROR")
        self._set_running(False)
        self.statusBar().showMessage(message, 8000)
        self._refresh_stats()

    def _show_tutorial(self, _checked: bool = False, *, topic: str | None = None) -> None:
        if self._runner.busy:
            QMessageBox.information(
                self, "Command running", "Finish the current command before opening the tutorial."
            )
            return
        try:
            dialog = TutorialDialog(self, start_topic=topic)
        except (OSError, UnicodeError, ValueError) as exc:
            QMessageBox.warning(self, "Tutorial unavailable", str(exc))
            return
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    # -- configuration -------------------------------------------------------
    def _on_config_path_changed(self) -> None:
        self._config_path = self._config_field.text().strip() or "configs/config.yaml"
        self._load_config_text()
        self._load_answers_text()
        self._update_command_preview()
        self._refresh_stats()

    def _browse_config(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(
            self, "Select config.yaml", str(self._root / "configs"), "YAML (*.yaml *.yml)"
        )
        if chosen:
            try:
                relative = str(Path(chosen).relative_to(self._root))
            except ValueError:
                relative = chosen
            self._config_field.setText(relative)
            self._on_config_path_changed()

    def _config_file(self) -> Path:
        path = Path(self._config_path)
        return path if path.is_absolute() else self._root / path

    def _answers_file(self) -> Path:
        """Resolve the same expanded answers path as the CLI."""
        configured = (
            self._loaded_config.answers.file
            if self._loaded_config is not None
            else Path("configs") / "answers.yaml"
        )
        path = Path(configured)
        return path if path.is_absolute() else self._root / path

    def _load_text(self, path: Path, editor: QPlainTextEdit, status: QLabel) -> None:
        if path.exists():
            try:
                editor.setPlainText(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                self._set_status(status, f"Could not read {path}: {exc}", "error")
                return
            status.setText(f"Loaded {path.name}")
            status.setProperty("role", "muted")
        else:
            editor.setPlainText("")
            status.setText(f"{path} does not exist yet")
            status.setProperty("role", "warning")
        self._restyle(status)

    def _load_config_text(self) -> None:
        self._load_text(self._config_file(), self._config_editor, self._config_status)
        try:
            self._loaded_config = load_config(self._config_file())
        except (ConfigError, OSError, UnicodeError) as exc:
            self._loaded_config = None
            self._set_status(self._config_status, str(exc), "warning")
            self._run_settings.setEnabled(False)
        else:
            self._run_settings.setEnabled(True)
            self._run_settings.load(self._loaded_config)
        self._update_command_preview()

    def _load_answers_text(self) -> None:
        self._load_text(self._answers_file(), self._answers_editor, self._answers_status)

    def _validate_yaml(self, editor: QPlainTextEdit, *, strict: bool) -> bool:
        """Parse the editor contents; *strict* also runs the AppConfig loader."""
        text = editor.toPlainText()
        status = self._config_status if strict else self._answers_status
        try:
            if strict:
                parse_config(text)
            else:
                data = yaml.safe_load(text)
                if not isinstance(data, dict):
                    raise ConfigError("Answers must be a YAML mapping.")
        except (yaml.YAMLError, ConfigError) as exc:
            self._set_status(status, str(exc), "error")
            return False
        self._set_status(status, "Valid", "document")
        return True

    def _set_status(self, label: QLabel, text: str, role: str) -> None:
        label.setText(text[:240])
        label.setProperty("role", role)
        self._restyle(label)

    def _restyle(self, widget: QWidget) -> None:
        """Re-evaluate the style sheet after changing a dynamic property."""
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)

    def _save_config_text(self) -> None:
        if self._answers_editor.document().isModified():
            QMessageBox.warning(
                self, "Not saved", "Save or reload your Answers edits before saving configuration."
            )
            return
        if not self._validate_yaml(self._config_editor, strict=True):
            QMessageBox.warning(
                self, "Not saved", "Fix the reported problem before saving the configuration."
            )
            return
        path = self._config_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._config_editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Configuration not saved", str(exc))
            return
        self._config_editor.document().setModified(False)
        self._set_status(self._config_status, f"Saved {path.name}", "document")
        self._loaded_config = load_config(path)
        self._run_settings.load(self._loaded_config)
        self._load_answers_text()

    def _save_answers_text(self) -> None:
        if not self._validate_yaml(self._answers_editor, strict=False):
            QMessageBox.warning(self, "Not saved", "Fix the YAML error before saving.")
            return
        path = self._answers_file()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._answers_editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(self, "Answers not saved", str(exc))
            return
        self._answers_editor.document().setModified(False)
        self._set_status(self._answers_status, f"Saved {path.name}", "document")

    # -- data ----------------------------------------------------------------
    def _refresh_stats(self) -> None:
        rows: list[tuple[str, str]] = []
        try:
            from linkedin_easy_apply.config import load_config
            from linkedin_easy_apply.database import Database

            config = load_config(self._config_file())
            db_path = config.database.path
            if not db_path.is_absolute():
                db_path = self._root / db_path
            database = Database(db_path)
            database.initialize()
            rows = [(k.replace("_", " ").capitalize(), str(v)) for k, v in database.stats().items()]
        except Exception as exc:
            rows = [("Unavailable", str(exc)[:120])]
        self._stats_table.setRowCount(len(rows))
        for index, (metric, value) in enumerate(rows):
            self._stats_table.setItem(index, 0, QTableWidgetItem(metric))
            self._stats_table.setItem(index, 1, QTableWidgetItem(value))
        self._stats_table.resizeColumnsToContents()

    def _export(self) -> None:
        fmt = self._export_format.currentText()
        default = str(self._root / f"applications.{fmt}")
        chosen, _filter = QFileDialog.getSaveFileName(
            self, "Export applications", default, f"{fmt.upper()} (*.{fmt})"
        )
        if chosen:
            self._run(commands.export_args(self._config_path, chosen, fmt))

    def _open_dashboard(self) -> None:
        """Start the Streamlit dashboard once, then open the browser."""
        if is_frozen():
            QMessageBox.information(
                self,
                "Optional analytics dashboard",
                "Streamlit is not bundled in the portable desktop build. "
                "Use the Data page or install the dashboard source extra.",
            )
            return
        if not self._dashboard_started:
            argv = commands.full_argv(commands.dashboard_args(self._config_path))
            if start_detached(argv, self._root):
                self._dashboard_started = True
                self.statusBar().showMessage("Dashboard starting…", 6000)
                QTimer.singleShot(4000, lambda: webbrowser.open(_DASHBOARD_URL))
                return
            QMessageBox.warning(
                self,
                "Dashboard",
                "Could not start the dashboard process. Run 'apply.py dashboard' "
                "in a terminal to see why (Streamlit may not be installed).",
            )
            return
        webbrowser.open(_DASHBOARD_URL)

    def _open_path(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # -- lifecycle -----------------------------------------------------------
    @override
    def closeEvent(self, event) -> None:  # noqa: ANN001 - Qt signature
        if self._runner.busy:
            answer = QMessageBox.question(
                self,
                "Command still running",
                "A command is still running. Stop it and close?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._runner.stop()
        event.accept()


def application_icon() -> QIcon:
    """The project mark, or an empty icon when the asset is missing.

    Importing ``QtSvg`` is what registers Qt's SVG image handler; without it
    ``QIcon`` silently loads nothing and the window gets a blank icon.
    """
    mark = resource_root() / "docs" / "mark.svg"
    if not mark.is_file():
        return QIcon()
    try:
        import PySide6.QtSvg  # noqa: F401
    except ImportError:  # pragma: no cover - QtSvg ships with PySide6
        return QIcon()
    return QIcon(str(mark))


def theme_icon(palette: Palette) -> QIcon:
    """Draw a sun/moon without relying on an installed symbol font."""
    pixmap = QPixmap(22, 22)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(palette["heading"])
    painter.setPen(QPen(color, 1.6))
    painter.setBrush(color)
    if palette.is_dark:
        painter.drawEllipse(7, 7, 8, 8)
        for x1, y1, x2, y2 in (
            (11, 1, 11, 4),
            (11, 18, 11, 21),
            (1, 11, 4, 11),
            (18, 11, 21, 11),
            (4, 4, 6, 6),
            (16, 16, 18, 18),
            (4, 18, 6, 16),
            (16, 6, 18, 4),
        ):
            painter.drawLine(x1, y1, x2, y2)
    else:
        painter.drawEllipse(3, 3, 16, 16)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.drawEllipse(9, 0, 15, 15)
    painter.end()
    return QIcon(pixmap)


def run(
    config_path: str = "configs/config.yaml", theme: str | None = None, *, tutorial: bool = False
) -> int:
    """Create the application and show the window. Returns the Qt exit code."""
    application = QApplication.instance() or QApplication([])
    if not isinstance(application, QApplication):
        raise RuntimeError("The desktop requires a QApplication, not a QCoreApplication.")
    application.setApplicationName("Easy Apply Automaton")
    application.setApplicationDisplayName("Easy Apply Automaton")
    application.setWindowIcon(application_icon())
    window: QWidget
    if tutorial:
        preferences = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, _ORG, _APP)
        stored = str(preferences.value("theme", DEFAULT_THEME))
        window = TutorialDialog()
        window.setStyleSheet(build_stylesheet(resolve(theme or stored)))
    else:
        window = MainWindow(config_path=config_path, theme=theme)
    window.show()
    try:
        return application.exec()
    finally:
        # The stopped event loop cannot deliver deferred deletion on its own.
        window.deleteLater()
        QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
