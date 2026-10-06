"""4x4 affine transform utilities for After Effects layer transforms.

Provides matrix composition and decomposition matching AE's internal
transform pipeline.  Pure Python with no external dependencies.

**AE transform order** (column-vector convention, right-to-left)::

    2D:  T(pos) * Rz(rz) * S(scale) * T(-anchor)
    3D:  T(pos) * Rx(ox)*Ry(oy)*Rz(oz) * Rx(rx)*Ry(ry)*Rz(rz)
         * S(scale) * T(-anchor)

where `o{x,y,z}` are Orientation angles and `r{x,y,z}` are
per-axis Rotation angles, all in degrees.

Coordinate system: left-handed, Y-down (X right, Y down, Z into screen).
Standard rotation matrices apply without sign flips.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, cast

from ..enums import AutoOrientType, LayerType, LightType

if TYPE_CHECKING:
    from typing import Any

    from ..models.items.composition import CompItem
    from ..models.layers.av_layer import AVLayer
    from ..models.layers.layer import Layer
    from ..models.layers.light_layer import LightLayer
    from ..models.properties.property import Property
    from ..models.properties.property_group import PropertyGroup


_DEG2RAD = math.pi / 180.0
_RAD2DEG = 180.0 / math.pi
_EPSILON = 1e-10


class Mat4:
    """4x4 matrix stored row-major: `m[row][col]`."""

    __slots__ = ("_rows",)

    def __init__(self, rows: list[list[float]]) -> None:
        self._rows = rows

    def __getitem__(self, row: int) -> list[float]:
        return self._rows[row]

    def __matmul__(self, other: Mat4) -> Mat4:
        rows = [[0.0] * 4 for _ in range(4)]
        for i in range(4):
            ai = self._rows[i]
            ri = rows[i]
            ob = other._rows
            for j in range(4):
                ri[j] = (
                    ai[0] * ob[0][j]
                    + ai[1] * ob[1][j]
                    + ai[2] * ob[2][j]
                    + ai[3] * ob[3][j]
                )
        return Mat4(rows)

    def __imatmul__(self, other: Mat4) -> Mat4:
        return self.__matmul__(other)

    @classmethod
    def identity(cls) -> Mat4:
        """Return a 4x4 identity matrix."""
        return cls(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )

    def transform_point(self, v: list[float]) -> list[float]:
        """Transform a 3D point (translation applied)."""
        x = v[0]
        y = v[1]
        z = v[2] if len(v) > 2 else 0.0
        r = self._rows
        return [
            r[0][0] * x + r[0][1] * y + r[0][2] * z + r[0][3],
            r[1][0] * x + r[1][1] * y + r[1][2] * z + r[1][3],
            r[2][0] * x + r[2][1] * y + r[2][2] * z + r[2][3],
        ]

    def transform_vector(self, v: list[float]) -> list[float]:
        """Transform a 3D direction vector (translation ignored)."""
        x = v[0]
        y = v[1]
        z = v[2] if len(v) > 2 else 0.0
        r = self._rows
        return [
            r[0][0] * x + r[0][1] * y + r[0][2] * z,
            r[1][0] * x + r[1][1] * y + r[1][2] * z,
            r[2][0] * x + r[2][1] * y + r[2][2] * z,
        ]

    def inverse(self) -> Mat4:
        """Compute the inverse using cofactor expansion.

        Raises `ValueError` if the matrix is singular (determinant ~ 0).
        """
        # Flatten for easier indexing.
        s = [self[r][c] for r in range(4) for c in range(4)]

        # 2x2 sub-determinants (Laplace expansion)
        s0 = s[0] * s[5] - s[1] * s[4]
        s1 = s[0] * s[6] - s[2] * s[4]
        s2 = s[0] * s[7] - s[3] * s[4]
        s3 = s[1] * s[6] - s[2] * s[5]
        s4 = s[1] * s[7] - s[3] * s[5]
        s5 = s[2] * s[7] - s[3] * s[6]

        c5 = s[10] * s[15] - s[11] * s[14]
        c4 = s[9] * s[15] - s[11] * s[13]
        c3 = s[9] * s[14] - s[10] * s[13]
        c2 = s[8] * s[15] - s[11] * s[12]
        c1 = s[8] * s[14] - s[10] * s[12]
        c0 = s[8] * s[13] - s[9] * s[12]

        det = s0 * c5 - s1 * c4 + s2 * c3 + s3 * c2 - s4 * c1 + s5 * c0
        # Relative to the linear part's magnitude: a layer uniformly scaled
        # to 0.03 % has a determinant of 2.7e-11 and is perfectly invertible
        # (AE 2026 compensates a parent that small).
        scale = max(abs(s[r * 4 + c]) for r in range(3) for c in range(3))
        if det == 0.0 or abs(det) <= _EPSILON * 1e-2 * scale**3:
            raise ValueError("Singular matrix, cannot invert.")

        inv_det = 1.0 / det

        return Mat4(
            [
                [
                    (s[5] * c5 - s[6] * c4 + s[7] * c3) * inv_det,
                    (-s[1] * c5 + s[2] * c4 - s[3] * c3) * inv_det,
                    (s[13] * s5 - s[14] * s4 + s[15] * s3) * inv_det,
                    (-s[9] * s5 + s[10] * s4 - s[11] * s3) * inv_det,
                ],
                [
                    (-s[4] * c5 + s[6] * c2 - s[7] * c1) * inv_det,
                    (s[0] * c5 - s[2] * c2 + s[3] * c1) * inv_det,
                    (-s[12] * s5 + s[14] * s2 - s[15] * s1) * inv_det,
                    (s[8] * s5 - s[10] * s2 + s[11] * s1) * inv_det,
                ],
                [
                    (s[4] * c4 - s[5] * c2 + s[7] * c0) * inv_det,
                    (-s[0] * c4 + s[1] * c2 - s[3] * c0) * inv_det,
                    (s[12] * s4 - s[13] * s2 + s[15] * s0) * inv_det,
                    (-s[8] * s4 + s[9] * s2 - s[11] * s0) * inv_det,
                ],
                [
                    (-s[4] * c3 + s[5] * c1 - s[6] * c0) * inv_det,
                    (s[0] * c3 - s[1] * c1 + s[2] * c0) * inv_det,
                    (-s[12] * s3 + s[13] * s1 - s[14] * s0) * inv_det,
                    (s[8] * s3 - s[9] * s1 + s[10] * s0) * inv_det,
                ],
            ]
        )

    def __repr__(self) -> str:
        return f"Mat4({self._rows})"


# ------------------------------------------------------------------
# Elementary transform matrices
# ------------------------------------------------------------------


def _translation(x: float, y: float, z: float) -> Mat4:
    m = Mat4.identity()
    m[0][3] = x
    m[1][3] = y
    m[2][3] = z
    return m


def _scale(sx: float, sy: float, sz: float) -> Mat4:
    m = Mat4.identity()
    m[0][0] = sx
    m[1][1] = sy
    m[2][2] = sz
    return m


def _rotate_x(deg: float) -> Mat4:
    r = deg * _DEG2RAD
    c, s = math.cos(r), math.sin(r)
    m = Mat4.identity()
    m[1][1] = c
    m[1][2] = -s
    m[2][1] = s
    m[2][2] = c
    return m


def _rotate_y(deg: float) -> Mat4:
    r = deg * _DEG2RAD
    c, s = math.cos(r), math.sin(r)
    m = Mat4.identity()
    m[0][0] = c
    m[0][2] = s
    m[2][0] = -s
    m[2][2] = c
    return m


def _rotate_z(deg: float) -> Mat4:
    r = deg * _DEG2RAD
    c, s = math.cos(r), math.sin(r)
    m = Mat4.identity()
    m[0][0] = c
    m[0][1] = -s
    m[1][0] = s
    m[1][1] = c
    return m


# ------------------------------------------------------------------
# AE local transform matrix
# ------------------------------------------------------------------


def build_local_matrix(
    position: list[float],
    anchor: list[float],
    scale_pct: list[float],
    rotation_z: float,
    *,
    orientation: list[float] | None = None,
    rotate_x: float = 0.0,
    rotate_y: float = 0.0,
    auto_rotation: Mat4 | None = None,
    source_aspect: float = 1.0,
    space_aspect: float = 1.0,
) -> Mat4:
    """Build the local transform matrix for an AE layer.

    After Effects scales and rotates in square pixels: a layer's own
    pixels are widened by its source's pixel aspect first, and the result
    narrowed by the pixel aspect of the space its Position lives in (its
    parent's source, or the composition) - `T(pos) . Sp^-1 . R . S . Sl .
    T(-anchor)` (measured on AE 2026 in a 2:1 pixel-aspect comp).

    Args:
        position: `[x, y, z]` position in pixels.
        anchor: `[x, y, z]` anchor point in pixels.
        scale_pct: `[sx, sy, sz]` scale as percentages (100 = 1x).
        rotation_z: Z-axis rotation in degrees.
        orientation: `[ox, oy, oz]` orientation angles in degrees
            (3D layers only).
        rotate_x: X-axis rotation in degrees (3D layers only).
        rotate_y: Y-axis rotation in degrees (3D layers only).
        auto_rotation: A 3D layer's auto-orientation, applied after its own
            rotations (before the translation).
        source_aspect: The pixel aspect of the layer's own pixels (`Sl`).
        space_aspect: The pixel aspect of the space the layer's Position
            lives in (`Sp`).

    Returns:
        A 4x4 matrix representing the layer's local transform.
    """
    sx = scale_pct[0] / 100.0
    sy = scale_pct[1] / 100.0
    sz = scale_pct[2] / 100.0 if len(scale_pct) > 2 else 1.0

    # Start from right: T(-anchor)
    m = _translation(-anchor[0], -anchor[1], -anchor[2] if len(anchor) > 2 else 0.0)
    if source_aspect != 1.0:
        m = _scale(source_aspect, 1.0, 1.0) @ m

    # Scale
    m = _scale(sx, sy, sz) @ m

    # Per-axis rotations: Rz * Ry * Rx (applied right-to-left)
    m = _rotate_z(rotation_z) @ m
    m = _rotate_y(rotate_y) @ m
    m = _rotate_x(rotate_x) @ m

    # Orientation: Rz(oz) * Ry(oy) * Rx(ox)
    if orientation is not None:
        ox, oy, oz = orientation[0], orientation[1], orientation[2]
        m = _rotate_z(oz) @ m
        m = _rotate_y(oy) @ m
        m = _rotate_x(ox) @ m

    if auto_rotation is not None:
        m = auto_rotation @ m

    if space_aspect != 1.0:
        m = _scale(1.0 / space_aspect, 1.0, 1.0) @ m

    # Position
    px = position[0]
    py = position[1]
    pz = position[2] if len(position) > 2 else 0.0
    m = _translation(px, py, pz) @ m

    return m


# ------------------------------------------------------------------
# World matrix (walks parent chain)
# ------------------------------------------------------------------


def build_world_matrix(
    layer: Layer,
    time: float | None = None,
    flatten_2d: bool = False,
    *,
    as_parent: bool = False,
    auto_orient: bool = False,
) -> Mat4:
    """Build the world transform matrix by composing the parent chain.

    Traverses `layer.parent` upward, composing local matrices so that::

        world = root_local @ ... @ parent_local @ layer_local

    A camera or light ancestor contributes its rig: its position and
    rotations (a two-node rig's look-at toward its point of interest
    first), with no anchor point or scale - what After Effects parents to
    (measured on AE 2026).

    Args:
        layer: The layer whose world matrix to build.
        time: Composition time in seconds to evaluate animated transform
            properties at; `None` uses each property's static `value`.
        flatten_2d: Drop the out-of-plane terms (see `_layer_local_matrix`).
        as_parent: Treat `layer` itself as a parent too - a camera or light
            then contributes its rig.
        auto_orient: Apply the layers' auto-orientation (needs `time`).

    Raises:
        NotImplementedError: With `auto_orient`, for an orientation the
            math does not model (see `_auto_rotation`).
    """
    chain = []
    current: Layer | None = layer
    while current is not None:
        chain.append(current)
        current = current.parent

    # Compose from root (last in chain) down to the layer itself. Each
    # Position lives in its parent's pixels (the comp's for the root).
    m = Mat4.identity()
    comp = layer.containing_comp
    space_aspect = float(comp.pixel_aspect)
    for lyr in reversed(chain):
        if (lyr is not layer or as_parent) and lyr._ldta.layer_type in _RIG_TYPES:
            if flatten_2d:
                # Under a 2D layer a rig acts as a 2D layer anchored on the
                # comp centre, turned by Rotate Z alone (AE 2026: children
                # of a camera, a spot and a point light all fit
                # `T(pos.xy) . Rz . T(-w/2, -h/2)` exactly).
                position = cast(
                    "list[float]", _prop_value(lyr.transform, "ADBE Position", time)
                )
                rz = cast("float", _prop_value(lyr.transform, "ADBE Rotate Z", time))
                m @= (
                    _translation(position[0], position[1], 0.0)
                    @ _rotate_z(rz)
                    @ _translation(-comp.width / 2.0, -comp.height / 2.0, 0.0)
                )
            else:
                m @= _rig_matrix(lyr, time, space_aspect)
            space_aspect = 1.0
        else:
            source_aspect = layer_source_aspect(lyr)
            m @= _layer_local_matrix(
                lyr, time, flatten_2d, auto_orient, source_aspect, space_aspect
            )
            space_aspect = source_aspect
    return m


def layer_source_aspect(layer: Layer) -> float:
    """Pixel aspect of a layer's own pixels: its source's, else square."""
    source = getattr(layer, "source", None)
    aspect = getattr(source, "pixel_aspect", None)
    return float(aspect) if aspect else 1.0


def position_space_aspect(parent: Layer | None, comp: CompItem) -> float:
    """Pixel aspect of the space a child of `parent` keeps its Position in:
    the comp's at the root, square under a camera or light."""
    if parent is None:
        return float(comp.pixel_aspect)
    if parent._ldta.layer_type in _RIG_TYPES:
        return 1.0
    return layer_source_aspect(parent)


def aspect_scale(aspect: float) -> Mat4:
    """`diag(aspect, 1, 1)`: widens pixels of that aspect to square ones."""
    return _scale(aspect, 1.0, 1.0)


def square_pixels(matrix: Mat4, comp_aspect: float, space_aspect: float) -> Mat4:
    """A world matrix from a `space_aspect` space into comp pixels, made to
    map square pixels to square pixels (so its rotation can be read)."""
    return aspect_scale(comp_aspect) @ matrix @ aspect_scale(1.0 / space_aspect)


def _prop_value(group: PropertyGroup, match_name: str, time: float | None) -> Any:
    """Evaluate `group[match_name]`: static `value` when `time` is `None`,
    else `value_at_time(time)`."""
    prop = cast("Property", group[match_name])
    if time is None:
        return prop.value
    return prop.value_at_time(time)


def _layer_local_matrix(
    layer: Layer,
    time: float | None = None,
    flatten_2d: bool = False,
    auto_orient: bool = False,
    source_aspect: float = 1.0,
    space_aspect: float = 1.0,
) -> Mat4:
    """Build the local matrix for a single layer from its properties.

    With `flatten_2d`, the out-of-plane terms are dropped - X/Y rotation,
    the whole Orientation and the Z translation. That is how After Effects
    places a 2D layer under 3D ancestors, for its point conversions as well
    as when compensating a reparent: a 2D layer parented to a null rotated
    20/-35/30 gets exactly the compensation of a null rotated 0/0/30, and
    a parent's Orientation does not turn it at all (measured on AE 2026: a
    parent with Orientation [0, 0, 30] leaves the child's Rotate Z at 0).
    """
    transform = layer.transform

    def value(match_name: str) -> Any:
        return _prop_value(transform, match_name, time)

    position = cast("list[float]", value("ADBE Position"))
    anchor = cast("list[float]", value("ADBE Anchor Point"))
    scale_pct = cast("list[float]", value("ADBE Scale"))
    rz = cast("float", value("ADBE Rotate Z"))
    orientation = cast("list[float]", value("ADBE Orientation"))
    rx = cast("float", value("ADBE Rotate X"))
    ry = cast("float", value("ADBE Rotate Y"))

    if flatten_2d:
        position = position[:2] + [0.0]
        rx = 0.0
        ry = 0.0
        orientation = [0.0, 0.0, 0.0]

    auto_rotation = None
    if auto_orient and time is not None:
        auto_rotation, auto_rz = _auto_rotation(layer, time, position)
        rz += auto_rz

    is_3d = rx != 0.0 or ry != 0.0 or any(v != 0.0 for v in orientation)

    return build_local_matrix(
        position=position,
        anchor=anchor,
        scale_pct=scale_pct,
        rotation_z=rz,
        orientation=orientation if is_3d else None,
        rotate_x=rx,
        rotate_y=ry,
        auto_rotation=auto_rotation,
        source_aspect=source_aspect,
        space_aspect=space_aspect,
    )


# Layer types (`ldta.layer_type`) a child parents to as a rig: light, camera.
_RIG_TYPES = frozenset({LayerType.LIGHT, LayerType.CAMERA})
_AIMED_LIGHTS = frozenset({LightType.SPOT, LightType.PARALLEL})


def rig_aims_at_poi(layer: Layer) -> bool:
    """Whether a camera or light layer is a two-node rig that looks at its
    point of interest: a camera, spot or parallel light orienting towards it
    (a point light keeps the flag but AE applies no look-at)."""
    layer_type = layer._ldta.layer_type
    if layer_type not in _RIG_TYPES:
        return False
    aims = layer_type == LayerType.CAMERA or (
        cast("LightLayer", layer).light_type in _AIMED_LIGHTS
    )
    return aims and layer.auto_orient == AutoOrientType.CAMERA_OR_POINT_OF_INTEREST


def _rig_rotation(layer: Layer, time: float | None, space_aspect: float) -> Mat4:
    """A camera or light's rotation: the two-node look-at toward its point
    of interest (stored in the anchor-point slot), then Orientation and the
    per-axis rotations.

    Only a camera and a light that aims (spot, parallel) look at their
    point of interest: a point light keeps the auto-orient flag and a point
    of interest but After Effects applies no look-at (measured on AE 2026).
    The look-at aims in square pixels, its Position and point of interest
    widened by the pixel aspect of the space they live in.
    """
    transform = layer.transform

    def value(match_name: str) -> Any:
        return _prop_value(transform, match_name, time)

    rotation = Mat4.identity()
    if rig_aims_at_poi(layer):
        eye = list(cast("list[float]", value("ADBE Position")))
        target = list(cast("list[float]", value("ADBE Anchor Point")))
        eye[0] *= space_aspect
        target[0] *= space_aspect
        rotation = _look_at_rotation(eye, target)
    orientation = cast("list[float]", value("ADBE Orientation"))
    return (
        rotation
        @ _rotate_x(orientation[0])
        @ _rotate_y(orientation[1])
        @ _rotate_z(orientation[2])
        @ _rotate_x(cast("float", value("ADBE Rotate X")))
        @ _rotate_y(cast("float", value("ADBE Rotate Y")))
        @ _rotate_z(cast("float", value("ADBE Rotate Z")))
    )


def _rig_matrix(layer: Layer, time: float | None, space_aspect: float) -> Mat4:
    """A camera or light's rig, turning in square pixels like a layer (see
    `build_local_matrix`)."""
    position = cast("list[float]", _prop_value(layer.transform, "ADBE Position", time))
    m = _rig_rotation(layer, time, space_aspect)
    if space_aspect != 1.0:
        m = _scale(1.0 / space_aspect, 1.0, 1.0) @ m
    return _translation(position[0], position[1], position[2]) @ m


def _auto_rotation(
    layer: Layer, time: float, position: list[float]
) -> tuple[Mat4 | None, float]:
    """A layer's auto-orientation at comp `time`: `(3D rotation, 2D Rotate Z
    increment)`, measured on AE 2026.

    - Along its path, a 2D layer turns its X axis to the motion direction;
      a 3D layer aims its Z axis along it (a two-node camera's look-at).
      A layer whose Position is not animated does not turn.
    - Towards the camera, a 3D layer aims its Z axis away from the active
      camera (the comp's default camera without one).

    Raises:
        NotImplementedError: For separated Position dimensions along a
            path, a parented layer turned towards the camera, and characters
            turned towards the camera.
    """
    mode = layer.auto_orient
    three_d = bool(layer._ldta.three_d_layer)
    if mode == AutoOrientType.ALONG_PATH:
        prop = cast("Property", layer.transform["ADBE Position"])
        if prop.dimensions_separated:
            raise NotImplementedError(
                f"layer {layer.name!r} auto-orients along a path with separated "
                "Position dimensions, which the transform math does not model"
            )
        direction = prop._motion_direction_at(time)
        if direction is None:
            return None, 0.0
        if three_d:
            forward = (list(direction) + [0.0, 0.0])[:3]
            return _look_at_rotation([0.0, 0.0, 0.0], forward), 0.0
        return None, math.degrees(math.atan2(direction[1], direction[0]))
    if mode == AutoOrientType.CAMERA_OR_POINT_OF_INTEREST and three_d:
        if layer.parent is not None:
            raise NotImplementedError(
                f"layer {layer.name!r} is parented and turned towards the "
                "camera, which the transform math does not model"
            )
        return _look_at_rotation(_camera_position(layer, time), position), 0.0
    if mode == AutoOrientType.CHARACTERS_TOWARD_CAMERA:
        raise NotImplementedError(
            f"layer {layer.name!r} turns its characters towards the camera, "
            "which the transform math does not model"
        )
    return None, 0.0


def _camera_position(layer: Layer, time: float) -> list[float]:
    """World position of the camera active at `time` in `layer`'s comp:
    the front-most enabled camera layer, else the comp's default camera."""
    comp = layer.containing_comp
    camera = cast("AVLayer", layer)._active_camera_at(time)
    if camera is not None:
        world = build_world_matrix(camera, time, as_parent=True)
        return world.transform_point([0.0, 0.0, 0.0])
    zoom = default_camera_zoom(comp.width, comp.pixel_aspect)
    return [comp.width / 2.0, comp.height / 2.0, -zoom]


# ------------------------------------------------------------------
# Matrix decomposition
# ------------------------------------------------------------------


def _vec3_norm(v: list[float]) -> float:
    # hypot, not sqrt(x*x + y*y + z*z): squaring overflows to inf above ~1.34e154
    # and the norm then poisons every value derived from it. Nested 2-argument
    # calls because hypot only takes 3 arguments from Python 3.8.
    return math.hypot(math.hypot(v[0], v[1]), v[2])


def _mat3_det(m: Mat4) -> float:
    """Determinant of the upper-left 3x3 of a 4x4 matrix."""
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def rotation_part(matrix: Mat4) -> Mat4:
    """The rotation of `matrix`, with translation and scale divided out.

    Column-normalizes the 3x3 block, then negates all three columns when the
    result is a reflection, so what comes back is always a proper rotation.
    That mirrors AE, which keeps the rotation proper and pushes the flip into
    the scale as an all-negative triple: a parent scaled `[-100, 100, 100]`
    leaves the child at scale `[-100, -100, -100]` with Orientation
    `[180, 0, 0]`, not at a mirrored rotation.

    Exact for a rotation composed with a uniform scale. A non-uniform parent
    scale combined with a rotation that is not axis-aligned shears the block,
    and no rotation represents it - the case where AE's own reparenting jumps
    too.
    """
    rows = [[0.0] * 4 for _ in range(4)]
    rows[3][3] = 1.0
    for column in range(3):
        axis = [matrix[row][column] for row in range(3)]
        length = _vec3_norm(axis) or 1.0
        for row in range(3):
            rows[row][column] = axis[row] / length
    normalized = Mat4(rows)
    if _mat3_det(normalized) < 0:
        for row in range(3):
            for column in range(3):
                rows[row][column] = -rows[row][column]
    return Mat4(rows)


def compose_orientation(orientation: list[float], delta: Mat4) -> list[float]:
    """Euler angles for `delta` applied on top of `orientation`.

    After Effects compensates a reparent of a 3D layer through Orientation
    rather than through Rotate X/Y/Z: `O_new = parent_rotation^-1 . O_old`,
    with the rotations left exactly as they were. Verified on AE 2026 across
    ten cases to 0.01 degrees, including a child carrying its own non-zero
    rotations - those cancel out of the relation, which is why the answer
    does not depend on them.
    """
    current = (_rotate_x(orientation[0]) @ _rotate_y(orientation[1])) @ _rotate_z(
        orientation[2]
    )
    combined = delta @ current
    angles = _euler_xyz(
        combined[0][0],
        combined[0][1],
        combined[0][2],
        combined[1][0],
        combined[1][1],
        combined[1][2],
        combined[2][2],
    )
    return [angle % 360.0 for angle in angles]


def strip_orientation(matrix: Mat4, orientation: list[float]) -> Mat4:
    """`matrix` with a layer's Orientation divided out of its 3x3 block.

    `build_local_matrix` composes `T(pos) . O . R . S . T(-anchor)`, so the
    rotation After Effects would store for a given local matrix is `O^-1`
    times its 3x3 part - and AE leaves Orientation itself untouched when
    reparenting (measured on AE 2026: an oriented child under a translating
    parent gets a new Position and nothing else).

    Only the 3x3 is divided. Orientation sits *inside* the position
    translation, so left-multiplying the whole 4x4 by `O^-1` would rotate the
    compensated position as well; the position decomposes from
    `M[:,3] + M3 . anchor`, which the orientation never enters.
    """
    ox, oy, oz = orientation[0], orientation[1], orientation[2]
    inverse = _rotate_z(-oz) @ _rotate_y(-oy) @ _rotate_x(-ox)
    rotated = inverse @ matrix
    rows = [list(matrix[r]) for r in range(4)]
    for r in range(3):
        rows[r][0], rows[r][1], rows[r][2] = (
            rotated[r][0],
            rotated[r][1],
            rotated[r][2],
        )
    return Mat4(rows)


def decompose_transform(
    matrix: Mat4,
    anchor: list[float],
) -> tuple[list[float], list[float], float, float, float]:
    """Decompose a 4x4 matrix into AE transform components.

    Given a matrix `M` and a fixed anchor point, extracts the
    Position, Scale, and Rotation values that would produce `M`
    via `build_local_matrix`.

    Orientation is assumed to be `[0, 0, 0]` - i.e. any orientation
    contribution must already be factored out before calling this.

    Args:
        matrix: The 4x4 transform matrix to decompose.
        anchor: `[ax, ay, az]` anchor point (held constant).

    Returns:
        A tuple of `(position, scale_pct, rotation_z, rotate_x,
        rotate_y)` where `scale_pct` is in percentage units (100 = 1x).
    """
    ax = anchor[0]
    ay = anchor[1]
    az = anchor[2] if len(anchor) > 2 else 0.0

    # Q = M @ T(anchor) - factors out the anchor translation.
    # This gives Q = T(pos) * R * S, which is straightforward to
    # decompose.
    t_anchor = _translation(ax, ay, az)
    q = matrix @ t_anchor

    # Position is in the last column.
    pos = [q[0][3], q[1][3], q[2][3]]

    # Extract 3x3 upper-left (contains R * S).
    col0 = [q[0][0], q[1][0], q[2][0]]
    col1 = [q[0][1], q[1][1], q[2][1]]
    col2 = [q[0][2], q[1][2], q[2][2]]

    sx = _vec3_norm(col0)
    sy = _vec3_norm(col1)
    sz = _vec3_norm(col2)

    # Flip detection: if determinant is negative, one scale axis is
    # flipped. Convention: negate sx.
    if _mat3_det(q) < 0:
        sx = -sx

    # Clamp near-zero scales to avoid division by zero.
    if abs(sx) < _EPSILON:
        sx = _EPSILON if sx >= 0 else -_EPSILON
    if abs(sy) < _EPSILON:
        sy = _EPSILON if sy >= 0 else -_EPSILON
    if abs(sz) < _EPSILON:
        sz = _EPSILON if sz >= 0 else -_EPSILON

    # Rotation matrix = Q3 * diag(1/sx, 1/sy, 1/sz)
    r00 = col0[0] / sx
    r10 = col0[1] / sx
    r01 = col1[0] / sy
    r11 = col1[1] / sy
    r02 = col2[0] / sz
    r12 = col2[1] / sz
    r22 = col2[2] / sz

    rx_deg, ry_deg, rz_deg = _euler_xyz(r00, r01, r02, r10, r11, r12, r22)

    scale_pct = [sx * 100.0, sy * 100.0, sz * 100.0]
    return pos, scale_pct, rz_deg, rx_deg, ry_deg


def _euler_xyz(
    r00: float,
    r01: float,
    r02: float,
    r10: float,
    r11: float,
    r12: float,
    r22: float,
) -> tuple[float, float, float]:
    """Extract intrinsic X-Y-Z Euler angles (degrees) from R = Rx*Ry*Rz.

    R = | cb*cg       -cb*sg        sb    |
        | sa*sb*cg+ca*sg  -sa*sb*sg+ca*cg  -sa*cb |
        | -ca*sb*cg+sa*sg  ca*sb*sg+sa*cg   ca*cb |
    """
    # Clamp to [-1, 1] for asin safety.
    sin_beta = max(-1.0, min(1.0, r02))
    beta = math.asin(sin_beta)
    # cos(beta) straight off the matrix. Going through `cos(asin(r02))`
    # loses most of its digits as r02 approaches 1, which matters because
    # an orientation slerping towards a 90-degree Y passes near the pole
    # on almost every frame without ever reaching it.
    cos_beta = math.hypot(r00, r01)

    if abs(cos_beta) > _EPSILON:
        # Normal case: no gimbal lock.
        rx_deg = math.atan2(-r12, r22) * _RAD2DEG
        ry_deg = beta * _RAD2DEG
        rz_deg = math.atan2(-r01, r00) * _RAD2DEG
    else:
        # Gimbal lock: beta = +/-90 deg, where X and Z turn about the same
        # line and only their combination is recoverable. AE puts all of it
        # on Z and leaves X at zero - measured on AE 2026 by reparenting a
        # 3D child at orientation [0, 0, g] under a parent rotated Y = +/-90,
        # which AE writes back as [0, 270, g] / [0, 90, g] for g across a
        # full turn. Solving the same relation for X instead (the previous
        # behavior) does not even reconstruct the rotation at beta = -90.
        rx_deg = 0.0
        rz_deg = math.atan2(r10, r11) * _RAD2DEG
        ry_deg = beta * _RAD2DEG
    return rx_deg, ry_deg, rz_deg


# ------------------------------------------------------------------
# Vector helpers
# ------------------------------------------------------------------


def _vec3_cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _vec3_normalize(v: list[float]) -> list[float]:
    n = _vec3_norm(v)
    if n < _EPSILON:
        raise ValueError("cannot normalize a zero-length vector")
    return [v[0] / n, v[1] / n, v[2] / n]


# ------------------------------------------------------------------
# calculateTransformFromPoints
# ------------------------------------------------------------------


def transform_from_points(
    top_left: list[float],
    top_right: list[float],
    bottom_left: list[float],
    width: float,
    height: float,
) -> dict[str, Any]:
    """Compute AE transform values mapping a layer source onto three points.

    Pure function of the three points and the layer's SOURCE dimensions
    (verified against AE 2026: the layer's current transform is ignored,
    and 2D and 3D layers return identical results). The y axis is
    Gram-Schmidt-orthogonalized against x, absorbing any shear into
    `scale[2] = 100 * sin(angle(x, y))`; reflections come out as 180-degree
    rotation combinations, never negative scale.

    Args:
        top_left: `[x, y, z]` comp-space position of the source's top-left.
        top_right: `[x, y, z]` position of the source's top-right.
        bottom_left: `[x, y, z]` position of the source's bottom-left.
        width: Layer source width in pixels.
        height: Layer source height in pixels.

    Returns:
        A dict with `anchor_point`, `position`, `x_rotation`, `y_rotation`,
        `z_rotation` and `scale` keys, matching the transform property
        values AE's `calculateTransformFromPoints()` returns.

    Raises:
        ValueError: If the points are coincident or collinear.
    """
    x_axis = [top_right[i] - top_left[i] for i in range(3)]
    y_axis = [bottom_left[i] - top_left[i] for i in range(3)]
    x_len = _vec3_norm(x_axis)
    y_len = _vec3_norm(y_axis)
    if x_len < _EPSILON or y_len < _EPSILON:
        raise ValueError("transform points must not be coincident")
    x_hat = [c / x_len for c in x_axis]
    y_raw_hat = [c / y_len for c in y_axis]

    # Shear is absorbed into the z scale: 100 * sin(angle between x and y).
    sin_theta = _vec3_norm(_vec3_cross(x_hat, y_raw_hat))

    x_dot_y = sum(x_hat[i] * y_axis[i] for i in range(3))
    y_ortho = [y_axis[i] - x_dot_y * x_hat[i] for i in range(3)]
    y_ortho_len = _vec3_norm(y_ortho)
    if y_ortho_len < _EPSILON:
        raise ValueError("transform points must not be collinear")
    y_hat = [c / y_ortho_len for c in y_ortho]
    z_hat = _vec3_cross(x_hat, y_hat)

    rx_deg, ry_deg, rz_deg = _euler_xyz(
        x_hat[0], y_hat[0], z_hat[0], x_hat[1], y_hat[1], z_hat[1], z_hat[2]
    )

    return {
        "anchor_point": [0.0, 0.0, 0.0],
        "position": [float(top_left[0]), float(top_left[1]), float(top_left[2])],
        "x_rotation": rx_deg,
        "y_rotation": ry_deg,
        "z_rotation": rz_deg,
        "scale": [
            x_len / width * 100.0,
            y_ortho_len / height * 100.0,
            sin_theta * 100.0,
        ],
    }


# ------------------------------------------------------------------
# Camera projection (sourcePointToComp / compPointToSource)
# ------------------------------------------------------------------


def default_camera_zoom(comp_width: float, pixel_aspect: float) -> float:
    """AE's default comp camera zoom in pixels: `width * pixel_aspect / 0.72`
    (the 50mm preset; 2 * tan(fov/2) held at the exact 0.72 ratio).

    The zoom is in SQUARE pixels, so a non-square-pixel comp scales the
    width by its pixel aspect ratio first (verified against AE 2026 at
    pixel aspects 0.5 / 1.0 / 1.21212).
    """
    return comp_width * pixel_aspect / 0.72


def project_to_comp(
    world_point: list[float],
    comp_width: float,
    comp_height: float,
    pixel_aspect: float,
) -> list[float]:
    """Project a world-space point to comp coordinates.

    Always uses AE's DEFAULT comp camera: `sourcePointToComp()` is
    camera-independent (verified against AE 2026 - one-node, two-node and
    keyframed-zoom rigs all return the values of the default camera). For
    a point in the z=0 plane the projection is the identity, so 2D layers
    fall out naturally.
    """
    zoom = default_camera_zoom(comp_width, pixel_aspect)
    cx = comp_width / 2.0
    cy = comp_height / 2.0
    factor = zoom / (zoom + world_point[2])
    return [
        cx + (world_point[0] - cx) * factor,
        cy + (world_point[1] - cy) * factor,
    ]


def _look_at_rotation(eye: list[float], target: list[float]) -> Mat4:
    """Rotation orienting a camera at `eye` toward `target` (AE two-node
    rig): the camera z axis points at the target, roll referenced to +Y.

    Both degenerate inputs resolve the way AE does, rather than raising
    (probed AE 2026 over a 116-point elevation x azimuth sweep, both
    poles, three radii):

    - `eye == target`: AE applies no look-at at all, leaving its neutral
      +Z heading.
    - view direction parallel to +Y (a plain top-down or bottom-up
      camera, where `cross(up, forward)` vanishes): AE resolves the roll
      as if the azimuth were 0. Away from the poles AE is smooth and
      azimuth-dependent down to at least 1e-7 degrees - it does NOT snap
      within a tolerance band - so the fallback must apply only where the
      cross product is genuinely zero, which `_EPSILON` already separates
      (|cross| is ~1.7e-9 at 1e-7 degrees off vertical, vs ~6e-17 or an
      exact 0 at the pole).
    """
    delta = [target[i] - eye[i] for i in range(3)]
    if _vec3_norm(delta) < _EPSILON:
        forward = [0.0, 0.0, 1.0]
    else:
        forward = _vec3_normalize(delta)
    up = [0.0, 1.0, 0.0]
    cross = _vec3_cross(up, forward)
    if _vec3_norm(cross) < _EPSILON:
        x_axis = [1.0, 0.0, 0.0]
    else:
        x_axis = _vec3_normalize(cross)
    y_axis = _vec3_cross(forward, x_axis)
    m = Mat4.identity()
    for row in range(3):
        m[row][0] = x_axis[row]
        m[row][1] = y_axis[row]
        m[row][2] = forward[row]
    return m


def camera_ray(
    camera: Layer | None,
    comp_point: list[float],
    comp_width: float,
    comp_height: float,
    pixel_aspect: float,
    time: float | None = None,
) -> tuple[list[float], list[float]]:
    """Build the world-space ray a comp-space point casts from a camera.

    With no camera, uses AE's default comp camera (centered at
    `(w/2, h/2, -zoom)`, unrotated). With a camera layer, the ray starts at
    the camera position and passes through the comp point on the image
    plane at the camera's zoom distance; a two-node camera derives its
    rotation from the look-at toward its point of interest (stored in the
    anchor-point slot), then applies Orientation and the per-axis
    rotations on top.

    Returns:
        `(origin, direction)` in world space.
    """
    cx = comp_width / 2.0
    cy = comp_height / 2.0

    if camera is None:
        zoom = default_camera_zoom(comp_width, pixel_aspect)
        origin = [cx, cy, -zoom]
        direction = [comp_point[0] - cx, comp_point[1] - cy, zoom]
        return origin, direction

    # The camera's whole parent chain places it (AE 2026: a camera parented
    # to a turned null casts its rays from where the null carries it).
    world = build_world_matrix(camera, time, as_parent=True)
    position = world.transform_point([0.0, 0.0, 0.0])

    camera_options = cast("PropertyGroup", camera["ADBE Camera Options Group"])
    zoom = cast("float", _prop_value(camera_options, "ADBE Camera Zoom", time))

    # The image plane is in square pixels; the rig matrix narrows the ray
    # back into comp pixels (see `build_local_matrix`).
    direction = world.transform_vector(
        [(comp_point[0] - cx) * pixel_aspect, comp_point[1] - cy, zoom]
    )
    return list(position), direction


def intersect_layer_plane(
    world: Mat4, origin: list[float], direction: list[float]
) -> list[float]:
    """Intersect a world-space ray with a layer's source plane.

    Solves `origin + t * direction = world(u, v, 0)` for the layer
    coordinates `(u, v)` directly, without inverting `world`: the plane
    only needs the layer's X and Y axes, so a layer whose Z scale is 0
    still resolves (AE 2026 answers for one).

    Only the FORWARD ray counts, like AE: a plane at or behind the ray's
    origin is not hit. Probed AE 2026 over a sub-0.001-unit sweep through
    `t = 0` and a dedicated parallel-ray rig - the boundary is inclusive
    (`t == 0` already misses), and a parallel ray is the same case rather
    than a special one.

    Where this raises, AE returns a literal `[0, 0]`. That is NOT mirrored:
    the sentinel is type- and range-indistinguishable from a real answer
    (a rig whose genuine intersection IS the layer origin returns the same
    `[0, 0]`), the AE Scripting Guide does not document it, and a caller
    that cannot tell a miss from a hit will use the miss as a coordinate.

    Raises:
        ValueError: If the forward ray does not meet the layer plane - it
            is parallel to the plane, or the plane is at or behind the ray
            origin - or if the layer plane is degenerate (an X or Y scale
            of 0).
    """
    axis_u = [world[r][0] for r in range(3)]
    axis_v = [world[r][1] for r in range(3)]
    rhs = [origin[r] - world[r][3] for r in range(3)]
    neg_d = [-direction[r] for r in range(3)]
    normal = _vec3_cross(axis_u, axis_v)
    normal_len = _vec3_norm(normal)
    if normal_len == 0.0:
        raise ValueError("the layer plane is degenerate")
    det = _det3(axis_u, axis_v, neg_d)
    if abs(det) <= _EPSILON * normal_len * _vec3_norm(direction):
        raise ValueError("ray is parallel to the layer plane")
    t = _det3(axis_u, axis_v, rhs) / det
    if t <= 0.0:
        raise ValueError("the layer plane is not in front of the camera")
    return [_det3(rhs, axis_v, neg_d) / det, _det3(axis_u, rhs, neg_d) / det]


def _det3(a: list[float], b: list[float], c: list[float]) -> float:
    """Determinant of the 3x3 matrix with columns `a`, `b`, `c`."""
    cross = _vec3_cross(b, c)
    return a[0] * cross[0] + a[1] * cross[1] + a[2] * cross[2]
