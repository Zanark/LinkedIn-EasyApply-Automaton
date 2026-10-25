"""Tests for the dashboard 'Reports' corner control (``dashboard/app.py``):
report-directory resolution and the injectable folder-opener behind the
first-page button that opens the exported-reports folders.
"""

from __future__ import annotations

from pathlib import Path

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
        raise RuntimeError("no file browser")

    ok, message = _reveal_directory(target, opener=boom)

    assert ok is False
    assert "no file browser" in message
    assert target.is_dir()  # folder is still created before the opener runs
