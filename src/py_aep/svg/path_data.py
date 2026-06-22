"""SVG path `d` attribute parser.

Parses a path data string into subpaths of cubic bezier segments. Every
segment is represented as `(x0, y0, x1, y1, x2, y2, x3, y3)` so straight
lines, quadratics, and arcs all reduce to a single uniform form that the
shape converter turns into After Effects vertices + tangents.
"""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, NamedTuple

from ._util import NUMBER_RE
from .errors import UnsupportedSVGError

if TYPE_CHECKING:
    # A cubic segment: start, control 1, control 2, end.
    CubicSeg = tuple[float, float, float, float, float, float, float, float]


class RawSubpath(NamedTuple):
    """A run of cubic segments from one `M ... [Z]` group."""

    segments: list[CubicSeg]
    closed: bool


_COMMANDS = set("MmLlHhVvCcSsQqTtAaZz")
_CMD_RE = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")
# Argument count per command (per coordinate-set repetition).
_ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}


def _tokenize(d: str) -> list[str]:
    """Split a path `d` string into command and argument tokens.

    The elliptical-arc large-arc-flag and sweep-flag are single-character
    flags (`0`/`1`) in the W3C path grammar, so they may be written with no
    separator from each other or the following coordinate (e.g.
    `A5 5 0 11 0,10`). A context-free scan would misread `11` as the single
    number 11; this scanner tracks the active command and per-repetition
    argument index and peels off exactly one flag character at the two flag
    positions of an `A`/`a` command. Every other token matches the same
    number grammar as before, so non-arc paths tokenize identically.
    """
    tokens: list[str] = []
    i = 0
    n = len(d)
    cmd = ""
    arg = 0
    while i < n:
        c = d[i]
        if c == "," or c.isspace():
            i += 1
            continue
        if _CMD_RE.match(c):
            tokens.append(c)
            cmd = "" if c in "Zz" else c
            arg = 0
            i += 1
            continue
        argc = _ARGC.get(cmd.upper(), 0)
        # large-arc-flag (index 3) and sweep-flag (index 4) of each arc
        # repetition are single chars; peel one off so `11`/`110` split.
        if cmd.upper() == "A" and argc and arg % argc in (3, 4) and c in "01":
            tokens.append(c)
            arg += 1
            i += 1
            continue
        m = NUMBER_RE.match(d, i)
        if m and m.group():
            tokens.append(m.group())
            if argc:
                arg += 1
            i = m.end()
            continue
        # Unrecognized character: skip it, matching the prior findall scan
        # which silently ignored anything outside the command/number grammar.
        i += 1
    return tokens


def parse_path(d: str) -> list[RawSubpath]:
    """Parse an SVG path `d` string into cubic-bezier subpaths.

    Args:
        d: The path data string.

    Returns:
        Subpaths in document order; each holds cubic segments and a
        closed flag.

    Raises:
        UnsupportedSVGError: For malformed data or unknown commands.
    """
    tokens = _tokenize(d)
    parser = _PathParser(tokens)
    return parser.run()


