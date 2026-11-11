"""Offline widget and subprocess checks; never open a LinkedIn browser."""

from __future__ import annotations

import ctypes
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import get_args
from unittest.mock import Mock

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QContextMenuEvent,
    QFont,
    QFontInfo,
    QHelpEvent,
    QRawFont,
    QTextDocument,
)
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QToolBar,
    QToolTip,
    QWidget,
    QWidgetAction,
)

from linkedin_easy_apply.config import load_config  # noqa: E402
from linkedin_easy_apply.gui import commands, main_window  # noqa: E402
from linkedin_easy_apply.gui.activity import _STATES, Lifecycle  # noqa: E402
from linkedin_easy_apply.gui.activity_icons import activity_icon  # noqa: E402
from linkedin_easy_apply.gui.main_window import MainWindow  # noqa: E402
from linkedin_easy_apply.gui.process import CommandRunner  # noqa: E402
from linkedin_easy_apply.gui.theme import THEMES  # noqa: E402
from linkedin_easy_apply.gui.tutorial import CUSTOMIZE_TOPIC, TutorialDialog  # noqa: E402
from linkedin_easy_apply.gui.widgets import Console  # noqa: E402
from linkedin_easy_apply.progress import (  # noqa: E402
    Activity,
    ActivitySnapshot,
    ProgressSnapshot,
    RetryPreviewSnapshot,
    encode_progress,
)
from tools.media.capture_screenshots import ensure_fonts  # noqa: E402


def test_application_mark_renders_all_windows_sizes(qapp):
    icon = main_window.application_icon()
    sizes = {16, 20, 24, 32, 40, 48, 64, 128, 256}
    assert {size.width() for size in icon.availableSizes()} == sizes
    for side in sizes:
        image = icon.pixmap(side, side).toImage()
        assert not image.isNull()
        assert image.width() == image.height() == side
        assert image.pixelColor(side // 3, side // 2).alpha() == 255
        assert image.pixelColor(0, 0).alpha() < 8


def test_application_mark_uses_frozen_resource_not_workspace(qapp, tmp_path, monkeypatch):
    source = main_window.resource_root() / "docs" / "assets" / "branding" / "mark.ico"
    bundle = tmp_path / "bundle"
    bundled = bundle / "docs" / "assets" / "branding"
    bundled.mkdir(parents=True)
    (bundled / "mark.ico").write_bytes(source.read_bytes())
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("LEA_WORKSPACE", str(tmp_path / "uninitialized"))
    assert not main_window.application_icon().pixmap(32, 32).isNull()
    assert not (tmp_path / "uninitialized").exists()


def test_missing_application_mark_is_reported(qapp, tmp_path, monkeypatch):
    warning = Mock()
    monkeypatch.setattr(main_window, "resource_root", lambda: tmp_path)
    monkeypatch.setattr(main_window.logger, "warning", warning)
    assert main_window.application_icon().isNull()
    warning.assert_called_once()


@pytest.mark.parametrize("result", [0, -2147024809])
def test_windows_identity_uses_unicode_and_reports_hresult(monkeypatch, result):
    setter = Mock(return_value=result)
    library = Mock(return_value=SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=setter))
    warning = Mock()
    monkeypatch.setattr(main_window, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ctypes, "WinDLL", library, raising=False)
    monkeypatch.setattr(main_window.logger, "warning", warning)
    main_window._set_windows_app_id()
    library.assert_called_once_with("shell32", use_last_error=True)
    setter.assert_called_once_with("LinkedInEasyApplyAutomaton.DesktopGUI")
    assert setter.argtypes == [ctypes.c_wchar_p]
    assert setter.restype is ctypes.c_long
    assert warning.call_count == (1 if result < 0 else 0)


def test_windows_identity_library_failure_is_reported(monkeypatch):
    warning = Mock()
    monkeypatch.setattr(main_window, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(ctypes, "WinDLL", Mock(side_effect=OSError("fixture")), raising=False)
    monkeypatch.setattr(main_window.logger, "warning", warning)
    main_window._set_windows_app_id()
    warning.assert_called_once()


def test_other_platforms_do_not_load_windows_libraries(monkeypatch):
    library = Mock(side_effect=AssertionError("Windows API on another platform"))
    monkeypatch.setattr(main_window, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(ctypes, "WinDLL", library, raising=False)
    main_window._set_windows_app_id()
    library.assert_not_called()


def test_application_identity_precedes_qt_lookup(qapp, monkeypatch):
    events = []
    monkeypatch.setattr(main_window, "_set_windows_app_id", lambda: events.append("identity"))
    monkeypatch.setattr(QApplication, "instance", staticmethod(lambda: events.append("qt") or qapp))
    assert main_window.create_application() is qapp
    assert events == ["identity", "qt"]
    assert not qapp.windowIcon().pixmap(32, 32).isNull()


@pytest.fixture(scope="module")
def qapp(qt_app, tmp_path_factory):
    families = ensure_fonts()
    if not families:
        pytest.skip("GUI geometry requires usable fonts, not missing-glyph boxes.")
    previous_font = qt_app.font()
    qt_app.setFont(QFont("Segoe UI" if "Segoe UI" in families else families[0], 9))
    settings = tmp_path_factory.mktemp("qt-settings")
    previous_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(settings))
    yield qt_app
    QSettings.setDefaultFormat(previous_format)
    qt_app.setFont(previous_font)


@pytest.fixture
def window(qapp, tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "jobs": {"max_daily": 37, "pause_seconds": 2.5},
                "search": {
                    "searches": [
                        {"name": "backend", "url": "https://www.linkedin.com/jobs/search/"}
                    ]
                },
                "logging": {"level": "WARNING"},
            }
        ),
        encoding="utf-8",
    )
    (configs / "answers.yaml").write_text("full_name: Example User\n", encoding="utf-8")
    widget = MainWindow("configs\\config.yaml", workspace=tmp_path)
    widget.show()
    qapp.processEvents()
    yield widget
    if widget._runner.busy:
        widget._runner.stop()
        _until(qapp, lambda: not widget._runner.busy)
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _until(qapp, predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        qapp.processEvents()
        QTest.qWait(10)
    assert predicate(), "Timed out waiting for the Qt event path"


def _send_context_menu(qapp, widget, dismiss_popup):
    QTimer.singleShot(0, dismiss_popup)
    point = widget.rect().center()
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point, widget.mapToGlobal(point))
    QApplication.sendEvent(widget, event)
    qapp.processEvents()


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("target", ["toolbar", "tutorial"])
def test_toolbar_context_menu_cannot_hide_main_controls(window, qapp, theme, target):
    window._apply_theme(THEMES[theme])
    toolbar = window.findChild(QToolBar)
    widget = toolbar if target == "toolbar" else toolbar.widgetForAction(window._tutorial_action)
    assert widget is not None
    menus = []

    def try_to_hide_toolbar():
        popup = QApplication.activePopupWidget()
        if isinstance(popup, QMenu):
            menus.append([action.text() for action in popup.actions()])
            for action in popup.actions():
                if action.isCheckable() and action.text() == toolbar.windowTitle():
                    action.trigger()
                    break
            popup.close()

    _send_context_menu(qapp, widget, try_to_hide_toolbar)

    assert not menus, menus
    assert toolbar.isVisible()
    assert window._config_field.isVisible()
    assert toolbar.widgetForAction(window._tutorial_action).isVisible()
    assert not window._runner.busy


