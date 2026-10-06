"""Shape value model for mask and shape path properties."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...binary.ldat_chunks import ShapePoint
from ...binary.misc_chunks import ShphChunk, TensionItem
from ...resolvers.roto_bezier import (
    DEFAULT_TENSION,
    roto_bezier_tangents,
)
from ..descriptors import ChunkField
from ..validators import (
    validate_bool,
    validate_f4_point,
    validate_normalized_float,
    validate_positive_int,
)

if TYPE_CHECKING:
    from ...binary.misc_chunks import FeatherPointItem, OmtnChunk
    from ..layers.av_layer import AVLayer
    from ..layers.layer import Layer
    from .mask_property_group import MaskPropertyGroup
    from .property import Property


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
        property normalizes the coordinates to the layer.

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

        Raises:
            ValueError: If the tangent lists do not match the vertices, or a
                coordinate (or a vertex plus its tangent) is not a finite
                float32: paths are stored as single-precision floats.
        """
        validate_bool(closed)
        if feather_points is not None and not (
            isinstance(feather_points, list)
            and all(isinstance(fp, FeatherPoint) for fp in feather_points)
        ):
            raise TypeError("feather_points must be a list of FeatherPoint")
        self._shph: ShphChunk | None = ShphChunk()
        self._shph.open = not closed
        self._is_mask = False
        self._layer: Layer | None = None
        self._omtn: OmtnChunk | None = None
        self._mask_path: Property | None = None
        self._tensions: list[float] | None = None
        self._closed_fallback = closed
        # A shape built here owns its points, so a different vertex count
        # can rebuild them; a parsed one shares them with its file chunks.
        self._detached = True
        self.feather_points = feather_points if feather_points is not None else []
        """List of variable-width mask feather points."""

        verts = vertices if vertices is not None else []
        n = len(verts)
        in_t = in_tangents if in_tangents is not None else [[0.0, 0.0]] * n
        out_t = out_tangents if out_tangents is not None else [[0.0, 0.0]] * n
        # Three points per vertex: vertex, out-tangent, in-tangent-of-next.
        self._points: list[ShapePoint] | None = []
        self._write_geometry(verts, in_t, out_t)

    def _write_geometry(
        self,
        vertices: list[list[float]],
        in_tangents: list[list[float]],
        out_tangents: list[list[float]],
    ) -> None:
        """Store `vertices` (absolute) and their relative tangents.

        The points are stored normalized to a bounding box spanning every
        control point, so the box is recomputed from the whole new geometry:
        a box kept from an earlier geometry cannot hold a coordinate along
        an axis it has no extent in (a flat or single-point path would keep
        its old values). Everything is validated before anything is written.
        """
        for coords in (vertices, in_tangents, out_tangents):
            if not isinstance(coords, (list, tuple)):
                raise ValueError("vertices and tangents must be lists of [x, y] pairs")
            for pt in coords:
                validate_f4_point(pt)
        count = len(vertices)
        if len(in_tangents) != count or len(out_tangents) != count:
            raise ValueError(
                "in_tangents and out_tangents must match the number of vertices"
            )
        assert self._shph is not None and self._points is not None
        if 3 * count != len(self._points) and not self._detached:
            raise ValueError(
                f"this path has {len(self._points) // 3} vertices; to change "
                "the vertex count assign a new Shape to the property"
            )
        mask_size = self._comp_size if self._is_mask else None
        sx, sy = mask_size if mask_size is not None else (1.0, 1.0)
        verts = [[x / sx, y / sy] for x, y in vertices]
        ins = [
            [vx + x / sx, vy + y / sy] for (vx, vy), (x, y) in zip(verts, in_tangents)
        ]
        outs = [
            [vx + x / sx, vy + y / sy] for (vx, vy), (x, y) in zip(verts, out_tangents)
        ]
        for pt in ins + outs:
            # A vertex plus its tangent can overflow even when both fit.
            validate_f4_point(pt)
        if 3 * count != len(self._points):
            self._points[:] = [ShapePoint() for _ in range(3 * count)]
        if not count:
            return
        xs = [p[0] for p in verts + ins + outs]
        ys = [p[1] for p in verts + ins + outs]
        shph = self._shph
        shph.top_left_x, shph.top_left_y = min(xs), min(ys)
        shph.bottom_right_x, shph.bottom_right_y = max(xs), max(ys)
        total = len(self._points)
        for j in range(count):
            i = 3 * j
            for index, (x, y) in (
                (i, verts[j]),
                (i + 1, outs[j]),
                ((i - 1) % total, ins[j]),
            ):
                self._points[index].x, self._points[index].y = self._normalize_point(
                    x, y
                )

    @classmethod
    def _from_binary(
        cls,
        *,
        _shph: ShphChunk,
        _points: list[ShapePoint],
        _is_mask: bool = False,
        _layer: Layer | None = None,
        _omtn: OmtnChunk | None = None,
        _mask_path: Property | None = None,
        feather_points: list[FeatherPoint] | None = None,
    ) -> Shape:
        """Wrap parsed shape chunks as a `Shape` view.

        `_mask_path` is the owning Mask Path: its mask's RotoBezier switch
        decides which tangents the shape reports.
        """
        obj = cls.__new__(cls)
        obj._shph = _shph
        obj._points = _points
        obj._is_mask = _is_mask
        obj._layer = _layer
        obj._omtn = _omtn
        obj._mask_path = _mask_path
        obj._tensions = None
        obj._detached = False
        obj.feather_points = feather_points if feather_points is not None else []
        return obj

    def _is_roto_bezier(self) -> bool:
        """Whether this is the path of a mask whose RotoBezier switch is on."""
        prop = self._mask_path
        if prop is None or prop._tdb4 is None:
            return False
        mask = prop._parent_property
        return (
            mask is not None
            and mask._is_mask
            and cast("MaskPropertyGroup", mask).roto_bezier
        )

    def _roto_tangents(self) -> tuple[list[list[float]], list[list[float]]] | None:
        """The tangents AE draws the path with when its mask is RotoBezier
        (`resolvers.roto_bezier`), or `None` for any other shape."""
        if not self._is_roto_bezier():
            return None
        prop = cast("Property", self._mask_path)
        width, height = cast("AVLayer", prop._containing_layer)._mask_scale
        vertices = self.vertices
        tensions = self._tensions
        if tensions is None or len(tensions) != len(vertices):
            tensions = self._own_tensions()
            if len(tensions) != len(vertices):
                tensions = [DEFAULT_TENSION] * len(vertices)
        return roto_bezier_tangents(
            vertices,
            self.closed,
            tensions,
            prop._tdb4.pixel_aspect / width,
            1.0 / height,
        )

    def _own_tensions(self) -> list[float]:
        """The tensions stored with this shape value (the `omtn` chunk)."""
        if self._omtn is None:
            return []
        return [item.value for item in self._omtn.tensions]

    def _set_tensions(self, tensions: list[float]) -> None:
        """Store per-vertex RotoBezier tensions in this value's `omtn`."""
        if self._omtn is not None:
            self._omtn.tensions = [TensionItem(value=t) for t in tensions]

    @property
    def _comp_size(self) -> tuple[float, float] | None:
        """Mask-shape denormalization size, read lazily.

        Mask space is LAYER space, so this is the owning layer's source
        size (pinned by the psd_vector_mask_cropped fixture: a 56 px layer
        in a 64 px comp), or 1 x 1 on a text or shape layer (see
        `AVLayer._mask_scale`). Read on demand rather than snapshotted at
        parse time, so it follows the layer if its source is later replaced.
        """
        if self._layer is None:
            return None
        return cast("AVLayer", self._layer)._mask_scale

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

        Moving the vertices keeps each tangent relative to its vertex. A
        shape built with `Shape()` can take a different number of vertices
        (its tangents then reset to `[0, 0]`); one read from a project keeps
        its vertex count, so assign a new `Shape` to the property instead.
        """
        if self._points is None or self._shph is None:
            return []
        result: list[list[float]] = []
        for i in range(0, len(self._points), 3):
            result.append(self._denormalize_point(self._points[i]))
        mask_size = self._comp_size if self._is_mask else None
        if mask_size is not None:
            w, h = mask_size
            result = [[x * w, y * h] for x, y in result]
        return result

    @vertices.setter
    def vertices(self, value: list[list[float]]) -> None:
        if self._points is None or self._shph is None:
            return
        if not isinstance(value, (list, tuple)):
            raise ValueError("vertices must be a list of [x,y] pairs")
        if not value:
            # AE 2026 refuses it too: "Value array does not have at least 1
            # element(s)".
            raise ValueError("vertices needs at least one [x, y] pair")
        if len(value) == len(self._points) // 3:
            in_t, out_t = self._stored_tangents(-1), self._stored_tangents(1)
        else:
            # A new vertex count: the old tangents belonged to other vertices.
            in_t = out_t = [[0.0, 0.0]] * len(value)
        self._write_geometry(list(value), in_t, out_t)

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
        roto = self._roto_tangents()
        return roto[0] if roto is not None else self._stored_tangents(-1)

    @in_tangents.setter
    def in_tangents(self, value: list[list[float]]) -> None:
        if self._points is None or self._shph is None:
            return
        if not isinstance(value, (list, tuple)):
            raise ValueError("in_tangents must be a list of [x,y] pairs")
        self._write_geometry(self.vertices, list(value), self._stored_tangents(1))

    def _stored_tangents(self, offset: int) -> list[list[float]]:
        """The stored handles (which a RotoBezier mask ignores): the
        incoming ones for `offset` -1, the outgoing ones for +1 (each handle
        point sits beside its vertex in `_points`)."""
        if self._points is None or self._shph is None:
            return []
        result: list[list[float]] = []
        for i in range(0, len(self._points), 3):
            v = self._denormalize_point(self._points[i])
            t = self._denormalize_point(self._points[(i + offset) % len(self._points)])
            result.append([t[0] - v[0], t[1] - v[1]])
        mask_size = self._comp_size if self._is_mask else None
        if mask_size is not None:
            w, h = mask_size
            result = [[x * w, y * h] for x, y in result]
        return result

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
        roto = self._roto_tangents()
        return roto[1] if roto is not None else self._stored_tangents(1)

    @out_tangents.setter
    def out_tangents(self, value: list[list[float]]) -> None:
        if self._points is None or self._shph is None:
            return
        if not isinstance(value, (list, tuple)):
            raise ValueError("out_tangents must be a list of [x,y] pairs")
        self._write_geometry(self.vertices, self._stored_tangents(-1), list(value))

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
