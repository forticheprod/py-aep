"""Shape value model for mask and shape path properties."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...binary.ldat_chunks import ShapePoint
from ...binary.misc_chunks import ShphChunk
from ..descriptors import ChunkField
from ..validators import (
    validate_bool,
    validate_normalized_float,
    validate_positive_int,
    validate_vector2,
)

if TYPE_CHECKING:
    from ...binary.misc_chunks import FeatherPointItem
    from ..items.composition import CompItem
    from ..layers.av_layer import AVLayer
    from ..layers.layer import Layer


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

    seg_loc = ChunkField[int]("_fp", "seg_loc", validate=validate_positive_int)
    """Mask path segment number where this feather point is located
    (0-based, segments are portions of the path between vertices).
    Read / Write."""

    rel_seg_loc = ChunkField[float](
        "_fp", "rel_seg_loc", validate=validate_normalized_float
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
        reverse=_interp_reverse,
    )
    """Radius interpolation type: 0 for non-Hold feather points,
    1 for Hold feather points. Read / Write."""

    tension = ChunkField[float]("_fp", "tension", validate=validate_normalized_float)
    """Feather tension amount, from 0.0 (0%) to 1.0 (100%). Read / Write."""

    rel_corner_angle = ChunkField[float]("_fp", "corner_angle")
    """Relative angle percentage between the two normals on either side
    of a curved outer feather boundary at a corner on a mask path.
    The angle value is 0% for feather points not at corners.
    Read / Write."""

    def __init__(self, *, _fp: FeatherPointItem) -> None:
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
        vertices: list[list[float]] | None = None,
        in_tangents: list[list[float]] | None = None,
        out_tangents: list[list[float]] | None = None,
        *,
        closed: bool = True,
        feather_points: list[FeatherPoint] | None = None,
    ) -> None:
        """Create a shape from scratch.

        Coordinates are absolute (pixel-space), matching a shape-layer
        path. When this shape is later assigned to a mask property, the
        property normalizes the coordinates to the composition.

        Args:
            vertices: Anchor points as `[x, y]` pairs.
            in_tangents: Incoming tangent offsets relative to each vertex,
                same length as `vertices`. Defaults to `[0, 0]` (straight
                line in) for every vertex.
            out_tangents: Outgoing tangent offsets relative to each vertex,
                same length as `vertices`. Defaults to `[0, 0]` (straight
                line out) for every vertex.
            closed: When `True`, the first and last vertices are connected.
            feather_points: Variable-width mask feather points.
        """
        self._shph: ShphChunk | None = ShphChunk()
        self._shph.open = not closed
        self._is_mask = False
        self._composition: CompItem | None = None
        self._layer: Layer | None = None
        self._closed_fallback = closed
        self.feather_points = feather_points if feather_points is not None else []
        """List of variable-width mask feather points."""

        verts = vertices if vertices is not None else []
        n = len(verts)
        in_t = in_tangents if in_tangents is not None else [[0.0, 0.0]] * n
        out_t = out_tangents if out_tangents is not None else [[0.0, 0.0]] * n
        if len(in_t) != n or len(out_t) != n:
            raise ValueError(
                "in_tangents and out_tangents must match the number of vertices"
            )
        # Validate the coordinate pairs up front so the bounding-box pass
        # below fails cleanly rather than on a tuple-unpack error.
        for coords in (verts, in_t, out_t):
            for pt in coords:
                validate_vector2(pt)
        # Three points per vertex: vertex, out-tangent, in-tangent-of-next.
        self._points: list[ShapePoint] | None = [ShapePoint() for _ in range(3 * n)]
        if n:
            self._init_bounding_box(verts, in_t, out_t)
            # Vertices first - tangent setters read back the vertex positions.
            self.vertices = verts
            self.in_tangents = in_t
            self.out_tangents = out_t

    def _init_bounding_box(
        self,
        vertices: list[list[float]],
        in_tangents: list[list[float]],
        out_tangents: list[list[float]],
    ) -> None:
        """Set the shph bounding box to span all absolute control points.

        Vertex coordinates are stored normalized to this box, so it must
        be non-degenerate in any axis that carries a tangent offset for
        the normalize / denormalize round-trip to be lossless.
        """
        assert self._shph is not None
        xs: list[float] = []
        ys: list[float] = []
        for (vx, vy), (ix, iy), (ox, oy) in zip(vertices, in_tangents, out_tangents):
            xs.extend([vx, vx + ix, vx + ox])
            ys.extend([vy, vy + iy, vy + oy])
        self._shph.top_left_x = min(xs)
        self._shph.top_left_y = min(ys)
        self._shph.bottom_right_x = max(xs)
        self._shph.bottom_right_y = max(ys)

    @classmethod
    def _from_binary(
        cls,
        *,
        _shph: ShphChunk,
        _points: list[ShapePoint],
        _is_mask: bool = False,
        _composition: CompItem | None = None,
        feather_points: list[FeatherPoint] | None = None,
    ) -> Shape:
        """Wrap parsed shape chunks as a `Shape` view."""
        obj = cls.__new__(cls)
        obj._shph = _shph
        obj._points = _points
        obj._is_mask = _is_mask
        obj._composition = _composition
        obj._layer = None
        obj.feather_points = feather_points if feather_points is not None else []
        return obj

    @property
    def _comp_size(self) -> tuple[float, float] | None:
        """Mask-shape denormalization size, read lazily.

        Mask space is LAYER space, so the owning layer's source size wins
        (pinned by the psd_vector_mask_cropped fixture: a layer smaller
        than its comp); the composition is the parse-context fallback for
        shapes not yet bound to a layer.
        """
        if self._layer is not None:
            layer = cast("AVLayer", self._layer)
            return (float(layer.width), float(layer.height))
        if self._composition is not None:
            return (float(self._composition.width), float(self._composition.height))
        return None

    def _denormalize_point(self, pt: ShapePoint) -> list[float]:
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
        if not isinstance(value, (list, tuple)):
            raise ValueError("vertices must be a list of [x,y] pairs")
        for pt in value:
            validate_vector2(pt)
        coords = value
        if self._is_mask and self._comp_size is not None:
            w, h = self._comp_size
            coords = [[x / w, y / h] for x, y in coords]
        for j, (x, y) in enumerate(coords):
            i = j * 3
            nx, ny = self._normalize_point(x, y)
            self._points[i].x = nx
            self._points[i].y = ny

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
        if not isinstance(value, (list, tuple)):
            raise ValueError("in_tangents must be a list of [x,y] pairs")
        for pt in value:
            validate_vector2(pt)
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
        if not isinstance(value, (list, tuple)):
            raise ValueError("out_tangents must be a list of [x,y] pairs")
        for pt in value:
            validate_vector2(pt)
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

    @property
    def closed(self) -> bool:
        """When `True`, the first and last vertices are connected to form a closed
        curve. When `False`, the closing segment is not drawn."""
        if self._shph is not None:
            return not self._shph.open
        return self._closed_fallback

    @closed.setter
    def closed(self, value: bool) -> None:
        validate_bool(value)
        if self._shph is not None:
            self._shph.open = not value
        else:
            self._closed_fallback = value
