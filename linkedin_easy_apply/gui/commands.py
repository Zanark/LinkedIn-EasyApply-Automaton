"""Argument builders shared by the GUI and the command line.

Every button in the desktop app resolves to an ``apply.py`` invocation built
here, so the GUI can never grow behaviour the CLI does not have. These helpers
are pure data transformations - no Qt, no subprocesses - which keeps them unit
testable and makes the exact command visible to the user before it runs.
"""

from __future__ import annotations

import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "RUN_ACTIONS",
    "TOOLS",
    "RunOptions",
    "describe",
    "entry_script",
    "full_argv",
    "run_args",
    "tool_args",
]


def entry_script() -> Path:
    """Absolute path to ``apply.py`` at the repository root."""
    return Path(__file__).resolve().parents[2] / "apply.py"


# -- run actions ------------------------------------------------------------ #
# label -> CLI sub-command. These are the long-running crawls, i.e. everything
# that drives a browser.
RUN_ACTIONS: dict[str, str] = {
    "Scan (score only, never applies)": "scan",
    "Apply": "apply",
    "Reapply (retry failed/aborted)": "reapply",
    "Connect (send pending invitations)": "connect",
}

@dataclass(frozen=True)
class Tool:
    """A one-shot CLI command the Tools page can run."""

    command: str
    hint: str = ""  # placeholder text; empty means the tool takes no value
    accepts_config: bool = True

    @property
    def needs_value(self) -> bool:
        return bool(self.hint)


# ``init`` and ``version`` genuinely have no --config option; passing one would
# make Typer exit with a usage error.
TOOLS: dict[str, Tool] = {
    "Sign in to LinkedIn": Tool("login"),
    "Verify browser session": Tool("test-browser"),
    "Database statistics": Tool("stats"),
    "Scaffold example configs": Tool("init", accepts_config=False),
    "Show version": Tool("version", accepts_config=False),
    "Preview résumé choice": Tool("resume-test", "Job title, e.g. Senior Backend Engineer"),
    "Recognise a question": Tool("test-form", "Question, e.g. Years of Java experience?"),
}


@dataclass
class RunOptions:
    """Everything the Run page can vary for one crawl."""

    action: str = "scan"
    config: str = "configs/config.yaml"
    limit: int | None = None
    url: str | None = None
    dry_run: bool = False
    ignore_score: bool = False
    confirm_submit: bool = False
    message_hiring_team: bool | None = None
    assume_yes: bool = True
    verbose: bool = False
    # connect-only
    connect_run_id: int | None = None
    # reapply-only
    list_only: bool = False
    extra: list[str] = field(default_factory=list)


def _common(options: RunOptions) -> list[str]:
    args = ["--config", options.config]
    if options.limit is not None:
        args += ["--limit", str(options.limit)]
    return args


def run_args(options: RunOptions) -> list[str]:
    """Build the CLI arguments for a run action.

    Raises ``ValueError`` for an unknown action rather than guessing, so a typo
    can never silently turn an apply into a scan.
    """
    action = options.action
    if action not in set(RUN_ACTIONS.values()):
        raise ValueError(f"Unknown run action: {action!r}")

    args: list[str] = []
    if options.verbose:
        args.append("--verbose")
    args.append(action)
    args += _common(options)

    if action == "scan":
        if options.url:
            args += ["--url", options.url]
        return args + options.extra

    if action == "connect":
        if options.dry_run:
            args.append("--dry-run")
        if options.connect_run_id is not None:
            args += ["--run", str(options.connect_run_id)]
        if options.assume_yes:
            args.append("--yes")
        return args + options.extra

    # apply / reapply share the submission-flow flags
    if options.dry_run:
        args.append("--dry-run")
    args.append("--confirm-submit" if options.confirm_submit else "--no-confirm-submit")
    if options.ignore_score:
        args.append("--ignore-score")
    if options.message_hiring_team is not None:
        args.append(
            "--message-hiring-team" if options.message_hiring_team else "--no-message-hiring-team"
        )
    if action == "apply" and options.url:
        args += ["--url", options.url]
    if action == "reapply" and options.list_only:
        args.append("--list")
    if options.assume_yes and not options.confirm_submit:
        args.append("--yes")
    return args + options.extra


def tool_args(tool: str, config: str, value: str = "") -> list[str]:
    """Build the CLI arguments for a one-shot tool command."""
    if tool not in TOOLS:
        raise ValueError(f"Unknown tool: {tool!r}")
    spec = TOOLS[tool]
    args = [spec.command]
    if spec.needs_value:
        if not value.strip():
            raise ValueError(f"'{tool}' needs a value")
        args.append(value.strip())
    if spec.accepts_config:
        args += ["--config", config]
    return args


def dashboard_args(config: str) -> list[str]:
    """Arguments that launch the Streamlit dashboard through the CLI."""
    return ["dashboard", "--config", config]


def export_args(config: str, output: str, fmt: str = "csv") -> list[str]:
    """Arguments for the data export command."""
    if fmt not in {"csv", "xlsx"}:
        raise ValueError(f"Unsupported export format: {fmt!r}")
    return ["export", "--config", config, "--output", output, "--format", fmt]


def sync_answers_args(config: str, *, apply_changes: bool = False) -> list[str]:
    """Arguments for the answer-quality sync command.

    ``--apply`` prompts for confirmation in the terminal, which a GUI console
    cannot answer, so it is always paired with ``--yes``.
    """
    args = ["sync-answers", "--config", config]
    if apply_changes:
        args += ["--apply", "--yes"]
    return args


def full_argv(
    args: list[str], *, python: str | None = None, script: Path | None = None
) -> list[str]:
    """Prefix *args* with the interpreter and ``apply.py``.

    The GUI always runs the *current* interpreter so a virtual environment is
    inherited automatically.
    """
    return [python or sys.executable, str(script or entry_script()), *args]


def describe(argv: list[str]) -> str:
    """Render *argv* as a copy-pasteable command line."""
    return " ".join(shlex.quote(part) for part in argv)
