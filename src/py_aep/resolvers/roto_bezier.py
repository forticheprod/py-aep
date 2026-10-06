"""The tangents After Effects draws a RotoBezier mask path with.

A RotoBezier mask ignores its stored direction handles: After Effects
derives every vertex's tangents from the vertices and a per-vertex tension
(the shape value's `omtn` chunk), and reports those through
`Shape.in_tangents` / `out_tangents`. Rules measured on After Effects 2026
by reading back masks with patched tensions and aspects (3-6 vertices, open
and closed paths, collinear and repeated vertices, keyed paths):

- Tangents are computed in normalized mask space with x scaled by the Mask
  Path's stored aspect (`Tdb4Chunk.pixel_aspect`: the layer's width /
  height, so pixel space, in current files).
- With `k = (1 - tension) / 2`, an interior vertex (every vertex of a closed
  path) points along `next - prev`: its in tangent is `k` times the distance
  to the previous vertex, its out tangent `k` times the distance to the
  next one. A zero `next - prev` chord gives zero tangents.
- An open path's last vertex aims its in tangent at the previous vertex's
  out handle, then its first vertex aims its out tangent at the second
  vertex's in handle, each scaled by the end's own `k`; the outer tangents
  stay zero.
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
    closed: bool,
    tensions: Sequence[float],
    scale_x: float,
    scale_y: float,
) -> tuple[list[list[float]], list[list[float]]]:
    """`(in_tangents, out_tangents)` of a RotoBezier path.

    Args:
        vertices: The path's vertices, in layer pixels.
        closed: Whether the path is closed.
        tensions: One tension per vertex.
        scale_x: Multiplier from layer pixels to the measuring space along x
            (the stored aspect over the layer width).
        scale_y: The same along y (one over the layer height).
    """
    points = [(x * scale_x, y * scale_y) for x, y in vertices]
    count = len(points)
    ks = [(1.0 - t) * 0.5 for t in tensions]
    ins = [[0.0, 0.0] for _ in range(count)]
    outs = [[0.0, 0.0] for _ in range(count)]
    for i in range(count) if closed else range(1, count - 1):
        vx, vy = points[i]
        px, py = points[i - 1]
        nx, ny = points[(i + 1) % count]
        chord = math.hypot(nx - px, ny - py)
        if chord < 1e-12:
            continue
        ux, uy = (nx - px) / chord, (ny - py) / chord
        before = math.hypot(vx - px, vy - py) * ks[i]
        after = math.hypot(nx - vx, ny - vy) * ks[i]
        ins[i] = [-ux * before, -uy * before]
        outs[i] = [ux * after, uy * after]
    if not closed and count >= 2:
        (lx, ly), (bx, by) = points[-1], points[-2]
        ins[-1] = [
            (bx + outs[-2][0] - lx) * ks[-1],
            (by + outs[-2][1] - ly) * ks[-1],
        ]
        (fx, fy), (sx, sy) = points[0], points[1]
        outs[0] = [
            (sx + ins[1][0] - fx) * ks[0],
            (sy + ins[1][1] - fy) * ks[0],
        ]
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