class _PathParser:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._i = 0
        self.cx = 0.0
        self.cy = 0.0
        self.sx = 0.0
        self.sy = 0.0
        self._prev_cmd = ""
        # Last cubic control point (for S) and quadratic control (for T).
        self._prev_cubic_ctrl: tuple[float, float] | None = None
        self._prev_quad_ctrl: tuple[float, float] | None = None
        self._segs: list[CubicSeg] = []
        self._subpaths: list[RawSubpath] = []

    def run(self) -> list[RawSubpath]:
        cmd = ""
        while self._i < len(self._tokens):
            tok = self._tokens[self._i]
            if tok in _COMMANDS:
                cmd = tok
                self._i += 1
                if cmd in ("Z", "z"):
                    self._close()
                    cmd = ""
                    continue
            elif cmd == "":
                raise UnsupportedSVGError(f"Path data starts with a number: {tok!r}")
            else:
                # Implicit repeat: a subsequent M/m becomes L/l.
                if cmd == "M":
                    cmd = "L"
                elif cmd == "m":
                    cmd = "l"
            self._exec(cmd)
        self._flush(closed=False)
        return self._subpaths

    def _read_args(self, n: int) -> list[float]:
        args = []
        for _ in range(n):
            if self._i >= len(self._tokens) or self._tokens[self._i] in _COMMANDS:
                raise UnsupportedSVGError("Path data ended mid-command")
            args.append(float(self._tokens[self._i]))
            self._i += 1
        return args

    def _flush(self, closed: bool) -> None:
        if self._segs:
            self._subpaths.append(RawSubpath(self._segs, closed))
            self._segs = []

    def _close(self) -> None:
        if self._segs:
            # Add the closing straight segment back to the subpath start.
            if (self.cx, self.cy) != (self.sx, self.sy):
                self._segs.append(
                    (
                        self.cx,
                        self.cy,
                        self.cx,
                        self.cy,
                        self.sx,
                        self.sy,
                        self.sx,
                        self.sy,
                    )
                )
            self._subpaths.append(RawSubpath(self._segs, True))
            self._segs = []
        self.cx, self.cy = self.sx, self.sy
        self._prev_cubic_ctrl = None
        self._prev_quad_ctrl = None
        self._prev_cmd = "Z"

    def _line_to(self, x: float, y: float) -> None:
        self._segs.append((self.cx, self.cy, self.cx, self.cy, x, y, x, y))
        self.cx, self.cy = x, y

    def _cubic_to(
        self, x1: float, y1: float, x2: float, y2: float, x: float, y: float
    ) -> None:
        self._segs.append((self.cx, self.cy, x1, y1, x2, y2, x, y))
        self._prev_cubic_ctrl = (x2, y2)
        self.cx, self.cy = x, y

    def _quad_to(self, qx: float, qy: float, x: float, y: float) -> None:
        # Elevate quadratic to cubic.
        c1x = self.cx + 2.0 / 3.0 * (qx - self.cx)
        c1y = self.cy + 2.0 / 3.0 * (qy - self.cy)
        c2x = x + 2.0 / 3.0 * (qx - x)
        c2y = y + 2.0 / 3.0 * (qy - y)
        self._segs.append((self.cx, self.cy, c1x, c1y, c2x, c2y, x, y))
        self._prev_quad_ctrl = (qx, qy)
        self.cx, self.cy = x, y

    def _exec(self, cmd: str) -> None:  # noqa: C901 - flat command dispatch
        rel = cmd.islower()
        up = cmd.upper()
        a = self._read_args(_ARGC[up])
        ox, oy = (self.cx, self.cy) if rel else (0.0, 0.0)

        if up == "M":
            self._flush(closed=False)
            self.cx, self.cy = a[0] + ox, a[1] + oy
            self.sx, self.sy = self.cx, self.cy
        elif up == "L":
            self._line_to(a[0] + ox, a[1] + oy)
        elif up == "H":
            self._line_to(a[0] + (self.cx if rel else 0.0), self.cy)
        elif up == "V":
            self._line_to(self.cx, a[0] + (self.cy if rel else 0.0))
        elif up == "C":
            self._cubic_to(
                a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy, a[4] + ox, a[5] + oy
            )
        elif up == "S":
            if self._prev_cmd in ("C", "S") and self._prev_cubic_ctrl is not None:
                rx = 2 * self.cx - self._prev_cubic_ctrl[0]
                ry = 2 * self.cy - self._prev_cubic_ctrl[1]
            else:
                rx, ry = self.cx, self.cy
            self._cubic_to(rx, ry, a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy)
        elif up == "Q":
            self._quad_to(a[0] + ox, a[1] + oy, a[2] + ox, a[3] + oy)
        elif up == "T":
            if self._prev_cmd in ("Q", "T") and self._prev_quad_ctrl is not None:
                qx = 2 * self.cx - self._prev_quad_ctrl[0]
                qy = 2 * self.cy - self._prev_quad_ctrl[1]
            else:
                qx, qy = self.cx, self.cy
            self._quad_to(qx, qy, a[0] + ox, a[1] + oy)
        elif up == "A":
            self._arc_to(a[0], a[1], a[2], a[3] != 0, a[4] != 0, a[5] + ox, a[6] + oy)

        if up not in ("C", "S"):
            self._prev_cubic_ctrl = None
        if up not in ("Q", "T"):
            self._prev_quad_ctrl = None
        self._prev_cmd = up

    def _arc_to(
        self,
        rx: float,
        ry: float,
        phi_deg: float,
        large: bool,
        sweep: bool,
        x: float,
        y: float,
    ) -> None:
        """Convert an SVG elliptical arc to cubic segments (W3C algorithm)."""
        x1, y1 = self.cx, self.cy
        if rx == 0 or ry == 0:
            self._line_to(x, y)
            return
        rx, ry = abs(rx), abs(ry)
        phi = math.radians(phi_deg % 360.0)
        cos_p, sin_p = math.cos(phi), math.sin(phi)
        dx, dy = (x1 - x) / 2.0, (y1 - y) / 2.0
        x1p = cos_p * dx + sin_p * dy
        y1p = -sin_p * dx + cos_p * dy
        # Correct out-of-range radii.
        lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
        if lam > 1:
            s = math.sqrt(lam)
            rx, ry = rx * s, ry * s
        num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
        den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
        co = math.sqrt(max(0.0, num / den)) if den != 0 else 0.0
        if large == sweep:
            co = -co
        cxp = co * rx * y1p / ry
        cyp = -co * ry * x1p / rx
        cx_ = cos_p * cxp - sin_p * cyp + (x1 + x) / 2.0
        cy_ = sin_p * cxp + cos_p * cyp + (y1 + y) / 2.0

        def angle(ux: float, uy: float, vx: float, vy: float) -> float:
            dot = ux * vx + uy * vy
            ln = math.hypot(ux, uy) * math.hypot(vx, vy)
            ang = math.acos(max(-1.0, min(1.0, dot / ln))) if ln else 0.0
            return -ang if (ux * vy - uy * vx) < 0 else ang

        theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
        dtheta = angle(
            (x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry
        )
        if not sweep and dtheta > 0:
            dtheta -= 2 * math.pi
        elif sweep and dtheta < 0:
            dtheta += 2 * math.pi

        n_segs = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2.0))))
        delta = dtheta / n_segs
        t = 4.0 / 3.0 * math.tan(delta / 4.0)
        theta = theta1
        for _ in range(n_segs):
            cos1, sin1 = math.cos(theta), math.sin(theta)
            cos2, sin2 = math.cos(theta + delta), math.sin(theta + delta)
            ep_x = cos_p * rx * cos2 - sin_p * ry * sin2 + cx_
            ep_y = sin_p * rx * cos2 + cos_p * ry * sin2 + cy_
            d1x, d1y = -rx * sin1, ry * cos1
            d2x, d2y = -rx * sin2, ry * cos2
            c1x = self.cx + t * (cos_p * d1x - sin_p * d1y)
            c1y = self.cy + t * (sin_p * d1x + cos_p * d1y)
            c2x = ep_x - t * (cos_p * d2x - sin_p * d2y)
            c2y = ep_y - t * (sin_p * d2x + cos_p * d2y)
            self._segs.append((self.cx, self.cy, c1x, c1y, c2x, c2y, ep_x, ep_y))
            self.cx, self.cy = ep_x, ep_y
            theta += delta
