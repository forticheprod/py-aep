"""General-purpose utilities for py_aep."""

from __future__ import annotations

import functools
import warnings
from typing import Any, Callable, TypeVar

R = TypeVar("R")


def deprecated(message: str) -> Callable[..., Any]:
    """Decorator that marks a function as deprecated.

    Emits a `DeprecationWarning` with `message` each time the decorated
    function is called.

    Args:
        message: Explanation shown in the warning (e.g. migration path).
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> R:
            warnings.warn(
                f"{func.__qualname__} is deprecated. {message}",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator
