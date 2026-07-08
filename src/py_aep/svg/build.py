"""Build a shape layer's Contents from parsed SVG drawables.

Translates [SvgDrawable][py_aep.svg.types.SvgDrawable]s into After Effects
shape groups through the public `add_property` API - one `ADBE Vector
Group` per drawable, in reverse document order (AE Contents index 0
renders on top, matching SVG's last-painted-on-top), each holding the
path(s), stroke, and fill. Solid paints become Fill/Stroke; gradient
paints become Gradient Fill/Stroke (G-Fill/G-Stroke) with the start/end
points, type, and color stops AE writes for an SVG import.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, cast

from ..binary.bin_utils import to_f4
from ..models.properties.gradient import (
    Gradient,
    GradientAlphaStop,
    GradientColorStop,
)
from ..models.properties.shape import Shape
from .types import GradientPaint, SolidPaint, StrokeStyle, SvgDrawable

if TYPE_CHECKING:
    from ..models.properties.property import Property
    from ..models.properties.property_group import PropertyGroup

_GRAD_TYPE = {"linear": 1.0, "radial": 2.0}


def _leaf(group: PropertyGroup, match_name: str) -> Property:
    """Return a child leaf property (narrowed from `Property | PropertyGroup`)."""
    return cast("Property", group[match_name])


def _grp(prop: object) -> PropertyGroup:
    """Narrow an `add_property` / child result to `PropertyGroup`."""
    return cast("PropertyGroup", prop)


def build_shape_layer_contents(
    contents: PropertyGroup, drawables: list[SvgDrawable]
) -> None:
    """Populate a shape layer's Root Vectors Group from SVG drawables.

    Args:
        contents: The layer's `ADBE Root Vectors Group` property group.
        drawables: Drawables in SVG document order; added in reverse so
            the document's last-painted shape ends up on top.
    """
    for drawable in reversed(drawables):
        _add_drawable(contents, drawable)


def _add_drawable(contents: PropertyGroup, drawable: SvgDrawable) -> None:
    group = _grp(contents.add_property("ADBE Vector Group"))
    inner = _grp(group["ADBE Vectors Group"])

    # AE stores each group's vertices centred on their bounding box and puts
    # the offset in the group's Vector Position (verified against AE's own
    # SVG import). Mirror that so the output matches AE byte-for-byte.
    cx, cy = _bbox_center(drawable)
    for subpath in drawable.subpaths:
        path_group = _grp(inner.add_property("ADBE Vector Shape - Group"))
        _leaf(path_group, "ADBE Vector Shape").value = Shape(
            [[v[0] - cx, v[1] - cy] for v in subpath.vertices],
            in_tangents=[list(t) for t in subpath.in_tangents],
            out_tangents=[list(t) for t in subpath.out_tangents],
            closed=subpath.closed,
        )

    # A compound path (one SVG `<path>` with several subpaths) needs a Merge
    # Paths op so overlapping subpaths cut holes via the nonzero winding rule;
    # without it AE fills each subpath solid and the holes disappear. AE adds
    # one (Merge Type 1 = "Merge", the default) after the paths, before paint.
    if len(drawable.subpaths) > 1:
        inner.add_property("ADBE Vector Filter - Merge")

    # Stroke is listed before fill so it renders on top (SVG paint order).
    # AE flattens an SVG group/element opacity into the paint's Fill/Stroke
    # Opacity (verified against AE's own import), so pass it through.
    if drawable.stroke is not None:
        _add_stroke(inner, drawable.stroke, cx, cy, drawable.opacity)
    if drawable.fill is not None:
        _add_fill(inner, drawable.fill, cx, cy, drawable.opacity)

    transform = _grp(group["ADBE Vector Transform Group"])
    _leaf(transform, "ADBE Vector Position").value = [cx, cy]


def _bbox_center(drawable: SvgDrawable) -> tuple[float, float]:
    """Centre of the bounding box of all the drawable's vertices."""
    xs = [v[0] for sp in drawable.subpaths for v in sp.vertices]
    ys = [v[1] for sp in drawable.subpaths for v in sp.vertices]
    if not xs:
        return (0.0, 0.0)
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def _opacity_pct(alpha: float) -> float | None:
    """AE's 8-bit-quantized Fill/Stroke Opacity percentage for a 0-1 alpha.

    AE stores opacity as an 8-bit value, so `0.3` becomes
    `round(0.3*255)=77` -> `77/255*100` = 30.196% (as float32), not 30.0%
    (verified against AE 2026's SVG import: group opacity 0.3 -> 30.196,
    0.5 -> 50.196). Returns `None` when fully opaque, since AE omits the
    default 100%.
    """
    a8 = math.floor(to_f4(alpha) * 255.0 + 0.5)
    if a8 >= 255:
        return None
    return to_f4(a8 / 255.0 * 100.0)


def _grad_opacity_pct(opacity: float) -> float | None:
    """Gradient Fill/Stroke Opacity percentage for a 0-1 group opacity.

    Unlike a solid paint (`_opacity_pct`), a gradient fill/stroke stores the
    group/element opacity as the RAW percentage, NOT 8-bit-quantized: AE 2026
    writes `0.5 -> 50.0` and `0.3 -> 30.0` (vs `50.196` / `30.196` for solids,
    which route opacity through the 8-bit colour alpha). The gradient's own
    per-stop alpha stays in Grad Colors. Returns `None` when fully opaque,
    since AE leaves the default 100%.

    AE reads the SVG opacity as float32 before scaling, so quantize to f4
    first to match its exact byte (e.g. `0.3 -> 30.000001907`, not `30.0`).
    """
    if opacity >= 1.0:
        return None
    return to_f4(to_f4(opacity) * 100.0)


def _add_fill(
    inner: PropertyGroup,
    paint: SolidPaint | GradientPaint,
    cx: float,
    cy: float,
    opacity: float,
) -> None:
    _apply_paint(inner, paint, "Fill", cx, cy, opacity)


def _add_stroke(
    inner: PropertyGroup, stroke: StrokeStyle, cx: float, cy: float, opacity: float
) -> None:
    sg = _apply_paint(inner, stroke.paint, "Stroke", cx, cy, opacity)
    _leaf(sg, "ADBE Vector Stroke Width").value = stroke.width
    _apply_stroke_style(sg, stroke)


def _apply_paint(
    inner: PropertyGroup,
    paint: SolidPaint | GradientPaint,
    kind: str,
    cx: float,
    cy: float,
    opacity: float,
) -> PropertyGroup:
    """Add a paint group ("Fill"/"Stroke" match-name stem `kind`) and set
    its gradient-or-solid color and opacity. Returns the added group."""
    if isinstance(paint, GradientPaint):
        grp = _grp(inner.add_property(f"ADBE Vector Graphic - G-{kind}"))
        _apply_gradient(grp, paint, cx, cy)
        pct = _grad_opacity_pct(opacity)
    else:
        grp = _grp(inner.add_property(f"ADBE Vector Graphic - {kind}"))
        c = paint.color
        _leaf(grp, f"ADBE Vector {kind} Color").value = [c[0], c[1], c[2], 1.0]
        pct = _opacity_pct(c[3] * opacity)
    if pct is not None:
        _leaf(grp, f"ADBE Vector {kind} Opacity").value = pct
    return grp


def _apply_stroke_style(sg: PropertyGroup, stroke: StrokeStyle) -> None:
    _set_optional(sg, "ADBE Vector Stroke Line Cap", float(stroke.cap), 1.0)
    _set_optional(sg, "ADBE Vector Stroke Line Join", float(stroke.join), 1.0)
    _set_optional(sg, "ADBE Vector Stroke Miter Limit", stroke.miter_limit, 4.0)


def _apply_gradient(
    group: PropertyGroup, paint: GradientPaint, cx: float, cy: float
) -> None:
    """Configure a G-Fill/G-Stroke group from a gradient paint.

    Start/end points are stored relative to the group centre `(cx, cy)`,
    matching the centred vertex encoding.
    """
    _leaf(group, "ADBE Vector Grad Type").value = _GRAD_TYPE.get(paint.kind, 1.0)
    _leaf(group, "ADBE Vector Grad Start Pt").value = [
        paint.start[0] - cx,
        paint.start[1] - cy,
    ]
    _leaf(group, "ADBE Vector Grad End Pt").value = [
        paint.end[0] - cx,
        paint.end[1] - cy,
    ]
    _leaf(group, "ADBE Vector Grad Colors").value = _gradient_value(paint)
    # A radial gradientTransform's vertical stretch and rotation live in Grad
    # Scale / Grad Rotation (the start/end points only encode the x-radius);
    # AE writes a 360-degree baseline rotation on every radial gradient. These
    # leaves are AE 2026-only, so they are absent when importing into an
    # older project - in which case AE itself can only render the circular
    # approximation, so skipping them matches AE's pre-2026 behaviour.
    if paint.scale != (100.0, 100.0):
        _set_if_present(
            group, "ADBE Vector Grad Scale", [paint.scale[0], paint.scale[1]]
        )
    if paint.rotation:
        _set_if_present(group, "ADBE Vector Grad Rotation", paint.rotation)


def _gradient_value(paint: GradientPaint) -> Gradient:
    """Convert reader gradient stops to an AE `Gradient` (color + alpha)."""
    stops = paint.stops or []
    if not stops:
        return Gradient()
    color_stops = [
        GradientColorStop(s.offset, 0.5, (s.color[0], s.color[1], s.color[2]))
        for s in stops
    ]
    alpha_stops = [GradientAlphaStop(s.offset, 0.5, s.color[3]) for s in stops]
    return Gradient(color_stops, alpha_stops)


def _set_optional(
    group: PropertyGroup, match_name: str, value: float, default: float
) -> None:
    """Set a leaf only when it differs from its AE default (keeps the
    output minimal, matching AE which writes only non-defaults)."""
    if value != default:
        _leaf(group, match_name).value = value


def _set_if_present(
    group: PropertyGroup, match_name: str, value: list[float] | float
) -> None:
    """Set a leaf only if the group actually has it.

    Some leaves (e.g. the AE 2026 Grad Scale / Grad Rotation) are absent
    when importing into an older project; skip them rather than raise."""
    if any(p.match_name == match_name for p in group.properties):
        _leaf(group, match_name).value = value
