"""Build an allowlisted one-folder Windows distribution and integrity files."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tomllib
import zipfile
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def copy_notices(bundle: Path) -> dict[str, str]:
    versions = {}
    destination = bundle / "THIRD_PARTY_NOTICES"
    for requirement in (
        (ROOT / "packaging" / "windows" / "requirements.txt").read_text().splitlines()
    ):
        if not requirement or requirement.startswith("#"):
            continue
        name, expected = requirement.split("==")
        package = distribution(name)
        if package.version != expected:
            raise RuntimeError(f"Build dependency mismatch: {name} {package.version} != {expected}")
        versions[name] = expected
        for item in package.files or ():
            if not any(
                part.casefold().startswith(("license", "copying", "notice")) for part in item.parts
            ):
                continue
            source = Path(package.locate_file(item))
            if source.is_file():
                target = destination / name / str(item).replace("../", "").replace("..\\", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise FileNotFoundError(f"Python redistribution license missing: {python_license}")
    destination.mkdir(exist_ok=True)
    shutil.copyfile(python_license, destination / "PYTHON_LICENSE.txt")
    supplemental = ROOT / "packaging" / "windows" / "licenses"
    for relative in (
        Path("Qt") / "README.txt",
        Path("Qt") / "LGPL-3.0.txt",
        Path("Qt") / "GPL-3.0.txt",
        Path("loguru") / "LICENSE.txt",
        Path("et-xmlfile") / "LICENCE.rst",
        Path("et-xmlfile") / "LICENCE.python",
    ):
        if not (supplemental / relative).is_file():
            raise FileNotFoundError(f"Supplemental redistribution notice missing: {relative}")
    shutil.copytree(supplemental, destination, dirs_exist_ok=True)
    font_notice = ROOT / "linkedin_easy_apply" / "gui" / "fonts" / "OFL.txt"
    if not font_notice.is_file():
        raise FileNotFoundError(f"Bundled Nunito redistribution notice missing: {font_notice}")
    (destination / "Nunito").mkdir(exist_ok=True)
    shutil.copyfile(font_notice, destination / "Nunito" / "OFL.txt")
    return versions


def build(output: Path, source_commit: str) -> Path:
    if sys.platform != "win32" or platform.machine().upper() not in {"AMD64", "X86_64"}:
        raise RuntimeError("The desktop release must be built with 64-bit Windows Python.")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]

    output.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(output),
            "--workpath",
            str(ROOT / "build" / "windows-freeze"),
            str(ROOT / "packaging" / "windows" / "EasyApplyAutomaton.spec"),
        ],
        cwd=ROOT,
        check=True,
    )
    bundle = output / "EasyApplyAutomaton"
    shutil.copyfile(ROOT / "LICENSE", bundle / "LICENSE.txt")
    shutil.copyfile(ROOT / "packaging" / "windows" / "START_HERE.txt", bundle / "START_HERE.txt")
    versions = copy_notices(bundle)
    for path in bundle.rglob("*"):
        if path.is_file() and (
            path.name in {"config.yaml", "answers.yaml", "searches.yaml"}
            or path.name.startswith(".env")
            or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".har"}
            or path.name.startswith(("Qt6Pdf", "Qt6Qml", "Qt6Quick", "Qt6VirtualKeyboard"))
            or path.name == "qpdf.dll"
            or any(
                part in {".agent-context", ".browser-profile", ".local-browsers"}
                for part in path.parts
            )
        ):
            raise RuntimeError(f"Private runtime data or excluded component rejected: {path}")
    files = {
        path.relative_to(bundle).as_posix(): {"bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(bundle.rglob("*"))
        if path.is_file()
    }
    manifest = {
        "version": version,
        "source_commit": source_commit,
        "platform": "windows-x64",
        "python": platform.python_version(),
        "signed": False,
        "browser_bundled": False,
        "unpacked_bytes": sum(item["bytes"] for item in files.values()),
        "build_dependencies": versions,
        "files": files,
    }
    name = f"EasyApplyAutomaton-{version}-windows-x64"
    archive = output / f"{name}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(output))
    manifest["zip_bytes"] = archive.stat().st_size
    manifest["zip_sha256"] = digest(archive)
    manifest_path = output / f"{name}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest(path)}  {path.name}\n" for path in (archive, manifest_path)),
        encoding="utf-8",
    )
    print(
        f"Built {archive}\nDownload: {archive.stat().st_size / 1024**2:.1f} MiB; "
        f"extracted: {manifest['unpacked_bytes'] / 1024**2:.1f} MiB"
    )
    return bundle


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "windows")
    parser.add_argument("--source-commit", default="working-tree")
    arguments = parser.parse_args()
    build(arguments.output.resolve(), arguments.source_commit)
