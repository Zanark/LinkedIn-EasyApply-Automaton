"""Fictional report fixtures for dashboard browsing, previews and native dispatch."""

from __future__ import annotations

import subprocess
from base64 import b64decode
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import linkedin_easy_apply.dashboard.app as dashboard
from linkedin_easy_apply.dashboard.app import _reveal_directory, resolve_report_dirs


def test_resolve_report_dirs_anchors_to_project_root(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    root = config_path.resolve().parent.parent

    analysis, outreach = resolve_report_dirs(config_path, "generated/outreach")

    assert analysis == root / "reports"
    assert outreach == root / "generated" / "outreach"


def test_resolve_report_dirs_keeps_absolute_outreach_dir(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    absolute = tmp_path / "elsewhere" / "outreach"

    _, outreach = resolve_report_dirs(config_path, absolute)

    assert outreach == absolute


def test_reveal_directory_creates_missing_folder_then_opens(tmp_path: Path) -> None:
    target = tmp_path / "reports"
    opened: list[Path] = []

    ok, message = _reveal_directory(target, opener=opened.append)

    assert ok is True
    assert target.is_dir()
    assert opened == [target]
    assert str(target) in message


def test_reveal_directory_surfaces_opener_failure(tmp_path: Path) -> None:
    target = tmp_path / "reports"

    def boom(_: Path) -> None:
        raise OSError("no file browser")

    ok, message = _reveal_directory(target, opener=boom)

    assert ok is False
    assert "no file browser" in message
    assert target.is_dir()  # folder is still created before the opener runs


def _reports_script(root: str) -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from linkedin_easy_apply.dashboard.app import _reports_corner

    _reports_corner(
        str(Path(root) / "configs" / "config.yaml"),
        SimpleNamespace(outreach=SimpleNamespace(report_dir=Path("generated") / "outreach")),
    )


def _browser_script(folder: str) -> None:
    from pathlib import Path

    from linkedin_easy_apply.dashboard.app import _report_browser

    _report_browser("Example reports", Path(folder), "example")


@pytest.mark.parametrize(
    ("category", "directory"),
    [("analysis", ("reports",)), ("outreach", ("generated", "outreach"))],
)
def test_in_browser_button_opens_report_picker(
    tmp_path: Path, category: str, directory: tuple[str, ...]
) -> None:
    folder = tmp_path.joinpath(*directory)
    folder.mkdir(parents=True)
    (folder / "example.txt").write_text("Fictional report content.", encoding="utf-8")
    app = AppTest.from_function(_reports_script, args=(str(tmp_path),), default_timeout=20).run()
    app.session_state["reports_popover"] = True

    app.button(key=f"view_reports_{category}").click().run()

    assert not app.exception
    assert app.session_state["reports_popover"] is False
    assert app.selectbox(key=f"report_file_{category}").options == ["example.txt"]
    assert not app.get("link_button")


def test_windows_opener_explicitly_requests_explorer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    startfile = Mock()
    monkeypatch.setattr(dashboard, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(dashboard.os, "startfile", startfile, raising=False)

    ok, message = _reveal_directory(tmp_path / "folder with spaces")

    assert ok
    startfile.assert_called_once_with(str(tmp_path / "folder with spaces"), "explore")
    assert "request" in message and "dashboard host" in message
    assert "Opened" not in message


@pytest.mark.parametrize(("platform", "command"), [("darwin", "open"), ("linux", "xdg-open")])
def test_native_opener_checks_failed_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str, command: str
) -> None:
    run = Mock(side_effect=subprocess.CalledProcessError(3, command))
    monkeypatch.setattr(dashboard, "sys", SimpleNamespace(platform=platform))
    monkeypatch.setattr(dashboard.subprocess, "run", run)

    ok, message = _reveal_directory(tmp_path)

    assert not ok
    assert "non-zero exit status 3" in message
    run.assert_called_once_with([command, str(tmp_path)], check=True)


@pytest.mark.parametrize("fails", [False, True])
def test_folder_button_reports_dispatch_or_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: bool
) -> None:
    opener = Mock(side_effect=OSError("no desktop") if fails else None)
    monkeypatch.setattr(dashboard, "_default_opener", opener)
    app = AppTest.from_function(_reports_script, args=(str(tmp_path),), default_timeout=20).run()

    app.button(key="open_reports_analysis").click().run()

    assert not app.exception
    opener.assert_called_once_with(tmp_path / "reports")
    assert not app.success
    if fails:
        assert any("no desktop" in element.value for element in app.error)
    else:
        assert any("dashboard host" in element.value for element in app.info)


def test_report_listing_excludes_subfolders_and_symbolic_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("b.TXT", "A.html", "not-a-report.exe", "linked.txt"):
        (tmp_path / name).write_text("fictional", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "hidden.txt").write_text("not listed", encoding="utf-8")
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path == tmp_path / "linked.txt" or original_is_symlink(path),
    )

    assert [file.name for file in dashboard._report_files(tmp_path)] == ["A.html", "b.TXT"]


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("report.txt", b"\xef\xbb\xbfFictional report content."),
        ("report.md", b"# Fictional report\n\nExample **summary**."),
        ("report.html", b"<h1>Fictional HTML report</h1>"),
        ("report.pdf", b"%PDF-fictional-download-fixture"),
    ],
)
def test_selected_report_preview_and_download(tmp_path: Path, name: str, data: bytes) -> None:
    (tmp_path / name).write_bytes(data)
    app = AppTest.from_function(_browser_script, args=(str(tmp_path),), default_timeout=20).run()

    app.selectbox(key="report_file_example").select(name).run()

    assert not app.exception
    assert len(app.get("download_button")) == 1
    if name.endswith(".html"):
        src = app.get("iframe")[0].proto.src
        assert src.startswith("data:text/html;charset=utf-8;base64,")
        assert b64decode(src.split(",", 1)[1]) == data
    elif name.endswith(".md"):
        assert any(element.value == data.decode("utf-8") for element in app.markdown)
    elif name.endswith(".pdf"):
        assert any("download-only" in element.value for element in app.info)
    else:
        assert any(element.value == "Fictional report content." for element in app.code)


