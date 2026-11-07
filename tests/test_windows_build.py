"""Redistribution notices must survive packaging, including incomplete wheel metadata."""

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_windows


@pytest.fixture
def notice_root(tmp_path, monkeypatch):
    root = tmp_path / "source"
    packaging = root / "packaging" / "windows"
    packaging.mkdir(parents=True)
    (packaging / "requirements.txt").write_text("example==1.0\n", encoding="utf-8")
    shutil.copytree(
        build_windows.ROOT / "packaging" / "windows" / "licenses",
        packaging / "licenses",
    )
    python = tmp_path / "python"
    python.mkdir()
    (python / "LICENSE.txt").write_text("Python fixture license", encoding="utf-8")
    monkeypatch.setattr(build_windows, "ROOT", root)
    monkeypatch.setattr(build_windows, "sys", SimpleNamespace(base_prefix=str(python)))
    monkeypatch.setattr(
        build_windows, "distribution", lambda name: SimpleNamespace(version="1.0", files=())
    )
    return packaging / "licenses"


def test_supplemental_notices_keep_dependency_groups(notice_root, tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    build_windows.copy_notices(bundle)
    notices = bundle / "THIRD_PARTY_NOTICES"
    for relative in (
        Path("Qt") / "README.txt",
        Path("loguru") / "LICENSE.txt",
        Path("et-xmlfile") / "LICENCE.rst",
        Path("et-xmlfile") / "LICENCE.python",
    ):
        assert (notices / relative).read_bytes() == (notice_root / relative).read_bytes()
    assert (notices / "PYTHON_LICENSE.txt").is_file()
    assert not (notices / "Qt" / "loguru").exists()


@pytest.mark.parametrize(
    "relative",
    [
        Path("loguru") / "LICENSE.txt",
        Path("et-xmlfile") / "LICENCE.rst",
        Path("et-xmlfile") / "LICENCE.python",
    ],
)
def test_missing_supplemental_notice_blocks_packaging(notice_root, tmp_path, relative):
    (notice_root / relative).unlink()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with pytest.raises(FileNotFoundError, match="Supplemental redistribution notice missing"):
        build_windows.copy_notices(bundle)