@pytest.mark.parametrize("theme", THEMES)
def test_toolbar_config_field_keeps_its_edit_context_menu(window, qapp, theme):
    window._apply_theme(THEMES[theme])
    original = window._config_field.text()
    menus = []

    def dismiss_edit_menu():
        popup = QApplication.activePopupWidget()
        if isinstance(popup, QMenu):
            menus.append([action.text() for action in popup.actions()])
            popup.close()

    _send_context_menu(qapp, window._config_field, dismiss_edit_menu)

    assert menus and menus[0]
    assert "Main" not in menus[0]
    assert window._config_field.text() == original
    assert window.findChild(QToolBar).isVisible()


@pytest.mark.parametrize("theme", THEMES)
def test_toolbar_reappears_on_reopen_without_resetting_setup(window, qapp, theme):
    window._apply_theme(THEMES[theme])
    window._settings.sync()
    preferences = Path(window._settings.fileName()).read_bytes()
    configs = {path: path.read_bytes() for path in (window._root / "configs").iterdir()}
    toolbar = window.findChild(QToolBar)
    toolbar.toggleViewAction().trigger()
    assert not toolbar.isVisible()
    window.close()

    reopened = MainWindow(window._config_path, workspace=window._root)
    try:
        reopened.show()
        qapp.processEvents()
        assert reopened.findChild(QToolBar).isVisible()
        assert reopened._config_field.text() == window._config_path
        assert reopened._palette == THEMES[theme]
        assert reopened._loaded_config.jobs.max_daily == 37
        reopened._settings.sync()
        assert Path(reopened._settings.fileName()).read_bytes() == preferences
        assert configs == {path: path.read_bytes() for path in configs}
    finally:
        reopened.close()
        reopened.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.mark.parametrize("route", ["toolbar", "f1", "context"])
def test_tutorial_help_events_preserve_unsaved_run_state(window, qapp, monkeypatch, route):
    monkeypatch.setattr(
        window._runner, "start", lambda *args: pytest.fail("Help cannot start a command")
    )
    window._run_settings.customize.setChecked(True)
    window._run_settings._fields["jobs.max_daily"].setValue(12)
    window._config_editor.appendPlainText("# Unsaved configuration note")
    window._answers_editor.appendPlainText("# Unsaved answer note")
    window._input.setText("unsent response")
    window._console.append_text("Existing console output\n")
    window._console.flush()
    qapp.processEvents()
    window._settings.sync()
    files = {path: path.read_bytes() for path in window._root.rglob("*") if path.is_file()}
    before = (
        window._current_options(),
        window._run_settings.overrides(),
        window._config_editor.toPlainText(),
        window._answers_editor.toPlainText(),
        window._input.text(),
        window._console.toPlainText(),
        window._config_editor.document().isModified(),
        window._answers_editor.document().isModified(),
        Path(window._settings.fileName()).read_bytes(),
    )
    titles = []

    def close_guide():
        guide = QApplication.activeModalWidget()
        if isinstance(guide, TutorialDialog):
            titles.append(guide._title.text())
            guide.reject()
        else:
            titles.append(None)

    for _ in range(2):
        window.activateWindow()
        qapp.processEvents()
        QTimer.singleShot(0, close_guide)
        if route == "toolbar":
            window._tutorial_action.trigger()
        elif route == "f1":
            QTest.keyClick(window, Qt.Key.Key_F1)
        else:
            QTest.mouseClick(window._run_settings.help_button, Qt.MouseButton.LeftButton)
        qapp.processEvents()

    assert titles == [CUSTOMIZE_TOPIC if route == "context" else "Start here"] * 2
    window._settings.sync()
    assert before == (
        window._current_options(),
        window._run_settings.overrides(),
        window._config_editor.toPlainText(),
        window._answers_editor.toPlainText(),
        window._input.text(),
        window._console.toPlainText(),
        window._config_editor.document().isModified(),
        window._answers_editor.document().isModified(),
        Path(window._settings.fileName()).read_bytes(),
    )
    assert files == {path: path.read_bytes() for path in window._root.rglob("*") if path.is_file()}
    assert not window._runner.busy


def test_tutorial_cannot_cover_a_running_command(window, monkeypatch):
    notices = []
    monkeypatch.setattr(CommandRunner, "busy", property(lambda self: True))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args[2]))
    window._set_running(True)
    assert not window._tutorial_action.isEnabled()
    assert not window._run_settings.help_button.isEnabled()
    window._show_tutorial()
    assert notices and "Finish" in notices[0]


def test_missing_tutorial_is_reported_instead_of_opening_empty_help(window, monkeypatch):
    from linkedin_easy_apply.gui import tutorial

    notices = []
    monkeypatch.setattr(
        tutorial, "load_tutorial", lambda path: (_ for _ in ()).throw(FileNotFoundError("guide"))
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: notices.append(args[1:]))
    window._show_tutorial()
    assert notices == [("Tutorial unavailable", "guide")]


def _assert_option_help(text):
    lines = text.splitlines()
    assert len(lines) == 2, text
    assert lines[0].strip() and not lines[0].startswith("Example:"), text
    assert lines[1].startswith("Example: ") and lines[1][9:].strip(), text


def test_option_help_covers_controls_items_labels_and_changing_selections(window, qapp):
    field_types = (
        QAbstractSpinBox,
        QCheckBox,
        QComboBox,
        QLineEdit,
        QListWidget,
        QPlainTextEdit,
        QPushButton,
        QTableWidget,
    )
    for theme in THEMES.values():
        window._apply_theme(theme)
        window._load_config_text()
        for field in window.findChildren(QWidget):
            if not isinstance(field, field_types) or isinstance(field, Console):
                continue
            if isinstance(field, QLineEdit) and isinstance(field.parent(), QAbstractSpinBox):
                continue
            _assert_option_help(field.toolTip())
            if isinstance(field, QComboBox):
                for index in range(field.count()):
                    _assert_option_help(field.itemData(index, Qt.ItemDataRole.ToolTipRole))
        for form in window.findChildren(QFormLayout):
            for row in range(form.rowCount()):
                item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                field = item.widget() if item is not None else None
                label = form.labelForField(field) if field is not None else None
                if isinstance(label, QLabel):
                    assert label.toolTip() == field.toolTip()
        for index in range(window._run_settings.tabs.count()):
            _assert_option_help(window._run_settings.tabs.tabToolTip(index))
        for index in range(window._run_settings.searches.count()):
            _assert_option_help(window._run_settings.searches.item(index).toolTip())
        actions = [
            *window.actions(),
            *(action for bar in window.findChildren(QToolBar) for action in bar.actions()),
        ]
        for action in actions:
            if action.isSeparator() or isinstance(action, QWidgetAction):
                continue
            _assert_option_help(action.toolTip())

    limit_help = {}
    for label, action in commands.RUN_ACTIONS.items():
        window._action_box.setCurrentText(label)
        limit_help[action] = window._limit_spin.toolTip()
        _assert_option_help(limit_help[action])
        assert window._action_form.labelForField(window._limit_spin).toolTip() == limit_help[action]
    assert len(set(limit_help.values())) == len(commands.RUN_ACTIONS)
    assert "confirmed submissions" in limit_help["apply"]
    assert "retry candidates" in limit_help["reapply"]
    assert "pending invitations" in limit_help["connect"]
    assert "discovered jobs" in limit_help["scan"]

    for label, spec in commands.TOOLS.items():
        window._tool_box.setCurrentText(label)
        for field in (window._tool_value, window._tool_option):
            _assert_option_help(field.toolTip())
            assert window._tool_form.labelForField(field).toolTip() == field.toolTip()
        assert ("does not use" in window._tool_value.toolTip()) == (not spec.needs_value)
        assert ("does not use" in window._tool_option.toolTip()) == (not bool(spec.optional_flag))


