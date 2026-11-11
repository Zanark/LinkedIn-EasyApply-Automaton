from __future__ import annotations

import sys

import pytest
import yaml

from linkedin_easy_apply import runtime
from linkedin_easy_apply.config import ConfigError, load_config
from linkedin_easy_apply.gui import commands
from linkedin_easy_apply.gui.settings import write_run_config


def test_first_launch_copies_examples_but_upgrade_preserves_user_files(tmp_path, monkeypatch):
    resources = tmp_path / "resources" / "configs"
    resources.mkdir(parents=True)
    for name in ("config", "answers", "searches"):
        (resources / f"{name}.example.yaml").write_text(f"{name}: example\n", encoding="utf-8")
    workspace = tmp_path / "user-data"
    monkeypatch.setenv("LEA_WORKSPACE", str(workspace))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(resources.parent), raising=False)
    assert runtime.prepare_workspace() == workspace
    config = workspace / "configs" / "config.yaml"
    config.write_text("custom: preserved\n", encoding="utf-8")
    runtime.prepare_workspace()
    assert config.read_text(encoding="utf-8") == "custom: preserved\n"
    assert (workspace / "configs" / "answers.yaml").is_file()


def test_frozen_child_uses_console_executable_not_python(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "EasyApplyAutomaton.exe"))
    assert commands.full_argv(["version"]) == [str(tmp_path / "lea.exe"), "version"]


def test_private_preset_preserves_environment_references_and_saved_source(tmp_path, monkeypatch):
    monkeypatch.setenv("EXAMPLE_DAILY_CAP", "29")
    source = tmp_path / "config.yaml"
    source.write_text(
        "jobs:\n  max_daily: ${EXAMPLE_DAILY_CAP}\nlogging:\n  level: WARNING\n",
        encoding="utf-8",
    )
    original = source.read_bytes()
    preset = write_run_config(source, {"browser.headless": True}, tmp_path)
    assert load_config(preset).jobs.max_daily == 29
    assert load_config(preset).browser.headless
    assert yaml.safe_load(preset.read_text(encoding="utf-8"))["jobs"]["max_daily"] == (
        "${EXAMPLE_DAILY_CAP}"
    )
    assert source.read_bytes() == original


def test_invalid_preset_fails_and_is_not_left_as_a_valid_run_file(tmp_path):
    source = tmp_path / "config.yaml"
    source.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="job_urls"):
        write_run_config(source, {"search.job_urls": ["not a LinkedIn job"]}, tmp_path)
    assert list((tmp_path / "logs" / "gui-runs").iterdir()) == []


@pytest.mark.parametrize("text", ["[]", "false", "0"])
def test_falsy_nonmapping_source_is_not_silently_replaced_by_defaults(tmp_path, text):
    source = tmp_path / "config.yaml"
    source.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        write_run_config(source, {"browser.headless": True}, tmp_path)
    assert not (tmp_path / "logs").exists()
    assert source.read_text(encoding="utf-8") == text
