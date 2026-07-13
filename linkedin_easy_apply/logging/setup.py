"""Configure Loguru sinks for console and rotating file output.

This module deliberately uses *absolute* imports of the standard library so
that living inside a package named ``logging`` does not shadow ``logging`` for
the rest of the application.
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from linkedin_easy_apply.config.models import LoggingConfig

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"

_configured = False


def setup_logging(config: LoggingConfig) -> None:
    """Initialise Loguru sinks from *config*. Idempotent per process."""
    global _configured

    logger.remove()

    if config.console:
        logger.add(
            sys.stderr,
            level=config.level,
            format=_CONSOLE_FORMAT,
            colorize=True,
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )

    log_dir = Path(config.directory)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "easy_apply_{time:YYYY-MM-DD}.log",
        level=config.level,
        format=_FILE_FORMAT,
        rotation=config.rotation,
        retention=config.retention,
        serialize=config.serialize,
        enqueue=True,
        backtrace=True,
        diagnose=False,
        encoding="utf-8",
    )
    _configured = True
    logger.debug("Logging initialised at level {}", config.level)


def get_logger(name: str | None = None):
    """Return a Loguru logger, optionally bound to *name*."""
    if name:
        return logger.bind(name=name)
    return logger
