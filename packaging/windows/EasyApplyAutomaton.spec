# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

root = Path(SPECPATH).parents[1]
data = [
    (str(root / "configs" / f"{name}.example.yaml"), "configs")
    for name in ("config", "answers", "searches")
]
data += [
    (str(root / "docs" / name), "docs") for name in ("mark.svg", "mark.ico", "gui-tutorial.md")
]
data += collect_data_files(
    "linkedin_easy_apply", includes=["database/sql/*.sql", "gui/fonts/*.ttf", "gui/fonts/OFL.txt"]
)
data += collect_data_files("playwright", excludes=["driver/package/.local-browsers/**"])

analysis = Analysis(
    [str(root / "packaging" / "windows" / "entry.py")],
    pathex=[str(root)],
    binaries=[],
    datas=data,
    hiddenimports=["PySide6.QtSvg"],
    excludes=[
        "streamlit",
        "pandas",
        "numpy",
        "matplotlib",
        "IPython",
        "tkinter",
        "openai",
        # Optional helpers discovered in an existing development environment.
        "mypy",
        "mypy_extensions",
        "ast_serialize",
        "librt",
        "pytest",
        "_pytest",
        "email_validator",
        "dns",
        "anyio",
        "idna",
        "attr",
        "attrs",
        "toml",
        "tzdata",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6.QtTest",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
    ],
    noarchive=False,
)
# QtGui's generic plugin collection otherwise pulls in PDF and the QML keyboard.
analysis.binaries = [
    entry
    for entry in analysis.binaries
    if not (
        Path(entry[0]).name.startswith(("Qt6Pdf", "Qt6Qml", "Qt6Quick", "Qt6VirtualKeyboard"))
        or Path(entry[0]).name == "qpdf.dll"
        or "platforminputcontexts" in Path(entry[0]).parts
    )
]
pyz = PYZ(analysis.pure)
gui = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="EasyApplyAutomaton",
    icon=str(root / "docs" / "mark.ico"),
    console=False,
    upx=False,
)
cli = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="lea",
    icon=str(root / "docs" / "mark.ico"),
    console=True,
    upx=False,
)
COLLECT(gui, cli, analysis.binaries, analysis.datas, name="EasyApplyAutomaton", upx=False)
