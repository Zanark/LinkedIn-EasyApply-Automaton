"""Native desktop GUI for the Easy Apply Automaton.

The GUI is a *front end for the CLI*, not a second implementation: every action
it offers shells out to the same ``apply.py <command>`` the terminal uses, so the
two interfaces can never drift apart. Only the window code depends on PySide6;
:mod:`linkedin_easy_apply.gui.theme` and :mod:`linkedin_easy_apply.gui.commands`
are plain Python and import without Qt installed.
"""

from __future__ import annotations

from linkedin_easy_apply.gui.theme import DEFAULT_THEME, THEMES, Palette

__all__ = ["DEFAULT_THEME", "THEMES", "GuiUnavailableError", "Palette", "launch"]

_INSTALL_HINT = (
    "The desktop GUI needs PySide6, which is not installed.\n"
    "Install it with:\n"
    "    pip install .[gui]\n"
    "or:\n"
    "    pip install PySide6\n"
    "The command line interface works without it."
)


class GuiUnavailableError(RuntimeError):
    """Raised when the GUI is requested but its Qt dependency is missing."""


def launch(config_path: str = "configs/config.yaml", theme: str | None = None) -> int:
    """Open the desktop window. Returns the Qt exit code.

    Imported lazily so that ``import linkedin_easy_apply.gui`` stays cheap and
    works in environments (CI, headless servers) without Qt.
    """
    try:
        from linkedin_easy_apply.gui.main_window import run
    except ImportError as exc:  # pragma: no cover - environment specific
        raise GuiUnavailableError(_INSTALL_HINT) from exc
    return run(config_path=config_path, theme=theme)