@pytest.mark.parametrize("theme", list(THEMES))
def test_real_tooltip_events_preserve_unsaved_fields_files_and_preferences(
    window, qapp, monkeypatch, theme
):
    monkeypatch.setattr(
        window._runner, "start", lambda *args: pytest.fail("Hover help cannot start a command")
    )
    window._apply_theme(THEMES[theme])
    window._action_box.setCurrentText("Apply")
    settings = window._run_settings
    settings.customize.setChecked(True)
    daily = settings._fields["jobs.max_daily"]
    daily.setValue(12)
    window._config_editor.appendPlainText("# Unsaved hover-help example")
    window._answers_editor.appendPlainText("# Unsaved hover-help example")
    window._input.setText("unsent response")
    window._console.append_text("Existing console output\n")
    window._console.flush()
    qapp.processEvents()
    window._settings.sync()

    def snapshot():
        return (
            window._current_options(),
            settings.overrides(),
            window._command_preview.toPlainText(),
            window._config_editor.toPlainText(),
            window._answers_editor.toPlainText(),
            window._input.text(),
            window._console.toPlainText(),
            window._config_editor.document().isModified(),
            window._answers_editor.document().isModified(),
            Path(window._settings.fileName()).read_bytes(),
        )

    before = snapshot()
    files = {path: path.read_bytes() for path in window._root.rglob("*") if path.is_file()}

    def show_help(target, expected, position=None):
        ancestor = target.parentWidget()
        while ancestor is not None:
            if isinstance(ancestor, QScrollArea):
                ancestor.ensureWidgetVisible(target)
            ancestor = ancestor.parentWidget()
        window.activateWindow()
        qapp.processEvents()
        point = position if position is not None else target.rect().center()
        event = QHelpEvent(QEvent.Type.ToolTip, point, target.mapToGlobal(point))
        QApplication.sendEvent(target, event)
        _until(qapp, lambda: QToolTip.isVisible() and QToolTip.text() == expected)
        assert snapshot() == before

    try:
        settings.tabs.setCurrentIndex(1)
        show_help(daily, daily.toolTip())
        form = daily.parentWidget().layout()
        show_help(form.labelForField(daily), daily.toolTip())
        show_help(daily.findChild(QLineEdit), daily.toolTip())
        assert not window._input.isEnabled()
        show_help(window._input, window._input.toolTip())
        settings.tabs.setCurrentIndex(0)
        item = settings.searches.item(0)
        show_help(
            settings.searches.viewport(),
            item.toolTip(),
            settings.searches.visualItemRect(item).center(),
        )
        show_help(settings.job_urls.viewport(), settings.job_urls.toolTip())
        window._pages.setCurrentIndex(1)
        show_help(window._config_editor.viewport(), window._config_editor.toolTip())
        window._pages.setCurrentIndex(4)
        assert not window._tool_option.isEnabled()
        show_help(window._tool_option, window._tool_option.toolTip())
    finally:
        QToolTip.hideText()
        qapp.processEvents()

    window._settings.sync()
    assert snapshot() == before
    assert files == {path: path.read_bytes() for path in window._root.rglob("*") if path.is_file()}
    assert not (window._root / "logs" / "gui-runs").exists()
    assert not window._runner.busy


def test_run_controls_build_actual_cli_flags(window):
    window._action_box.setCurrentText("Apply")
    QTest.mouseClick(window._confirm_submit, Qt.LeftButton)
    window._limit_spin.setValue(6)
    window._url_field.setText("https://www.linkedin.com/jobs/search/")
    args = commands.run_args(window._current_options())
    assert "--confirm-submit" in args
    assert "--yes" not in args
    assert args[args.index("--limit") + 1] == "6"
    assert "--url" in args

    window._action_box.setCurrentText("Reapply (retry failed/aborted)")
    QTest.mouseClick(window._list_only, Qt.LeftButton)
    assert "--list" in commands.run_args(window._current_options())
    assert not window._url_field.isEnabled()

    window._action_box.setCurrentText("Connect (send pending invitations)")
    window._connect_run.setValue(21)
    args = commands.run_args(window._current_options())
    assert args[args.index("--run") + 1] == "21"
    assert not window._confirm_submit.isEnabled()


@pytest.mark.parametrize(
    "label", ["Apply", "Reapply (retry failed/aborted)", "Connect (send pending invitations)"]
)
def test_every_live_action_asks_before_starting(window, monkeypatch, label):
    started = []
    questions = []
    monkeypatch.setattr(window, "_run", lambda args, **kwargs: started.append(args))

    def decline(*args):
        questions.append(args)
        return QMessageBox.No

    monkeypatch.setattr(QMessageBox, "question", decline)
    window._action_box.setCurrentText(label)
    window._dry_run.setChecked(False)
    QTest.mouseClick(window._start_button, Qt.LeftButton)
    assert len(questions) == 1
    assert started == []


def test_retry_listing_does_not_request_live_confirmation(window, monkeypatch):
    calls = []
    monkeypatch.setattr(window, "_run", lambda args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: pytest.fail("A retry list cannot submit")
    )
    window._action_box.setCurrentText("Reapply (retry failed/aborted)")
    window._dry_run.setChecked(False)
    window._list_only.setChecked(True)
    QTest.mouseClick(window._start_button, Qt.LeftButton)
    assert "--list" in calls[0][0]
    assert calls[0][1]["metrics_action"] == "reapply-list"


@pytest.mark.parametrize(
    "label", ["Scan (score only, never applies)", "Apply", "Connect (send pending invitations)"]
)
def test_hidden_retry_list_checkbox_cannot_change_other_actions(window, monkeypatch, label):
    calls = []
    monkeypatch.setattr(window, "_run", lambda args, **kwargs: calls.append((args, kwargs)))
    window._action_box.setCurrentText("Reapply (retry failed/aborted)")
    window._list_only.setChecked(True)
    window._action_box.setCurrentText(label)
    window._dry_run.setChecked(True)
    options = window._current_options()
    assert not options.list_only
    assert not window._list_only.isVisible()
    window._start_run()
    assert "--list" not in calls[0][0]
    assert calls[0][1]["metrics_action"] == options.action


def test_run_preset_preserves_saved_bytes_and_other_settings(window):
    original = window._config_file().read_bytes()
    window._run_settings.customize.setChecked(True)
    assert window._run_settings.overrides() == {}
    window._run_settings._fields["jobs.max_daily"].setValue(12)
    window._action_box.setCurrentText("Apply")
    options = window._prepared_options()
    config = load_config(options.config)
    assert config.jobs.max_daily == 12
    assert config.jobs.pause_seconds == 2.5
    assert config.logging.level == "WARNING"
    assert window._config_file().read_bytes() == original
    assert Path(options.config).is_relative_to(window._root / "logs" / "gui-runs")


@pytest.mark.parametrize(
    "action", ["Apply", "Reapply (retry failed/aborted)", "Connect (send pending invitations)"]
)
@pytest.mark.parametrize("saved", [False, True])
def test_connection_fallback_toggle_roundtrips_without_changing_saved_config(window, action, saved):
    path = window._config_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if saved:
        data["outreach"] = {"connect_without_note": True}
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
    original = path.read_bytes()
    window._load_config_text()
    settings = window._run_settings
    field = settings._fields["outreach.connect_without_note"]
    assert field.isChecked() is saved
    settings.customize.setChecked(True)
    field.setChecked(not saved)
    window._action_box.setCurrentText(action)
    options = window._prepared_options()
    assert load_config(options.config).outreach.connect_without_note is not saved
    assert load_config(options.config).jobs.max_daily == 37
    assert path.read_bytes() == original
    assert Path(options.config).is_relative_to(window._root / "logs" / "gui-runs")
    settings.customize.setChecked(False)
    restored = window._root / window._prepared_options().config
    assert load_config(restored).outreach.connect_without_note is saved


