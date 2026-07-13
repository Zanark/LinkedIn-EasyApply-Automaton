"""A small, dependency-free retry helper with exponential backoff."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable, Iterable
from typing import TypeVar

from loguru import logger

T = TypeVar("T")


class RetryError(RuntimeError):
    """Raised when all retry attempts have been exhausted."""


def retry(
    attempts: int = 3,
    backoff_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Iterable[type[BaseException]] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries the wrapped callable on the given *exceptions*.

    Uses exponential backoff. On exhausting all *attempts* it raises
    :class:`RetryError` chained from the final underlying exception.
    """
    catch = tuple(exceptions)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: object, **kwargs: object) -> T:
            delay = backoff_seconds
            last_exc: BaseException | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except catch as exc:  # noqa: PERF203 - retry loop
                    last_exc = exc
                    if attempt >= attempts:
                        break
                    logger.warning(
                        "{} failed (attempt {}/{}): {}. Retrying in {:.1f}s",
                        func.__name__,
                        attempt,
                        attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
            raise RetryError(f"{func.__name__} failed after {attempts} attempts") from last_exc

        return wrapper

    return decorator
