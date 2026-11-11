"""Windows bundles retain redistribution notices and native application branding."""

import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_windows


def test_freezer_embeds_and_bundles_the_application_icon(monkeypatch):
    specification = build_windows.ROOT / "packaging" / "windows" / "EasyApplyAutomaton.spec"
    executables = []
    collected = []

    def collect_data_files(package, **kwargs):
        collected.append((package, kwargs))
        return []

    monkeypatch.setitem(
        sys.modules,
        "PyInstaller.utils.hooks",
        SimpleNamespace(collect_data_files=collect_data_files),
    )
    namespace = {
        "SPECPATH": str(specification.parent),
        "Analysis": lambda *a, **k: SimpleNamespace(
            pure=[], scripts=[], binaries=[], datas=k["datas"]
        ),
        "PYZ": lambda *a: None,
        "EXE": lambda *a, **k: executables.append(k),
        "COLLECT": lambda *a, **k: None,
    }
    exec(compile(specification.read_text(encoding="utf-8"), str(specification), "exec"), namespace)
    assert {entry["name"] for entry in executables} == {"EasyApplyAutomaton", "lea"}
    for entry in executables:
        icon = Path(entry["icon"])
        assert icon == build_windows.ROOT / "docs" / "mark.ico"
        assert icon.is_file()
        assert (str(icon), "docs") in namespace["analysis"].datas
    assert (
        "linkedin_easy_apply",
        {"includes": ["database/sql/*.sql", "gui/fonts/*.ttf", "gui/fonts/OFL.txt"]},
    ) in collected


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
    fonts = root / "linkedin_easy_apply" / "gui" / "fonts"
    fonts.mkdir(parents=True)
    shutil.copyfile(
        build_windows.ROOT / "linkedin_easy_apply" / "gui" / "fonts" / "OFL.txt",
        fonts / "OFL.txt",
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
    assert (notices / "Nunito" / "OFL.txt").read_bytes() == (
        notice_root.parents[2] / "linkedin_easy_apply" / "gui" / "fonts" / "OFL.txt"
    ).read_bytes()


def test_missing_bundled_font_notice_blocks_packaging(notice_root, tmp_path):
    (notice_root.parents[2] / "linkedin_easy_apply" / "gui" / "fonts" / "OFL.txt").unlink()
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with pytest.raises(FileNotFoundError, match="Bundled Nunito redistribution notice missing"):
        build_windows.copy_notices(bundle)


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
