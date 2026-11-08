"""Capture README screenshots of the desktop GUI.

    .\\.venv\\Scripts\\python.exe tools\\capture_screenshots.py

Works on a normal desktop *and* headless (``QT_QPA_PLATFORM=offscreen``). A
headless Qt reports **zero font families**, and every glyph then renders as an
empty box - visually obvious, but invisible to a colour check, which is exactly
how a set of unreadable screenshots once got committed. So this script:

1. registers real font files itself when the font database is empty, and
2. refuses to write anything until a **tofu self-test** passes.

The self-test draws ``iiiiiiiiii`` and ``WWWWWWWWWW`` and compares the ink. In a
real font the W line has several times more ink; with missing-glyph boxes both
lines are identical rectangles and the ratio is 1.00.
"""

from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
# Running a script inside tools/ puts tools/ on sys.path, not the repository
# root, so the local package would lose to anything already installed.
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from linkedin_easy_apply.gui.main_window import MainWindow  # noqa: E402
from linkedin_easy_apply.gui.theme import THEMES  # noqa: E402
from linkedin_easy_apply.gui.tutorial import CUSTOMIZE_TOPIC, TutorialDialog  # noqa: E402

OUT = ROOT / "docs" / "images"
WINDOWS_FONTS = Path(r"C:\Windows\Fonts")
# UI font first; the console falls back through these in the stylesheet.
FONT_FILES = (
    "segoeui.ttf",
    "segoeuib.ttf",
    "consola.ttf",
    "consolab.ttf",
    "CascadiaMono.ttf",
    "CascadiaCode.ttf",
    "arial.ttf",
)

SAMPLE_LOG = (
    "ILLUSTRATIVE OFFLINE PREVIEW - no browser or application was started.\n"
    "2026-10-28 15:04:10 | DEBUG    | linkedin_easy_apply.logging.setup:setup_logging:61 - "
    "Logging initialised at level DEBUG\n"
    "2026-10-28 15:04:11 | INFO     | linkedin_easy_apply.orchestrator:run:201 - "
    "Run starting: mode=apply dry_run=True interactive=True max_per_run=5\n"
    "2026-10-28 15:04:11 | INFO     | linkedin_easy_apply.browser.manager:start:70 - "
    "Launching edge (headless=False) with profile .browser-profile\n"
    "2026-10-28 15:04:18 | INFO     | linkedin_easy_apply.jobs.search:iterate:58 - "
    "Collected 25 job id(s) from 'software-engineer'\n"
    "2026-10-28 15:04:21 | INFO     | linkedin_easy_apply.orchestrator:_process_job:431 - "
    "[SCORE PASS] 42/20 | Senior Backend Engineer at Acme Cloud\n"
    "2026-10-28 15:04:26 | SUCCESS  | linkedin_easy_apply.forms.easy_apply:submit:241 - "
    "Dry run reached Submit - Senior Backend Engineer at Acme Cloud (not sent)\n"
    "2026-10-28 15:04:29 | INFO     | linkedin_easy_apply.orchestrator:_process_job:452 - "
    "Skip (score 12 < 20) - Staff Rust Engineer at Globex\n"
    "2026-10-28 15:04:33 | WARNING  | linkedin_easy_apply.jobs.search:_report_empty_results:402 - "
    "No job cards found on https://www.linkedin.com/jobs/search\n"
)

# (page index, file-name stem, theme key)
SHOTS: list[tuple[int, str, str]] = [
    (0, "run", "deepseafoam"),
    (0, "run", "harbor-daylight"),
    (1, "config", "deepseafoam"),
    (2, "answers", "harbor-daylight"),
    (3, "data", "deepseafoam"),
    (4, "tools", "deepseafoam"),
    (0, "settings", "deepseafoam"),
    (0, "small", "harbor-daylight"),
]
TUTORIAL_THEMES = ("deepseafoam", "harbor-daylight")


def ensure_fonts() -> list[str]:
    """Make sure Qt has usable fonts, registering system files if it does not."""
    if QFontDatabase.families():
        return QFontDatabase.families()
    if not WINDOWS_FONTS.is_dir():
        return []
    for name in FONT_FILES:
        candidate = WINDOWS_FONTS / name
        if candidate.is_file():
            QFontDatabase.addApplicationFont(str(candidate))
    return QFontDatabase.families()


