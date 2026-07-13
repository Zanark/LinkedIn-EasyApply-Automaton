"""The ``lea`` command line interface.

Commands
--------
* ``apply``        run the Easy Apply automation
* ``scan``         discover & score jobs without applying
* ``stats``        print database statistics
* ``export``       export jobs/applications to CSV or XLSX
* ``dashboard``    launch the Streamlit dashboard
* ``resume-test``  show which resume would be selected for a job
* ``test-form``    recognise & resolve a single question (offline)
* ``test-browser`` launch the browser and verify the logged-in session
* ``login``        open the browser to sign in to LinkedIn once
* ``init``         scaffold example configuration files
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from linkedin_easy_apply import __version__
from linkedin_easy_apply.config import AppConfig, ConfigError, load_config
from linkedin_easy_apply.config.models import SearchConfig, SearchEntry
from linkedin_easy_apply.database import Database
from linkedin_easy_apply.logging import setup_logging

app = typer.Typer(
    name="lea",
    help="LinkedIn Easy Apply Automaton - automate the LinkedIn Easy Apply workflow.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()

_DEFAULT_CONFIG = Path("configs/config.yaml")
_EXAMPLES = Path(__file__).resolve().parents[2] / "configs"

# Set by the top-level --verbose/-v flag; forces DEBUG logging when true.
_verbose = False


@app.callback()
def _main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose DEBUG logging - narrate every decision, data lookup and outcome.",
    ),
) -> None:
    """LinkedIn Easy Apply Automaton."""
    global _verbose
    _verbose = verbose


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _load(config_path: Path) -> AppConfig:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=2) from exc
    if _verbose:
        config.logging.level = "DEBUG"
    setup_logging(config.logging)
    return config


def _load_answers(config: AppConfig):
    from linkedin_easy_apply.answers.store import AnswerStore

    try:
        return AnswerStore.from_yaml(config.answers.file)
    except FileNotFoundError:
        console.print(
            f"[red]Answers file not found:[/red] {config.answers.file}. "
            "Run 'lea init' or point 'answers.file' at your answers.yaml."
        )
        raise typer.Exit(code=2) from None


def _database(config: AppConfig) -> Database:
    db = Database(config.database.path)
    db.initialize()
    return db


def _interactive_unknown(question: str, screenshot):  # noqa: ANN001
    shot = f" (screenshot: {screenshot})" if screenshot else ""
    console.print(f"[yellow]Unknown question:[/yellow] {question}{shot}")
    answer = typer.prompt("Your answer (leave blank to skip)", default="", show_default=False)
    return answer or None


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"linkedin-easy-apply {__version__}")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config files."),
) -> None:
    """Scaffold example configuration files into ./configs and create directories."""
    for directory in ("configs", "resumes", "logs", "screenshots", "database"):
        Path(directory).mkdir(parents=True, exist_ok=True)

    pairs = [
        ("config.example.yaml", "config.yaml"),
        ("answers.example.yaml", "answers.yaml"),
        ("searches.example.yaml", "searches.yaml"),
    ]
    for example, target_name in pairs:
        source = _EXAMPLES / example
        target = Path("configs") / target_name
        if not source.exists():
            continue
        if target.exists() and not force:
            console.print(f"[dim]skip[/dim] {target} (exists)")
            continue
        shutil.copyfile(source, target)
        console.print(f"[green]created[/green] {target}")
    console.print(
        "\nNext: edit configs/config.yaml and configs/answers.yaml, then run 'lea apply --dry-run'."
    )


@app.command()
def apply(
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c", help="Path to config.yaml."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect and fill but never submit."),
    interactive: bool | None = typer.Option(
        None, "--interactive/--no-interactive", help="Confirm before each submit."
    ),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Max applications this run."),
    url: str | None = typer.Option(None, "--url", help="Override searches with a single URL."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Never prompt; auto-answer/submit."),
) -> None:
    """Run the Easy Apply automation."""
    cfg = _load(config)
    if url:
        cfg.search = SearchConfig(searches=[SearchEntry(name="cli", url=url)])
    _run_orchestrator(
        cfg, mode="apply", dry_run=dry_run, interactive=interactive, limit=limit, yes=yes
    )


@app.command()
def scan(
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
    limit: int | None = typer.Option(None, "--limit", "-n", help="Max jobs to scan."),
    url: str | None = typer.Option(None, "--url", help="Override searches with a single URL."),
) -> None:
    """Discover and score jobs without applying."""
    cfg = _load(config)
    if url:
        cfg.search = SearchConfig(searches=[SearchEntry(name="cli", url=url)])
    _run_orchestrator(cfg, mode="scan", dry_run=False, interactive=False, limit=limit, yes=True)


def _run_orchestrator(
    cfg: AppConfig,
    *,
    mode: str,
    dry_run: bool,
    interactive: bool | None,
    limit: int | None,
    yes: bool,
) -> None:
    from linkedin_easy_apply.orchestrator import Orchestrator

    answers = _load_answers(cfg)
    db = _database(cfg)

    prompts = not yes
    on_unknown = _interactive_unknown if prompts else None
    on_confirm: Callable[[Any], bool] | None = None
    if interactive and prompts:

        def _confirm(job: Any) -> bool:
            return typer.confirm(f"Submit application to {job.summary}?")

        on_confirm = _confirm

    orchestrator = Orchestrator(
        cfg, db, answers, on_unknown=on_unknown, on_confirm_submit=on_confirm
    )
    try:
        summary = orchestrator.run(
            mode=mode, dry_run=dry_run, interactive=bool(interactive), limit=limit
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Run failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title=f"Run #{summary.run_id} ({summary.mode})")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Scanned", str(summary.scanned))
    table.add_row("Applied", f"[green]{summary.applied}[/green]")
    table.add_row("Skipped", str(summary.skipped))
    table.add_row("Failed", f"[red]{summary.failed}[/red]")
    console.print(table)
    if summary.skip_reasons:
        console.print(
            "[dim]Skip reasons:[/dim] "
            + ", ".join(f"{k}={v}" for k, v in summary.skip_reasons.items())
        )


@app.command()
def stats(config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c")) -> None:
    """Print database statistics."""
    cfg = _load(config)
    db = _database(cfg)
    data = db.stats()

    table = Table(title="LinkedIn Easy Apply - Statistics")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key in (
        "total_jobs",
        "easy_apply_jobs",
        "applications_total",
        "applications_submitted",
        "applications_today",
        "applications_failed",
        "runs",
        "errors",
        "distinct_questions",
    ):
        table.add_row(key.replace("_", " ").title(), str(data[key]))
    console.print(table)

    if data["top_companies"]:
        comp = Table(title="Top Companies")
        comp.add_column("Company")
        comp.add_column("Applications", justify="right")
        for row in data["top_companies"]:
            comp.add_row(str(row["company"]), str(row["applications"]))
        console.print(comp)


@app.command()
def export(
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
    output: Path = typer.Option(Path("applications.csv"), "--output", "-o"),
    fmt: str = typer.Option("csv", "--format", "-f", help="csv or xlsx."),
) -> None:
    """Export applications (joined with jobs) to CSV or XLSX."""
    cfg = _load(config)
    db = _database(cfg)
    rows = db.query("""SELECT a.id, j.title, j.company, j.location, j.url, a.status, a.reason,
                  a.steps, a.started_at, a.finished_at
           FROM applications a JOIN jobs j ON a.job_id = j.id
           ORDER BY a.started_at DESC""")
    if not rows:
        console.print("[yellow]No applications to export.[/yellow]")
        return

    if fmt == "xlsx":
        _export_xlsx(rows, output)
    else:
        _export_csv(rows, output)
    console.print(f"[green]Exported[/green] {len(rows)} rows to {output}")


def _export_csv(rows, output: Path) -> None:  # noqa: ANN001
    import csv

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _export_xlsx(rows, output: Path) -> None:  # noqa: ANN001
    try:
        from openpyxl import Workbook
    except ImportError:
        console.print("[red]openpyxl not installed.[/red] Install with 'pip install .[export]'.")
        raise typer.Exit(code=2) from None
    wb = Workbook()
    ws = wb.active
    ws.title = "Applications"
    ws.append(list(rows[0].keys()))
    for row in rows:
        ws.append(list(row.values()))
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)


@app.command()
def dashboard(config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c")) -> None:
    """Launch the Streamlit dashboard."""
    import os
    import subprocess

    dashboard_app = Path(__file__).resolve().parents[1] / "dashboard" / "app.py"
    env = os.environ.copy()
    env["LEA_CONFIG"] = str(config)
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(dashboard_app)], env=env, check=False
        )
    except FileNotFoundError:
        console.print(
            "[red]Streamlit not installed.[/red] Install with 'pip install .[dashboard]'."
        )
        raise typer.Exit(code=2) from None


@app.command(name="resume-test")
def resume_test(
    title: str = typer.Argument(..., help="Job title to test."),
    description: str = typer.Option("", "--description", "-d"),
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
) -> None:
    """Show which resume would be selected for a job title/description."""
    from linkedin_easy_apply.answers.resume_selector import ResumeSelector

    cfg = _load(config)
    choice = ResumeSelector(cfg.resume).select(title, description)
    if choice is None:
        console.print("[yellow]No resume selected[/yellow] (check resume.directory / mapping).")
        return
    console.print(f"[green]{choice.name}[/green] -> {choice.path}\n[dim]{choice.reason}[/dim]")


@app.command(name="test-form")
def test_form(
    question: str = typer.Argument(..., help="A question to recognise and resolve."),
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
) -> None:
    """Recognise a question and resolve it against your answers (offline)."""
    from linkedin_easy_apply.answers.resolver import AnswerResolver
    from linkedin_easy_apply.parser import QuestionParser

    cfg = _load(config)
    answers = _load_answers(cfg)
    parser = QuestionParser(
        skills=answers.known_skills(), fuzzy_threshold=cfg.answers.fuzzy_threshold
    )
    parsed = parser.parse(question)
    resolution = AnswerResolver(answers).resolve(parsed)

    table = Table(title="Question analysis")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Category", parsed.category.value)
    table.add_row("Skill", parsed.skill or "-")
    table.add_row("Answer type", parsed.answer_type.value)
    table.add_row("Confidence", f"{parsed.confidence:.2f}")
    table.add_row("Resolved", "yes" if resolution.found else "no")
    table.add_row("Answer", str(resolution.value) if resolution.found else "-")
    console.print(table)


@app.command(name="test-browser")
def test_browser(
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
    url: str = typer.Option("https://www.linkedin.com/feed/", "--url"),
) -> None:
    """Launch the browser with your profile and verify the session."""
    from linkedin_easy_apply.browser import BrowserLaunchError, BrowserManager
    from linkedin_easy_apply.utils.screenshots import ScreenshotManager

    cfg = _load(config)
    try:
        with BrowserManager(cfg.browser) as browser:
            browser.page.goto(url, wait_until="domcontentloaded")
            browser.page.wait_for_timeout(3000)
            shot = ScreenshotManager(cfg.screenshots.directory, True).capture(
                browser.page, "test-browser"
            )
            console.print(f"[green]Opened[/green] {url}")
            console.print(f"Page title: {browser.page.title()}")
            if shot:
                console.print(f"Screenshot: {shot}")
    except BrowserLaunchError as exc:
        console.print(f"[red]Browser launch failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def login(
    config: Path = typer.Option(_DEFAULT_CONFIG, "--config", "-c"),
) -> None:
    """Open the browser so you can sign in to LinkedIn once (session is reused)."""
    from linkedin_easy_apply.browser import BrowserLaunchError, BrowserManager

    cfg = _load(config)
    try:
        with BrowserManager(cfg.browser) as browser:
            browser.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            console.print(
                "[cyan]A browser window is open.[/cyan] Sign in to LinkedIn there, "
                "then return here.\nYour session is saved to the browser profile "
                f"([dim]{cfg.browser.profile_path or '.browser-profile'}[/dim]) and "
                "reused on future runs."
            )
            typer.prompt(
                "Press Enter when you have finished signing in",
                default="",
                show_default=False,
            )
            console.print(f"[green]Signed in as:[/green] {browser.page.title()}")
    except BrowserLaunchError as exc:
        console.print(f"[red]Browser launch failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":  # pragma: no cover
    app()
