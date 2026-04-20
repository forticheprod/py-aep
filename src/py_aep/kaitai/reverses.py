"""Generic reverse functions for chunk-backed descriptors.

Reverse functions decompose user-facing values back into the binary fields
stored in the Kaitai chunk body. Each factory returns a callable matching
the `ChunkField` `reverse_instance_field` signature: `(value, body) -> dict`.
"""

from __future__ import annotations

from typing import Any, Callable

# Divisor used when writing tick-based time values.  10 000 gives sub-frame
# precision for all standard frame rates.
_TIME_DIVISOR = 10000


def reverse_frame_ticks(
    prefix: str,
) -> Callable[[int, Any], dict[str, int]]:
    """Convert a frame count to `{prefix}_dividend / divisor` time ticks.

    The frame count is divided by `body.frame_rate` to obtain seconds,
    then stored as tick-based dividend / divisor.

    Args:
        prefix: Field-name prefix (e.g. `"duration"`).
    """
    dividend_field = f"{prefix}_dividend"
    divisor_field = f"{prefix}_divisor"

    def _reverse(value: int, body: Any) -> dict[str, int]:
        seconds = value / body.frame_rate
        return {
            dividend_field: round(seconds * _TIME_DIVISOR),
            divisor_field: _TIME_DIVISOR,
        }

    return _reverse


def reverse_fractional(
    integer_field: str,
    fractional_field: str,
    *,
    scale: int = 65536,
) -> Callable[[float, Any], dict[str, int]]:
    """Split a float into an integer part and a scaled fractional part.

    Example: `29.97` -> `{integer: 29, fractional: round(0.97 * 65536)}`.

    Args:
        integer_field: Name of the integer-part field.
        fractional_field: Name of the fractional-part field.
        scale: Multiplier for the fractional part (default 65536).
    """

    def _reverse(value: float, _body: Any) -> dict[str, int]:
        integer = int(value)
        fractional = round((value - integer) * scale)
        return {integer_field: integer, fractional_field: fractional}

    return _reverse


def denormalize_value(value: float, *, scale: int = 255) -> int:
    """Denormalize a single 0.0-1.0 float back to an integer."""
    return round(value * scale)


def denormalize_values(value: list[float], *, scale: int = 255) -> list[int]:
    """Denormalize a list of 0.0-1.0 floats back to integers."""
    return [denormalize_value(v, scale=scale) for v in value]


def reverse_ratio(
    prefix: str,
    *,
    denominator_value: int = 100000,
) -> Callable[[float, Any], dict[str, int]]:
    """Decompose a float ratio into `{prefix}_dividend / divisor` fields.

    Example: `reverse_ratio("pixel_ratio")` with value `0.909091`
    -> `{"pixel_ratio_dividend": 909091, "pixel_ratio_divisor": 100000}`.

    Args:
        prefix: Field-name prefix (e.g. `"pixel_ratio"`).
        denominator_value: Fixed denominator (default 100000).
    """
    dividend_field = f"{prefix}_dividend"
    divisor_field = f"{prefix}_divisor"

    def _reverse(value: float, _body: Any) -> dict[str, int]:
        return {
            dividend_field: round(value * denominator_value),
            divisor_field: denominator_value,
        }

    return _reverse
