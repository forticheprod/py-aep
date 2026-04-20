"""Shape value model for mask and shape path properties."""

from __future__ import annotations

import typing

from ...kaitai.descriptors import ChunkField
from ...kaitai.utils import propagate_check
from ..validators import validate_number

if typing.TYPE_CHECKING:
    from ...kaitai import Aep
    from ..items.composition import CompItem


def _interp_transform(raw: int) -> int:
    """Map binary interpolation (0=non-Hold, 2=Hold) to ExtendScript (0/1)."""
    return 1 if raw == 2 else 0


def _interp_reverse(value: int) -> int:
    """Map ExtendScript interpolation (0/1) back to binary (0/2)."""
    return 2 if value == 1 else 0


class FeatherPoint:
    """A single variable-width mask feather point.

    Feather points can be placed anywhere along a closed mask path to vary
    the feather radius at different positions. Reference a specific feather
    point by the number of the mask path segment (portion of the path
    between adjacent vertices) where it appears.

    Tip:
        The feather points on a mask are listed in an array in the order
        that they were created.
    """

    seg_loc = ChunkField[int](
        "_fp", "seg_loc", validate=validate_number(min=0, integer=True)
    )
    """Mask path segment number where this feather point is located
    (0-based, segments are portions of the path between vertices).
    Read / Write."""

    rel_seg_loc = ChunkField[float](
        "_fp", "rel_seg_loc", validate=validate_number(min=0.0, max=1.0)
    )
    """Relative position on the segment, from 0.0 (at the starting
    vertex) to 1.0 (at the next vertex). Read / Write."""

    radius = ChunkField[float]("_fp", "radius")
    """Feather radius (amount). Negative values indicate inner feather
    points; positive values indicate outer feather. Read / Write."""

    interp = ChunkField[int](
        "_fp",
        "interp_raw",
        transform=_interp_transform,
        reverse_seq_field=_interp_reverse,
    )
    """Radius interpolation type: 0 for non-Hold feather points,
    1 for Hold feather points. Read / Write."""

    tension = ChunkField[float](
        "_fp", "tension", validate=validate_number(min=0.0, max=1.0)
    )
    """Feather tension amount, from 0.0 (0%) to 1.0 (100%). Read / Write."""

    rel_corner_angle = ChunkField[float]("_fp", "corner_angle")
    """Relative angle percentage between the two normals on either side
    of a curved outer feather boundary at a corner on a mask path.
    The angle value is 0% for feather points not at corners.
    Read / Write."""

    def __init__(self, *, _fp: Aep.FeatherPoint) -> None:
        self._fp = _fp

    @property
    def type(self) -> int:
        """Feather point direction: 0 (outer feather point) or
        1 (inner feather point). Read-only."""
        return 1 if self.radius < 0 else 0


