"""Generic transform functions for chunk-backed descriptors.

Transform functions convert raw binary values into user-facing Python types.
Each factory returns a callable matching the `ChunkField` /
`ChunkField` transform signature: `(raw_value) -> value`.
"""

from __future__ import annotations


def normalize_value(raw: int, *, scale: int = 255) -> float:
    """Normalize a single integer value to a 0.0-1.0 float."""
    return raw / scale


def normalize_values(raw: list[int], *, scale: int = 255) -> list[float]:
    """Normalize a list of integer values to 0.0-1.0 floats."""
    return [normalize_value(v, scale=scale) for v in raw]


def strip_null(s: str | bytes) -> str:
    """Strip null-padding from a fixed-size string."""
    if isinstance(s, bytes):
        s = s.decode("ascii", errors="replace")
    return s.split("\x00")[0]
