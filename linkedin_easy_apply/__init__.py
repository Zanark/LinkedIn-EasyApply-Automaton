"""LinkedIn Easy Apply Automaton.

A production-quality, modular automation framework for the LinkedIn Easy Apply
workflow. See ``ARCHITECTURE.md`` for the full design specification.

The package is organised into single-responsibility subpackages:

* :mod:`linkedin_easy_apply.config`    - typed configuration (Pydantic + YAML)
* :mod:`linkedin_easy_apply.logging`   - Loguru based logging setup
* :mod:`linkedin_easy_apply.database`  - SQLite persistence layer
* :mod:`linkedin_easy_apply.answers`   - answer store, resume selection, cover letters
* :mod:`linkedin_easy_apply.parser`    - dynamic question recognition
* :mod:`linkedin_easy_apply.scoring`   - keyword-weighted job scoring engine
* :mod:`linkedin_easy_apply.browser`   - Playwright persistent-context manager
* :mod:`linkedin_easy_apply.forms`     - dynamic form detection & Easy Apply workflow
* :mod:`linkedin_easy_apply.jobs`      - job discovery & extraction
* :mod:`linkedin_easy_apply.ai`        - optional LLM advisory providers
* :mod:`linkedin_easy_apply.cli`       - Typer command line interface
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