def test_gui_can_disable_a_saved_dry_run_without_changing_original(window):
    path = window._config_file()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["run"] = {"dry_run": True}
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    window._load_config_text()
    window._action_box.setCurrentText("Apply")
    window._dry_run.setChecked(False)
    options = window._prepared_options()
    assert not load_config(options.config).run.dry_run
    assert load_config(path).run.dry_run


def test_unknown_question_setting_controls_unattended_flag(window):
    window._action_box.setCurrentText("Apply")
    assert "--yes" not in commands.run_args(window._current_options())
    window._interactive.setChecked(False)
    assert "--yes" in commands.run_args(window._current_options())


def test_prompt_is_visible_before_newline_and_survives_theme_switch(qapp):
    console = Console(THEMES["deepseafoam"])
    console.append_text("First line\nYour ")
    assert console.toPlainText() == "First line\nYour "
    console.append_text("answer: ")
    assert console.toPlainText() == "First line\nYour answer: "
    console.apply_palette(THEMES["harbor-daylight"])
    assert console.toPlainText() == "First line\nYour answer: "
    console.append_text("\nNext line\n")
    assert console.toPlainText() == "First line\nYour answer: \nNext line"
    console.flush()
    assert console.toPlainText().count("Your answer") == 1


def test_runner_streams_an_unterminated_prompt_and_accepts_input(qapp, tmp_path):
    runner = CommandRunner(tmp_path)
    chunks = []
    outcomes = []
    runner.output.connect(chunks.append)
    runner.finished.connect(lambda code, message: outcomes.append((code, message)))
    code = "print('Your answer: ', end='', flush=True); answer=input(); print('Received:'+answer)"
    assert runner.start([sys.executable, "-u", "-c", code])
    try:
        _until(qapp, lambda: "Your answer: " in "".join(chunks))
        assert runner.send_input("caf\u00e9")
        _until(qapp, lambda: bool(outcomes))
    finally:
        if runner.busy:
            runner.stop()
    assert outcomes[0][0] == 0
    assert "Received:caf\u00e9" in "".join(chunks)
    assert not runner.send_input("too late")


def test_window_input_buttons_reach_the_running_child(window, qapp, monkeypatch):
    seen = []
    window._runner.output.connect(seen.append)
    code = (
        "print('First: ',end='',flush=True); first=input(); "
        "print('Second: ',end='',flush=True); second=input(); "
        "print('Received:'+first+':'+repr(second))"
    )
    monkeypatch.setattr(commands, "full_argv", lambda _args: [sys.executable, "-u", "-c", code])
    window._run(["offline-input-fixture"])
    _until(qapp, lambda: "First: " in "".join(seen))
    assert window._input.isEnabled()
    window._input.setText("caf\u00e9")
    QTest.mouseClick(window._send_button, Qt.LeftButton)
    _until(qapp, lambda: "Second: " in "".join(seen))
    window._input.setText("this must not be sent")
    QTest.mouseClick(window._enter_button, Qt.LeftButton)
    _until(qapp, lambda: not window._runner.busy)
    assert "Received:caf\u00e9:''" in "".join(seen)
    assert not window._input.isEnabled()
    assert window._input.text() == ""


def test_utf8_character_split_across_output_chunks_is_not_corrupted(qapp, tmp_path):
    runner = CommandRunner(tmp_path)
    seen = []
    runner.output.connect(seen.append)
    code = "import os,time; os.write(1,b'\\xe2'); time.sleep(.15); " "os.write(1,b'\\x82\\xac\\n')"
    assert runner.start([sys.executable, "-u", "-c", code])
    _until(qapp, lambda: not runner.busy)
    assert "".join(seen) == "\u20ac\n"


def test_real_child_updates_metrics_before_finish_and_controls_preserve_them(
    window, qapp, monkeypatch
):
    seen = []
    window._runner.output.connect(seen.append)
    code = (
        "from linkedin_easy_apply.progress import gui_progress; "
        "p=gui_progress(); assert p is not None; "
        "p.start('apply',run_id=42,target=3); "
        "print('First: ',end='',flush=True); input(); "
        "p.increment({'scanned':4,'applied':1,'skipped':1,'failed':1,'hr_sent':1}); "
        "print('Second: ',end='',flush=True); input(); p.increment({'applied':1})"
    )
    monkeypatch.setattr(commands, "full_argv", lambda _args: [sys.executable, "-u", "-c", code])
    window._run(["offline-metrics-fixture"], metrics_action="apply")
    _until(qapp, lambda: "First: " in "".join(seen))
    assert [value.text() for value in window._metrics._values] == ["0"] * 5
    window._runner.send_input("continue")
    _until(qapp, lambda: "Second: " in "".join(seen))
    assert window._runner.busy
    assert [value.text() for value in window._metrics._values] == ["4", "1", "1", "1", "1"]
    before = window._metrics._snapshot
    window._action_box.setCurrentText("Connect (send pending invitations)")
    window._apply_theme(THEMES["harbor-daylight"])
    next(
        button for button in window.findChildren(QPushButton) if button.text() == "Clear log"
    ).click()
    assert window._metrics._snapshot == before
    assert "Apply #42" in window._metrics.caption.text()
    assert window._metrics._titles[-1].text() == "HR sent"
    window._runner.send_input("finish")
    _until(qapp, lambda: not window._runner.busy)
    assert window._metrics._values[1].text() == "2"
    assert "Finished - last reported" in window._metrics._details.text()
    assert not window._metrics._timer.isActive()
    assert "LEA_METRICS" not in "".join(seen)
    assert window._metrics._target.value() == 666

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    window._action_box.setCurrentText("Apply")
    window._dry_run.setChecked(False)
    window._start_run()
    assert window._metrics._values[1].text() == "2"

    code = "print('Offline tool finished')"
    window._run(["offline-tool-fixture"])
    _until(qapp, lambda: not window._runner.busy)
    assert window._metrics._snapshot is None
    assert not window._metrics.isVisible()


@pytest.mark.parametrize("empty", [False, True])
def test_real_retry_list_child_keeps_five_historical_cards_and_writes_no_run(
    window, qapp, monkeypatch, empty
):
    from linkedin_easy_apply.database import Database

    database = Database(window._root / "database" / "easy_apply.db")
    database.initialize()
    if not empty:
        run_id = database.start_run("apply")
        for index, status in enumerate(("failed", "aborted")):
            job_id = database.upsert_job(
                {
                    "url": f"https://www.linkedin.com/jobs/view/fictional-{index}/",
                    "title": f"Fictional job {index}",
                    "company": "Example Company",
                },
                run_id,
            )
            database.create_application(job_id, run_id, None, status)
        database.create_application(job_id, database.start_run("apply"), None, "aborted")
    with database.connect() as connection:
        before = connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: pytest.fail("A retry preview is not live")
    )
    window._action_box.setCurrentText("Reapply (retry failed/aborted)")
    window._list_only.setChecked(True)
    window._dry_run.setChecked(False)
    window._start_run()
    _until(qapp, lambda: not window._runner.busy, timeout=15)
    assert window._metrics.isVisible()
    assert isinstance(window._metrics._snapshot, RetryPreviewSnapshot)
    assert [value.text() for value in window._metrics._values] == (
        ["0"] * 5 if empty else ["2", "1", "1", "3", "1"]
    )
    assert "Retry preview" in window._metrics.caption.text()
    assert "saved retry history" in window._metrics._details.text()
    assert "No browser or sends" in window._metrics._details.text()
    assert not window._metrics._target.isVisible()
    assert not window._metrics._timer.isActive()
    assert "LEA_METRICS" not in window._console.toPlainText()
    before_snapshot = window._metrics._snapshot
    window._apply_theme(THEMES["harbor-daylight"])
    window._action_box.setCurrentText("Apply")
    next(
        button for button in window.findChildren(QPushButton) if button.text() == "Clear log"
    ).click()
    assert window._metrics._snapshot == before_snapshot
    assert window._metrics._titles[0].text() == "Targets"
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == before
    assert not (window._root / ".browser-profile").exists()


