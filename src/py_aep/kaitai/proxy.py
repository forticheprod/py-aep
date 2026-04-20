"""Lightweight stand-in for Kaitai body objects on synthesized properties.

A `ProxyBody` stores the same named attributes as a real Kaitai body
(e.g. `TdsbBody`, `Tdb4Body`) but does not participate in the binary
chunk tree.  `ChunkField` descriptors read from and write to it
transparently.  On first end-user write the owning model's
`_ensure_materialized()` replaces the proxy with real Kaitai chunks.
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar
from typing import Iterator

# During `parse()` this is set to False so that `__setattr__` and
# `ChunkField.__set__` skip materialization / reject writes.
# Outside `parse()` the default (True) lets end-user writes through.
_materialization_allowed: ContextVar[bool] = ContextVar(
    "_materialization_allowed",
    default=True,
)


@contextlib.contextmanager
def _suppress_materialization() -> Iterator[None]:
    """Context manager that disables materialization for the current context."""
    token = _materialization_allowed.set(False)
    try:
        yield
    finally:
        _materialization_allowed.reset(token)


class ProxyBody:
    """Attribute bag that mimics a Kaitai body without binary backing.

    `propagate_check` walks `_parent` upward; setting it to `None`
    makes the walk stop immediately so no serialization happens.
    """

    def __init__(self, **attrs: object) -> None:
        for name, value in attrs.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_parent", None)

    def _check(self) -> None:  # noqa: PLR6301
        """No-op - satisfies the `propagate_check` contract."""
