"""Offline tutorial navigation, resource failures and setup-free startup."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, QTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

from linkedin_easy_apply.gui import main_window  # noqa: E402
from linkedin_easy_apply.gui.process import CommandRunner  # noqa: E402
from linkedin_easy_apply.gui.tutorial import TutorialDialog, load_tutorial  # noqa: E402
from linkedin_easy_apply.runtime import resource_root  # noqa: E402


@pytest.fixture(scope="module")
def qapp(qt_app, tmp_path_factory):
    preferences = tmp_path_factory.mktemp("tutorial-preferences")
    previous_format = QSettings.defaultFormat()
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(preferences))
    yield qt_app
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QSettings.setDefaultFormat(previous_format)


def test_topic_navigation_finish_and_replay(qapp):
    guide = TutorialDialog()
    guide.show()
    qapp.processEvents()
    first = guide._body.toPlainText()
    for field in (guide._topic_list, guide._body, *guide.findChildren(QPushButton)):
        purpose, example = field.toolTip().splitlines()
        assert purpose and example.startswith("Example: ")
    for index in range(guide._topic_list.count()):
        purpose, example = guide._topic_list.item(index).toolTip().splitlines()
        assert purpose and example.startswith("Example: ")
    next_help = guide._next.toolTip()
    assert not guide._back.isEnabled()
    QTest.mouseClick(guide._next, Qt.MouseButton.LeftButton)
    assert guide._topic_list.currentRow() == 1
    assert guide._body.toPlainText() != first
    QTest.mouseClick(guide._back, Qt.MouseButton.LeftButton)
    assert guide._body.toPlainText() == first
    guide._topic_list.setCurrentRow(len(guide._topics) - 1)
    assert guide._next.text() == "Finish"
    assert guide._next.toolTip() != next_help
    assert "Close the tutorial" in guide._next.toolTip()
    assert "\nExample: Finish" in guide._next.toolTip()
    assert not guide._body.openLinks() and not guide._body.openExternalLinks()
    QTest.mouseClick(guide._next, Qt.MouseButton.LeftButton)
    assert guide.result() == QDialog.DialogCode.Accepted
    assert not guide.isVisible()
    guide.show()
    qapp.processEvents()
    QTest.keyClick(guide, Qt.Key.Key_Escape)
    assert guide.result() == QDialog.DialogCode.Rejected
    assert not guide.isVisible()
    guide.deleteLater()


@pytest.mark.parametrize(
    "body",
    ["# No chapters", "## Empty\n", "## Same\nFirst\n## Same\nSecond\n"],
)
def test_invalid_resource_is_an_error(tmp_path, body):
    path = tmp_path / "guide.md"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match="tutorial"):
        load_tutorial(path)


def test_missing_resource_is_not_a_blank_tutorial(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_tutorial(tmp_path / "missing.md")


def test_frozen_tutorial_uses_bundled_guide_not_workspace(qapp, tmp_path, monkeypatch):
    bundled = tmp_path / "bundle" / "docs"
    bundled.mkdir(parents=True)
    (bundled / "gui-tutorial.md").write_text(
        "## Bundled reference\nThis came from the bundle, not the workspace.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundled.parent), raising=False)
    monkeypatch.setenv("LEA_WORKSPACE", str(tmp_path / "missing-workspace"))
    guide = TutorialDialog()
    assert "came from the bundle" in guide._body.toPlainText()
    assert guide._title.text() == "Bundled reference"
    guide.deleteLater()


def test_standalone_opens_without_configuration_database_or_runner(qapp, tmp_path, monkeypatch):
    workspace = tmp_path / "not-initialized"
    monkeypatch.setenv("LEA_WORKSPACE", str(workspace))

    def forbidden(*args, **kwargs):
        pytest.fail("The standalone tutorial must not open private setup or a command runner")

    monkeypatch.setattr(main_window, "MainWindow", forbidden)
    monkeypatch.setattr(main_window, "load_config", forbidden)
    monkeypatch.setattr(CommandRunner, "__init__", forbidden)
    preferences = QSettings(
        QSettings.defaultFormat(), QSettings.Scope.UserScope, main_window._ORG, main_window._APP
    )
    preferences.setValue("theme", "deepseafoam")
    preferences.sync()
    before = Path(preferences.fileName()).read_bytes()
    observed = []
    destroyed = []

    def inspect_and_close():
        dialog = QApplication.activeModalWidget()
        observed.append(isinstance(dialog, TutorialDialog))
        if isinstance(dialog, TutorialDialog):
            dialog.destroyed.connect(lambda *_args: destroyed.append(True))
            dialog.reject()
        qapp.quit()

    QTimer.singleShot(0, inspect_and_close)
    assert main_window.run("missing-config.yaml", "harbor-daylight", tutorial=True) == 0
    assert observed == [True]
    assert destroyed == [True], "The tutorial must be destroyed before QApplication shutdown"
    assert not workspace.exists()
    preferences.sync()
    assert Path(preferences.fileName()).read_bytes() == before


@pytest.mark.parametrize("console", [False, True])
def test_frozen_entry_tutorial_bypasses_first_run_preparation(monkeypatch, console):
    source = resource_root() / "packaging" / "windows" / "entry.py"
    spec = importlib.util.spec_from_file_location("tutorial_windows_entry", source)
    assert spec and spec.loader
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    monkeypatch.setattr(
        entry, "prepare_workspace", lambda: pytest.fail("Tutorial must not prepare a workspace")
    )
    called = []
    executable = "lea.exe" if console else "EasyApplyAutomaton.exe"
    monkeypatch.setattr(sys, "executable", executable)
    if console:
        from linkedin_easy_apply.cli import main as cli

        monkeypatch.setattr(cli, "app", lambda: called.append("console"))
        monkeypatch.setattr(sys, "argv", [executable, "gui", "--tutorial"])
    else:
        monkeypatch.setattr(main_window, "run", lambda **kwargs: called.append(kwargs) or 0)
        monkeypatch.setattr(sys, "argv", [executable, "--tutorial", "--theme", "deepseafoam"])
    assert entry.main() == 0
    assert called == (["console"] if console else [{"theme": "deepseafoam", "tutorial": True}])