def _ink(text: str, font: QFont) -> int:
    """Count dark pixels produced by drawing *text*."""
    image = QImage(640, 64, QImage.Format_RGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setFont(font)
    painter.setPen(QColor("black"))
    painter.drawText(10, 44, text)
    painter.end()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).value() < 128
    )


def glyphs_are_real(font_family: str) -> tuple[bool, float]:
    """True when narrow and wide characters differ in ink, i.e. not tofu boxes."""
    font = QFont(font_family, 20)
    narrow = _ink("iiiiiiiiii", font)
    wide = _ink("WWWWWWWWWW", font)
    ratio = wide / max(narrow, 1)
    return ratio > 1.5, ratio


def main() -> int:
    application = QApplication.instance() or QApplication(sys.argv)

    families = ensure_fonts()
    if not families:
        print(
            "Qt has no fonts available and none could be registered from "
            f"{WINDOWS_FONTS}. Every glyph would render as an empty box.",
            file=sys.stderr,
        )
        return 2

    family = "Segoe UI" if "Segoe UI" in families else families[0]
    application.setFont(QFont(family, 9))

    real, ratio = glyphs_are_real(family)
    print(f"fonts: {len(families)} families, using {family!r}")
    print(f"tofu self-test: ink(W)/ink(i) = {ratio:.2f}  ->  {'text' if real else 'BOXES'}")
    if not real:
        print(
            "Refusing to write screenshots: glyphs are rendering as missing-character "
            "boxes, so the images would be unreadable.",
            file=sys.stderr,
        )
        return 3

    OUT.mkdir(parents=True, exist_ok=True)
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="gui-demo-", dir=build) as temporary:
        workspace = Path(temporary)
        configs = workspace / "configs"
        configs.mkdir()
        (configs / "config.yaml").write_text(
            "browser:\n  engine: edge\njobs:\n  max_daily: 25\n  pause_seconds: 10\n"
            "search:\n  searches:\n    - name: Example backend search\n"
            "      url: https://www.linkedin.com/jobs/search/?keywords=backend&f_AL=true\n"
            "run:\n  dry_run: true\n",
            encoding="utf-8",
        )
        (configs / "answers.yaml").write_text(
            "# Fictional demonstration only. Replace with your own verified answers.\n"
            "full_name: Example User\nemail: example@example.com\n"
            "location: Example City\n",
            encoding="utf-8",
        )
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(workspace))
        window = MainWindow(config_path="configs\\config.yaml", workspace=workspace)
        window.resize(1340, 860)
        window.show()
        application.processEvents()
        window._action_box.setCurrentText("Apply")
        window._limit_spin.setValue(5)
        window._console.append_text(SAMPLE_LOG)
        window._console.flush()
        for page, stem, theme in SHOTS:
            window.resize(980, 680) if stem == "small" else window.resize(1340, 860)
            window._run_settings.customize.setChecked(stem in {"settings", "small"})
            window._run_settings.tabs.setCurrentIndex(1)
            window._apply_theme(THEMES[theme])
            window._pages.setCurrentIndex(page)
            window._nav_buttons[page].setChecked(True)
            application.processEvents()
            scroll = window._run_splitter.widget(0)
            scroll.verticalScrollBar().setValue(
                scroll.verticalScrollBar().maximum() if stem == "settings" else 0
            )
            application.processEvents()
            target = OUT / f"gui-{stem}-{theme}.png"
            if not window.grab().save(str(target)):
                raise OSError(f"Could not save {target}")
            print(f"saved {target.relative_to(ROOT)}  ({target.stat().st_size // 1024} KB)")
        for theme in TUTORIAL_THEMES:
            window._apply_theme(THEMES[theme])
            tutorial = TutorialDialog(window, start_topic=CUSTOMIZE_TOPIC)
            tutorial.show()
            application.processEvents()
            target = OUT / f"gui-tutorial-{theme}.png"
            if not tutorial.grab().save(str(target)):
                raise OSError(f"Could not save {target}")
            print(f"saved {target.relative_to(ROOT)}  ({target.stat().st_size // 1024} KB)")
            tutorial.close()
            tutorial.deleteLater()
            application.processEvents()
        window.close()
        application.processEvents()
    print(f"\nDone. {len(SHOTS) + len(TUTORIAL_THEMES)} screenshots in {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