class Shape:
    """
    The Shape object encapsulates information describing a shape in a shape layer, or
    the outline shape of a Mask. It is the value of the "Mask Path" AE properties, and
    of the "Path" AE property of a shape layer.

    A shape has a set of anchor points, or vertices, and a pair of direction handles, or
    tangent vectors, for each anchor point. A tangent vector (in a non-roto_bezier mask)
    determines the direction of the line that is drawn to or from an anchor point. There
    is one incoming tangent vector and one outgoing tangent vector associated with each
    `vertex` in the shape.

    A tangent value is a pair of x,y coordinates specified relative to the associated
    `vertex`. For example, a tangent of [-1,-1] is located above and to the left of the
    `vertex` and has a 45 degree slope, regardless of the actual location of the
    `vertex`. The longer a handle is, the greater its influence; for example, an
    incoming shape segment stays closer to the vector for an `in_tangent` of [-2,-2]
    than it does for an `in_tangent` of [-1,-1], even though both of these come toward
    the `vertex` from the same direction.

    If a shape is not closed, the `in_tangent` for the first `vertex` and the
    `out_tangent` for the final `vertex` are ignored. If the shape is closed, these two
    vectors specify the direction handles of the final connecting segment out of the
    final `vertex` and back into the first `vertex`.

    roto_bezier masks calculate their tangents automatically
    (see MaskPropertyGroup.roto_bezier). If a shape is used in a roto_bezier mask, the
    tangent values are ignored.

    For closed mask shapes, variable-width mask feather points can exist anywhere along
    the mask path. Feather points are part of the Mask Path property. Reference a
    specific feather point by the number of the mask path segment (portion of the path
    between adjacent vertices) where it appears.

    Tip:
        The feather points on a mask are listed in an array in the order that they were
        created.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        shape_layer = comp.shape_layers[0]
        shape_prop = shape_layer.content.property("ADBE Vector Shape - Group").property("ADBE Vector Shape")
        print(shape_prop.value.vertices)
        ```

    See: https://ae-scripting.docsforadobe.dev/other/shape/
    """

    def __init__(
        self,
        *,
        _shph: Aep.ShphBody | None = None,
        _points: list[Aep.ShapePoint] | None = None,
        _is_mask: bool = False,
        _composition: CompItem | None = None,
        closed: bool | None = None,
        feather_points: list[FeatherPoint] | None = None,
    ) -> None:
        self._shph = _shph
        self._points = _points
        self._is_mask = _is_mask
        self._composition = _composition
        if _shph is None and closed is not None:
            self._closed_fallback = closed
        self.feather_points = feather_points if feather_points is not None else []
        """List of variable-width mask feather points."""

    @property
    def _comp_size(self) -> tuple[float, float] | None:
        """Composition size for mask shape denormalization, read lazily."""
        if self._composition is not None:
            return (float(self._composition.width), float(self._composition.height))
        return None

    def _denormalize_point(self, pt: Aep.ShapePoint) -> list[float]:
        """Convert a normalized [0,1] shape point to absolute coordinates."""
        shph = self._shph
        assert shph is not None
        x = shph.top_left_x * (1 - pt.x) + shph.bottom_right_x * pt.x
        y = shph.top_left_y * (1 - pt.y) + shph.bottom_right_y * pt.y
        return [x, y]

    def _normalize_point(self, x: float, y: float) -> tuple[float, float]:
        """Convert absolute coordinates back to normalized [0,1]."""
        shph = self._shph
        assert shph is not None
        dx = shph.bottom_right_x - shph.top_left_x
        dy = shph.bottom_right_y - shph.top_left_y
        nx = (x - shph.top_left_x) / dx if dx != 0 else 0.0
        ny = (y - shph.top_left_y) / dy if dy != 0 else 0.0
        return nx, ny

    @property
    def vertices(self) -> list[list[float]]:
        """
        The anchor points of the shape. Specify each point as an array of two
        floating-point values, and collect the point pairs into an array for the
        complete set of points.
        """
        if self._points is None or self._shph is None:
            return []
        result: list[list[float]] = []
        for i in range(0, len(self._points), 3):
            result.append(self._denormalize_point(self._points[i]))
        if self._is_mask and self._comp_size is not None:
            w, h = self._comp_size
            result = [[x * w, y * h] for x, y in result]
        return result

    @vertices.setter
    def vertices(self, value: list[list[float]]) -> None:
        if self._points is None or self._shph is None:
            return
        coords = value
        if self._is_mask and self._comp_size is not None:
            w, h = self._comp_size
            coords = [[x / w, y / h] for x, y in coords]
        for j, (x, y) in enumerate(coords):
            i = j * 3
            nx, ny = self._normalize_point(x, y)
            self._points[i].x = nx
            self._points[i].y = ny
        propagate_check(self._shph)

    @property
    def in_tangents(self) -> list[list[float]]:
        """
        The incoming tangent vectors, or direction handles, associated with the vertices
        of the shape. Specify each vector as an array of two floating-point values, and
        collect the vectors into an array the same length as the vertices array.

        Each tangent value defaults to [0,0]. When the mask shape is not roto_bezier,
        this results in a straight line segment.

        If the shape is in a roto_bezier mask, all tangent values are ignored and the
        tangents are automatically calculated.
        """
        if self._points is None or self._shph is None:
            return []
        result: list[list[float]] = []
        for i in range(0, len(self._points), 3):
            v = self._denormalize_point(self._points[i])
            in_idx = (i - 1) % len(self._points)
            t = self._denormalize_point(self._points[in_idx])
            result.append([t[0] - v[0], t[1] - v[1]])
        if self._is_mask and self._comp_size is not None:
            w, h = self._comp_size
            result = [[x * w, y * h] for x, y in result]
        return result

    @in_tangents.setter
    def in_tangents(self, value: list[list[float]]) -> None:
        if self._points is None or self._shph is None:
            return
        tangents = value
        if self._is_mask and self._comp_size is not None:
            w, h = self._comp_size
            tangents = [[x / w, y / h] for x, y in tangents]
        for j, (tx, ty) in enumerate(tangents):
            i = j * 3
            v = self._denormalize_point(self._points[i])
            abs_x, abs_y = v[0] + tx, v[1] + ty
            nx, ny = self._normalize_point(abs_x, abs_y)
            in_idx = (i - 1) % len(self._points)
            self._points[in_idx].x = nx
            self._points[in_idx].y = ny
        propagate_check(self._shph)

    @property
    def out_tangents(self) -> list[list[float]]:
        """
        The outgoing tangent vectors, or direction handles, associated with the vertices
        of the shape. Specify each vector as an array of two floating-point values, and
        collect the vectors into an array the same length as the vertices array.

        Each tangent value defaults to [0,0]. When the mask shape is not roto_bezier,
        this results in a straight line segment.

        If the shape is in a roto_bezier mask, all tangent values are ignored and the
        tangents are automatically calculated.
        """
        if self._points is None or self._shph is None:
            return []
        result: list[list[float]] = []
        for i in range(0, len(self._points), 3):
            v = self._denormalize_point(self._points[i])
            t = self._denormalize_point(self._points[i + 1])
            result.append([t[0] - v[0], t[1] - v[1]])
        if self._is_mask and self._comp_size is not None:
            w, h = self._comp_size
            result = [[x * w, y * h] for x, y in result]
        return result

    @out_tangents.setter
    def out_tangents(self, value: list[list[float]]) -> None:
        if self._points is None or self._shph is None:
            return
        tangents = value
        if self._is_mask and self._comp_size is not None:
            w, h = self._comp_size
            tangents = [[x / w, y / h] for x, y in tangents]
        for j, (tx, ty) in enumerate(tangents):
            i = j * 3
            v = self._denormalize_point(self._points[i])
            abs_x, abs_y = v[0] + tx, v[1] + ty
            nx, ny = self._normalize_point(abs_x, abs_y)
            self._points[i + 1].x = nx
            self._points[i + 1].y = ny
        propagate_check(self._shph)

    @property
    def closed(self) -> bool:
        """When `True`, the first and last vertices are connected to form a closed
        curve. When `False`, the closing segment is not drawn."""
        if self._shph is not None:
            return not self._shph.open
        return self._closed_fallback

    @closed.setter
    def closed(self, value: bool) -> None:
        if self._shph is not None:
            self._shph.open = not value
            propagate_check(self._shph)
        else:
            self._closed_fallback = value
