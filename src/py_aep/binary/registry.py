"""Chunk type registry for dispatching binary parsing."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from typing import Callable

    from .chunk import Chunk

T = TypeVar("T")

CHUNK_TYPES: dict[str, type[Chunk]] = {}


def register(*chunk_types: str) -> Callable[[type[T]], type[T]]:
    """Decorator that registers a Chunk subclass for one or more chunk_types."""

    def decorator(cls: type[T]) -> type[T]:
        for ct in chunk_types:
            CHUNK_TYPES[ct] = cls  # type: ignore[assignment]
        return cls

    return decorator
