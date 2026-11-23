"""The tangents After Effects draws a RotoBezier mask path with.

After Effects re-aims a RotoBezier mask's stored direction handles from the
vertices and a per-vertex tension (the shape value's `omtn` chunk), and
reports the result through `Shape.in_tangents` / `out_tangents`. Rules
measured on After Effects 2026 by reading back masks with patched tensions
and aspects (1-6 vertices, open and closed paths, collinear and repeated
vertices, near-coincident neighbours, keyed paths):

- Tangents are computed in normalized mask space with x scaled by the Mask
  Path's stored aspect (`Tdb4Chunk.pixel_aspect`: the layer's width /
  height, so pixel space, in current files).
- With `k = (1 - tension) / 2`, an interior vertex (every vertex of a closed
  path) points along `next - prev`: its in tangent is `k` times the distance
  to the previous vertex, its out tangent `k` times the distance to the
  next one.
- An open path's last vertex aims its in tangent at the previous vertex's
  out handle, then its first vertex aims its out tangent at the second
  vertex's in handle, each scaled by the end's own `k`; the outer tangents
  become zero. On a two-vertex path the last vertex aims at the stored out
  handle of the first.
- A vertex whose `next - prev` chord is shorter than 1e-6 in that space,
  and the vertex of a one-vertex path, keep their stored handles.
- A shape value without tensions uses 1/3 for every vertex.
- Between keyframes, the tensions blend linearly with the path's progress. A
  keyframe without tensions contributes 1 at a vertex whose stored handles
  are both zero, 1/3 at any other.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_TENSION = 1.0 / 3.0


def roto_bezier_tangents(
    vertices: Sequence[Sequence[float]],
    in_tangents: Sequence[Sequence[float]],
    out_tangents: Sequence[Sequence[float]],
    closed: bool,
    tensions: Sequence[float],
    scale_x: float,
    scale_y: float,
) -> tuple[list[list[float]], list[list[float]]]:
    """`(in_tangents, out_tangents)` of a RotoBezier path.

    Args:
        vertices: The path's vertices, in layer pixels.
        in_tangents: The stored incoming handles, in layer pixels.
        out_tangents: The stored outgoing handles, in layer pixels.
        closed: Whether the path is closed.
        tensions: One tension per vertex.
        scale_x: Multiplier from layer pixels to the measuring space along x
            (the stored aspect over the layer width).
        scale_y: The same along y (one over the layer height).
    """
    points = [(x * scale_x, y * scale_y) for x, y in vertices]
    count = len(points)
    ks = [(1.0 - t) * 0.5 for t in tensions]
    ins = [[x * scale_x, y * scale_y] for x, y in in_tangents]
    outs = [[x * scale_x, y * scale_y] for x, y in out_tangents]

    def aim(i: int, prev: tuple[float, float], nxt: tuple[float, float]) -> None:
        vx, vy = points[i]
        px, py = prev
        nx, ny = nxt
        dx, dy = nx - px, ny - py
        # A chord shorter than 1e-6 keeps the stored handles.
        if dx * dx + dy * dy < 1e-12:
            return
        chord = math.hypot(dx, dy)
        ux, uy = dx / chord, dy / chord
        before = math.hypot(vx - px, vy - py) * ks[i]
        after = math.hypot(nx - vx, ny - vy) * ks[i]
        ins[i] = [-ux * before, -uy * before]
        outs[i] = [ux * after, uy * after]

    for i in range(count) if closed else range(1, count - 1):
        aim(i, points[i - 1], points[(i + 1) % count])
    if not closed and count >= 2:
        bx, by = points[-2]
        aim(count - 1, (bx + outs[-2][0], by + outs[-2][1]), points[-1])
        sx, sy = points[1]
        aim(0, points[0], (sx + ins[1][0], sy + ins[1][1]))
    return (
        [[x / scale_x, y / scale_y] for x, y in ins],
        [[x / scale_x, y / scale_y] for x, y in outs],
    )


def keyframe_tensions(
    tensions: Sequence[float],
    in_tangents: Sequence[Sequence[float]],
    out_tangents: Sequence[Sequence[float]],
) -> list[float]:
    """The tensions a keyframe's path contributes to an in-between value:
    its own, or, when it has none, 1 at a vertex whose stored handles are
    both zero and 1/3 at any other."""
    if len(tensions) == len(in_tangents):
        return list(tensions)
    return [
        1.0 if not any(a) and not any(b) else DEFAULT_TENSION
        for a, b in zip(in_tangents, out_tangents)
    ]
