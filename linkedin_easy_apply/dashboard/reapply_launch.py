"""Launch the ``reapply`` CLI from the dashboard's *Reapply all* button.

Easy Apply needs a live Playwright browser and your logged-in session, neither of
which can run inside the Streamlit process, so the button shells out to
``apply.py reapply`` in a **new console window**. The pure command-building and
process-spawning logic lives here (rather than in ``app.py``) so it can be unit
tested without importing the Streamlit-running dashboard module.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CREATE_NEW_CONSOLE = 0x00000010  # Windows: give the retry its own console window.


def reapply_command(config_path: str, answer_unknowns: bool) -> str:
    """The copy-paste PowerShell command shown under the button.

    Mirrors :func:`launch_reapply`'s arguments so the fallback the user sees is
    exactly what the button runs. Interactive (the default) omits ``--yes`` so
    the retry can pause for never-seen questions; unattended appends ``--yes``.
    """
    parts = [".\\.venv\\Scripts\\python.exe", "apply.py", "reapply", "--config", config_path]
    if not answer_unknowns:
        parts.append("--yes")
    return " ".join(parts)


def launch_reapply(config_path: str, *, answer_unknowns: bool) -> tuple[bool, str]:
    """Spawn ``apply.py reapply`` in a new console; return ``(ok, message)``.

    ``answer_unknowns`` (the dashboard checkbox) controls whether ``--yes`` is
    passed: interactive keeps prompts on so the user can answer previously
    unknown questions in the new window; unattended runs fully hands-off.
    """
    args = [sys.executable, str(_REPO_ROOT / "apply.py"), "reapply", "--config", config_path]
    if not answer_unknowns:
        args.append("--yes")
    kwargs: dict[str, Any] = {"cwd": str(_REPO_ROOT)}
    if os.name == "nt":
        kwargs["creationflags"] = _CREATE_NEW_CONSOLE
    else:  # pragma: no cover - non-Windows glue
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(args, **kwargs)  # noqa: S603 - fixed args, user-triggered
    except Exception as exc:  # pragma: no cover - platform/UI glue
        return False, f"Could not launch reapply automatically. Run it yourself: {exc}"
    kind = "interactive" if answer_unknowns else "unattended"
    return True, (
        f"Launched an {kind} reapply run in a new console window — it opens the browser and "
        "reuses your login there. Refresh this tab once it finishes to see the updated status."
    )