def test_real_child_activity_and_resume_survive_controls_scan_tools_and_failed_start(
    window, qapp, monkeypatch
):
    seen = []
    window._runner.output.connect(seen.append)
    first = ActivitySnapshot(activity="preparing_application", resume_name="Example_caf\u00e9.pdf")
    code = (
        "import os,time; from pathlib import Path; "
        "from linkedin_easy_apply.progress import gui_progress; "
        "p=gui_progress(); assert p is not None; p.start('apply'); "
        f"frame={encode_progress(first)!r}.encode('utf-8'); "
        "split=frame.index(b'\\xc3')+1; os.write(2,frame[:split]); "
        "time.sleep(.03); os.write(2,frame[split:]); "
        "print('Selected: ',end='',flush=True); input(); "
        "p.activity('awaiting_input'); print('Waiting: ',end='',flush=True); input(); "
        "p.activity('preparing_application',resume_path=Path('private')/'Example_tailored.pdf'); "
        "print('Replaced: ',end='',flush=True); input()"
    )
    monkeypatch.setattr(commands, "full_argv", lambda _args: [sys.executable, "-u", "-c", code])
    window._run(["offline-activity-fixture"], metrics_action="apply")
    _until(qapp, lambda: "Selected: " in "".join(seen))
    assert window._runner.busy
    assert window._activity.name.text() == "Preparing application"
    assert window._resume_display.filename == "Example_caf\u00e9.pdf"
    assert window._metrics._values[1].text() == "0"
    assert not window._activity.icon.pixmap().isNull()

    notices = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: notices.append(args))
    window._run(["must-not-replace-an-active-run"])
    assert notices and window._activity.name.text() == "Preparing application"
    window._action_box.setCurrentText("Connect (send pending invitations)")
    window._apply_theme(THEMES["harbor-daylight"])
    next(
        button for button in window.findChildren(QPushButton) if button.text() == "Clear log"
    ).click()
    assert window._resume_display.filename == "Example_caf\u00e9.pdf"
    assert window._activity.name.text() == "Preparing application"

    window._runner.send_input("continue")
    _until(qapp, lambda: "Waiting: " in "".join(seen))
    assert window._activity.name.text() == "Waiting for you"
    assert window._activity.name.property("tone") == "warning"
    assert window._resume_display.filename == "Example_caf\u00e9.pdf"
    window._runner.send_input("continue")
    _until(qapp, lambda: "Replaced: " in "".join(seen))
    assert window._resume_display.filename == "Example_tailored.pdf"
    window._runner.send_input("finish")
    _until(qapp, lambda: not window._runner.busy)
    assert window._activity.name.text() == "Command finished"
    assert window._resume_display.filename == "Example_tailored.pdf"

    for action in ("scan", None):
        seen.clear()
        code = (
            "from linkedin_easy_apply.progress import gui_progress; p=gui_progress(); "
            + ("p.start('scan'); p.activity('searching_jobs'); " if action == "scan" else "")
            + "print('Next: ',end='',flush=True); input()"
        )
        window._run(["offline-next-fixture"], metrics_action=action)
        _until(qapp, lambda: "Next: " in "".join(seen))
        assert window._activity.name.text() == (
            "Searching jobs" if action == "scan" else "Running command"
        )
        assert window._resume_display.filename == "Example_tailored.pdf"
        window._runner.send_input("finish")
        _until(qapp, lambda: not window._runner.busy)
    assert "LEA_METRICS" not in "".join(seen)
    monkeypatch.setattr(commands, "full_argv", lambda _args: [str(window._root / "missing.exe")])
    window._run(["offline-missing-fixture"], metrics_action="apply")
    qapp.processEvents()
    assert window._activity.name.text() == "Command error"
    assert window._resume_display.filename == "Example_tailored.pdf"


@pytest.mark.parametrize("stop", [False, True])
def test_real_child_stop_and_error_freeze_dry_invites_without_claiming_sends(
    window, qapp, monkeypatch, stop
):
    seen = []
    window._runner.output.connect(seen.append)
    code = (
        "from pathlib import Path; from linkedin_easy_apply.progress import gui_progress; "
        "p=gui_progress(); p.start('connect',dry_run=True); "
        "p.activity('connecting',resume_path=Path('Example_retained.pdf')); "
        "p.connections(5,dry_run=True); p.increment({'connect_processed':2,'connect_dry_runs':2}); "
        "print('Ready: ',end='',flush=True); input(); raise SystemExit(2)"
    )
    monkeypatch.setattr(commands, "full_argv", lambda _args: [sys.executable, "-u", "-c", code])
    window._run(["offline-connect-fixture"], metrics_action="connect")
    _until(qapp, lambda: "Ready: " in "".join(seen))
    if stop:
        window._stop_button.click()
    else:
        window._runner.send_input("finish")
    _until(qapp, lambda: not window._runner.busy)
    assert [value.text() for value in window._metrics._values] == ["2", "0", "0", "0", "0"]
    assert ("Stopped" if stop else "Error") in window._metrics._details.text()
    assert "Would-send 2" in window._metrics._details.text()
    assert not window._metrics._timer.isActive()
    assert window._metrics._target.value() == 400
    assert window._activity.name.text() == ("Stopped" if stop else "Command error")
    assert window._resume_display.filename == "Example_retained.pdf"


def test_real_child_bad_and_truncated_metrics_keep_last_valid_counts(window, qapp, monkeypatch):
    seen = []
    warnings = []
    window._runner.output.connect(seen.append)
    window._runner.progress_error.connect(warnings.append)
    code = (
        "import sys; from pathlib import Path; "
        "from linkedin_easy_apply.progress import gui_progress,FRAME_START,FRAME_END; "
        "p=gui_progress(); p.start('apply'); p.increment({'applied':2}); "
        "p.activity('preparing_application',resume_path=Path('Example_retained.pdf')); "
        "sys.stderr.write(FRAME_START+'not-json'+FRAME_END+FRAME_START+'{'); sys.stderr.flush()"
    )
    monkeypatch.setattr(commands, "full_argv", lambda _args: [sys.executable, "-u", "-c", code])
    window._run(["offline-malformed-fixture"], metrics_action="apply")
    _until(qapp, lambda: not window._runner.busy)
    assert window._metrics._values[1].text() == "2"
    assert "Metrics interrupted" in window._metrics._details.text()
    assert "[STATUS]" in window._console.toPlainText()
    assert "not-json" not in "".join(seen + warnings)
    assert not window._metrics._timer.isActive()
    assert window._resume_display.filename == "Example_retained.pdf"


@pytest.mark.parametrize("action", ["apply", "reapply-list"])
def test_failed_launch_never_presents_unreported_metrics_as_zero(window, qapp, monkeypatch, action):
    monkeypatch.setattr(commands, "full_argv", lambda _args: [str(window._root / "missing.exe")])
    window._run(["offline-missing-fixture"], metrics_action=action)
    qapp.processEvents()
    assert [value.text() for value in window._metrics._values] == ["--"] * 5
    assert (
        "Error: saved history unavailable"
        if action == "reapply-list"
        else "Error: no run metrics received"
    ) in window._metrics._details.text()
    assert not window._metrics._timer.isActive()


