"""DeepSeaFoam (dark) and Harbor Daylight (light) themes rendered as Qt QSS.

Both palettes come from the DeepSeaFoam project (``palette/deepseafoam.json``
and ``palette/harbor-daylight.json``). They are transcribed here as *semantic
roles* rather than copied field names, per that project's porting rules, so one
stylesheet template serves both themes.

Two details the porting rules call out explicitly and that are easy to get
wrong in Qt:

* **Alpha is last in CSS** (``#RRGGBBAA``) but *first* in Qt's ``#AARRGGBB``
  named-colour form. Every translucent token is therefore emitted as
  ``rgba(r, g, b, a)`` by :func:`qt_color`, never pasted in as 8-digit hex.
* **Roles are not interchangeable.** DeepSeaFoam has no second accent fill: its
  ``text`` role is documented as "primary text *and primary-action hover*", so
  that is what ``accent_hover`` maps to in the dark theme, with the near-black
  base as the ink on top. Harbor Daylight has a real ``accentHover`` solid and
  uses paper as button ink.

This module is deliberately free of Qt imports so it can be unit tested (and
reasoned about) without PySide6 installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "DEEP_SEA_FOAM",
    "DEFAULT_THEME",
    "HARBOR_DAYLIGHT",
    "THEMES",
    "Palette",
    "build_stylesheet",
    "log_palette",
    "qt_color",
    "resolve",
]

# Semantic roles every theme must define. Keeping this explicit means a new
# theme cannot silently omit a role the stylesheet depends on.
ROLES: tuple[str, ...] = (
    "background",  # ambient window field
    "surface",  # panels, toolbars, headers
    "raised",  # cards/inputs lifted off the surface
    "text",  # ordinary reading ink
    "muted",  # genuinely lower-emphasis labels
    "heading",  # strong emphasis, titles, selected labels
    "border",  # structural edge (not ordinary text)
    "accent",  # links, focus, primary-action fill
    "accent_hover",  # hovered/pressed primary action
    "button_text",  # ink on an accent fill
    "document",  # positive/document status ink
    "warning",  # caution ink
    "error",  # error ink
    "separator",  # decorative translucent rule
    "hover",  # translucent state fill
    "selection",  # translucent text selection
)


@dataclass(frozen=True)
class Palette:
    """One theme: a key, a display label, a mode and its semantic roles."""

    key: str
    label: str
    mode: str  # "dark" | "light"
    source: str  # provenance of the colour values
    tokens: Mapping[str, str]

    def __post_init__(self) -> None:
        missing = [role for role in ROLES if role not in self.tokens]
        if missing:
            raise ValueError(f"Palette '{self.key}' is missing roles: {', '.join(missing)}")

    def __getitem__(self, role: str) -> str:
        return self.tokens[role]

    @property
    def is_dark(self) -> bool:
        return self.mode == "dark"


DEEP_SEA_FOAM = Palette(
    key="deepseafoam",
    label="DeepSeaFoam",
    mode="dark",
    source="DeepSeaFoam palette/deepseafoam.json v0.7.0",
    tokens=MappingProxyType(
        {
            "background": "#000F13",  # base
            "surface": "#001E26",  # panel
            "raised": "#001E26",  # dark side has no third opaque surface
            "text": "#93A1A1",
            "muted": "#839496",  # faintText
            "heading": "#EEE8D5",  # warm
            "border": "#586E75",
            "accent": "#00A591",
            "accent_hover": "#93A1A1",  # documented "primary-action hover"
            "button_text": "#000F13",  # base ink on the light hover fill
            "document": "#45D072",
            "warning": "#EBE565",
            "error": "#E84A5F",
            "separator": "#586E7566",
            "hover": "#586E7533",
            "selection": "#00A59126",
        }
    ),
)

HARBOR_DAYLIGHT = Palette(
    key="harbor-daylight",
    label="Harbor Daylight",
    mode="light",
    source="DeepSeaFoam palette/harbor-daylight.json",
    tokens=MappingProxyType(
        {
            "background": "#F3F2E9",
            "surface": "#E3ECE7",
            "raised": "#FCFAF2",  # paper
            "text": "#355451",
            "muted": "#536B66",
            "heading": "#173D3A",
            "border": "#6B857E",
            "accent": "#006F63",
            "accent_hover": "#00594F",
            "button_text": "#FCFAF2",  # paper ink on accent fills
            "document": "#247449",
            "warning": "#77600E",
            "error": "#AD3E55",
            "separator": "#6B857E66",
            "hover": "#6B857E1A",
            "selection": "#006F631F",
        }
    ),
)

THEMES: Mapping[str, Palette] = MappingProxyType(
    {palette.key: palette for palette in (DEEP_SEA_FOAM, HARBOR_DAYLIGHT)}
)
DEFAULT_THEME = DEEP_SEA_FOAM.key


def resolve(theme: str | None) -> Palette:
    """Return the named palette, falling back to the default for unknown names."""
    if not theme:
        return THEMES[DEFAULT_THEME]
    return THEMES.get(theme.strip().lower(), THEMES[DEFAULT_THEME])


def qt_color(value: str) -> str:
    """Translate a CSS colour token into something Qt reads correctly.

    ``#RRGGBB`` passes through; ``#RRGGBBAA`` (alpha **last**, as the palettes
    publish it) becomes ``rgba(r, g, b, a)`` because Qt would otherwise read the
    same eight digits as ``#AARRGGBB`` and silently shift every channel.
    """
    token = value.strip()
    if not token.startswith("#"):
        return token
    digits = token[1:]
    if len(digits) == 6:
        return token
    if len(digits) != 8:
        raise ValueError(f"Unsupported colour token: {value!r}")
    red, green, blue, alpha = (int(digits[i : i + 2], 16) for i in range(0, 8, 2))
    return f"rgba({red}, {green}, {blue}, {alpha})"


def log_palette(palette: Palette) -> Mapping[str, str]:
    """Log-level → colour used by the run console.

    Status colour is always paired with the level word itself in the log line,
    so colour never carries the meaning on its own.
    """
    return MappingProxyType(
        {
            "TRACE": palette["muted"],
            "DEBUG": palette["muted"],
            "INFO": palette["text"],
            "SUCCESS": palette["document"],
            "WARNING": palette["warning"],
            "ERROR": palette["error"],
            "CRITICAL": palette["error"],
        }
    )


_TEMPLATE = """
/* {label} - {source} */
QWidget {{
    background-color: {background};
    color: {text};
    font-size: 13px;
}}
QMainWindow, QDialog {{ background-color: {background}; }}

