"""The curves of the Curves effect (`ADBE CurvesCustom-0001`).

After Effects keeps them as the effect's own arbitrary data: an `aRbp`
chunk of 1644 big-endian bytes in a `LIST:aRbs` beside the property's
`tdbs`.

- `u16` version (1), then `u16` mode: 1 when the curves are drawn with
  points, 0 when drawn with the pencil. The maps are then the curves and
  the points are stale.
- Five 256-entry `u8` maps, in the channel order RGB (the master), red,
  green, blue, alpha. With points, each is its curve rounded to the
  nearest level and clamped to 0..255. 8 bpc renders these maps.
- Five 72-byte records in the same order:
  - 16 `(i16 x, i16 y)` point slots, input then output, in 0..255;
  - a `u32` count of the live slots (the slots past it hold stale points,
    or junk);
  - an `i32` selected point (-1 for none).

A curve through points is the natural cubic spline through them (second
derivative 0 at both ends, a straight line through two points). It is flat
beyond the first and last points, and clamped to 0..1 in 8 and 16 bpc. The
master applies after a channel's own curve,
`out = master(channel(in))`. Alpha has its own curve, and colour is never
unpremultiplied.
"""

from __future__ import annotations

import math
import struct
from typing import Sequence

CURVES_CHANNELS = ("rgb", "red", "green", "blue", "alpha")
"""Channel names, in After Effects' order: `rgb` is the master curve."""

_SIZE = 4 + 5 * 256 + 5 * 72
_MAPS = 4
_RECORDS = 4 + 5 * 256
_RECORD = 72
_SLOTS = 16


class _NaturalSpline:
    """Natural cubic spline through `(x, y)` points, flat outside them."""

    def __init__(self, points: Sequence[tuple[float, float]]) -> None:
        pts = sorted((float(x), float(y)) for x, y in points)
        self.xs = [p[0] for p in pts]
        self.ys = [p[1] for p in pts]
        n = len(pts)
        # Second derivatives, 0 at both ends.
        self.m = [0.0] * n
        if n < 3:
            return
        xs, ys = self.xs, self.ys
        h = [xs[i + 1] - xs[i] for i in range(n - 1)]
        a = [0.0] * n
        b = [1.0] * n
        c = [0.0] * n
        d = [0.0] * n
        for i in range(1, n - 1):
            a[i] = h[i - 1]
            b[i] = 2.0 * (h[i - 1] + h[i])
            c[i] = h[i]
            d[i] = 6.0 * ((ys[i + 1] - ys[i]) / h[i] - (ys[i] - ys[i - 1]) / h[i - 1])
        for i in range(1, n):
            w = a[i] / b[i - 1]
            b[i] -= w * c[i - 1]
            d[i] -= w * d[i - 1]
        self.m[n - 1] = d[n - 1] / b[n - 1]
        for i in range(n - 2, -1, -1):
            self.m[i] = (d[i] - c[i] * self.m[i + 1]) / b[i]

    def _segment(self, x: float) -> int:
        xs = self.xs
        lo, hi = 0, len(xs) - 2
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid - 1
        return lo

    def __call__(self, x: float) -> float:
        xs, ys, m = self.xs, self.ys, self.m
        if len(xs) == 1 or x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = self._segment(x)
        h = xs[i + 1] - xs[i]
        u = (xs[i + 1] - x) / h
        v = 1.0 - u
        return u * ys[i] + v * ys[i + 1] + ((u**3 - u) * m[i] + (v**3 - v) * m[i + 1]) * h * h / 6.0

    def slope(self, x: float, side: int = 1) -> float:
        """dy/dx at `x`, on the segment right of it (`side` 1) or left of it (-1)."""
        xs, ys, m = self.xs, self.ys, self.m
        if len(xs) < 2 or x < xs[0] or x > xs[-1]:
            return 0.0
        if (x == xs[0] and side < 0) or (x == xs[-1] and side > 0):
            return 0.0
        i = self._segment(x - 1e-12 if side < 0 else x)
        i = min(max(i, 0), len(xs) - 2)
        h = xs[i + 1] - xs[i]
        u = (xs[i + 1] - x) / h
        v = 1.0 - u
        return (ys[i + 1] - ys[i]) / h + (-(3 * u * u - 1) * m[i] + (3 * v * v - 1) * m[i + 1]) * h / 6.0


class CurvesChannel:
    """One channel's curve: its points and its 8-bit map."""

    def __init__(self, name: str, points: list[tuple[int, int]], lut: bytes, selected: int) -> None:
        self.name = name
        self.points = points
        """The live points, `(input, output)` in 0..255."""
        self.map = lut
        """256 output levels, one per input level."""
        self.selected = selected
        self._spline: _NaturalSpline | None = None

    def spline(self) -> _NaturalSpline:
        """The natural cubic spline through the points, in 0..255 on both axes."""
        if self._spline is None:
            self._spline = _NaturalSpline(self.points)
        return self._spline

    @property
    def is_identity(self) -> bool:
        return all(v == i for i, v in enumerate(self.map)) and all(x == y for x, y in self.points)

    def __repr__(self) -> str:
        return f"CurvesChannel({self.name!r}, points={self.points!r})"


class Curves:
    """The five curves of a Curves effect.

    Read only: a change is not written back to the project.
    """

    def __init__(self, data: bytes) -> None:
        if len(data) != _SIZE:
            raise ValueError(f"a Curves value is {_SIZE} bytes, not {len(data)}")
        self.version, self.mode = struct.unpack_from(">HH", data, 0)
        self.channels: dict[str, CurvesChannel] = {}
        for c, name in enumerate(CURVES_CHANNELS):
            lut = bytes(data[_MAPS + 256 * c : _MAPS + 256 * (c + 1)])
            offset = _RECORDS + _RECORD * c
            slots = struct.unpack_from(f">{2 * _SLOTS}h", data, offset)
            count, selected = struct.unpack_from(">Ii", data, offset + 4 * _SLOTS)
            count = min(count, _SLOTS)
            points = [(slots[2 * i], slots[2 * i + 1]) for i in range(count)]
            if len(points) < 2:
                # Nothing usable: the channel's map is all there is.
                points = [(0, lut[0]), (255, lut[255])]
            self.channels[name] = CurvesChannel(name, points, lut, selected)

    @property
    def uses_points(self) -> bool:
        """Whether the curves go through their points; if not they were drawn with the pencil and
        their maps are what renders."""
        return self.mode != 0

    def evaluate(self, channel: str, x: float, clamp: bool = True) -> float:
        """One channel's curve at `x` in 0..1, on its own (not through the master), as 16 bpc renders
        it. `clamp=False` leaves the spline's overshoot as 32 bpc does between the points."""
        ch = self.channels[channel]
        if self.uses_points:
            y = ch.spline()(x * 255.0) / 255.0
        else:
            f = min(max(x, 0.0), 1.0) * 255.0
            i = min(int(math.floor(f)), 254)
            t = f - i
            y = (ch.map[i] * (1.0 - t) + ch.map[i + 1] * t) / 255.0
        return min(max(y, 0.0), 1.0) if clamp else y

    def __repr__(self) -> str:
        edited = [n for n, c in self.channels.items() if not c.is_identity]
        return f"Curves(mode={self.mode}, edited={edited})"
