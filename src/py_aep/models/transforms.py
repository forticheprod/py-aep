"""Generic transform and compute helpers for chunk-backed descriptors.

Transform functions convert raw binary values into user-facing Python types.
Helpers in this module are used by both `ChunkField` transforms and
`ComputedField` compute callables.
"""

from __future__ import annotations

from typing import Any


def pack_values(body: Any, *field_names: str) -> list[Any]:
    """Pack multiple raw chunk fields into a list.

    Args:
        body: The chunk body.
        field_names: Field names to read in order.
    """
    return [getattr(body, field_name) for field_name in field_names]


def compute_fractional(
    body: Any,
    integer_field: str,
    fractional_field: str,
    *,
    scale: int = 65536,
) -> float:
    """Compute a float from an integer + fractional field pair.

    Args:
        body: The chunk body.
        integer_field: Name of the integer field.
        fractional_field: Name of the fractional field.
        scale: Divisor for the fractional part (default 65536).
    """
    return float(
        getattr(body, integer_field)
        + getattr(body, fractional_field) / scale
    )


def compute_ratio(body: Any, dividend_field: str, divisor_field: str) -> float:
    """Compute a float from a dividend / divisor field pair.

    Args:
        body: The chunk body.
        dividend_field: Name of the dividend field.
        divisor_field: Name of the divisor field.
    """
    return float(getattr(body, dividend_field) / getattr(body, divisor_field))


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
