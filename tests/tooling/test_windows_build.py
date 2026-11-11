"""Windows bundles retain redistribution notices and native application branding."""

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.windows import build_windows


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
        assert icon == build_windows.ROOT / "docs" / "assets" / "branding" / "mark.ico"
        assert icon.is_file()
        assert (str(icon), str(Path("docs") / "assets" / "branding")) in namespace["analysis"].datas
    for source, destination in namespace["analysis"].datas:
        path = Path(source)
        assert path.is_file()
        assert Path(destination) == path.parent.relative_to(build_windows.ROOT)
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


@pytest.fixture
def fictional_build(tmp_path, monkeypatch):
    root = tmp_path / "source checkout with spaces"
    packaging = root / "packaging" / "windows"
    packaging.mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    (root / "LICENSE").write_text("Fictional test license\n", encoding="utf-8")
    (packaging / "START_HERE.txt").write_text("Fictional start guide\n", encoding="utf-8")
    specification = packaging / "EasyApplyAutomaton.spec"
    specification.touch()
    output = tmp_path / "delivery with spaces"
    bundle = output / "EasyApplyAutomaton"
    calls = []

    def freeze(command, *, cwd, check):
        calls.append((command, cwd, check))
        bundle.mkdir(parents=True, exist_ok=True)
        (bundle / "lea.exe").write_bytes(b"fictional console")
        (bundle / "EasyApplyAutomaton.exe").write_bytes(b"fictional desktop")
        tutorial = bundle / "_internal" / "docs" / "guides" / "gui-tutorial.md"
        tutorial.parent.mkdir(parents=True, exist_ok=True)
        tutorial.write_text("## Fictional tutorial\nOffline only.\n", encoding="utf-8")

    monkeypatch.setattr(build_windows, "ROOT", root)
    monkeypatch.setattr(
        build_windows, "sys", SimpleNamespace(platform="win32", executable=sys.executable)
    )
    monkeypatch.setattr(build_windows.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(build_windows, "subprocess", SimpleNamespace(run=freeze))
    monkeypatch.setattr(build_windows, "copy_notices", lambda target: {"fixture": "1.0"})
    caller = tmp_path / "unrelated caller"
    caller.mkdir()
    (caller / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n', encoding="utf-8")
    monkeypatch.chdir(caller)
    return SimpleNamespace(
        root=root, output=output, bundle=bundle, specification=specification, calls=calls
    )


def test_moved_build_helper_uses_checkout_and_verifies_every_archive_byte(fictional_build):
    fixture = fictional_build
    source_commit = "1" * 40
    assert build_windows.build(fixture.output, source_commit) == fixture.bundle
    command, cwd, check = fixture.calls[0]
    assert cwd == fixture.root and check is True
    assert command[-1] == str(fixture.specification)
    assert command[command.index("--workpath") + 1] == str(
        fixture.root / "build" / "windows-freeze"
    )
    manifest_path = fixture.output / "EasyApplyAutomaton-1.2.3-windows-x64.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_commit"] == source_commit
    assert manifest["version"] == "1.2.3"
    archive_path = fixture.output / "EasyApplyAutomaton-1.2.3-windows-x64.zip"
    assert manifest["zip_sha256"] == hashlib.sha256(archive_path.read_bytes()).hexdigest()
    assert manifest["zip_bytes"] == archive_path.stat().st_size
    with zipfile.ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {
            f"EasyApplyAutomaton/{relative}" for relative in manifest["files"]
        }
        for relative, expected in manifest["files"].items():
            contents = archive.read(f"EasyApplyAutomaton/{relative}")
            assert len(contents) == expected["bytes"]
            assert hashlib.sha256(contents).hexdigest() == expected["sha256"]
    assert manifest["unpacked_bytes"] == sum(item["bytes"] for item in manifest["files"].values())
    for line in (fixture.output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, filename = line.split("  ", 1)
        assert hashlib.sha256((fixture.output / filename).read_bytes()).hexdigest() == expected


@pytest.mark.parametrize(
    "relative",
    [
        "configs/config.yaml",
        "configs/answers.yaml",
        "configs/searches.yaml",
        ".env",
        ".env.backup",
        "runtime/history.db",
        "runtime/history.sqlite",
        "runtime/history.sqlite3",
        "runtime/capture.HAR",
        ".agent-context/STATE.md",
        ".browser-profile/Default/Preferences",
        "playwright/.local-browsers/browser.exe",
        "_internal/Qt6Pdf.dll",
        "_internal/Qt6Qml.dll",
        "_internal/Qt6Quick.dll",
        "_internal/Qt6VirtualKeyboard.dll",
        "_internal/qpdf.dll",
    ],
)
def test_fictional_private_or_excluded_payload_blocks_release(fictional_build, relative):
    fixture = fictional_build
    forbidden = fixture.bundle.joinpath(*relative.split("/"))
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_text("fictional rejected payload", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Private runtime data or excluded component rejected"):
        build_windows.build(fixture.output, "2" * 40)
    assert not list(fixture.output.glob("*.zip"))
    assert not list(fixture.output.glob("*.manifest.json"))
    assert not (fixture.output / "SHA256SUMS").exists()


def test_failed_freezer_does_not_publish_success_shaped_assets(fictional_build, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("Fictional freezer failure")

    monkeypatch.setattr(build_windows, "subprocess", SimpleNamespace(run=fail))
    with pytest.raises(RuntimeError, match="Fictional freezer failure"):
        build_windows.build(fictional_build.output, "3" * 40)
    assert not list(fictional_build.output.glob("*.zip"))
    assert not (fictional_build.output / "SHA256SUMS").exists()


@pytest.mark.parametrize("system,machine", [("linux", "AMD64"), ("win32", "ARM64")])
def test_unsupported_build_platform_never_invokes_freezer(
    fictional_build, monkeypatch, system, machine
):
    monkeypatch.setattr(build_windows, "sys", SimpleNamespace(platform=system))
    monkeypatch.setattr(build_windows.platform, "machine", lambda: machine)
    with pytest.raises(RuntimeError, match="64-bit Windows"):
        build_windows.build(fictional_build.output, "4" * 40)
    assert fictional_build.calls == []
    assert not fictional_build.output.exists()
