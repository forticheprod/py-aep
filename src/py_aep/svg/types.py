"""Value types for the parsed SVG document.

All coordinates are absolute, in the SVG viewBox coordinate system, with
every ancestor transform already applied. Tangents are stored relative to
their vertex (After Effects' [Shape][py_aep.models.properties.shape.Shape]
convention).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # RGBA in 0.0-1.0 range (annotation-only alias; py37-safe).
    Rgba = tuple[float, float, float, float]


@dataclass
class Subpath:
    """A single bezier outline: one `M ... [Z]` run of a path.

    `in_tangents` / `out_tangents` are per-vertex offsets relative to the
    vertex, matching After Effects' Shape model (straight segments have
    zero tangents).
    """

    vertices: list[list[float]]
    """Anchor points as absolute `[x, y]` pairs."""

    in_tangents: list[list[float]]
    """Incoming tangent offset per vertex (relative to the vertex)."""

    out_tangents: list[list[float]]
    """Outgoing tangent offset per vertex (relative to the vertex)."""

    closed: bool
    """Whether the subpath closes back to its first vertex."""


@dataclass
class GradientStop:
    """A single gradient color stop."""

    offset: float
    """Stop position along the gradient, 0.0-1.0."""

    color: Rgba
    """Stop color (alpha folds in `stop-opacity`)."""


@dataclass
class SolidPaint:
    """A flat color fill or stroke paint."""

    color: Rgba
    """Paint color in 0.0-1.0 RGBA."""


@dataclass
class GradientPaint:
    """A linear or radial gradient paint (resolved to absolute geometry)."""

    kind: str
    """`"linear"` or `"radial"`."""

    stops: list[GradientStop]
    """Color stops in offset order."""

    start: tuple[float, float]
    """Linear: gradient start point. Radial: focal/center point."""

    end: tuple[float, float]
    """Linear: gradient end point. Radial: a point on the outer circle
    (center + radius along x), used to derive the highlight/radius."""

    scale: tuple[float, float] = (100.0, 100.0)
    """After Effects Grad Scale percentages `(x, y)`. A radial gradient
    whose `gradientTransform` stretches it into an ellipse encodes the
    aspect ratio in `y` (e.g. `(100, 200)` for a 2x-tall ellipse); without
    it the gradient renders as a circle. Linear gradients keep `(100, 100)`."""

    rotation: float = 0.0
    """After Effects Grad Rotation in degrees. A radial gradient's
    un-rotated baseline is `360` (AE's convention, visually equal to 0);
    linear gradients use `0`."""


@dataclass
class StrokeStyle:
    """Stroke appearance for a drawable."""

    paint: SolidPaint | GradientPaint
    """SolidPaint or GradientPaint."""

    width: float
    """Stroke width in viewBox units (post-transform scaled)."""

    cap: int = 1
    """Line cap: 1 butt, 2 round, 3 projecting (AE enum values)."""

    join: int = 1
    """Line join: 1 miter, 2 round, 3 bevel (AE enum values)."""

    miter_limit: float = 4.0
    """Miter limit."""

    dashes: list[float] = field(default_factory=list)
    """Dash array (empty for a solid stroke)."""


@dataclass
class SvgDrawable:
    """One leaf drawable: its outline(s) plus fill and stroke.

    Mirrors the single `ADBE Vector Group` After Effects creates per leaf
    element. `fill` / `stroke` are `None` when the element has no such
    paint.
    """

    subpaths: list[Subpath]
    """Outline(s); compound paths produce multiple subpaths."""

    fill: SolidPaint | GradientPaint | None = None
    """SolidPaint, GradientPaint, or None."""

    stroke: StrokeStyle | None = None
    """Stroke style, or None when unstroked."""

    name: str | None = None
    """Source element `id`, if any (AE ignores it for naming; kept for
    debugging / round-trip inspection)."""

    opacity: float = 1.0
    """Element group opacity, 0.0-1.0."""


@dataclass
class SvgDocument:
    """A flattened SVG: canvas size plus drawables in document order."""

    width: float
    """Comp width in pixels (from viewBox or width attribute)."""

    height: float
    """Comp height in pixels."""

    drawables: list[SvgDrawable]
    """Leaf drawables in document (paint) order; first painted first."""
