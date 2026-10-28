"""Tests for the GUI → CLI command builders.

The GUI never reimplements behaviour: each control maps to an ``apply.py``
invocation built here. These tests pin the flags against the real Typer
signatures, including the two commands that genuinely do not accept
``--config`` (``init`` and ``version``) and would exit with a usage error if
one were passed.

This module must import without PySide6 installed.
"""

from __future__ import annotations

import pytest

from linkedin_easy_apply.cli.main import app as cli_app
from linkedin_easy_apply.gui import commands


def _args(**kwargs) -> list[str]:
    return commands.run_args(commands.RunOptions(**kwargs))


# -- scan -------------------------------------------------------------------- #
def test_scan_is_minimal():
    assert _args(action="scan", config="c.yaml") == ["scan", "--config", "c.yaml"]


def test_scan_takes_limit_and_url():
    args = _args(action="scan", config="c.yaml", limit=20, url="https://example.com/jobs")
    assert args == [
        "scan",
        "--config",
        "c.yaml",
        "--limit",
        "20",
        "--url",
        "https://example.com/jobs",
    ]


def test_scan_never_gets_submission_flags():
    """Scan has no --dry-run/--yes/--ignore-score; passing them would be a usage error."""
    args = _args(action="scan", config="c.yaml", dry_run=True, ignore_score=True, assume_yes=True)
    assert args == ["scan", "--config", "c.yaml"]


# -- apply ------------------------------------------------------------------- #
def test_apply_defaults_to_unattended():
    args = _args(action="apply", config="c.yaml")
    assert "--no-confirm-submit" in args
    assert "--yes" in args
    assert "--dry-run" not in args


def test_apply_dry_run_and_ignore_score():
    args = _args(action="apply", config="c.yaml", dry_run=True, ignore_score=True)
    assert "--dry-run" in args
    assert "--ignore-score" in args


def test_apply_outreach_tristate():
    assert "--message-hiring-team" in _args(action="apply", message_hiring_team=True)
    assert "--no-message-hiring-team" in _args(action="apply", message_hiring_team=False)
    neutral = _args(action="apply", message_hiring_team=None)
    assert not [a for a in neutral if "message-hiring-team" in a]


def test_confirm_submit_suppresses_yes():
    """--yes would make the confirmation prompt pointless; never emit both."""
    args = _args(action="apply", confirm_submit=True, assume_yes=True)
    assert "--confirm-submit" in args
    assert "--yes" not in args


def test_verbose_precedes_the_subcommand():
    """--verbose lives on the Typer callback, so it must come first."""
    args = _args(action="apply", verbose=True)
    assert args[0] == "--verbose"
    assert args[1] == "apply"


# -- reapply / connect ------------------------------------------------------- #
def test_reapply_has_no_url():
    args = _args(action="reapply", config="c.yaml", url="https://example.com")
    assert "--url" not in args


def test_reapply_list_only():
    assert "--list" in _args(action="reapply", list_only=True)


def test_connect_flags():
    args = _args(action="connect", config="c.yaml", dry_run=True, connect_run_id=7, limit=3)
    assert args == [
        "connect",
        "--config",
        "c.yaml",
        "--limit",
        "3",
        "--dry-run",
        "--run",
        "7",
        "--yes",
    ]


def test_unknown_action_is_rejected():
    with pytest.raises(ValueError, match="Unknown run action"):
        _args(action="delete-everything")


# -- tools ------------------------------------------------------------------- #
def test_tool_without_value():
    assert commands.tool_args("Sign in to LinkedIn", "c.yaml") == ["login", "--config", "c.yaml"]


def test_tool_with_value():
    args = commands.tool_args("Preview résumé choice", "c.yaml", "  Backend Engineer ")
    assert args == ["resume-test", "Backend Engineer", "--config", "c.yaml"]


def test_tool_requiring_value_rejects_blank():
    with pytest.raises(ValueError, match="needs a value"):
        commands.tool_args("Recognise a question", "c.yaml", "   ")


@pytest.mark.parametrize("label", ["Scaffold example configs", "Show version"])
def test_tools_without_config_option(label: str):
    """init and version have no --config; adding one is a Typer usage error."""
    assert "--config" not in commands.tool_args(label, "c.yaml")


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="Unknown tool"):
        commands.tool_args("Format my hard drive", "c.yaml")


# -- other commands ---------------------------------------------------------- #
def test_dashboard_args():
    assert commands.dashboard_args("c.yaml") == ["dashboard", "--config", "c.yaml"]


def test_export_args():
    assert commands.export_args("c.yaml", "out.xlsx", "xlsx") == [
        "export",
        "--config",
        "c.yaml",
        "--output",
        "out.xlsx",
        "--format",
        "xlsx",
    ]


def test_export_rejects_unknown_format():
    with pytest.raises(ValueError, match="Unsupported export format"):
        commands.export_args("c.yaml", "out.pdf", "pdf")


def test_sync_answers_pairs_apply_with_yes():
    """--apply prompts in the terminal, which a GUI console cannot answer."""
    assert commands.sync_answers_args("c.yaml") == ["sync-answers", "--config", "c.yaml"]
    applied = commands.sync_answers_args("c.yaml", apply_changes=True)
    assert applied[-2:] == ["--apply", "--yes"]


# -- argv assembly ----------------------------------------------------------- #
def test_full_argv_uses_entry_script():
    argv = commands.full_argv(["scan"], python="py.exe", script=commands.entry_script())
    assert argv[0] == "py.exe"
    assert argv[1].endswith("apply.py")
    assert argv[2] == "scan"


def test_entry_script_exists():
    assert commands.entry_script().is_file()


def test_describe_quotes_arguments():
    rendered = commands.describe(["py", "apply.py", "scan", "--url", "a b"])
    assert "'a b'" in rendered or '"a b"' in rendered


# -- the CLI really has these commands and flags ----------------------------- #
def _registered_commands() -> set[str]:
    names = set()
    for command in cli_app.registered_commands:
        names.add(command.name or (command.callback.__name__.replace("_", "-")))
    return names


def test_every_generated_command_exists_in_the_cli():
    generated = {
        *commands.RUN_ACTIONS.values(),
        *(tool.command for tool in commands.TOOLS.values()),
        "dashboard",
        "export",
        "sync-answers",
        "gui",
    }
    assert generated <= _registered_commands()