QLabel {{ background: transparent; color: {text}; }}
QLabel[role="heading"] {{ color: {heading}; font-size: 19px; font-weight: 600; }}
QLabel[role="subheading"] {{ color: {heading}; font-size: 14px; font-weight: 600; }}
QLabel[role="muted"] {{ color: {muted}; }}
QLabel[role="document"] {{ color: {document}; }}
QLabel[role="warning"] {{ color: {warning}; }}
QLabel[role="error"] {{ color: {error}; }}

/* Sidebar ------------------------------------------------------------- */
QFrame#Sidebar {{
    background-color: {surface};
    border-right: 1px solid {separator};
}}
QFrame#Sidebar QPushButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: {text};
    padding: 9px 12px;
    text-align: left;
}}
QFrame#Sidebar QPushButton:hover {{
    background-color: {hover};
    color: {heading};
}}
QFrame#Sidebar QPushButton:checked {{
    background-color: {selection};
    border: 1px solid {accent};
    color: {heading};
    font-weight: 600;
}}

/* Cards and group boxes ------------------------------------------------ */
QFrame#Card {{
    background-color: {raised};
    border: 1px solid {separator};
    border-radius: 8px;
}}
QGroupBox {{
    background-color: {raised};
    border: 1px solid {separator};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
}}
QGroupBox::title {{
    color: {heading};
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    font-weight: 600;
}}

/* Buttons -------------------------------------------------------------- */
QPushButton {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 6px;
    color: {text};
    padding: 7px 14px;
}}
QPushButton:hover {{ background-color: {hover}; color: {heading}; }}
QPushButton:pressed {{ background-color: {selection}; }}
QPushButton:disabled {{ color: {muted}; border-color: {separator}; }}
QPushButton[role="primary"] {{
    background-color: {accent};
    border: 1px solid {accent};
    color: {button_text};
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background-color: {accent_hover};
    border-color: {accent_hover};
    color: {button_text};
}}
QPushButton[role="primary"]:disabled {{
    background-color: {surface};
    border-color: {separator};
    color: {muted};
}}
QPushButton[role="danger"] {{ border-color: {error}; color: {error}; }}
QPushButton[role="danger"]:hover {{ background-color: {hover}; color: {error}; }}

/* Inputs --------------------------------------------------------------- */
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {raised};
    border: 1px solid {border};
    border-radius: 6px;
    color: {text};
    padding: 6px 8px;
    selection-background-color: {selection};
    selection-color: {heading};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {accent};
}}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: {muted}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background-color: {raised};
    border: 1px solid {border};
    color: {text};
    selection-background-color: {selection};
    selection-color: {heading};
}}

QCheckBox, QRadioButton {{ background: transparent; color: {text}; spacing: 8px; }}
QCheckBox:hover, QRadioButton:hover {{ color: {heading}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    background-color: {raised};
    border: 1px solid {border};
    width: 14px;
    height: 14px;
}}
QCheckBox::indicator {{ border-radius: 3px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background-color: {accent};
    border: 1px solid {accent};
}}

/* Console -------------------------------------------------------------- */
QPlainTextEdit#Console {{
    background-color: {background};
    border: 1px solid {separator};
    color: {text};
    font-family: "Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 12px;
}}

/* Tables and lists ----------------------------------------------------- */
QTableWidget, QTableView, QListWidget, QTreeWidget {{
    background-color: {raised};
    alternate-background-color: {hover};
    border: 1px solid {separator};
    border-radius: 6px;
    color: {text};
    gridline-color: {separator};
    selection-background-color: {selection};
    selection-color: {heading};
}}
QHeaderView::section {{
    background-color: {surface};
    border: none;
    border-bottom: 1px solid {separator};
    color: {heading};
    font-weight: 600;
    padding: 6px 8px;
}}

/* Chrome --------------------------------------------------------------- */
QToolBar {{
    background-color: {surface};
    border-bottom: 1px solid {separator};
    padding: 4px 8px;
    spacing: 6px;
}}
QStatusBar {{ background-color: {surface}; color: {muted}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background-color: {separator}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: transparent; border: none; }}
QScrollBar:vertical {{ width: 10px; }}
QScrollBar:horizontal {{ height: 10px; }}
QScrollBar::handle {{ background-color: {border}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:hover {{ background-color: {accent}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QProgressBar {{
    background-color: {raised};
    border: 1px solid {separator};
    border-radius: 6px;
    color: {text};
    text-align: center;
}}
QProgressBar::chunk {{ background-color: {accent}; border-radius: 5px; }}
QToolTip {{
    background-color: {surface};
    border: 1px solid {border};
    color: {text};
    padding: 4px 6px;
}}
"""


def build_stylesheet(palette: Palette) -> str:
    """Render *palette* into a Qt style sheet."""
    values = {role: qt_color(palette[role]) for role in ROLES}
    return _TEMPLATE.format(label=palette.label, source=palette.source, **values)