@pytest.mark.parametrize("theme", list(THEMES))
@pytest.mark.parametrize("action", ["apply", "reapply", "reapply-list"])
@pytest.mark.parametrize("size", [(940, 640), (980, 680), (1340, 860)])
def test_metrics_fit_compact_and_expanded_themes_with_purpose_example_help(
    window, qapp, size, theme, action
):
    counts = ProgressSnapshot(action="apply").counts | {
        "scanned": 10_000,
        "applied": 12,
        "skipped": 9000,
        "failed": 7,
        "hr_drafted": 3,
        "dry_runs": 2,
        "unconfirmed": 1,
    }
    window.resize(*size)
    window._apply_theme(THEMES[theme])
    window._metrics.prepare(action)
    window._set_running(True)
    window._metrics.begin()
    snapshot = (
        RetryPreviewSnapshot(
            targets=10_000,
            last_failed=9000,
            last_aborted=1000,
            prior_attempts=12_000,
            repeated_jobs=1000,
        )
        if action == "reapply-list"
        else ProgressSnapshot(action=action, run_id=42, target=20, counts=counts)
    )
    window._metrics.update_progress(snapshot)
    qapp.processEvents()
    assert window.size().width() == size[0]
    assert window._console.width() > 260
    assert window._console.height() > 80
    assert window._activity.size().toTuple() == (112, 108)
    assert window._metrics.isVisible()
    assert window._activity.geometry().right() < window._metrics.geometry().left()
    assert max(window._activity.geometry().bottom(), window._metrics.geometry().bottom()) < (
        window._command_preview.y()
    )
    assert window._metrics._row_widgets[1].isVisible() == (window._metrics.width() < 540)
    caption = window._metrics.caption
    assert (
        max(caption.fontMetrics().horizontalAdvance(line) for line in caption.text().splitlines())
        <= caption.contentsRect().width()
    )
    assert caption.fontMetrics().height() * len(caption.text().splitlines()) <= caption.height()
    for title, value in zip(window._metrics._titles, window._metrics._values, strict=True):
        assert value.fontMetrics().horizontalAdvance(value.text()) <= value.contentsRect().width()
        assert title.toolTip().count("\n") == value.toolTip().count("\n") == 1
        assert "Example:" in value.toolTip()


@pytest.mark.parametrize("theme", list(THEMES))
@pytest.mark.parametrize("pixel_ratio", [1.0, 2.0])
def test_every_activity_has_distinct_detailed_multicolor_artwork(qapp, theme, pixel_ratio):
    palette = THEMES[theme]
    assert set(_STATES) == set(get_args(Activity)) | set(get_args(Lifecycle))
    colors = {
        QColor(palette[role]).rgb()
        for role in ("information", "accent", "document", "warning", "error", "heading")
    }
    silhouettes = set()
    for state in _STATES:
        pixmap = activity_icon(state, palette, pixel_ratio=pixel_ratio)
        assert pixmap.deviceIndependentSize().toTuple() == (64, 64)
        image = pixmap.toImage()
        pixels = [
            image.pixelColor(x, y) for y in range(image.height()) for x in range(image.width())
        ]
        assert image.pixelColor(0, 0).alpha() == 0
        assert 0.1 < sum(pixel.alpha() > 0 for pixel in pixels) / len(pixels) < 0.9, state
        opaque_ink = {pixel.rgb() for pixel in pixels if pixel.alpha() == 255}
        assert len(opaque_ink & colors) >= 2, state
        silhouette = bytes(pixel.alpha() for pixel in pixels)
        assert silhouette not in silhouettes, f"{state} reuses another stage's shape"
        silhouettes.add(silhouette)


@pytest.mark.parametrize("theme", list(THEMES))
@pytest.mark.parametrize("size", [(940, 640), (1340, 860)])
def test_larger_action_icons_keep_the_original_box_and_centered_full_labels(
    window, qapp, theme, size
):
    assert ensure_fonts()
    window.resize(*size)
    window._apply_theme(THEMES[theme])
    tile = window._activity
    reference_size = window._resume_display.name.font().pixelSize()
    for state in _STATES:
        tile.set_state(state)
        qapp.processEvents()
        assert not any(label.text() == "CURRENT ACTION" for label in tile.findChildren(QLabel))
        assert tile.name.font().pixelSize() == round(reference_size * 0.77)
        assert QFontInfo(tile.name.font()).family() == "Nunito"
        assert tile.name.font().weight() == QFont.Weight.DemiBold
        raw_font = QRawFont.fromFont(tile.name.font())
        assert all(raw_font.supportsCharacter(ord(character)) for character in tile.name.text())
        assert window._resume_display.name.font().family() != "Nunito"
        icon, name = tile.icon.geometry(), tile.name.geometry()
        assert tile.size().toTuple() == (112, 108)
        assert icon.size().toTuple() == (64, 64)
        assert tile.icon.pixmap().deviceIndependentSize().toTuple() == (64, 64)
        assert tile.icon.pixmap().devicePixelRatio() == tile.devicePixelRatioF()
        assert abs(icon.center().x() - tile.rect().center().x()) <= 1
        assert abs(name.center().x() - tile.rect().center().x()) <= 1
        assert abs((icon.top() + name.bottom()) / 2 - tile.rect().center().y()) <= 1
        assert icon.top() >= 5 and tile.height() - name.bottom() >= 5
        assert name.top() - icon.bottom() >= 4
        assert tile.name.height() >= tile.name.heightForWidth(tile.name.width())
        assert window.size().toTuple() == size
        assert window._console.height() > 80
        assert "not an application outcome" in tile.toolTip()
        assert tile.accessibleName() == f"Current action: {tile.name.text()}"


