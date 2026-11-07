"""Offline widget and subprocess checks; never open a LinkedIn browser."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from linkedin_easy_apply.config import load_config  # noqa: E402
from linkedin_easy_apply.gui import commands  # noqa: E402
from linkedin_easy_apply.gui.main_window import MainWindow  # noqa: E402
from linkedin_easy_apply.gui.process import CommandRunner  # noqa: E402
from linkedin_easy_apply.gui.theme import THEMES  # noqa: E402
from linkedin_easy_apply.gui.widgets import Console  # noqa: E402


@pytest.fixture(scope="module")
def qapp(tmp_path_factory):
    settings = tmp_path_factory.mktemp("qt-settings")
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(settings))
    app = QApplication.instance() or QApplication([])
    yield app


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
    widget.close()
    qapp.processEvents()


def _until(qapp, predicate, timeout=5):
    end = time.monotonic() + timeout
    while not predicate() and time.monotonic() < end:
        qapp.processEvents()
        QTest.qWait(10)
    assert predicate(), "Timed out waiting for the Qt event path"


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
    monkeypatch.setattr(window, "_run", lambda args: started.append(args))

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
    monkeypatch.setattr(window, "_run", lambda args: calls.append(args))
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: pytest.fail("A retry list cannot submit")
    )
    window._action_box.setCurrentText("Reapply (retry failed/aborted)")
    window._dry_run.setChecked(False)
    window._list_only.setChecked(True)
    QTest.mouseClick(window._start_button, Qt.LeftButton)
    assert "--list" in calls[0]


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
