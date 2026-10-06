"""2x3 affine transforms and the SVG `transform` attribute parser.

An `Affine` is the matrix `[[a, c, e], [b, d, f]]` mapping
`(x, y) -> (a*x + c*y + e, b*x + d*y + f)`, matching SVG's
`matrix(a b c d e f)` ordering.
"""

from __future__ import annotations

import math
import re
from typing import NamedTuple

from ._util import NUMBER_RE
from .errors import UnsupportedSVGError


class Affine(NamedTuple):
    """A 2x3 affine transform in SVG `matrix(a b c d e f)` order."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def multiply(self, other: Affine) -> Affine:
        """Return `self @ other` (apply `other` first, then `self`)."""
        return Affine(
            a=self.a * other.a + self.c * other.b,
            b=self.b * other.a + self.d * other.b,
            c=self.a * other.c + self.c * other.d,
            d=self.b * other.c + self.d * other.d,
            e=self.a * other.e + self.c * other.f + self.e,
            f=self.b * other.e + self.d * other.f + self.f,
        )

    def apply(self, x: float, y: float) -> tuple[float, float]:
        """Map a point through the transform."""
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def apply_vector(self, x: float, y: float) -> tuple[float, float]:
        """Map a direction/offset (ignores translation)."""
        return (self.a * x + self.c * y, self.b * x + self.d * y)

    @property
    def mean_scale(self) -> float:
        """Geometric-mean scale factor (for scaling stroke widths)."""
        det = abs(self.a * self.d - self.b * self.c)
        return math.sqrt(det) if det > 0 else 1.0


IDENTITY = Affine()

# One transform function: name + parenthesized numeric args.
_FUNC_RE = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")


_FUNCTIONS = frozenset({"matrix", "translate", "scale", "rotate", "skewX", "skewY"})


def _numbers(text: str) -> list[float]:
    return [float(m) for m in NUMBER_RE.findall(text)]


def parse_transform(value: str) -> Affine:
    """Parse an SVG `transform` attribute into a single `Affine`.

    Supports `matrix`, `translate`, `scale`, `rotate`, `skewX`, `skewY`.
    Multiple functions compose left-to-right (the leftmost is applied
    last), per the SVG spec.

    Args:
        value: The `transform` attribute string.

    Returns:
        The composed transform (identity for an empty string, and for a
        malformed list: a known function with the wrong number of
        arguments or a non-finite one).

    Raises:
        UnsupportedSVGError: For an unknown transform function.
    """
    result = IDENTITY
    if not value:
        return result
    for name, args in _FUNC_RE.findall(value):
        nums = _numbers(args)
        if name not in _FUNCTIONS:
            raise UnsupportedSVGError(f"Unsupported transform function: {name!r}")
        if (
            not all(math.isfinite(x) for x in nums)
            or (name == "matrix" and len(nums) != 6)
            or (name in ("skewX", "skewY") and not nums)
        ):
            # An attribute in error is ignored as a whole (SVG 1.1 7.6); AE
            # 2026 imports a `matrix(1 0 0 1)` group untransformed.
            return IDENTITY
        result = result.multiply(_single_transform(name, nums))
    return result


def _single_transform(name: str, n: list[float]) -> Affine:
    """One transform function, its name and argument count already checked
    by `parse_transform`."""
    if name == "matrix":
        return Affine(n[0], n[1], n[2], n[3], n[4], n[5])
    if name == "translate":
        tx = n[0] if n else 0.0
        ty = n[1] if len(n) > 1 else 0.0
        return Affine(e=tx, f=ty)
    if name == "scale":
        sx = n[0] if n else 1.0
        sy = n[1] if len(n) > 1 else sx
        return Affine(a=sx, d=sy)
    if name == "rotate":
        ang = math.radians(n[0]) if n else 0.0
        cos, sin = math.cos(ang), math.sin(ang)
        rot = Affine(a=cos, b=sin, c=-sin, d=cos)
        if len(n) >= 3:
            cx, cy = n[1], n[2]
            # translate(cx,cy) . rotate . translate(-cx,-cy)
            return Affine(e=cx, f=cy).multiply(rot).multiply(Affine(e=-cx, f=-cy))
        return rot
    if name == "skewX":
        return Affine(c=math.tan(math.radians(n[0])))
    return Affine(b=math.tan(math.radians(n[0])))  # skewY
