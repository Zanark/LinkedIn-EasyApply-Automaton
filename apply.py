#!/usr/bin/env python
"""Convenience entrypoint so the tool can be run as ``python apply.py ...``.

This simply delegates to the Typer CLI. Installing the package also exposes the
same interface via the ``lea`` console script.

Examples
--------
    python apply.py apply --dry-run
    python apply.py apply --url "https://www.linkedin.com/jobs/search/?keywords=backend"
    python apply.py scan --limit 20
"""

from __future__ import annotations

from linkedin_easy_apply.cli.main import app

if __name__ == "__main__":
    app()
