"""Version-gating decorator for model methods."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    pass

F = TypeVar("F", bound=Callable[..., Any])


def _get_ae_version_major(obj: Any) -> int:
    """Navigate from a model object to the AE version major number.

    Supports Layer (via `containing_comp`), Item (via `_project`),
    and Project (via `_head`).
    """
    # Layer -> CompItem -> Project -> HeadChunk
    if hasattr(obj, "_containing_comp"):
        return int(obj._containing_comp._project._head.ae_version_major)
    # Item -> Project -> HeadChunk
    if hasattr(obj, "_project"):
        return int(obj._project._head.ae_version_major)
    # Project -> HeadChunk
    if hasattr(obj, "_head"):
        return int(obj._head.ae_version_major)
    raise TypeError(f"Cannot determine AE version from {type(obj).__name__}")


def requires_version(min_major: int) -> Callable[[F], F]:
    """Restrict a model method to files from a minimum AE major version.

    Args:
        min_major: Minimum AE major version number (e.g. 23 for AE 23.x).

    Raises:
        AttributeError: If the file predates the required version.
    """

    def decorator(method: F) -> F:
        @functools.wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            major = _get_ae_version_major(self)
            if major < min_major:
                raise AttributeError(
                    f"{method.__name__}() requires AE {min_major}+ "
                    f"file format (file is AE {major})."
                )
            return method(self, *args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
