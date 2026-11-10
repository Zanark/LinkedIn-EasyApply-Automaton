"""Capture README screenshots and scripted GIF walkthroughs of the desktop GUI.

    .\\.venv\\Scripts\\python.exe tools\\capture_screenshots.py

Works on a normal desktop *and* headless (``QT_QPA_PLATFORM=offscreen``). A
headless Qt can report **zero font families**, and every glyph then renders as an
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
from argparse import ArgumentParser
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
# Running a script inside tools/ puts tools/ on sys.path, not the repository
# root, so the local package would lose to anything already installed.
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from PySide6.QtCore import (  # noqa: E402
    QBuffer,
    QCoreApplication,
    QEvent,
    QIODevice,
    QPoint,
    QRect,
    QSettings,
    Qt,
)
from PySide6.QtGui import QColor, QFont, QFontDatabase, QHelpEvent, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QToolTip,
    QWidget,
)

from linkedin_easy_apply.gui import commands  # noqa: E402
from linkedin_easy_apply.gui.main_window import _APP, _ORG, MainWindow  # noqa: E402
from linkedin_easy_apply.gui.theme import THEMES  # noqa: E402
from linkedin_easy_apply.gui.tutorial import CUSTOMIZE_TOPIC, TutorialDialog  # noqa: E402
from linkedin_easy_apply.gui.widgets import PathRow  # noqa: E402
from linkedin_easy_apply.progress import Activity, Metric, ProgressReporter, RunAction  # noqa: E402

OUT = ROOT / "docs" / "images"
DEMO_ROOT = Path(r"C:\EasyApplyDemo")
CAPTION_HEIGHT = 56
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
    "OFFLINE DEMO - illustrative output only; no automation command was started.\n"
    "2026-01-15 09:12:01 | INFO     | linkedin_easy_apply.orchestrator:run:100"
    " - Example target: 5 applications, dry run enabled.\n"
    "2026-01-15 09:12:02 | INFO     | linkedin_easy_apply.jobs.search:search:100"
    " - Example saved search: Backend engineering.\n"
    "2026-01-15 09:12:03 | INFO     | linkedin_easy_apply.orchestrator:_process_job:100"
    " - [SCORE PASS] 42/20 | Backend Engineer at Example Company\n"
    "2026-01-15 09:12:04 | DEBUG    | linkedin_easy_apply.forms.detector:detect:100"
    " - Detected 4 required fields.\n"
    "2026-01-15 09:12:05 | INFO     | linkedin_easy_apply.answers.resolver:resolve:100"
    " - Example answer resolved from saved YAML.\n"
    "2026-01-15 09:12:06 | WARNING  | linkedin_easy_apply.forms.easy_apply:_finalize_submit:100"
    " - DRY-RUN: Stop at Submit; nothing is sent.\n"
    "2026-01-15 09:12:07 | ERROR    | linkedin_easy_apply.forms.filler:fill:100"
    " - Example only: required option missing.\n"
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
    (0, "settings-search", "deepseafoam"),
    (0, "settings-browser", "deepseafoam"),
    (0, "settings-behavior", "deepseafoam"),
    (0, "small", "harbor-daylight"),
]
TUTORIAL_THEMES = ("deepseafoam", "harbor-daylight")
SETTINGS_TABS = {
    "settings": 1,
    "settings-search": 0,
    "settings-browser": 2,
    "settings-behavior": 3,
    "small": 1,
}


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
    image = QImage(640, 64, QImage.Format.Format_RGB32)
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


def _demo_paths(window: MainWindow) -> None:
    """Keep rendered location labels fictional; never redirect actual runtime paths."""
    for row in window.findChildren(PathRow):
        field = row.findChild(QLineEdit)
        if field is None:
            raise RuntimeError("A location row has no path field.")
        path = Path(field.text())
        if path.is_relative_to(window._root):
            displayed = str(DEMO_ROOT / path.relative_to(window._root))
            field.setText(displayed)
            field.setCursorPosition(0)
        elif not path.is_relative_to(DEMO_ROOT):
            raise RuntimeError("A capture location is outside the fictional workspace.")
    preview = window._command_preview.toPlainText()
    for original, displayed in (
        (str(Path(sys.executable)), r".\.venv\Scripts\python.exe"),
        (str(commands.entry_script()), "apply.py"),
        (str(window._root), str(DEMO_ROOT)),
    ):
        preview = preview.replace(original, displayed)
    window._command_preview.setPlainText(preview)


def _save_screenshot(
    widget: QWidget, target: Path, *, tooltip_target: QWidget | None = None
) -> None:
    if isinstance(widget, MainWindow):
        _demo_paths(widget)
    capture = widget.grab()
    if tooltip_target is not None:
        point = tooltip_target.rect().center()
        try:
            QApplication.sendEvent(
                tooltip_target,
                QHelpEvent(QEvent.Type.ToolTip, point, tooltip_target.mapToGlobal(point)),
            )
            QCoreApplication.processEvents()
            popup = next(
                (
                    candidate
                    for candidate in QApplication.topLevelWidgets()
                    if candidate.isVisible() and candidate.windowType() == Qt.WindowType.ToolTip
                ),
                None,
            )
            if popup is None or QToolTip.text() != tooltip_target.toolTip():
                raise RuntimeError("The requested native tooltip did not appear.")
            offset = popup.mapToGlobal(QPoint()) - widget.mapToGlobal(QPoint())
            if not widget.rect().contains(QRect(offset, popup.size())):
                raise RuntimeError("The tooltip would be clipped; adjust the capture layout.")
            # Native tooltips are separate windows; grab only our two owned widgets.
            painter = QPainter(capture)
            try:
                painter.drawPixmap(offset, popup.grab())
            finally:
                painter.end()
        finally:
            QToolTip.hideText()
            QCoreApplication.processEvents()
    if not capture.save(str(target)):
        raise OSError(f"Could not save {target}")
    print(f"saved {target.resolve()}  ({target.stat().st_size // 1024} KB)")


def _walkthrough_frame(widget: QWidget, caption: str) -> Image.Image:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    try:
        if not widget.grab().save(buffer, "PNG"):
            raise OSError("Could not render the walkthrough widget.")
        with Image.open(BytesIO(buffer.data().data())) as rendered:
            image = rendered.convert("RGB")
    finally:
        buffer.close()
    if image.width > 1040:
        image = image.resize(
            (1040, round(image.height * 1040 / image.width)), Image.Resampling.LANCZOS
        )
    frame = Image.new("RGB", (image.width, image.height + CAPTION_HEIGHT), "#000F13")
    frame.paste(image, (0, CAPTION_HEIGHT))
    draw = ImageDraw.Draw(frame)
    font_path = WINDOWS_FONTS / "segoeuib.ttf"
    font = (
        ImageFont.truetype(str(font_path), 20)
        if font_path.is_file()
        else ImageFont.load_default(size=20)
    )
    draw.text((16, 7), caption, font=font, fill="#EEE8D5")
    draw.text(
        (16, 34),
        "Scripted offline GUI - fictional data, no automation command executed",
        font=ImageFont.load_default(size=12),
        fill="#93A1A1",
    )
    return frame


def _save_gif(frames: list[Image.Image], target: Path) -> None:
    palette = frames[0].quantize(colors=256, dither=Image.Dither.NONE)
    indexed = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    durations = [1800] * len(indexed)
    durations[0], durations[-1] = 2400, 2800
    indexed[0].save(
        target,
        save_all=True,
        append_images=indexed[1:],
        duration=durations,
        loop=0,
        disposal=2,
        optimize=True,
    )
    print(
        f"saved {target}  ({target.stat().st_size // 1024} KB, "
        f"{len(frames)} frames, {sum(durations) / 1000:.1f} s)"
    )


def _select_action(window: MainWindow, action: str) -> None:
    label = next(label for label, command in commands.RUN_ACTIONS.items() if command == action)
    window._action_box.setCurrentText(label)


def _demo_metrics(
    window: MainWindow,
    action: RunAction,
    counts: Mapping[Metric, int],
    *,
    activity: Activity | None = None,
    resume_name: str | None = None,
) -> None:
    """Render explicitly fictional outcomes without starting a child or timer."""
    window._metrics.prepare(action)
    reporter = ProgressReporter(
        window._metrics.update_progress, activity_sink=window._runner.activity.emit
    )
    reporter.start(
        action,
        run_id=11 if action != "connect" else None,
        dry_run=action != "scan",
        target=window._limit_spin.value(),
    )
    if action == "connect":
        reporter.connections(3, dry_run=True)
    reporter.increment(
        counts,
        phase=(
            "connecting" if action == "connect" else "reviewing" if action == "scan" else "applying"
        ),
    )
    reporter.activity(
        activity
        or (
            "connecting"
            if action == "connect"
            else "searching_jobs" if action == "scan" else "filling_application"
        ),
        resume_path=Path(resume_name) if resume_name is not None else None,
    )
    window._metrics.finish("Offline demo")


def _capture_run_walkthrough(window: MainWindow, application: QApplication, target: Path) -> None:
    window.resize(1340, 860)
    window._run_splitter.setSizes([330, 750])
    window._nav_buttons[0].click()
    window._apply_theme(THEMES["deepseafoam"])
    window._limit_spin.setValue(5)
    window._run_settings.customize.setChecked(False)
    window._dry_run.setChecked(True)
    window._confirm_submit.setChecked(False)
    window._verbose.setChecked(False)
    scroll = window._run_splitter.widget(0)
    if not isinstance(scroll, QScrollArea):
        raise TypeError("The run setup must be scrollable.")
    frames: list[Image.Image] = []

    def capture(caption: str, *, expanded: bool = False) -> None:
        application.processEvents()
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum() if expanded else 0)
        application.processEvents()
        _demo_paths(window)
        frames.append(_walkthrough_frame(window, caption))

    _select_action(window, "scan")
    _demo_metrics(window, "scan", {"scanned": 3, "skipped": 3})
    capture("1. Scan discovers and scores; it never applies")
    _select_action(window, "apply")
    _demo_metrics(
        window,
        "apply",
        {"scanned": 4, "skipped": 4, "dry_runs": 1},
        resume_name="Example_Backend_Resume.pdf",
    )
    window._verbose.click()
    capture("2. Choose Apply; keep Dry run and review the command")
    window._run_settings.customize.click()
    window._run_settings.tabs.setCurrentIndex(0)
    capture("3. Customize this run: choose saved searches", expanded=True)
    window._run_settings.tabs.setCurrentIndex(1)
    daily_cap = window._run_settings._fields["jobs.max_daily"]
    if not isinstance(daily_cap, QSpinBox):
        raise TypeError("The daily cap must be a numeric control.")
    daily_cap.setValue(15)
    _demo_metrics(
        window,
        "apply",
        {"scanned": 8, "skipped": 7, "failed": 1, "dry_runs": 2},
        activity="awaiting_input",
    )
    capture("4. Waiting for you: the action icon identifies an input pause", expanded=True)
    window._run_settings.tabs.setCurrentIndex(2)
    ProgressReporter(activity_sink=window._runner.activity.emit).activity(
        "uploading_document", resume_path=Path("Example_Backend_Tailored.pdf")
    )
    capture("5. A new application resume replaces the displayed filename", expanded=True)
    window._run_settings.tabs.setCurrentIndex(3)
    ProgressReporter(activity_sink=window._runner.activity.emit).activity("reviewing_application")
    capture("6. Later actions keep the last selected resume visible", expanded=True)
    _select_action(window, "reapply")
    window._list_only.setChecked(True)
    window._metrics.prepare(None)
    capture("7. Reapply can list retry targets without a browser")
    _select_action(window, "connect")
    window._connect_run.setValue(11)
    _demo_metrics(
        window, "connect", {"connect_processed": 3, "connect_already": 1, "connect_dry_runs": 2}
    )
    capture("8. Connect can filter pending drafts by run ID")
    _select_action(window, "apply")
    window._run_settings.customize.click()
    _demo_metrics(window, "apply", {"scanned": 10, "skipped": 9, "failed": 1, "dry_runs": 4})
    capture("9. Review before Start; this walkthrough executes nothing")
    _save_gif(frames, target)


def _dispose_widget(widget: QWidget) -> None:
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)


def _capture_tutorial_walkthrough(
    window: MainWindow, application: QApplication, target: Path
) -> None:
    tutorial = TutorialDialog(window)
    try:
        tutorial.show()
        frames: list[Image.Image] = []

        def capture(caption: str) -> None:
            application.processEvents()
            frames.append(_walkthrough_frame(tutorial, caption))

        capture("1. Open the read-only guided tutorial")
        tutorial._next.click()
        capture("2. Next moves through the guide")
        tutorial._back.click()
        capture("3. Back returns to the previous explanation")
        index = next(
            i for i, topic in enumerate(tutorial._topics) if topic.title == CUSTOMIZE_TOPIC
        )
        tutorial._topic_list.setCurrentRow(index)
        capture("4. Jump directly to a topic in the list")
        tutorial._next.click()
        capture(f"5. Next: {tutorial._title.text()}")
        tutorial._next.click()
        capture(f"6. Next: {tutorial._title.text()}")
        tutorial._back.click()
        capture("7. Replay a topic; parent settings and files stay unchanged")
        _save_gif(frames, target)
    finally:
        _dispose_widget(tutorial)


def main(*, run_only: bool = False) -> int:
    application = QApplication.instance() or QApplication(sys.argv)
    if not isinstance(application, QApplication):
        raise RuntimeError("Screenshot capture requires a QApplication.")

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
    shots = [shot for shot in SHOTS if not run_only or shot[0] == 0]
    tutorial_themes = () if run_only else TUTORIAL_THEMES
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="gui-demo-", dir=build) as temporary:
        workspace = Path(temporary)
        configs = workspace / "configs"
        configs.mkdir()
        (configs / "config.yaml").write_text(
            "browser:\n  engine: edge\n  profile_path: .browser-profile\n"
            "jobs:\n  max_daily: 25\n  pause_seconds: 10\n"
            "scoring:\n  threshold: 20\n"
            "search:\n  searches:\n    - name: Backend engineering\n"
            "      url: https://www.linkedin.com/jobs/search/?keywords=backend&f_AL=true\n"
            "    - name: Frontend engineering\n"
            "      url: https://www.linkedin.com/jobs/search/?keywords=frontend&f_AL=true\n"
            "      enabled: false\n"
            "resume:\n  directory: generated/resume\n  default: Example_Resume.pdf\n"
            "run:\n  dry_run: true\n",
            encoding="utf-8",
        )
        (configs / "answers.yaml").write_text(
            "# Fictional demonstration only. Replace with your own verified answers.\n"
            "full_name: Example User\nemail: example@example.com\n"
            "city: Example City\nyears_experience: 3\nnotice_period_days: 30\n"
            "authorization: true\nrelocation: false\n"
            "skills:\n  Python:\n    years: 3\n  TypeScript:\n    years: 2\n",
            encoding="utf-8",
        )
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(workspace))
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(workspace / "system")
        )
        preferences = QSettings(QSettings.defaultFormat(), QSettings.Scope.UserScope, _ORG, _APP)
        if not Path(preferences.fileName()).is_relative_to(workspace):
            raise RuntimeError("Capture preferences must use the isolated INI workspace.")
        window = MainWindow(
            config_path="configs\\config.yaml", theme="deepseafoam", workspace=workspace
        )
        try:
            window.resize(1340, 860)
            window.show()
            application.processEvents()
            if window._loaded_config is None:
                raise RuntimeError("The fictional capture configuration did not load.")
            window._action_box.setCurrentText("Apply")
            window._limit_spin.setValue(5)
            window._console.append_text(SAMPLE_LOG)
            window._console.flush()
            _demo_metrics(
                window,
                "apply",
                {"scanned": 8, "skipped": 7, "failed": 1, "dry_runs": 2},
                activity="awaiting_input",
                resume_name="Example_Backend_Resume.pdf",
            )
            for page, stem, theme in shots:
                window.resize(980, 680) if stem == "small" else window.resize(1340, 860)
                window._run_settings.customize.setChecked(stem in SETTINGS_TABS)
                window._run_settings.tabs.setCurrentIndex(SETTINGS_TABS.get(stem, 0))
                window._apply_theme(THEMES[theme])
                window._nav_buttons[page].click()
                application.processEvents()
                scroll = window._run_splitter.widget(0)
                if not isinstance(scroll, QScrollArea):
                    raise TypeError("The run setup must be scrollable.")
                scroll.verticalScrollBar().setValue(
                    scroll.verticalScrollBar().maximum() if stem.startswith("settings") else 0
                )
                application.processEvents()
                _save_screenshot(
                    window,
                    OUT / f"gui-{stem}-{theme}.png",
                    tooltip_target=(
                        window._run_settings._fields["jobs.max_daily"]
                        if stem == "settings"
                        else None
                    ),
                )
            for theme in tutorial_themes:
                window._apply_theme(THEMES[theme])
                tutorial = TutorialDialog(window, start_topic=CUSTOMIZE_TOPIC)
                try:
                    tutorial.show()
                    application.processEvents()
                    _save_screenshot(tutorial, OUT / f"gui-tutorial-{theme}.png")
                finally:
                    _dispose_widget(tutorial)
            _capture_run_walkthrough(window, application, OUT / "gui-run-walkthrough.gif")
            if not run_only:
                window._apply_theme(THEMES["deepseafoam"])
                _capture_tutorial_walkthrough(
                    window, application, OUT / "gui-tutorial-walkthrough.gif"
                )
            if window._runner.busy:
                raise RuntimeError("A documentation capture must never start a command.")
        finally:
            window._settings.sync()
            _dispose_widget(window)
    print(
        f"\nDone. {len(shots) + len(tutorial_themes)} screenshots and {1 if run_only else 2} GIFs "
        f"in {OUT.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-only", action="store_true", help="Refresh only Run-page PNGs and GIF."
    )
    raise SystemExit(main(run_only=parser.parse_args().run_only))
