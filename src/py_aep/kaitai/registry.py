"""Chunk type registry for dispatching binary parsing."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from typing import Callable

    from py_aep.kaitai.chunk import Chunk

T = TypeVar("T")

CHUNK_TYPES: dict[str, type[Chunk]] = {}


def register(chunk_type: str) -> Callable[[type[T]], type[T]]:
    """Decorator that registers a Chunk subclass for a chunk_type."""

    def decorator(cls: type[T]) -> type[T]:
        CHUNK_TYPES[chunk_type] = cls  # type: ignore[assignment]
        cls.chunk_type = chunk_type  # type: ignore[attr-defined]
        return cls

    return decorator
