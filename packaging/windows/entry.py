"""Shared frozen entrypoint; the executable name selects GUI or console."""

from __future__ import annotations

import argparse
import io
import json
import multiprocessing
import os
import sys
from pathlib import Path

from linkedin_easy_apply.runtime import prepare_workspace


def _smoke_gui(report: Path) -> int:
    from playwright.sync_api import sync_playwright
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    from linkedin_easy_apply import __version__
    from linkedin_easy_apply.gui.main_window import MainWindow
    from linkedin_easy_apply.gui.tutorial import CUSTOMIZE_TOPIC, TutorialDialog

    with sync_playwright() as playwright:
        driver_ready = playwright.chromium.name == "chromium"

    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(Path.cwd() / "smoke-settings")
    )
    application = QApplication([])
    window = MainWindow("configs\\config.yaml")
    output: list[str] = []
    window._runner.output.connect(output.append)
    result: dict[str, object] = {"ok": False, "error": "GUI child command timed out"}

    def finished(code: int, status: str) -> None:
        rendered = not window.grab().isNull()
        try:
            tutorial = TutorialDialog(window, start_topic=CUSTOMIZE_TOPIC)
        except (OSError, UnicodeError, ValueError) as exc:
            result["error"] = f"Tutorial unavailable: {exc}"
            application.quit()
            return
        tutorial.show()
        application.processEvents()
        tutorial_rendered = not tutorial.grab().isNull()
        tutorial_topics = len(tutorial._topics)
        tutorial.close()
        ok = (
            code == 0
            and __version__ in "".join(output)
            and rendered
            and driver_ready
            and tutorial_rendered
        )
        result.update(
            ok=ok,
            cli_exit_code=code,
            cli_status=status,
            playwright_driver=driver_ready,
            rendered=rendered,
            tutorial_rendered=tutorial_rendered,
            tutorial_topics=tutorial_topics,
            output="".join(output),
            version=__version__,
        )
        result.pop("error", None)
        application.quit()

    window._runner.finished.connect(finished)
    window.show()
    QTimer.singleShot(0, lambda: window._run(["version"]))
    QTimer.singleShot(15000, application.quit)
    application.exec()
    if window._runner.busy:
        window._runner.stop()
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(window, QEvent.Type.DeferredDelete)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


def main() -> int:
    multiprocessing.freeze_support()
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    if Path(sys.executable).stem.casefold() == "lea":
        from linkedin_easy_apply.cli.main import app

        if "--tutorial" not in sys.argv[1:]:
            os.chdir(prepare_workspace())
        app()
        return 0

    from PySide6.QtWidgets import QApplication, QMessageBox

    from linkedin_easy_apply.gui.main_window import run

    parser = argparse.ArgumentParser(description="Easy Apply Automaton desktop")
    parser.add_argument("--config", default="configs\\config.yaml")
    parser.add_argument("--theme", choices=("deepseafoam", "harbor-daylight"))
    parser.add_argument("--tutorial", action="store_true", help="Open only the offline tutorial")
    parser.add_argument("--smoke-report", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.tutorial:
        try:
            return run(theme=args.theme, tutorial=True)
        except (OSError, UnicodeError, ValueError) as exc:
            application = QApplication.instance() or QApplication([])
            QMessageBox.critical(None, "Tutorial unavailable", str(exc))
            application.quit()
            return 1
    try:
        os.chdir(prepare_workspace())
    except OSError as exc:
        if args.smoke_report:
            args.smoke_report.write_text(
                json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8"
            )
        else:
            application = QApplication([])
            QMessageBox.critical(None, "Workspace unavailable", str(exc))
            application.quit()
        return 1
    if args.smoke_report:
        return _smoke_gui(args.smoke_report)
    return run(config_path=args.config, theme=args.theme)


if __name__ == "__main__":
    raise SystemExit(main())