def test_non_utf8_report_keeps_download_and_explains_preview(tmp_path: Path) -> None:
    (tmp_path / "report.txt").write_bytes(b"fictional \xff report")
    app = AppTest.from_function(_browser_script, args=(str(tmp_path),), default_timeout=20).run()

    app.selectbox(key="report_file_example").select("report.txt").run()

    assert not app.exception
    assert len(app.get("download_button")) == 1
    assert any("No UTF-8 preview" in element.value for element in app.warning)


@pytest.mark.parametrize("missing", [False, True])
def test_report_browser_explains_empty_or_missing_folder(tmp_path: Path, missing: bool) -> None:
    folder = tmp_path / "missing" if missing else tmp_path
    app = AppTest.from_function(_browser_script, args=(str(folder),), default_timeout=20).run()

    assert not app.exception
    assert not app.selectbox
    expected = "does not exist" if missing else "No supported report files"
    assert any(expected in element.value for element in app.info)
    assert folder.exists() is not missing


def test_report_browser_surfaces_listing_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        dashboard, "_report_files", Mock(side_effect=PermissionError("fixture denied"))
    )

    app = AppTest.from_function(_browser_script, args=(str(tmp_path),), default_timeout=20).run()

    assert not app.exception
    assert any("Could not list reports" in element.value for element in app.error)
    assert any("fixture denied" in element.value for element in app.error)


def test_report_browser_reads_only_selection_and_surfaces_read_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selected = tmp_path / "selected.txt"
    selected.write_bytes(b"fictional")
    (tmp_path / "other.txt").write_bytes(b"not selected")
    original_read = Path.read_bytes
    reads = []

    def read_report(path: Path) -> bytes:
        if path.parent == tmp_path:
            reads.append(path)
            raise PermissionError("fixture read denied")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", read_report)
    app = AppTest.from_function(_browser_script, args=(str(tmp_path),), default_timeout=20).run()
    assert reads == []

    app.selectbox(key="report_file_example").select(selected.name).run()

    assert not app.exception
    assert reads == [selected]
    assert any("fixture read denied" in element.value for element in app.error)
    assert not app.get("download_button")


def test_report_browser_rejects_selection_outside_configured_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "reports"
    folder.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"must not be read")
    monkeypatch.setattr(dashboard, "_report_files", Mock(return_value=[outside]))
    read = Mock(side_effect=AssertionError("Must not read outside the report folder"))
    monkeypatch.setattr(Path, "read_bytes", read)
    app = AppTest.from_function(_browser_script, args=(str(folder),), default_timeout=20).run()

    app.selectbox(key="report_file_example").select(outside.name).run()

    assert not app.exception
    assert any("no longer a regular file" in element.value for element in app.error)
    read.assert_not_called()
    assert not app.get("download_button")
