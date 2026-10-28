"""The Easy Apply desktop window.

Five pages behind a sidebar - Run, Configuration, Answers, Data and Tools -
each of which drives the same ``apply.py`` commands the terminal uses. The
Streamlit dashboard stays a separate read-only analytics surface; this window
simply launches it (as does ``apply.py dashboard``).
"""

from __future__ import annotations

import webbrowser
from pathlib import Path

import yaml
from PySide6.QtCore import QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
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
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from linkedin_easy_apply import __version__
from linkedin_easy_apply.gui import commands
from linkedin_easy_apply.gui.process import CommandRunner, start_detached
from linkedin_easy_apply.gui.theme import DEFAULT_THEME, THEMES, Palette, build_stylesheet, resolve
from linkedin_easy_apply.gui.widgets import Card, Console, PathRow, heading, muted

__all__ = ["MainWindow", "run"]

_ORG = "LinkedInEasyApplyAutomaton"
_APP = "DesktopGUI"
_DASHBOARD_URL = "http://localhost:8501"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class MainWindow(QMainWindow):
    def __init__(self, config_path: str, theme: str | None = None) -> None:
        super().__init__()
        self._settings = QSettings(_ORG, _APP)
        stored = str(self._settings.value("theme", DEFAULT_THEME))
        self._palette: Palette = resolve(theme or stored)
        self._root = project_root()
        self._config_path = config_path
        self._runner = CommandRunner(self._root, self)
        self._dashboard_started = False

        self.setWindowTitle(f"Easy Apply Automaton {__version__}")
        self.resize(1180, 780)
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
        sidebar.setFixedWidth(208)
        column = QVBoxLayout(sidebar)
        column.setContentsMargins(12, 16, 12, 16)
        column.setSpacing(6)

        title = QLabel("Easy Apply")
        title.setProperty("role", "heading")
        column.addWidget(title)
        column.addWidget(muted("Automaton"))
        column.addSpacing(14)

        self._nav_buttons: list[QPushButton] = []
        group = QButtonGroup(self)
        group.setExclusive(True)
        for index, (label, tip) in enumerate(
            [
                ("Run", "Scan, apply, reapply and connect"),
                ("Configuration", "Edit config.yaml"),
                ("Answers", "Edit answers.yaml"),
                ("Data", "Statistics, export and the dashboard"),
                ("Tools", "Sign in, verify the browser, one-shot commands"),
            ]
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setToolTip(tip)
            button.clicked.connect(lambda _checked, i=index: self._pages.setCurrentIndex(i))
            group.addButton(button)
            column.addWidget(button)
            self._nav_buttons.append(button)

        column.addStretch(1)
        self._theme_button = QPushButton()
        self._theme_button.setToolTip("Switch between DeepSeaFoam and Harbor Daylight")
        self._theme_button.clicked.connect(self._toggle_theme)
        column.addWidget(self._theme_button)
        return sidebar

    def _build_toolbar(self) -> None:
        bar = self.addToolBar("Main")
        bar.setMovable(False)

        self._config_field = QLineEdit(self._config_path)
        self._config_field.setToolTip("Configuration file every command is given")
        self._config_field.editingFinished.connect(self._on_config_path_changed)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_config)

        bar.addWidget(QLabel("Config "))
        bar.addWidget(self._config_field)
        bar.addWidget(browse)

        dashboard_action = QAction("Open dashboard", self)
        dashboard_action.setShortcut(QKeySequence("Ctrl+D"))
        dashboard_action.triggered.connect(self._open_dashboard)
        bar.addAction(dashboard_action)

        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        self.addAction(quit_action)

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
            "Run",
            "Every action here runs the same apply.py command the CLI does. "
            "The exact command is echoed into the log before it starts.",
        )

        controls = Card("Action")
        self._action_box = QComboBox()
        for label in commands.RUN_ACTIONS:
            self._action_box.addItem(label)
        self._action_box.currentTextChanged.connect(self._on_action_changed)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 999)
        self._limit_spin.setSpecialValueText("config default")
        self._limit_spin.setToolTip(
            "apply/reapply: successful submissions to target. scan: jobs to scan. 0 = use config."
        )
        self._url_field = QLineEdit()
        self._url_field.setPlaceholderText("Optional: override searches with one LinkedIn URL")

        form = QFormLayout()
        form.setSpacing(8)
        form.addRow("Action", self._action_box)
        form.addRow("Limit", self._limit_spin)
        form.addRow("Search URL", self._url_field)
        controls.body().addLayout(form)

        self._dry_run = QCheckBox("Dry run (fill everything, never submit)")
        self._ignore_score = QCheckBox("Ignore score (apply regardless of scoring.threshold)")
        self._confirm_submit = QCheckBox("Confirm each submit in the log window")
        self._confirm_submit.setToolTip(
            "Leave this off for GUI runs: confirmation prompts need a terminal to answer them."
        )
        self._confirm_submit.setEnabled(False)
        self._outreach = QCheckBox("Draft hiring-team outreach after each apply")
        self._outreach.setTristate(True)
        self._outreach.setCheckState(Qt.PartiallyChecked)
        self._outreach.setToolTip("Partially checked = use the outreach.enabled config value")
        self._verbose = QCheckBox("Verbose (DEBUG logging)")
        for box in (
            self._dry_run,
            self._ignore_score,
            self._confirm_submit,
            self._outreach,
            self._verbose,
        ):
            controls.add(box)
        column.addWidget(controls)

        buttons = QHBoxLayout()
        self._start_button = QPushButton("Start")
        self._start_button.setProperty("role", "primary")
        self._start_button.clicked.connect(self._start_run)
        self._stop_button = QPushButton("Stop")
        self._stop_button.setProperty("role", "danger")
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self._runner.stop)
        copy_button = QPushButton("Copy command")
        copy_button.clicked.connect(self._copy_command)
        clear_button = QPushButton("Clear log")
        buttons.addWidget(self._start_button)
        buttons.addWidget(self._stop_button)
        buttons.addWidget(copy_button)
        buttons.addWidget(clear_button)
        buttons.addStretch(1)
        column.addLayout(buttons)

        self._console = Console(self._palette)
        clear_button.clicked.connect(self._console.clear)
        column.addWidget(self._console, 1)
        self._on_action_changed(self._action_box.currentText())
        return page

    def _build_config_page(self) -> QWidget:
        page, column = self._page(
            "Configuration",
            "Edit configs/config.yaml. Validate parses the file through the same "
            "loader the CLI uses, so a mistake is caught here rather than mid-run.",
        )
        self._config_editor = QPlainTextEdit()
        self._config_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        column.addWidget(self._config_editor, 1)

        row = QHBoxLayout()
        validate = QPushButton("Validate")
        validate.clicked.connect(lambda: self._validate_yaml(self._config_editor, strict=True))
        save = QPushButton("Save")
        save.setProperty("role", "primary")
        save.clicked.connect(self._save_config_text)
        reload_button = QPushButton("Reload")
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
        self._answers_editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        column.addWidget(self._answers_editor, 1)

        row = QHBoxLayout()
        validate = QPushButton("Validate")
        validate.clicked.connect(lambda: self._validate_yaml(self._answers_editor, strict=False))
        save = QPushButton("Save")
        save.setProperty("role", "primary")
        save.clicked.connect(self._save_answers_text)
        reload_button = QPushButton("Reload")
        reload_button.clicked.connect(self._load_answers_text)
        sync = QPushButton("Run sync-answers")
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
        self._stats_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._stats_table.horizontalHeader().setStretchLastSection(True)
        self._stats_table.verticalHeader().setVisible(False)
        self._stats_table.setAlternatingRowColors(True)
        self._stats_table.setEditTriggers(QTableWidget.NoEditTriggers)

        stats_card = Card("Database")
        stats_card.add(self._stats_table)
        refresh = QPushButton("Refresh")
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
        open_dashboard.setProperty("role", "primary")
        open_dashboard.clicked.connect(self._open_dashboard)
        browser = QPushButton("Open in browser")
        browser.clicked.connect(lambda: webbrowser.open(_DASHBOARD_URL))
        dashboard_card.add_row(open_dashboard, browser)
        column.addWidget(dashboard_card)

        export_card = Card("Export")
        self._export_format = QComboBox()
        self._export_format.addItems(["csv", "xlsx"])
        export_button = QPushButton("Export applications…")
        export_button.clicked.connect(self._export)
        export_card.add_row(QLabel("Format"), self._export_format, export_button)
        column.addWidget(export_card)
        return page

    def _build_tools_page(self) -> QWidget:
        page, column = self._page(
            "Tools",
            "One-shot commands. Output goes to the Run page log.",
        )
        card = Card("Command")
        self._tool_box = QComboBox()
        self._tool_box.addItems(list(commands.TOOLS))
        self._tool_box.currentTextChanged.connect(self._on_tool_changed)
        self._tool_value = QLineEdit()

        form = QFormLayout()
        form.addRow("Tool", self._tool_box)
        form.addRow("Value", self._tool_value)
        card.body().addLayout(form)

        run_button = QPushButton("Run")
        run_button.setProperty("role", "primary")
        run_button.clicked.connect(self._run_tool)
        card.add(run_button)
        column.addWidget(card)

        paths = Card("Locations")
        for label, relative in (
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

    # -- theme ---------------------------------------------------------------
    def _apply_theme(self, palette: Palette) -> None:
        self._palette = palette
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(build_stylesheet(palette))
        self._console.apply_palette(palette)
        other = self._other_theme().label
        self._theme_button.setText(f"Theme: {palette.label}")
        self._theme_button.setToolTip(f"Switch to {other}")
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
            dry_run=self._dry_run.isChecked(),
            ignore_score=self._ignore_score.isChecked(),
            confirm_submit=False,
            message_hiring_team=(
                None
                if outreach_state == Qt.PartiallyChecked
                else outreach_state == Qt.Checked
            ),
            assume_yes=True,
            verbose=self._verbose.isChecked(),
        )

    def _on_action_changed(self, label: str) -> None:
        action = commands.RUN_ACTIONS.get(label, "scan")
        self._url_field.setEnabled(action in {"scan", "apply"})
        self._ignore_score.setEnabled(action in {"apply", "reapply"})
        self._outreach.setEnabled(action in {"apply", "reapply"})
        self._dry_run.setEnabled(action != "scan")
        if action == "scan":
            self._dry_run.setChecked(False)

    def _start_run(self) -> None:
        options = self._current_options()
        if options.action == "apply" and not options.dry_run:
            confirmation = QMessageBox.question(
                self,
                "Submit real applications?",
                "This submits real Easy Apply applications to LinkedIn.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirmation != QMessageBox.Yes:
                return
        self._run(commands.run_args(options))

    def _copy_command(self) -> None:
        argv = commands.full_argv(commands.run_args(self._current_options()))
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(commands.describe(argv))
        self.statusBar().showMessage("Command copied to the clipboard", 4000)

    def _run_tool(self) -> None:
        tool = self._tool_box.currentText()
        try:
            args = commands.tool_args(tool, self._config_path, self._tool_value.text())
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

    def _run(self, args: list[str], page_index: int = 0) -> None:
        if self._runner.busy:
            QMessageBox.information(
                self, "Already running", "Stop the current command before starting another."
            )
            return
        self._pages.setCurrentIndex(page_index)
        self._nav_buttons[page_index].setChecked(True)
        argv = commands.full_argv(args)
        self._console.note(f"$ {commands.describe(argv)}", "accent")
        if not self._runner.start(argv):
            self._console.note("Could not start the command.", "error")

    def _connect_runner(self) -> None:
        self._runner.output.connect(self._console.append_text)
        self._runner.finished.connect(self._on_finished)
        self._runner.started_command.connect(
            lambda _cmd: self._set_running(True)  # noqa: ARG005
        )

    def _set_running(self, running: bool) -> None:
        self._start_button.setEnabled(not running)
        self._stop_button.setEnabled(running)
        self.statusBar().showMessage("Running…" if running else "Ready")

    def _on_finished(self, exit_code: int, message: str) -> None:
        self._console.flush()
        self._console.note(message, "document" if exit_code == 0 else "warning")
        self._set_running(False)
        self.statusBar().showMessage(message, 8000)
        self._refresh_stats()

    # -- configuration -------------------------------------------------------
    def _on_config_path_changed(self) -> None:
        self._config_path = self._config_field.text().strip() or "configs/config.yaml"
        self._load_config_text()
        self._load_answers_text()
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
        """Resolve answers.file from the config, falling back to the default."""
        default = self._root / "configs" / "answers.yaml"
        try:
            data = yaml.safe_load(self._config_file().read_text(encoding="utf-8")) or {}
            configured = (data.get("answers") or {}).get("file")
        except Exception:
            return default
        if not configured:
            return default
        path = Path(str(configured))
        return path if path.is_absolute() else self._root / path

    def _load_text(self, path: Path, editor: QPlainTextEdit, status: QLabel) -> None:
        if path.exists():
            editor.setPlainText(path.read_text(encoding="utf-8"))
            status.setText(f"Loaded {path.name}")
            status.setProperty("role", "muted")
        else:
            editor.setPlainText("")
            status.setText(f"{path} does not exist yet")
            status.setProperty("role", "warning")
        self._restyle(status)

    def _load_config_text(self) -> None:
        self._load_text(self._config_file(), self._config_editor, self._config_status)

    def _load_answers_text(self) -> None:
        self._load_text(self._answers_file(), self._answers_editor, self._answers_status)

    def _validate_yaml(self, editor: QPlainTextEdit, *, strict: bool) -> bool:
        """Parse the editor contents; *strict* also runs the AppConfig loader."""
        text = editor.toPlainText()
        status = self._config_status if strict else self._answers_status
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            self._set_status(status, f"YAML error: {exc}", "error")
            return False
        if strict:
            try:
                from linkedin_easy_apply.config.models import AppConfig

                AppConfig.model_validate(data or {})
            except Exception as exc:
                self._set_status(status, f"Invalid configuration: {exc}", "error")
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
        if not self._validate_yaml(self._config_editor, strict=True):
            QMessageBox.warning(
                self, "Not saved", "Fix the reported problem before saving the configuration."
            )
            return
        path = self._config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._config_editor.toPlainText(), encoding="utf-8")
        self._set_status(self._config_status, f"Saved {path.name}", "document")

    def _save_answers_text(self) -> None:
        if not self._validate_yaml(self._answers_editor, strict=False):
            QMessageBox.warning(self, "Not saved", "Fix the YAML error before saving.")
            return
        path = self._answers_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._answers_editor.toPlainText(), encoding="utf-8")
        self._set_status(self._answers_status, f"Saved {path.name}", "document")

    # -- data ----------------------------------------------------------------
    def _refresh_stats(self) -> None:
        rows: list[tuple[str, str]] = []
        try:
            from linkedin_easy_apply.config import load_config
            from linkedin_easy_apply.database import Database

            config = load_config(self._config_file())
            database = Database(config.database.path)
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
    def closeEvent(self, event) -> None:  # noqa: ANN001 - Qt signature
        if self._runner.busy:
            answer = QMessageBox.question(
                self,
                "Command still running",
                "A command is still running. Stop it and close?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._runner.stop()
        event.accept()


def run(config_path: str = "configs/config.yaml", theme: str | None = None) -> int:
    """Create the application and show the window. Returns the Qt exit code."""
    application = QApplication.instance() or QApplication([])
    application.setApplicationName("Easy Apply Automaton")
    window = MainWindow(config_path=config_path, theme=theme)
    window.show()
    return application.exec()