@pytest.mark.parametrize("theme", list(THEMES))
def test_activity_border_and_real_halo_follow_stage_and_theme(window, qapp, theme):
    window._apply_theme(THEMES[theme])
    tile = window._activity
    glow = tile.graphicsEffect()
    assert isinstance(glow, QGraphicsDropShadowEffect)
    for state, tone in (
        ("searching_jobs", "information"),
        ("selecting_resume", "accent"),
        ("pausing", "warning"),
        ("error", "error"),
        ("finished", "document"),
    ):
        tile.set_state(state)
        qapp.processEvents()
        expected = QColor(window._palette[tone])
        assert tile.property("tone") == tone
        assert glow.color().rgb() == expected.rgb()
        assert 0 < glow.color().alpha() < 255
        origin = tile.mapTo(window, QPoint(0, 0))
        frame = window.grab().toImage()
        assert frame.pixelColor(origin.x() + tile.width() // 2, origin.y()) == expected
        point = QPoint(origin.x() - 3, origin.y() + tile.height() // 2)
        halo = frame.pixelColor(point)
        glow.setEnabled(False)
        background = window.grab().toImage().pixelColor(point)
        glow.setEnabled(True)
        assert halo != background
        assert sum(
            (a - b) ** 2 for a, b in zip(halo.getRgb()[:3], expected.getRgb()[:3], strict=True)
        ) < sum(
            (a - b) ** 2
            for a, b in zip(background.getRgb()[:3], expected.getRgb()[:3], strict=True)
        )


def test_missing_action_font_is_an_explicit_failure(qapp, monkeypatch):
    from linkedin_easy_apply.gui.activity import QFontDatabase, _load_action_font

    monkeypatch.setattr(QFontDatabase, "addApplicationFont", lambda _path: -1)
    with pytest.raises(ValueError, match="Bundled action font could not be loaded"):
        _load_action_font.__wrapped__()


@pytest.mark.parametrize("theme", list(THEMES))
@pytest.mark.parametrize("size", [(940, 640), (1340, 860)])
def test_activity_and_long_resume_remain_readable_without_expanding_the_window(
    window, qapp, size, theme
):
    filename = "Example_" + "Long_backend_role_" * 12 + ".pdf"
    window.resize(*size)
    window._apply_theme(THEMES[theme])
    snapshot = ActivitySnapshot(activity="verifying_submission", resume_name=filename)
    window._runner.activity.emit(snapshot)
    qapp.processEvents()
    assert window.width() == size[0]
    assert window._activity.isVisible() and window._resume_display.isVisible()
    assert window._activity.name.text() == "Checking submission"
    assert window._resume_display.filename == filename
    assert window._resume_display.name.text().endswith(".pdf")
    assert (
        window._resume_display.name.fontMetrics().horizontalAdvance(
            window._resume_display.name.text()
        )
        <= window._resume_display.name.contentsRect().width()
    )
    assert window._console.height() > 80
    counts = ProgressSnapshot(action="apply").counts | {
        "scanned": 10_000,
        "applied": 12,
        "skipped": 9000,
        "hr_drafted": 3,
        "dry_runs": 2,
        "unconfirmed": 1,
    }
    window._metrics.prepare("apply")
    window._metrics.begin()
    window._runner.progress.emit(
        ProgressSnapshot(action="apply", phase="applying", counts=counts, target=20)
    )
    qapp.processEvents()
    for value, title in zip(window._metrics._values, window._metrics._titles, strict=True):
        assert value.fontMetrics().horizontalAdvance(value.text()) <= value.contentsRect().width()
        assert title.fontMetrics().horizontalAdvance(title.text()) <= title.contentsRect().width()
        assert value.height() >= value.fontMetrics().height()
        assert title.height() >= title.fontMetrics().height()
    assert window._console.height() > 80
    assert max(window._activity.geometry().bottom(), window._metrics.geometry().bottom()) < (
        window._command_preview.y()
    )
    assert window._metrics._target.geometry().bottom() < window._metrics.height()
    assert window._input.geometry().bottom() < window._input.parentWidget().height()
    assert window.height() == size[1]
    for widget in (window._activity, window._activity.icon, window._activity.name):
        _assert_option_help(widget.toolTip())
    help_document = QTextDocument()
    help_document.setHtml(window._resume_display.name.toolTip())
    assert filename in help_document.toPlainText()
    assert "\nExample:" in help_document.toPlainText()
    assert window._activity.icon.mapToGlobal(window._activity.icon.rect().center()).y() < (
        window._activity.name.mapToGlobal(window._activity.name.rect().center()).y()
    )
    before = window._activity.name.text()
    window._runner.progress_error.emit("Fictional interrupted status")
    assert window._activity.name.text() == "Status unavailable"
    assert window._resume_display.filename == filename
    window._runner.activity.emit(snapshot)
    assert window._activity.name.text() == before


def test_filename_and_full_hover_are_plain_text_and_not_rich_content(window):
    filename = "<b>Example & Co.pdf"
    window._runner.activity.emit(
        ActivitySnapshot(activity="preparing_application", resume_name=filename)
    )
    assert window._resume_display.name.textFormat() == Qt.TextFormat.PlainText
    assert window._resume_display.name.value == filename
    document = QTextDocument()
    document.setHtml(window._resume_display.toolTip())
    assert filename in document.toPlainText()
    assert "Example &amp; Co.pdf" in window._resume_display.toolTip()


@pytest.mark.parametrize("prefix", ["", "Previous line\n"])
def test_partial_prompt_flush_and_clear_preserve_previous_text(qapp, prefix):
    console = Console(THEMES["deepseafoam"])
    console.append_text(prefix + "Ans")
    console.append_text("wer: ")
    console.flush()
    console.append_text("next")
    console.flush()
    assert console.toPlainText() == prefix + "Answer: \nnext"
    console.clear()
    console.append_text("Fresh ")
    console.append_text("prompt")
    assert console.toPlainText() == "Fresh prompt"


def test_config_editor_uses_the_canonical_environment_expansion(window, monkeypatch):
    monkeypatch.setenv("LEA_TEST_DAILY_CAP", "22")
    window._config_editor.setPlainText("jobs:\n  max_daily: ${LEA_TEST_DAILY_CAP}\n")
    assert window._validate_yaml(window._config_editor, strict=True)
    window._save_config_text()
    assert window._loaded_config.jobs.max_daily == 22
    assert "${LEA_TEST_DAILY_CAP}" in window._config_file().read_text(encoding="utf-8")


def test_saving_configuration_does_not_discard_unsaved_answers(window, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    before = window._config_file().read_bytes()
    window._answers_editor.setPlainText("full_name: Unsaved Example\n")
    window._answers_editor.document().setModified(True)
    window._config_editor.setPlainText("answers:\n  file: configs/other-answers.yaml\n")
    window._save_config_text()
    assert len(warnings) == 1
    assert window._config_file().read_bytes() == before
    assert window._answers_editor.toPlainText() == "full_name: Unsaved Example\n"
    assert window._answers_editor.document().isModified()


def test_missing_program_reports_failure_once(qapp, tmp_path):
    runner = CommandRunner(tmp_path)
    outcomes = []
    runner.finished.connect(lambda code, message: outcomes.append((code, message)))
    assert not runner.start([str(tmp_path / "missing.exe")])
    qapp.processEvents()
    assert len(outcomes) == 1
    assert outcomes[0][0] == -1
    assert not runner.busy


def test_small_window_keeps_console_and_controls_accessible(window, qapp):
    window.resize(980, 680)
    window._run_settings.customize.setChecked(True)
    qapp.processEvents()
    assert window.width() == 980
    assert window._console.width() > 260
    scroll = window._run_splitter.widget(0)
    assert scroll.verticalScrollBar().maximum() > 0
    assert not window._theme_button.icon().isNull()


def test_log_details_toggle_preserves_output_without_starting_a_command(window, monkeypatch):
    monkeypatch.setattr(
        window._runner, "start", lambda *args: pytest.fail("Details must not start a command")
    )
    raw = (
        "2026-01-01 09:12:34 | INFO     | "
        "linkedin_easy_apply.forms.easy_apply:_fill_field:123 - Example field was filled"
    )
    original_config = window._config_file().read_bytes()
    window._console.append_text(raw + "\nAnswer: ")
    assert "[FORM]" in window._console.toPlainText()
    window._log_details.click()
    assert window._console.toPlainText() == raw + "\nAnswer: "
    window._log_details.click()
    assert "[FORM]" in window._console.toPlainText()
    assert window._console.toPlainText().endswith("\nAnswer: ")
    assert window._config_file().read_bytes() == original_config


@pytest.mark.parametrize(
    ("code", "message", "label", "role"),
    [
        (0, "Finished successfully.", "DONE", "document"),
        (1, "Stopped.", "STOPPED", "warning"),
        (2, "Finished with exit code 2.", "ERROR", "error"),
    ],
)
def test_command_outcome_labels_distinguish_success_stop_and_failure(
    window, code, message, label, role
):
    window._on_finished(code, message)
    cursor = window._console.document().find(f"[{label}]")
    assert not cursor.isNull()
    assert cursor.charFormat().foreground().color().name() == window._palette[role].lower()


def test_readme_run_capture_uses_real_controls_without_execution(
    window, qapp, tmp_path, monkeypatch
):
    from PIL import Image

    from tools.media import capture_screenshots as capture

    started = []
    monkeypatch.setattr(window._runner, "start", lambda *args: started.append(args))
    files = {path: path.read_bytes() for path in (window._root / "configs").iterdir()}
    observed = []
    metrics = []
    activities = []
    previous_resume = window._resume_display.filename
    render = capture._walkthrough_frame

    def observe(widget, caption):
        options = widget._current_options()
        metrics.append((options.action, widget._metrics._snapshot))
        activities.append((widget._activity._state, widget._resume_display.filename))
        if widget._resume_display.filename in {
            "Example_Backend_Resume.pdf",
            "Example_Backend_Tailored.pdf",
        }:
            assert widget._resume_display.name.text() == widget._resume_display.filename
        assert widget._metrics._state == "Offline demo"
        assert widget._metrics.isVisible()
        assert not widget._metrics._timer.isActive()
        observed.append(
            (
                options.action,
                options.dry_run,
                options.list_only,
                options.connect_run_id,
                widget._run_settings.customize.isChecked(),
                widget._run_settings.tabs.currentIndex(),
            )
        )
        return render(widget, caption)

    monkeypatch.setattr(capture, "_walkthrough_frame", observe)
    target = tmp_path / "run.gif"
    capture._capture_run_walkthrough(window, qapp, target)
    assert {state[0] for state in observed} == {"scan", "apply", "reapply", "connect"}
    assert all(state[1] for state in observed if state[0] != "scan")
    assert {state[5] for state in observed if state[4]} == {0, 1, 2, 3}
    assert any(state[0] == "reapply" and state[2] for state in observed)
    assert any(state[0] == "connect" and state[3] == 11 for state in observed)
    assert all(
        snapshot is not None
        and (
            snapshot.action == action or (action == "reapply" and snapshot.action == "reapply-list")
        )
        for action, snapshot in metrics
    )
    preview = next(
        snapshot for _, snapshot in metrics if isinstance(snapshot, RetryPreviewSnapshot)
    )
    assert (preview.targets, preview.prior_attempts, preview.repeated_jobs) == (4, 7, 2)
    apply_counts = [
        snapshot.counts
        for action, snapshot in metrics
        if action == "apply" and snapshot is not None
    ]
    assert apply_counts[0]["scanned"] < apply_counts[-1]["scanned"]
    assert apply_counts[-1]["dry_runs"] > apply_counts[0]["dry_runs"]
    assert all(counts["applied"] == counts["hr_sent"] == 0 for counts in apply_counts)
    assert activities[0] == ("searching_jobs", previous_resume)
    assert ("filling_application", "Example_Backend_Resume.pdf") in activities
    assert ("awaiting_input", "Example_Backend_Resume.pdf") in activities
    assert ("uploading_document", "Example_Backend_Tailored.pdf") in activities
    assert ("reviewing_application", "Example_Backend_Tailored.pdf") in activities
    assert ("connecting", "Example_Backend_Tailored.pdf") in activities
    assert activities[-1][1] == "Example_Backend_Tailored.pdf"
    assert started == [] and not window._runner.busy
    assert files == {path: path.read_bytes() for path in (window._root / "configs").iterdir()}
    assert not (window._root / "logs" / "gui-runs").exists()
    with Image.open(target) as animation:
        assert animation.is_animated and animation.info["loop"] == 0
        states = set()
        for index in range(animation.n_frames):
            animation.seek(index)
            assert animation.info["duration"] >= 1000
            states.add(
                animation.convert("RGB")
                .crop((0, capture.CAPTION_HEIGHT, animation.width, animation.height))
                .tobytes()
            )
        assert len(states) >= 5, "The actual UI, not just captions, must change."


@pytest.mark.parametrize("theme", list(THEMES))
def test_readme_tooltip_capture_preserves_option_help_and_configuration(
    window, qapp, tmp_path, monkeypatch, theme
):
    from PIL import Image, ImageChops

    from tools.media import capture_screenshots as capture

    monkeypatch.setattr(
        window._runner, "start", lambda *args: pytest.fail("A capture cannot start a command")
    )
    window.resize(1340, 860)
    window._apply_theme(THEMES[theme])
    window._run_settings.customize.setChecked(True)
    window._run_settings.tabs.setCurrentIndex(1)
    qapp.processEvents()
    daily = window._run_settings._fields["jobs.max_daily"]
    scroll = window._run_splitter.widget(0)
    scroll.ensureWidgetVisible(daily)
    qapp.processEvents()
    options = window._current_options()
    files = {path: path.read_bytes() for path in (window._root / "configs").iterdir()}
    fields = window.findChildren(QLineEdit)
    help_before = [field.toolTip() for field in fields]
    plain = tmp_path / "plain.png"
    target = tmp_path / "help.png"
    capture._save_screenshot(window, plain)
    capture._save_screenshot(window, target, tooltip_target=daily)
    with Image.open(plain) as before, Image.open(target) as after:
        assert before.size == after.size
        assert ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox()
    _until(qapp, lambda: not QToolTip.isVisible())
    assert help_before == [field.toolTip() for field in fields]
    assert window._current_options() == options
    assert files == {path: path.read_bytes() for path in (window._root / "configs").iterdir()}
    assert not (window._root / "logs" / "gui-runs").exists()
    assert not window._runner.busy


@pytest.mark.parametrize("encoder_fails", [False, True])
def test_readme_tutorial_capture_preserves_parent_and_disposes_dialog(
    window, qapp, tmp_path, monkeypatch, encoder_fails
):
    from PIL import Image, ImageSequence
    from shiboken6 import isValid

    from tools.media import capture_screenshots as capture

    window._config_editor.appendPlainText("# Unsaved example")
    window._input.setText("Unsent example")
    window._console.append_text("Existing example output\n")
    window._console.flush()
    window._settings.sync()
    before = (
        window._current_options(),
        window._config_editor.toPlainText(),
        window._input.text(),
        window._console.toPlainText(),
        Path(window._settings.fileName()).read_bytes(),
    )
    files = {path: path.read_bytes() for path in (window._root / "configs").iterdir()}
    created = []
    dialog_type = capture.TutorialDialog

    def track_dialog(*args, **kwargs):
        guide = dialog_type(*args, **kwargs)
        created.append(guide)
        return guide

    monkeypatch.setattr(capture, "TutorialDialog", track_dialog)
    target = tmp_path / "tutorial.gif"
    if encoder_fails:

        def fail_encoder(*args):
            raise OSError("Example GIF encoder failure")

        monkeypatch.setattr(capture, "_save_gif", fail_encoder)
        with pytest.raises(OSError, match="Example GIF encoder failure"):
            capture._capture_tutorial_walkthrough(window, qapp, target)
    else:
        capture._capture_tutorial_walkthrough(window, qapp, target)
        with Image.open(target) as animation:
            assert animation.is_animated and animation.n_frames >= 5
            states = {
                frame.convert("RGB")
                .crop((0, capture.CAPTION_HEIGHT, frame.width, frame.height))
                .tobytes()
                for frame in ImageSequence.Iterator(animation)
            }
            assert len(states) >= 4, "Tutorial navigation must change the actual guide."
    assert len(created) == 1 and not isValid(created[0])
    assert window.isVisible() and not window._runner.busy
    window._settings.sync()
    assert before == (
        window._current_options(),
        window._config_editor.toPlainText(),
        window._input.text(),
        window._console.toPlainText(),
        Path(window._settings.fileName()).read_bytes(),
    )
    assert files == {path: path.read_bytes() for path in (window._root / "configs").iterdir()}
    assert not (window._root / "logs" / "gui-runs").exists()
