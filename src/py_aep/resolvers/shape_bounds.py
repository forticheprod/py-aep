"""Content bounds of a shape layer, for `AVLayer.source_rect_at_time`.

Rules measured on After Effects 2026 (`sourceRectAtTime` on shape layers
built by script, covering every shape type, stroke join and cap, group
transform and nesting case below):

- Only painted paths count: a Fill, Stroke, Gradient Fill or Gradient
  Stroke paints the paths above it in its group, nested groups included.
  A path with no paint below it adds nothing, and a layer with no painted
  path measures `0, 0, 0, 0`. Disabled items are skipped.
- The geometry box is the tight bounds of the painted paths in layer
  space, curves included (the extremes of each cubic, not its control
  points).
- `extents` adds, for every stroke, the tight bounds of its paths in the
  stroke's own group space grown on each side by `width / 2`, times
  `miter limit + 1` for a Miter join, times `sqrt(2)` for a Projecting
  (square) cap - even on a closed path - and mapped to layer space as a
  box. Dashes do not change it; the widest stroke wins.
- Parametric shapes are the paths After Effects draws: an ellipse is four
  cubic arcs with the circle constant `4/3 * (sqrt(2) - 1)`, a polystar
  vertex's roundness handle is `radius * roundness% * kappa * sin(pi /
  points)` long. A rectangle's rounded corners stay inside it.
- A group maps its content to its parent by `translate(position) *
  rotate * skew * scale * translate(-anchor)`, the skew shearing by
  `-tan(skew)` along the skew axis.
- Trim Paths and Repeater leave the box unchanged; Offset Paths grows it
  (and the other path operations were not measured), so those raise
  `NotImplementedError`.

Expressions are not evaluated: values are read before any expression, as
`Property.value_at_time` reads them.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, cast

from ..svg.transform import IDENTITY, Affine

if TYPE_CHECKING:
    from typing import Any

    from ..models.properties.property import Property
    from ..models.properties.property_group import PropertyGroup
    from ..models.properties.shape import Shape

    _Point = tuple[float, float]
    _Segment = tuple[_Point, _Point, _Point, _Point]
    _Path = list[_Segment]

_KAPPA = 4 / 3 * (math.sqrt(2) - 1)

_FILLS = frozenset({"ADBE Vector Graphic - Fill", "ADBE Vector Graphic - G-Fill"})
_STROKES = frozenset({"ADBE Vector Graphic - Stroke", "ADBE Vector Graphic - G-Stroke"})
# Path operations whose presence leaves the measured box unchanged.
_BOX_NEUTRAL_FILTERS = frozenset(
    {"ADBE Vector Filter - Trim", "ADBE Vector Filter - Repeater"}
)
_MITER_JOIN = 1
_SQUARE_CAP = 3


class BoxAccumulator:
    """A growing `(left, top, right, bottom)` accumulator."""

    def __init__(self) -> None:
        self.left = self.top = math.inf
        self.right = self.bottom = -math.inf

    def add(self, left: float, top: float, right: float, bottom: float) -> None:
        self.left = min(self.left, left)
        self.top = min(self.top, top)
        self.right = max(self.right, right)
        self.bottom = max(self.bottom, bottom)

    def add_box(self, other: BoxAccumulator) -> None:
        if other.left <= other.right:
            self.add(other.left, other.top, other.right, other.bottom)

    def rect(self) -> dict[str, float]:
        if self.left > self.right:
            return {"top": 0.0, "left": 0.0, "width": 0.0, "height": 0.0}
        return {
            "top": self.top,
            "left": self.left,
            "width": self.right - self.left,
            "height": self.bottom - self.top,
        }


def _value(group: PropertyGroup, match_name: str, time: float) -> Any:
    return cast("Property", group[match_name]).value_at_time(time)


# ---------------------------------------------------------------------------
# Affine maps (`svg.transform.Affine`: x' = a*x + c*y + e, y' = b*x + d*y + f)
# ---------------------------------------------------------------------------


def _rotation(degrees: float) -> Affine:
    r = math.radians(degrees)
    return Affine(math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0)


def _map_path(m: Affine, path: _Path) -> _Path:
    return [
        (m.apply(*p0), m.apply(*p1), m.apply(*p2), m.apply(*p3))
        for p0, p1, p2, p3 in path
    ]


def _group_matrix(transform: PropertyGroup, time: float) -> Affine:
    anchor = _value(transform, "ADBE Vector Anchor", time)
    position = _value(transform, "ADBE Vector Position", time)
    scale = _value(transform, "ADBE Vector Scale", time)
    skew = math.tan(math.radians(_value(transform, "ADBE Vector Skew", time)))
    axis = _value(transform, "ADBE Vector Skew Axis", time)
    shear = _rotation(-axis).multiply(
        Affine(1.0, 0.0, -skew, 1.0, 0.0, 0.0).multiply(_rotation(axis))
    )
    m = Affine(1.0, 0.0, 0.0, 1.0, -anchor[0], -anchor[1])
    m = Affine(scale[0] / 100, 0.0, 0.0, scale[1] / 100, 0.0, 0.0).multiply(m)
    m = shear.multiply(m)
    m = _rotation(_value(transform, "ADBE Vector Rotation", time)).multiply(m)
    return Affine(1.0, 0.0, 0.0, 1.0, position[0], position[1]).multiply(m)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------


def _closed_path(
    vertices: list[_Point], ins: list[_Point], outs: list[_Point], closed: bool
) -> _Path:
    """Cubic segments from vertices and handles relative to them."""
    count = len(vertices)
    path: _Path = []
    for i in range(count if closed else count - 1):
        j = (i + 1) % count
        (x0, y0), (x3, y3) = vertices[i], vertices[j]
        path.append(
            (
                (x0, y0),
                (x0 + outs[i][0], y0 + outs[i][1]),
                (x3 + ins[j][0], y3 + ins[j][1]),
                (x3, y3),
            )
        )
    return path


def _rect_path(item: PropertyGroup, time: float) -> _Path:
    w, h = _value(item, "ADBE Vector Rect Size", time)
    x, y = _value(item, "ADBE Vector Rect Position", time)
    r = min(
        max(_value(item, "ADBE Vector Rect Roundness", time), 0.0),
        abs(w) / 2,
        abs(h) / 2,
    )
    left, top, right, bottom = x - w / 2, y - h / 2, x + w / 2, y + h / 2
    if r == 0:
        corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
        zero = [(0.0, 0.0)] * 4
        return _closed_path(corners, zero, zero, True)
    k = r * _KAPPA
    vertices = [
        (left + r, top), (right - r, top),
        (right, top + r), (right, bottom - r),
        (right - r, bottom), (left + r, bottom),
        (left, bottom - r), (left, top + r),
    ]  # fmt: skip
    outs = [(0, 0), (k, 0), (0, 0), (0, k), (0, 0), (-k, 0), (0, 0), (0, -k)]
    ins = [(-k, 0), (0, 0), (0, -k), (0, 0), (k, 0), (0, 0), (0, k), (0, 0)]
    return _closed_path(vertices, ins, outs, True)


def _ellipse_path(item: PropertyGroup, time: float) -> _Path:
    w, h = _value(item, "ADBE Vector Ellipse Size", time)
    x, y = _value(item, "ADBE Vector Ellipse Position", time)
    rx, ry = w / 2, h / 2
    kx, ky = rx * _KAPPA, ry * _KAPPA
    vertices = [(x, y - ry), (x + rx, y), (x, y + ry), (x - rx, y)]
    outs = [(kx, 0.0), (0.0, ky), (-kx, 0.0), (0.0, -ky)]
    ins = [(-kx, 0.0), (0.0, -ky), (kx, 0.0), (0.0, ky)]
    return _closed_path(vertices, ins, outs, True)


def _polystar_path(item: PropertyGroup, time: float) -> _Path:
    points = _value(item, "ADBE Vector Star Points", time)
    if points != int(points):
        raise NotImplementedError(
            "source_rect_at_time does not model a polystar with a fractional "
            f"number of points ({points})"
        )
    points = int(points)
    star = _value(item, "ADBE Vector Star Type", time) == 1
    x, y = _value(item, "ADBE Vector Star Position", time)
    outer = _value(item, "ADBE Vector Star Outer Radius", time)
    outer_round = _value(item, "ADBE Vector Star Outer Roundess", time) / 100
    inner = _value(item, "ADBE Vector Star Inner Radius", time) if star else outer
    inner_round = (
        _value(item, "ADBE Vector Star Inner Roundess", time) / 100
        if star
        else outer_round
    )
    count = points * 2 if star else points
    handle = _KAPPA * math.sin(math.pi / points)
    angle = -math.pi / 2 + math.radians(_value(item, "ADBE Vector Star Rotation", time))
    vertices, ins, outs = [], [], []
    for i in range(count):
        radius, roundness = (
            (outer, outer_round) if i % 2 == 0 or not star else (inner, inner_round)
        )
        cos, sin = math.cos(angle), math.sin(angle)
        length = radius * roundness * handle
        vertices.append((x + radius * cos, y + radius * sin))
        # The handles run along the circle's tangent at the vertex.
        ins.append((sin * length, -cos * length))
        outs.append((-sin * length, cos * length))
        angle += 2 * math.pi / count
    return _closed_path(vertices, ins, outs, True)


def _bezier_path(item: PropertyGroup, time: float) -> _Path:
    shape = cast(
        "Shape", cast("Property", item["ADBE Vector Shape"]).value_at_time(time)
    )
    vertices = [(v[0], v[1]) for v in shape.vertices]
    if not vertices:
        return []
    return _closed_path(
        vertices,
        [(t[0], t[1]) for t in shape.in_tangents],
        [(t[0], t[1]) for t in shape.out_tangents],
        shape.closed,
    )


_PATH_BUILDERS = {
    "ADBE Vector Shape - Rect": _rect_path,
    "ADBE Vector Shape - Ellipse": _ellipse_path,
    "ADBE Vector Shape - Star": _polystar_path,
    "ADBE Vector Shape - Group": _bezier_path,
}


def cubic_range(a: float, b: float, c: float, d: float) -> tuple[float, float]:
    """The exact range of one cubic coordinate over `t` in `[0, 1]`."""
    low, high = min(a, d), max(a, d)
    qa = -a + 3 * b - 3 * c + d
    qb = 2 * (a - 2 * b + c)
    qc = b - a
    if abs(qa) < 1e-12:
        roots = [-qc / qb] if abs(qb) > 1e-12 else []
    else:
        disc = qb * qb - 4 * qa * qc
        if disc < 0:
            roots = []
        else:
            root = math.sqrt(disc)
            roots = [(-qb + root) / (2 * qa), (-qb - root) / (2 * qa)]
    for t in roots:
        if 0 < t < 1:
            mt = 1 - t
            v = mt**3 * a + 3 * mt * mt * t * b + 3 * mt * t * t * c + t**3 * d
            low, high = min(low, v), max(high, v)
    return low, high


def _path_box(path: _Path) -> BoxAccumulator:
    box = BoxAccumulator()
    for p0, p1, p2, p3 in path:
        left, right = cubic_range(p0[0], p1[0], p2[0], p3[0])
        top, bottom = cubic_range(p0[1], p1[1], p2[1], p3[1])
        box.add(left, top, right, bottom)
    return box


def _stroke_reach(item: PropertyGroup, time: float) -> float:
    reach = _value(item, "ADBE Vector Stroke Width", time) / 2
    if _value(item, "ADBE Vector Stroke Line Join", time) == _MITER_JOIN:
        reach *= _value(item, "ADBE Vector Stroke Miter Limit", time) + 1
    if _value(item, "ADBE Vector Stroke Line Cap", time) == _SQUARE_CAP:
        reach *= math.sqrt(2)
    return float(reach)


# ---------------------------------------------------------------------------
# Walk
# ---------------------------------------------------------------------------


def _walk(
    contents: PropertyGroup,
    time: float,
    to_layer: Affine,
    geometry: BoxAccumulator,
    extents: BoxAccumulator,
) -> list[_Path]:
    """Paint `contents`' paths into the boxes; return its paths in its space."""
    pending: list[_Path] = []
    # The geometry box is a union, so a path painted again adds nothing: only
    # the paths after the last paint are measured into it.
    painted = 0
    for item in contents.properties:
        if not item.enabled:
            continue
        match_name = item.match_name
        if match_name == "ADBE Vector Group":
            group = cast("PropertyGroup", item)
            local = _group_matrix(
                cast("PropertyGroup", group["ADBE Vector Transform Group"]), time
            )
            children = _walk(
                cast("PropertyGroup", group["ADBE Vectors Group"]),
                time,
                to_layer.multiply(local),
                geometry,
                extents,
            )
            pending.extend(_map_path(local, path) for path in children)
        elif match_name in _PATH_BUILDERS:
            pending.append(
                _PATH_BUILDERS[match_name](cast("PropertyGroup", item), time)
            )
        elif match_name in _FILLS or match_name in _STROKES:
            reach = (
                _stroke_reach(cast("PropertyGroup", item), time)
                if match_name in _STROKES
                else None
            )
            for path in pending[painted:]:
                if path:
                    geometry.add_box(_path_box(_map_path(to_layer, path)))
            painted = len(pending)
            if reach is None:
                continue
            for path in pending:
                if path:
                    local_box = _path_box(path)
                    corners = [
                        (local_box.left - reach, local_box.top - reach),
                        (local_box.right + reach, local_box.top - reach),
                        (local_box.right + reach, local_box.bottom + reach),
                        (local_box.left - reach, local_box.bottom + reach),
                    ]
                    mapped = [to_layer.apply(*corner) for corner in corners]
                    extents.add(
                        min(p[0] for p in mapped),
                        min(p[1] for p in mapped),
                        max(p[0] for p in mapped),
                        max(p[1] for p in mapped),
                    )
        elif match_name.startswith("ADBE Vector Filter") and (
            match_name not in _BOX_NEUTRAL_FILTERS
        ):
            raise NotImplementedError(
                f"source_rect_at_time does not model the {item.name!r} path operation"
            )
    return pending


def shape_layer_rect(
    root: PropertyGroup, time: float, extents: bool
) -> dict[str, float]:
    """`sourceRectAtTime` of a shape layer's `ADBE Root Vectors Group`.

    Args:
        root: The layer's contents group.
        time: Composition time in seconds.
        extents: `True` to include the stroke extents.

    Returns:
        A dict with `top`, `left`, `width` and `height` keys.

    Raises:
        NotImplementedError: For a path operation other than Trim Paths
            and Repeater, or a polystar with a fractional number of points.
    """
    geometry, stroke_boxes = BoxAccumulator(), BoxAccumulator()
    _walk(root, time, IDENTITY, geometry, stroke_boxes)
    if extents:
        geometry.add_box(stroke_boxes)
    return geometry.rect()
