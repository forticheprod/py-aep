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

from ..enums import AutoOrientType

if TYPE_CHECKING:
    from typing import Any

    from ..models.layers.layer import Layer
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
        if abs(det) < _EPSILON:
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
) -> Mat4:
    """Build the local transform matrix for an AE layer.

    Args:
        position: `[x, y, z]` position in pixels.
        anchor: `[x, y, z]` anchor point in pixels.
        scale_pct: `[sx, sy, sz]` scale as percentages (100 = 1x).
        rotation_z: Z-axis rotation in degrees.
        orientation: `[ox, oy, oz]` orientation angles in degrees
            (3D layers only).
        rotate_x: X-axis rotation in degrees (3D layers only).
        rotate_y: Y-axis rotation in degrees (3D layers only).

    Returns:
        A 4x4 matrix representing the layer's local transform.
    """
    sx = scale_pct[0] / 100.0
    sy = scale_pct[1] / 100.0
    sz = scale_pct[2] / 100.0 if len(scale_pct) > 2 else 1.0

    # Start from right: T(-anchor)
    m = _translation(-anchor[0], -anchor[1], -anchor[2] if len(anchor) > 2 else 0.0)

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

    # Position
    px = position[0]
    py = position[1]
    pz = position[2] if len(position) > 2 else 0.0
    m = _translation(px, py, pz) @ m

    return m


# ------------------------------------------------------------------
# World matrix (walks parent chain)
# ------------------------------------------------------------------


def build_world_matrix(layer: Layer, time: float | None = None) -> Mat4:
    """Build the world transform matrix by composing the parent chain.

    Traverses `layer.parent` upward, composing local matrices so that::

        world = root_local @ ... @ parent_local @ layer_local

    Args:
        layer: The layer whose world matrix to build.
        time: Composition time in seconds to evaluate animated transform
            properties at; `None` uses each property's static `value`.
    """
    chain = []
    current: Layer | None = layer
    while current is not None:
        chain.append(current)
        current = current.parent

    # Compose from root (last in chain) down to the layer itself.
    m = Mat4.identity()
    for lyr in reversed(chain):
        m @= _layer_local_matrix(lyr, time)
    return m


def _prop_value(group: PropertyGroup, match_name: str, time: float | None) -> Any:
    """Evaluate `group[match_name]`: static `value` when `time` is `None`,
    else `value_at_time(time)`."""
    prop = cast("Property", group[match_name])
    if time is None:
        return prop.value
    return prop.value_at_time(time)


def _layer_local_matrix(layer: Layer, time: float | None = None) -> Mat4:
    """Build the local matrix for a single layer from its properties."""
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

    is_3d = rx != 0.0 or ry != 0.0 or any(v != 0.0 for v in orientation)

    return build_local_matrix(
        position=position,
        anchor=anchor,
        scale_pct=scale_pct,
        rotation_z=rz,
        orientation=orientation if is_3d else None,
        rotate_x=rx,
        rotate_y=ry,
    )


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
    cos_beta = math.cos(beta)

    if abs(cos_beta) > _EPSILON:
        # Normal case: no gimbal lock.
        rx_deg = math.atan2(-r12, r22) * _RAD2DEG
        ry_deg = beta * _RAD2DEG
        rz_deg = math.atan2(-r01, r00) * _RAD2DEG
    else:
        # Gimbal lock: beta = +/-90 deg. Set rz=0 and solve for rx.
        rz_deg = 0.0
        rx_deg = math.atan2(r10, r11) * _RAD2DEG
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

    transform = camera.transform

    def value(match_name: str) -> Any:
        return _prop_value(transform, match_name, time)

    position = cast("list[float]", value("ADBE Position"))
    orientation = cast("list[float]", value("ADBE Orientation"))
    rx = cast("float", value("ADBE Rotate X"))
    ry = cast("float", value("ADBE Rotate Y"))
    rz = cast("float", value("ADBE Rotate Z"))

    rotation = Mat4.identity()

    if camera.auto_orient == AutoOrientType.CAMERA_OR_POINT_OF_INTEREST:
        # The camera's point of interest lives in the anchor-point slot.
        poi = cast("list[float]", value("ADBE Anchor Point"))
        rotation = _look_at_rotation(position, poi)
    rotation = (
        rotation
        @ _rotate_x(orientation[0])
        @ _rotate_y(orientation[1])
        @ _rotate_z(orientation[2])
        @ _rotate_x(rx)
        @ _rotate_y(ry)
        @ _rotate_z(rz)
    )

    camera_options = cast("PropertyGroup", camera["ADBE Camera Options Group"])
    zoom = cast("float", _prop_value(camera_options, "ADBE Camera Zoom", time))

    direction = rotation.transform_vector(
        [comp_point[0] - cx, comp_point[1] - cy, zoom]
    )
    return list(position), direction


def intersect_layer_plane(
    world: Mat4, origin: list[float], direction: list[float]
) -> list[float]:
    """Intersect a world-space ray with a layer's source plane.

    Transforms the ray into layer space with the inverse world matrix and
    solves against the `z=0` source plane.

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
            origin - or if the world matrix is singular.
    """
    inverse = world.inverse()
    o_l = inverse.transform_point(origin)
    d_l = inverse.transform_vector(direction)
    if abs(d_l[2]) < _EPSILON:
        raise ValueError("ray is parallel to the layer plane")
    t = -o_l[2] / d_l[2]
    if t <= 0.0:
        raise ValueError("the layer plane is not in front of the camera")
    return [o_l[0] + t * d_l[0], o_l[1] + t * d_l[1]]
