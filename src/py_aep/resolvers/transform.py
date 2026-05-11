"""4x4 affine transform utilities for After Effects layer transforms.

Provides matrix composition and decomposition matching AE's internal
transform pipeline.  Pure Python with no external dependencies.

**AE transform order** (column-vector convention, right-to-left)::

    2D:  T(pos) * Rz(rz) * S(scale) * T(-anchor)
    3D:  T(pos) * Rx(ox)*Ry(oy)*Rz(oz) * Rx(rx)*Ry(ry)*Rz(rz)
         * S(scale) * T(-anchor)

where ``o{x,y,z}`` are Orientation angles and ``r{x,y,z}`` are
per-axis Rotation angles, all in degrees.

Coordinate system: left-handed, Y-down (X right, Y down, Z into screen).
Standard rotation matrices apply without sign flips.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.layers.layer import Layer


_DEG2RAD = math.pi / 180.0
_RAD2DEG = 180.0 / math.pi
_EPSILON = 1e-10

class Mat4:
    """4x4 matrix stored row-major: ``m[row][col]``."""

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
        return cls([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ])

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

        return Mat4([
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
        ])

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
        position: ``[x, y, z]`` position in pixels.
        anchor: ``[x, y, z]`` anchor point in pixels.
        scale_pct: ``[sx, sy, sz]`` scale as percentages (100 = 1x).
        rotation_z: Z-axis rotation in degrees.
        orientation: ``[ox, oy, oz]`` orientation angles in degrees
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

def build_world_matrix(layer: Layer) -> Mat4:
    """Build the world transform matrix by composing the parent chain.

    Traverses `layer.parent` upward, composing local matrices so that::

        world = root_local @ ... @ parent_local @ layer_local
    """
    chain = []
    current: Layer | None = layer
    while current is not None:
        chain.append(current)
        current = current.parent

    # Compose from root (last in chain) down to the layer itself.
    m = Mat4.identity()
    for lyr in reversed(chain):
        m @= _layer_local_matrix(lyr)
    return m


def _layer_local_matrix(layer: Layer) -> Mat4:
    """Build the local matrix for a single layer from its properties."""
    transform = layer.transform
    position = transform["ADBE Position"].value
    anchor = transform["ADBE Anchor Point"].value
    scale_pct = transform["ADBE Scale"].value
    rz = transform["ADBE Rotate Z"].value
    orientation = transform["ADBE Orientation"].value
    rx = transform["ADBE Rotate X"].value
    ry = transform["ADBE Rotate Y"].value

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
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


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

    Given a matrix ``M`` and a fixed anchor point, extracts the
    Position, Scale, and Rotation values that would produce ``M``
    via `build_local_matrix`.

    Orientation is assumed to be ``[0, 0, 0]`` - i.e. any orientation
    contribution must already be factored out before calling this.

    Args:
        matrix: The 4x4 transform matrix to decompose.
        anchor: ``[ax, ay, az]`` anchor point (held constant).

    Returns:
        A tuple of ``(position, scale_pct, rotation_z, rotate_x,
        rotate_y)`` where *scale_pct* is in percentage units (100 = 1x).
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

    # Extract intrinsic X-Y-Z Euler angles from R = Rx(a) * Ry(b) * Rz(g).
    #
    # R = | cb*cg       -cb*sg        sb    |
    #     | sa*sb*cg+ca*sg  -sa*sb*sg+ca*cg  -sa*cb |
    #     | -ca*sb*cg+sa*sg  ca*sb*sg+sa*cg   ca*cb |
    ry_deg: float
    rx_deg: float
    rz_deg: float

    sin_beta = r02
    # Clamp to [-1, 1] for asin safety.
    sin_beta = max(-1.0, min(1.0, sin_beta))
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

    scale_pct = [sx * 100.0, sy * 100.0, sz * 100.0]
    return pos, scale_pct, rz_deg, rx_deg, ry_deg
