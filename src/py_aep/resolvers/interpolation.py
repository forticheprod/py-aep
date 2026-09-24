"""Interpolation utilities for keyframe-based property evaluation.

Implements HOLD, LINEAR, and BEZIER interpolation for
`Property.value_at_time()`.  Pure Python with no external dependencies.

The temporal structure follows `lottie-web <https://github.com/airbnb/
lottie-web>`_, the industry-standard renderer for Lottie/bodymovin
animations exported from After Effects, with the numerics adjusted to
match AE's own output:

- **Temporal ease** uses a normalised [0, 1] -> [0, 1] cubic-bezier
  easing function (`BezierEasing`), whose curve parameter is solved in
  closed form (Cardano).
- **Spatial paths** follow AE's own arc-length model instead: an ease curve
  in (seconds, distance) space gives the distance travelled, and a spline
  fitted to the segment's sampled arc length turns it into the curve
  parameter (see `_ArcSpline`).
"""

from __future__ import annotations

import functools
import math
from collections import deque
from typing import TYPE_CHECKING, NamedTuple, Tuple, cast

from py_aep.enums import KeyframeInterpolationType
from py_aep.models.properties.parallel import ORIENTATION_KIND, SHAPE_KIND
from py_aep.models.properties.shape import Shape
from py_aep.resolvers.transform import _euler_xyz

if TYPE_CHECKING:
    from ..models.properties.keyframe import Keyframe
    from ..models.properties.keyframe_ease import KeyframeEase
    from ..models.properties.parallel import ParallelKind

_DEFAULT_INFLUENCE = 100.0 / 6.0  # 16.6667 %


# ---------------------------------------------------------------------------
# BezierEasing
# ---------------------------------------------------------------------------
# A cached unit-square bezier easing function: given control points
# (cx1, cy1, cx2, cy2), maps x in [0,1] -> y in [0,1].
#
# The curve parameter is solved in CLOSED FORM, the way After Effects does it:
# the segment is rewritten in power basis and `a t^3 + b t^2 + c t + d = 0` is
# handed to a Cardano solver (the Numerical Recipes form, with
# Q = (A^2 - 3B)/9 and R = (2A^3 - 9AB + 27C)/54), after snapping to either
# endpoint within `_EPS`. This replaces an earlier sample-table + Newton port,
# which agreed with AE only to ~1e-5 in the parameter.

_EPS = 1e-10

# AE saturates a vertical slope instead of dividing by a near-zero dx: inside
# this window it reports +/- this value.
_VERTICAL_SLOPE_EPS = 1e-12
_VERTICAL_SLOPE = 1e10


def _bez_A(a1: float, a2: float) -> float:
    return 1.0 - 3.0 * a2 + 3.0 * a1


def _bez_B(a1: float, a2: float) -> float:
    return 3.0 * a2 - 6.0 * a1


def _bez_C(a1: float) -> float:
    return 3.0 * a1


def _calc_bezier(t: float, a1: float, a2: float) -> float:
    """Calculate bezier value at t for one axis (x or y)."""
    return ((_bez_A(a1, a2) * t + _bez_B(a1, a2)) * t + _bez_C(a1)) * t


def _solve_cubic(a: float, b: float, c: float, d: float) -> float | None:
    """The root of `a t^3 + b t^2 + c t + d` in [0, 1] that AE picks.

    Closed-form Cardano. The root preference order and its asymmetric
    bounds - the first root must be strictly inside [0, 1], the second may
    sit on either end - are AE's, and only tell the two apart on a
    non-monotonic curve.

    Returns `None` when no root lands in [0, 1]. AE's result is undefined
    there; that is a bug, not behaviour to copy.
    """
    if abs(a) >= _EPS:
        big_a = b / a
        q = (big_a * big_a - 3.0 * (c / a)) / 9.0
        r = (
            2.0 * big_a * big_a * big_a - 9.0 * big_a * (c / a) + 27.0 * (d / a)
        ) / 54.0
        third = big_a / 3.0
        q3 = q * q * q
        if q3 < r * r:
            # One real root. `sq +/- r` is strictly positive here, since
            # `q3 < r * r` rules out both terms vanishing together.
            sq = math.sqrt(r * r - q3)
            if r < 0.0:
                x = math.pow(sq - r, 1.0 / 3.0)
                return (q / x + x) - third
            x = math.pow(sq + r, 1.0 / 3.0)
            return (-x - q / x) - third
        if abs(q) < _EPS:
            return -third
        # Three real roots.
        theta = math.acos(r / math.sqrt(q3))
        scale = -2.0 * math.sqrt(q)
        first = math.cos(theta / 3.0) * scale - third
        if 0.0 < first < 1.0:
            return first
        second = math.cos((theta + 2.0 * math.pi) / 3.0) * scale - third
        if 0.0 <= second <= 1.0:
            return second
        root = math.cos((theta + 4.0 * math.pi) / 3.0) * scale - third
    else:
        # Degenerates to a quadratic (or a line).
        if abs(b) < _EPS:
            return -d / c if abs(c) >= _EPS else 0.0
        disc = c * c - 4.0 * b * d
        if disc < 0.0:
            return None
        if abs(disc) < _EPS:
            return -c / (2.0 * b)
        sq = math.sqrt(disc)
        # AE's numerically stable form: both branches yield 2d/q and q/2b.
        q_quad = (sq - c) if c <= 0.0 else -(sq + c)
        first = (2.0 * d) / q_quad
        root = q_quad / (2.0 * b)
        if 0.0 <= first <= 1.0:
            return first
    return root if 0.0 <= root <= 1.0 else None


class _BezierEasing:
    """Cached unit-square bezier easing function."""

    __slots__ = ("_cx1", "_cy1", "_cx2", "_cy2")

    def __init__(self, cx1: float, cy1: float, cx2: float, cy2: float) -> None:
        self._cx1 = cx1
        self._cy1 = cy1
        self._cx2 = cx2
        self._cy2 = cy2

    def get(self, x: float) -> float:
        """Map x in [0,1] to eased y in [0,1]."""
        # The curve is the identity when both handles sit on the diagonal.
        if self._cx1 == self._cy1 and self._cx2 == self._cy2:
            return x
        return _calc_bezier(self.parameter_at(x), self._cy1, self._cy2)

    def parameter_at(self, x: float) -> float:
        """The curve parameter `u` whose x-coordinate is `x`.

        Callers that place their control points in absolute value space
        (rather than the normalized 0-1 y used by `get`) need the parameter
        itself: only the TIME axis is normalized there.

        As in AE, an `x` within `_EPS` of either end snaps to that end
        before any solving happens.
        """
        if x < 0.0 or abs(x) < _EPS:
            return 0.0
        if x > 1.0 or abs(x - 1.0) < _EPS:
            return 1.0
        u = _solve_cubic(
            _bez_A(self._cx1, self._cx2),
            _bez_B(self._cx1, self._cx2),
            _bez_C(self._cx1),
            -x,
        )
        # No root in [0, 1] means the curve does not reach `x`, which only
        # happens on a degenerate one. Fall back to the linear estimate
        # rather than to AE's undefined result.
        return x if u is None else u


# Cache for easing functions (mirroring lottie-web's BezierFactory cache)
_easing_cache: dict[tuple[float, float, float, float], _BezierEasing] = {}


def _get_bezier_easing(cx1: float, cy1: float, cx2: float, cy2: float) -> _BezierEasing:
    """Get or create a cached BezierEasing instance."""
    key = (cx1, cy1, cx2, cy2)
    cached = _easing_cache.get(key)
    if cached is not None:
        return cached
    easing = _BezierEasing(cx1, cy1, cx2, cy2)
    _easing_cache[key] = easing
    return easing


# ---------------------------------------------------------------------------
# Speed/influence -> bezier control points conversion
# ---------------------------------------------------------------------------
# AEP stores temporal ease as (speed, influence) pairs.
# Lottie JSON stores temporal ease as bezier control points (o.x, o.y, i.x, i.y)
# in a normalized [0,1] coordinate space.
#
# The bodymovin exporter converts from AEP to Lottie format as follows:
#   outgoing: cx1 = out_influence / 100, cy1 = out_speed_normalized
#   incoming: cx2 = 1 - in_influence / 100, cy2 = 1 - in_speed_normalized
#
# Where speed_normalized = speed * influence_fraction * dt / (v1 - v0)
# For spatial properties, speed is in position-units/sec.


def _ease_to_bezier_1d(
    t0: float,
    t1: float,
    v0: float,
    v1: float,
    out_ease: KeyframeEase,
    in_ease: KeyframeEase,
) -> tuple[float, float, float, float]:
    """Convert AEP speed/influence ease to normalized bezier control points.

    Returns (cx1, cy1, cx2, cy2) for use with BezierEasing.
    """
    dt = t1 - t0
    dv = v1 - v0

    o_spd, o_inf = out_ease.speed, out_ease.influence
    i_spd, i_inf = in_ease.speed, in_ease.influence

    # Normalized influence (x-axis control points)
    cx1 = o_inf / 100.0
    cx2 = 1.0 - i_inf / 100.0

    # Normalized speed (y-axis control points)
    # cy1 = outgoing speed * influence_fraction * dt / dv
    # cy2 = 1 - incoming speed * influence_fraction * dt / dv
    if abs(dv) > 1e-12:
        cy1 = o_spd * cx1 * dt / dv
        cy2 = 1.0 - i_spd * (1.0 - cx2) * dt / dv
    else:
        # No value change: linear
        cy1 = cx1
        cy2 = cx2

    return cx1, cy1, cx2, cy2


def _ease_value_handles(
    t0: float,
    t1: float,
    v0: float,
    v1: float,
    out_ease: KeyframeEase,
    in_ease: KeyframeEase,
) -> tuple[float, float]:
    """The two value-space control points of a temporal bezier segment.

    After Effects places the ease handles absolutely - `v0 + speed_out * io
    * dt` and `v1 - speed_in * ii * dt`, with `io`/`ii` the influence
    fractions - not as a fraction of `v1 - v0`. The two formulations agree
    whenever the keys differ in value, and only the absolute one keeps the
    curve bowing when they do not (issue #225: a 1-D BEZIER segment whose
    keys both hold 50 peaks at 99.5 in AE, not 50).
    """
    dt = t1 - t0
    io = out_ease.influence / 100.0
    ii = in_ease.influence / 100.0
    return (
        v0 + out_ease.speed * io * dt,
        v1 - in_ease.speed * ii * dt,
    )


def segment_value_slope(
    t0: float,
    t1: float,
    v0: float,
    v1: float,
    out_ease: KeyframeEase,
    in_ease: KeyframeEase,
    t: float,
) -> float:
    """`dv/dt` on the temporal bezier segment at time `t`.

    The instantaneous speed a keyframe inserted at `t` has to carry for the
    curve to come through unchanged.
    """
    dt = t1 - t0
    if dt <= 0:
        return 0.0
    cx1, _cy1, cx2, _cy2 = _ease_to_bezier_1d(t0, t1, v0, v1, out_ease, in_ease)
    easing = _get_bezier_easing(cx1, _cy1, cx2, _cy2)
    u = easing.parameter_at((t - t0) / dt)
    y1, y2 = _ease_value_handles(t0, t1, v0, v1, out_ease, in_ease)
    mu = 1.0 - u
    dy_du = 3.0 * (mu * mu * (y1 - v0) + 2.0 * mu * u * (y2 - y1) + u * u * (v1 - y2))
    dx_du = 3.0 * (mu * mu * cx1 + 2.0 * mu * u * (cx2 - cx1) + u * u * (1.0 - cx2))
    if abs(dx_du) < _VERTICAL_SLOPE_EPS:
        # The curve is vertical here, so the speed is unbounded. AE reports
        # its saturation value rather than dividing, inside the same 1e-12
        # window; the sign follows the value axis. This is reachable at
        # 100 % influence on both sides, where dx/du is exactly 0 at the
        # midpoint.
        return _VERTICAL_SLOPE if dy_du >= 0.0 else -_VERTICAL_SLOPE
    return dy_du / (dx_du * dt)


def split_segment_influences(
    t0: float,
    t1: float,
    v0: float,
    v1: float,
    out_ease: KeyframeEase,
    in_ease: KeyframeEase,
    t: float,
) -> tuple[float, float, float, float]:
    """Influences after splitting a BEZIER segment at `t`, as percentages.

    De Casteljau subdivision of the segment's time handles, which is what
    keeps the curve identical. Returns
    `(left_out, new_in, new_out, right_in)`; measured on AE 2026, splitting
    a 5 s 0->100 segment eased 0/75 on both sides at 2.5 s gives
    `(75, 12.5, 12.5, 75)`.
    """
    dt = t1 - t0
    if dt <= 0:
        return (
            out_ease.influence,
            _DEFAULT_INFLUENCE,
            _DEFAULT_INFLUENCE,
            in_ease.influence,
        )
    cx1, cy1, cx2, cy2 = _ease_to_bezier_1d(t0, t1, v0, v1, out_ease, in_ease)
    easing = _get_bezier_easing(cx1, cy1, cx2, cy2)
    u = easing.parameter_at((t - t0) / dt)

    def lerp(a: float, b: float) -> float:
        return a + (b - a) * u

    a = lerp(0.0, cx1)
    b = lerp(cx1, cx2)
    c = lerp(cx2, 1.0)
    d = lerp(a, b)
    e = lerp(b, c)
    xs = lerp(d, e)

    left_span = xs
    right_span = 1.0 - xs
    if left_span <= 1e-12 or right_span <= 1e-12:
        return (
            out_ease.influence,
            _DEFAULT_INFLUENCE,
            _DEFAULT_INFLUENCE,
            in_ease.influence,
        )
    # An influence is a percentage of its own sub-span, and a long handle on
    # a short half can exceed 100 - which AE cannot represent either. Clamp
    # to the storable range; the curve then bends by whatever the clamp cost.
    return (
        _clamp_influence(a / left_span * 100.0),
        _clamp_influence((xs - d) / left_span * 100.0),
        _clamp_influence((e - xs) / right_span * 100.0),
        _clamp_influence((1.0 - c) / right_span * 100.0),
    )


def _clamp_influence(value: float) -> float:
    """Keep an influence inside the 0.1-100 % range AE stores."""
    return min(max(value, 0.1), 100.0)


# ---------------------------------------------------------------------------
# Spatial motion path - arc length
# ---------------------------------------------------------------------------
# A spatial property travels along its motion path at the pace its temporal
# ease sets, so evaluating one means finding the curve parameter at a given
# DISTANCE along the path. AE does not integrate the arc length. It samples
# each segment `_ARC_SAMPLES` times, uniformly in the curve parameter, sums
# the straight chords between the samples, fits a bezier spline through the
# (parameter * length, distance) samples with Schneider's algorithm (P. J.
# Schneider, "An Algorithm for Automatically Fitting Digitized Curves",
# Graphics Gems, 1990) and inverts THAT spline. The fit tolerance is the
# property's own stored arc accuracy, so a position read back differs from
# the exact curve by up to ~0.01 px - even on a straight segment, whose
# parameter still eases in and out (AE 2026: a LINEAR 100 px segment over
# 5 s reports 26.6774826 at 1.333 s, where the line gives 26.6667).
#
# The fit has to be reproduced exactly, arithmetic order included. A
# straight segment's samples are symmetric, so the fitter's split points are
# near-ties that rounding decides, and a different split moves the result by
# up to 6e-3 px: AE itself reports (0,0)->(100,100) and (20,0)->(120,100)
# that far apart. As written, this reproduces both - and every sampled frame
# of the value_at_time fixtures - to 1e-12, so keep the products and sums in
# the order they are in.

_ARC_SAMPLES = 128
# The `tdb4` arc accuracy of a property stored in pixels. A normalized point
# (effect point, a footage layer's Anchor Point) stores a far smaller one.
_DEFAULT_ARC_ACCURACY = 1e-4
# The fit's handle length for a two-sample run: a decimal literal, 6 ulps
# short of 1/3.
_FIT_THIRD = 0.333333333333333
# A LINEAR side's handle on the distance curve, as a fraction of the span on
# both axes. Also a decimal literal: it is 2e-11 off 1/6.
_LINEAR_HANDLE = 0.16666666667

# Four control points of an N-dimensional cubic; tuples so a curve can key
# the spline cache.
_Curve = Tuple[Tuple[float, ...], ...]
_Point2 = Tuple[float, float]


class ArcMetric(NamedTuple):
    """How AE measures one spatial property's motion path.

    AE measures a path in the property's STORED units, each dimension scaled
    by a per-property multiplier, and fits its arc spline to a per-property
    accuracy; both live in the property's `tdb4`. A layer's Position scales
    X by the composition's pixel aspect, so it measures in square pixels. A
    normalized point (stored as a fraction of the layer) scales X by the
    layer's width / height, so both axes measure in layer heights.
    """

    accuracy: float = _DEFAULT_ARC_ACCURACY
    # Per-dimension scale on a stored value before it is measured.
    multipliers: tuple[float, ...] = (1.0, 1.0, 1.0)
    # Reported / stored ratio per dimension, for a normalized point.
    divisors: tuple[float, ...] | None = None
    # Reported / stored ratio of a temporal ease speed.
    speed_divisor: float = 1.0


_DEFAULT_ARC_METRIC = ArcMetric()


def _cubic_1d(a: float, b: float, c: float, d: float, t: float) -> float:
    """One coordinate of a cubic bezier, evaluated the way AE evaluates it."""
    mt = 1.0 - t
    t2 = t * t
    return ((3.0 * b * t + mt * a) * mt + 3.0 * c * t2) * mt + t2 * t * d


def _cubic_point(curve: _Curve, t: float) -> list[float]:
    p0, p1, p2, p3 = curve
    return [_cubic_1d(p0[d], p1[d], p2[d], p3[d], t) for d in range(len(p0))]


def _spatial_curve(
    v0: list[float],
    v1: list[float],
    out_tangent: list[float],
    in_tangent: list[float],
) -> _Curve:
    """A spatial segment's control points, in reported units."""
    ndim = len(v0)
    return (
        tuple(v0),
        tuple(v0[d] + out_tangent[d] for d in range(ndim)),
        tuple(v1[d] + in_tangent[d] for d in range(ndim)),
        tuple(v1),
    )


def _measured(values: list[float], metric: ArcMetric) -> list[float]:
    """A reported vector in the space AE measures arc length in."""
    divisors = metric.divisors
    result = []
    for d, value in enumerate(values):
        if divisors is not None and d < len(divisors) and divisors[d]:
            value = value / divisors[d]
        result.append(metric.multipliers[d] * value)
    return result


def _measured_curve(
    v0: list[float],
    v1: list[float],
    out_tangent: list[float],
    in_tangent: list[float],
    metric: ArcMetric,
) -> _Curve:
    p0 = _measured(v0, metric)
    p3 = _measured(v1, metric)
    out_m = _measured(out_tangent, metric)
    in_m = _measured(in_tangent, metric)
    return (
        tuple(p0),
        tuple(out_m[d] + p0[d] for d in range(len(p0))),
        tuple(in_m[d] + p3[d] for d in range(len(p3))),
        tuple(p3),
    )


def _arc_samples(curve: _Curve) -> tuple[list[_Point2], float]:
    """`(parameter, distance)` samples along `curve`, and its length."""
    p0 = curve[0]
    step = 1.0 / (_ARC_SAMPLES - 1)
    samples = [(0.0, 0.0)]
    previous: tuple[float, ...] | list[float] = p0
    total = 0.0
    t = step
    for _ in range(1, _ARC_SAMPLES):
        point = _cubic_point(curve, t)
        squared = 0.0
        for d in range(len(point)):
            delta = point[d] - previous[d]
            squared = squared + delta * delta
        total = math.sqrt(squared) + total
        samples.append((t, total))
        previous = point
        # Accumulated, not `i * step`: the samples' low bits steer the fit.
        t = t + step
    return samples, total


def _unit(x: float, y: float) -> _Point2:
    length = math.sqrt(x * x + y * y)
    if length == 0.0:
        return (x, y)
    inverse = 1.0 / length
    return (inverse * x, inverse * y)


def _fit_point(curve: list[_Point2], u: float) -> _Point2:
    p0, p1, p2, p3 = curve
    return (
        _cubic_1d(p0[0], p1[0], p2[0], p3[0], u),
        _cubic_1d(p0[1], p1[1], p2[1], p3[1], u),
    )


def _chord_parameters(points: list[_Point2], first: int, last: int) -> list[float]:
    """Schneider's chord-length parameterization of `points[first:last+1]`."""
    u = [0.0]
    for i in range(first + 1, last + 1):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        u.append(math.sqrt(dy * dy + dx * dx) + u[-1])
    inverse = 1.0 / u[-1] if u[-1] != 0.0 else 0.0
    return [inverse * value for value in u]


def _fit_bezier(
    points: list[_Point2],
    first: int,
    last: int,
    u: list[float],
    tangent_1: _Point2,
    tangent_2: _Point2,
) -> list[_Point2]:
    """Schneider's least-squares cubic through `points[first:last+1]`.

    Two departures from the published code, both AE's: a near-singular
    system is regularized against 1e-4 rather than tested for exactly 0,
    and only a NEGATIVE handle length falls back to the Wu/Barsky heuristic.
    """
    p0 = points[first]
    p3 = points[last]
    c00 = c01 = c11 = x0 = x1 = 0.0
    for i, ui in enumerate(u):
        mu = 1.0 - ui
        u3 = ui * 3.0
        b1 = mu * mu * u3
        b2 = u3 * ui * mu
        a0x = tangent_1[0] * b1
        a0y = b1 * tangent_1[1]
        a1x = b2 * tangent_2[0]
        a1y = b2 * tangent_2[1]
        c00 += a0x * a0x + a0y * a0y
        c01 += a0x * a1x + a0y * a1y
        c11 += a1x * a1x + a1y * a1y
        b0 = mu * mu * mu
        b3 = ui * ui * ui
        point = points[first + i]
        tx = point[0] - (b1 * p0[0] + b0 * p0[0] + b2 * p3[0] + b3 * p3[0])
        ty = point[1] - (b1 * p0[1] + b0 * p0[1] + b2 * p3[1] + b3 * p3[1])
        x0 += a0x * tx + a0y * ty
        x1 += a1x * tx + ty * a1y
    det = c11 * c00 - c01 * c01
    if det < 1e-4:
        if det > -1e-4:
            det = c11 * c00 * 10.0 * 1e-4
        if det < 1e-4 and det > -1e-4:
            det = 1e-3
    alpha_l = (x0 * c11 - x1 * c01) / det
    alpha_r = (x1 * c00 - x0 * c01) / det
    if alpha_l < 0.0 or alpha_r < 0.0:
        dx = p3[0] - p0[0]
        dy = p3[1] - p0[1]
        alpha_l = alpha_r = math.sqrt(dx * dx + dy * dy) * _FIT_THIRD
    return [
        p0,
        (alpha_l * tangent_1[0] + p0[0], alpha_l * tangent_1[1] + p0[1]),
        (alpha_r * tangent_2[0] + p3[0], alpha_r * tangent_2[1] + p3[1]),
        p3,
    ]


def _fit_error(
    points: list[_Point2],
    first: int,
    last: int,
    curve: list[_Point2],
    u: list[float],
) -> tuple[float, int]:
    """The worst squared distance from `curve`, and where it is.

    A tie goes to the LATER sample, which is what decides the split on a
    symmetric run.
    """
    worst = 0.0
    split = (first + last + 1) // 2
    for i in range(first + 1, last):
        q = _fit_point(curve, u[i - first])
        dx = q[0] - points[i][0]
        dy = q[1] - points[i][1]
        squared = dy * dy + dx * dx
        if squared >= worst:
            worst = squared
            split = i
    return worst, split


def _fit_cubics(
    points: list[_Point2],
    first: int,
    last: int,
    tangent_1: _Point2,
    tangent_2: _Point2,
    error: float,
    knots: list[_Point2],
) -> None:
    """Fit `points[first:last+1]`, appending the cubics' control points.

    Schneider's fitter tries a few Newton reparameterizations before
    splitting, but only while the error is under the tolerance SQUARED. For
    every tolerance below 1 - all AE writes - that bound lies under the
    tolerance itself, so the fit always splits.
    """
    if last - first == 1:
        start = points[first]
        end = points[last]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        reach = math.sqrt(dx * dx + dy * dy) * _FIT_THIRD
        curve = [
            start,
            (reach * tangent_1[0] + start[0], reach * tangent_1[1] + start[1]),
            (reach * tangent_2[0] + end[0], reach * tangent_2[1] + end[1]),
            end,
        ]
    else:
        u = _chord_parameters(points, first, last)
        curve = _fit_bezier(points, first, last, u, tangent_1, tangent_2)
        worst, split = _fit_error(points, first, last, curve, u)
        if worst >= error:
            before, at, after = points[split - 1], points[split], points[split + 1]
            center = _unit(
                (before[0] - at[0] + (at[0] - after[0])) * 0.5,
                (before[1] - at[1] + (at[1] - after[1])) * 0.5,
            )
            _fit_cubics(points, first, split, tangent_1, center, error, knots)
            _fit_cubics(
                points, split, last, (-center[0], -center[1]), tangent_2, error, knots
            )
            return
    if not knots:
        knots.append(curve[0])
    knots.extend(curve[1:])


def _t_on_axis(curve: list[_Point2], axis: int, value: float) -> float:
    """The parameter at which `curve`'s `axis` coordinate reaches `value`.

    Snaps to either end within `_EPS`, and clamps outside them.
    """
    v0 = curve[0][axis]
    if v0 > value or abs(value - v0) < _EPS:
        return 0.0
    v3 = curve[3][axis]
    if value > v3 or abs(value - v3) < _EPS:
        return 1.0
    v1 = curve[1][axis]
    v2 = curve[2][axis]
    t = _solve_cubic(
        ((v1 - v2) * 3.0 - v0) + v3,
        ((v0 - (v1 + v1)) + v2) * 3.0,
        (v1 - v0) * 3.0,
        v0 - value,
    )
    # No root in [0, 1] only happens on a degenerate curve; AE's result is
    # undefined there, so take the linear estimate instead.
    return (value - v0) / (v3 - v0) if t is None else t


def _non_decreasing(curve: list[_Point2]) -> list[_Point2]:
    """Pull an overshooting handle back to the curve's range on the y axis.

    The handle is shortened along its own slope, not just clamped.
    """
    p0, p1, p2, p3 = curve
    if p3[1] < p1[1]:
        p1 = ((p3[1] - p0[1]) / (p1[1] - p0[1]) * (p1[0] - p0[0]) + p0[0], p3[1])
    if p2[1] < p0[1]:
        p2 = ((p3[1] - p0[1]) / (p3[1] - p2[1]) * (p2[0] - p3[0]) + p3[0], p0[1])
    return [p0, p1, p2, p3]


def _is_non_decreasing(curve: list[_Point2]) -> bool:
    y0, y1, y2, y3 = (point[1] for point in curve)
    return not (
        (y1 < y0 and abs(y1 - y0) >= _EPS)
        or (y3 < y1 and abs(y1 - y3) >= _EPS)
        or (y2 < y0 and abs(y2 - y0) >= _EPS)
        or (y3 < y2 and abs(y2 - y3) >= _EPS)
    )


class _ArcSpline:
    """AE's arc-length model of one spatial segment.

    Built from the segment's control points in measured units.
    """

    __slots__ = ("length", "_knots")

    def __init__(self, curve: _Curve, accuracy: float) -> None:
        samples, self.length = _arc_samples(curve)
        points = [(self.length * t, s) for t, s in samples]
        last = len(points) - 1
        knots: list[_Point2] = []
        _fit_cubics(
            points,
            0,
            last,
            _unit(points[1][0] - points[0][0], points[1][1] - points[0][1]),
            _unit(
                points[last - 1][0] - points[last][0],
                points[last - 1][1] - points[last][1],
            ),
            accuracy,
            knots,
        )
        inverse = 1.0 / self.length if self.length != 0.0 else 0.0
        self._knots = [(inverse * x, y) for x, y in knots[:-1]]
        self._knots.append((1.0, knots[-1][1]))

    def parameter_at(self, distance: float) -> float:
        """The curve parameter `distance` along the segment."""
        knots = self._knots
        total = knots[-1][1]
        if distance < 0.0 or abs(distance) < _EPS:
            return 0.0
        if distance > total or abs(distance - total) < _EPS:
            return 1.0
        end = 3
        while end < len(knots):
            if abs(distance - knots[end][1]) < _EPS:
                return knots[end][0]
            if distance < knots[end][1]:
                break
            end += 3
        cubic = knots[end - 3 : end + 1]
        if not _is_non_decreasing(cubic):
            cubic = _non_decreasing(cubic)
        t = _t_on_axis(cubic, 1, distance)
        return _cubic_1d(cubic[0][0], cubic[1][0], cubic[2][0], cubic[3][0], t)


@functools.lru_cache(maxsize=1024)
def _arc_spline(curve: _Curve, accuracy: float) -> _ArcSpline:
    """A cached `_ArcSpline`: every evaluated frame rebuilds the same one."""
    return _ArcSpline(curve, accuracy)


def motion_path_length(
    v0: list[float],
    v1: list[float],
    out_tangent: list[float],
    in_tangent: list[float],
    metric: ArcMetric,
) -> float:
    """A spatial segment's arc length, in the units its ease speeds report."""
    curve = _measured_curve(v0, v1, out_tangent, in_tangent, metric)
    return _arc_spline(curve, metric.accuracy).length * metric.speed_divisor


def _distance_curve(
    duration: float,
    distance: float,
    out_ease: KeyframeEase,
    in_ease: KeyframeEase,
    out_type: KeyframeInterpolationType,
    in_type: KeyframeInterpolationType,
    speed_divisor: float,
) -> list[_Point2]:
    """The ease curve of a spatial span, in (seconds, distance).

    Absolute units, not a unit square: an eased side's handle reaches
    `influence * duration` along time at its stored speed, and a LINEAR
    side's sits `_LINEAR_HANDLE` along the chord whatever its stored ease.
    An overshooting handle is pulled back so the distance never reverses.
    """
    if out_type == KeyframeInterpolationType.LINEAR:
        out_handle = (duration * _LINEAR_HANDLE, distance * _LINEAR_HANDLE)
    else:
        reach = duration * (out_ease.influence / 100.0)
        out_handle = (reach, reach * (out_ease.speed / speed_divisor))
    if in_type == KeyframeInterpolationType.LINEAR:
        in_handle = (
            duration - duration * _LINEAR_HANDLE,
            distance - distance * _LINEAR_HANDLE,
        )
    else:
        reach = -(in_ease.influence / 100.0) * duration
        in_handle = (
            reach + duration,
            reach * (in_ease.speed / speed_divisor) + distance,
        )
    return _non_decreasing([(0.0, 0.0), out_handle, in_handle, (duration, distance)])


def _spatial_distance(
    elapsed: float,
    duration: float,
    distance: float,
    kf_start: Keyframe,
    kf_end: Keyframe,
    speed_divisor: float,
) -> float:
    """Distance travelled `elapsed` seconds into a spatial span.

    The span runs from `kf_start` to `kf_end`, a single segment or a whole
    roving run. HOLD on either side keeps it at the start.
    """
    out_type = kf_start.out_interpolation_type
    in_type = kf_end.in_interpolation_type
    if KeyframeInterpolationType.HOLD in (out_type, in_type):
        return 0.0
    if (
        out_type == KeyframeInterpolationType.LINEAR
        and in_type == KeyframeInterpolationType.LINEAR
    ):
        return elapsed / duration * distance
    curve = _distance_curve(
        duration,
        distance,
        kf_start.out_temporal_ease[0],
        kf_end.in_temporal_ease[0],
        out_type,
        in_type,
        speed_divisor,
    )
    y0, y1, y2, y3 = (point[1] for point in curve)
    if y0 == y1 == y2 == y3:
        return y0
    t = _t_on_axis(curve, 0, elapsed)
    return _cubic_1d(y0, y1, y2, y3, t)


def split_spatial_path(
    v0: list[float],
    v1: list[float],
    out_tangent: list[float],
    in_tangent: list[float],
    u: float,
) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    """De Casteljau split of a spatial segment at parameter `u`.

    Returns `(left_out, new_in, split_point, new_out, right_in)` - the four
    tangents the two halves need, plus the point they meet at. Splitting the
    path is what lets a keyframe be inserted without moving the motion path.
    """
    ndim = len(v0)
    p0 = list(v0)
    p1 = [v0[d] + out_tangent[d] for d in range(ndim)]
    p2 = [v1[d] + in_tangent[d] for d in range(ndim)]
    p3 = list(v1)

    def lerp(a: list[float], b: list[float]) -> list[float]:
        return [a[d] + (b[d] - a[d]) * u for d in range(ndim)]

    a = lerp(p0, p1)
    b = lerp(p1, p2)
    c = lerp(p2, p3)
    d = lerp(a, b)
    e = lerp(b, c)
    split = lerp(d, e)
    return (
        [a[i] - p0[i] for i in range(ndim)],
        [d[i] - split[i] for i in range(ndim)],
        split,
        [e[i] - split[i] for i in range(ndim)],
        [c[i] - p3[i] for i in range(ndim)],
    )


def _tangents_are_zero(tangent: list[float] | None) -> bool:
    if tangent is None:
        return True
    return all(abs(x) < 1e-12 for x in tangent)


# ---------------------------------------------------------------------------
# Auto-bezier computation (same as original - needed for AEP binary data)
# ---------------------------------------------------------------------------


_AUTO_BEZIER_CHORD_SCALE = 1.0 / 6.0


def auto_spatial_tangents(
    values: list[list[float]], index: int
) -> tuple[list[float], list[float]]:
    """AE's auto-bezier spatial tangents for `values[index]`.

    The tangent is one sixth of the chord between the keyframe's two
    neighbours, applied symmetrically: `in = -out`. An endpoint uses the
    chord to its single neighbour, and still gets both tangents. A lone
    keyframe gets zeros.

    Measured on AE 2018 (a five-key diamond, every tangent matching) and on
    AE 2026 with deliberately uneven time spacing, which rules out the
    time-weighted variant this used to implement - that agrees with AE only
    when the neighbours are equidistant in time.

    The result is expressed in whatever space `values` are in, so callers
    working in raw chunk units and callers working in resolved units both
    get a self-consistent answer.

    Returns:
        An `(out_tangent, in_tangent)` pair.
    """
    ndim = len(values[index])
    zero = [0.0] * ndim
    if len(values) < 2:
        return zero, list(zero)
    low = values[index - 1] if index > 0 else values[index]
    high = values[index + 1] if index < len(values) - 1 else values[index]
    out_tangent = [(high[d] - low[d]) * _AUTO_BEZIER_CHORD_SCALE for d in range(ndim)]
    return out_tangent, [-component for component in out_tangent]


def auto_temporal_speeds(
    values: list[list[float]], times: list[float], index: int
) -> tuple[list[float], list[float]]:
    """AE's auto-bezier temporal speeds for `values[index]`, per dimension.

    An interior keyframe takes the through-slope across its neighbours on
    both sides. An endpoint takes the slope of its single segment on the
    inward side and zero on the outward side. Influence is always
    `_DEFAULT_INFLUENCE`.

    Multi-dimensional properties get a per-dimension slope (measured on AE
    2026: 2-D Scale 100->200->400 / 100->120->150 yields speeds 150 and 25).

    Returns:
        An `(in_speeds, out_speeds)` pair, one entry per dimension.
    """
    ndim = len(values[index])
    zero = [0.0] * ndim
    count = len(values)
    if count < 2:
        return list(zero), list(zero)

    def slope(lo: int, hi: int) -> list[float]:
        span = times[hi] - times[lo]
        if span <= 0:
            return [0.0] * ndim
        return [(values[hi][d] - values[lo][d]) / span for d in range(ndim)]

    if index == 0:
        return list(zero), slope(0, 1)
    if index == count - 1:
        return slope(count - 2, count - 1), list(zero)
    through = slope(index - 1, index + 1)
    return through, list(through)


def _spatial_progress_easing(
    dt: float,
    arc_length: float,
    out_ease: KeyframeEase | None,
    in_ease: KeyframeEase | None,
    *,
    out_linear: bool = False,
    in_linear: bool = False,
) -> _BezierEasing | None:
    """Ease curve mapping a time fraction to an arc-length fraction.

    A spatial ease carries a speed in units per second, which becomes
    progress per second once divided by the path's own arc length - one
    divisor for the whole segment. `None` means "no explicit ease", i.e.
    constant progress.
    """
    if out_ease is None or in_ease is None:
        return None
    if out_ease.influence <= 0 and in_ease.influence <= 0:
        return None

    out_inf_frac = out_ease.influence / 100.0
    in_inf_frac = in_ease.influence / 100.0
    ds_dt = 1.0 / arc_length if arc_length > 1e-12 else 0.0

    cx1 = out_inf_frac
    cy1 = out_ease.speed * ds_dt * out_inf_frac * dt
    cx2 = 1.0 - in_inf_frac
    cy2 = 1.0 - in_ease.speed * ds_dt * in_inf_frac * dt

    # A LINEAR side carries no ease: its handle sits on the diagonal, so
    # progress advances at a constant rate on that side. The side's
    # interpolation type governs the EASE only - the path itself always
    # follows the spatial tangents (AE 2026).
    if out_linear:
        cy1 = cx1
    if in_linear:
        cy2 = cx2

    # A handle that reaches past the unit square is shortened ALONG ITS OWN
    # SLOPE, which keeps the speed the user asked for and spends influence
    # instead. Clamping y alone would silently change the speed (AE 2026:
    # clamping is 0.15 out on the measured overshoot fixture, shortening
    # 3e-5).
    if cy1 > 1.0:
        cx1, cy1 = cx1 / cy1, 1.0
    elif cy1 < 0.0:
        cy1 = 0.0
    if cy2 < 0.0:
        cx2, cy2 = 1.0 - (1.0 - cx2) / (1.0 - cy2), 0.0
    elif cy2 > 1.0:
        cy2 = 1.0

    return _get_bezier_easing(cx1, cy1, cx2, cy2)


def roving_keyframe_times(
    keyframes: list[Keyframe], metric: ArcMetric
) -> dict[int, int]:
    """Time units for every roving keyframe, spaced along the motion path.

    A roving keyframe's time is derived, not stored: AE places it where the
    enclosing anchors' eased span has travelled the path up to it. The
    anchors' ease applies ONCE across the whole run, so the time is read
    off the same (seconds, distance) curve the run's value is evaluated on,
    then rounded half up to the layer's units - truncated instead when both
    anchors are LINEAR, whose time is computed in units directly. Each
    result is clamped so the run keeps one unit per keyframe inside its
    anchors.

    The spacing follows the length of the actual curve, not the chord
    between keyframes - measured on AE 2026 with one segment bowed by +/-400 px
    tangents, where chord length predicts 0.667 s and AE produced 2.2205 s.
    A 4-point run over 8 s with 0/80 ease on both anchors puts the two
    roving keys at 3.54484 and 4.308594.

    Returns:
        A `{keyframe index: time units}` mapping covering only the roving
        keyframes that sit between two anchors. Units count LAYER time, so
        a stretched layer needs no further conversion.
    """
    result: dict[int, int] = {}
    anchors = [i for i, kf in enumerate(keyframes) if not kf.roving]
    if len(anchors) < 2:
        return result
    tangents: list[tuple[list[float], list[float]]] | None = None
    for start, end in zip(anchors, anchors[1:]):
        if end - start < 2:
            continue
        if not all(isinstance(keyframes[i].value, list) for i in range(start, end + 1)):
            continue
        if tangents is None:
            tangents = _spatial_tangents(keyframes)
        lengths = [
            _segment_spline(keyframes, i, tangents, metric).length
            for i in range(start, end)
        ]
        total = 0.0
        for length in lengths:
            total += length
        if total <= 0:
            continue
        first = keyframes[start]
        last = keyframes[end]
        units0 = first.time_units
        units1 = last.time_units
        travelled = 0.0
        for index in range(start + 1, end):
            travelled += lengths[index - start - 1]
            units = _roving_units(first, last, units0, units1, travelled, total, metric)
            result[index] = min(
                max(units, units0 + index - start), units1 - (end - index)
            )
    return result


def _roving_units(
    first: Keyframe,
    last: Keyframe,
    units0: int,
    units1: int,
    travelled: float,
    total: float,
    metric: ArcMetric,
) -> int:
    """The time unit at which a roving run has travelled `travelled`."""
    out_type = first.out_interpolation_type
    in_type = last.in_interpolation_type
    if out_type == KeyframeInterpolationType.HOLD:
        return units0
    if (
        out_type == KeyframeInterpolationType.LINEAR
        and in_type == KeyframeInterpolationType.LINEAR
    ):
        return int((units1 - units0) * (travelled / total) + units0)
    if in_type == KeyframeInterpolationType.HOLD:
        return units0
    timebase = first._timebase
    curve = _distance_curve(
        (units1 - units0) / timebase,
        total,
        first.out_temporal_ease[0],
        last.in_temporal_ease[0],
        out_type,
        in_type,
        metric.speed_divisor,
    )
    t = _t_on_axis(curve, 1, travelled)
    seconds = _cubic_1d(curve[0][0], curve[1][0], curve[2][0], curve[3][0], t)
    return units0 + math.floor(timebase * seconds + 0.5)


def _spatial_tangents(
    keyframes: list[Keyframe],
) -> list[tuple[list[float], list[float]]]:
    """Every keyframe's `(out, in)` spatial tangents, auto-bezier derived.

    An auto-bezier keyframe's stored tangents are NOT used even when they
    are non-zero: AE recomputes them from the flag and ignores what is on
    disk, so its own files legitimately carry stale values.
    """
    values = [cast("list[float]", kf.value) for kf in keyframes]
    result: list[tuple[list[float], list[float]]] = []
    for i, kf in enumerate(keyframes):
        if kf.spatial_auto_bezier:
            result.append(auto_spatial_tangents(values, i))
            continue
        zero = [0.0] * len(values[i])
        result.append((kf.out_spatial_tangent or zero, kf.in_spatial_tangent or zero))
    return result


# ---------------------------------------------------------------------------
# Segment interpolation - lottie-web approach
# ---------------------------------------------------------------------------


def _interpolate_bezier_1d(
    t: float,
    t0: float,
    t1: float,
    v0: float,
    v1: float,
    out_ease: KeyframeEase,
    in_ease: KeyframeEase,
) -> float:
    """Interpolate 1D using lottie-web's BezierEasing approach.

    Converts speed/influence to normalized bezier control points,
    then uses BezierEasing to get the eased progress, then lerps.
    """
    dt = t1 - t0
    if dt == 0:
        return v0

    # Convert AEP ease to normalized bezier control points. Only the x
    # (time) axis is used to find the curve parameter; the value axis is
    # evaluated from absolute control points so a segment whose keys hold
    # the same value still bows (see `_ease_value_handles`).
    cx1, cy1, cx2, cy2 = _ease_to_bezier_1d(t0, t1, v0, v1, out_ease, in_ease)

    # Get easing function (cached)
    easing = _get_bezier_easing(cx1, cy1, cx2, cy2)

    # Normalized time fraction
    x = (t - t0) / dt
    u = easing.parameter_at(x)

    y1, y2 = _ease_value_handles(t0, t1, v0, v1, out_ease, in_ease)
    mu = 1.0 - u
    return (
        mu * mu * mu * v0
        + 3.0 * mu * mu * u * y1
        + 3.0 * mu * u * u * y2
        + u * u * u * v1
    )


def _segment_spline(
    keyframes: list[Keyframe],
    index: int,
    tangents: list[tuple[list[float], list[float]]],
    metric: ArcMetric,
) -> _ArcSpline:
    """The arc spline of the segment from `keyframes[index]` to the next."""
    curve = _measured_curve(
        cast("list[float]", keyframes[index].value),
        cast("list[float]", keyframes[index + 1].value),
        tangents[index][0],
        tangents[index + 1][1],
        metric,
    )
    return _arc_spline(curve, metric.accuracy)


def auto_path_speed(keyframes: list[Keyframe], index: int, metric: ArcMetric) -> float:
    """AE's temporal auto-bezier speed for `keyframes[index]` on a motion path.

    One speed along the path, not one per dimension: the arc distance
    between the neighbouring anchors (roving keys skipped) over their time
    span - at either end, the single segment's. AE derives it rather than
    storing it: its own files hold speed 0 and influence 0 there (AE 2026,
    three auto-bezier keys on Position).
    """
    low = index
    high = index
    if index > 0:
        low -= 1
        while low > 0 and keyframes[low].roving:
            low -= 1
    if index < len(keyframes) - 1:
        high += 1
        while high < len(keyframes) - 1 and keyframes[high].roving:
            high += 1
    span = keyframes[high]._layer_time - keyframes[low]._layer_time
    if span <= 0:
        return 0.0
    tangents = _spatial_tangents(keyframes)
    distance = 0.0
    for i in range(low, high):
        distance += _segment_spline(keyframes, i, tangents, metric).length
    return distance / span * metric.speed_divisor


def spatial_location(
    time: float,
    keyframes: list[Keyframe],
    left: int,
    metric: ArcMetric,
    tangents: list[tuple[list[float], list[float]]] | None = None,
) -> tuple[int, float]:
    """Where a motion path is at `time`: a segment and its curve parameter.

    `time` is in the owning layer's seconds, strictly inside the segment
    starting at `keyframes[left]`. A roving keyframe is not an ease
    boundary: AE eases a whole roving run once, between its anchors, and
    walks the run's segments by distance - so the segment returned can be
    another one of the run. Easing each sub-segment on its own instead (with
    the per-segment speeds AE leaves on the roving keys) is 99 px out on
    the measured 4-point fixture.

    Returns:
        `(index, u)`: the segment starting at `keyframes[index]`, and the
        curve parameter along it.
    """
    if tangents is None:
        tangents = _spatial_tangents(keyframes)
    start = left
    end = left + 1
    while start > 0 and keyframes[start].roving:
        start -= 1
    while end < len(keyframes) - 1 and keyframes[end].roving:
        end += 1
    splines = [
        _segment_spline(keyframes, i, tangents, metric) for i in range(start, end)
    ]
    total = 0.0
    for spline in splines:
        total += spline.length
    first = keyframes[start]
    last = keyframes[end]
    t0 = first._layer_time
    distance = _spatial_distance(
        time - t0, last._layer_time - t0, total, first, last, metric.speed_divisor
    )
    index = 0
    while index < len(splines) - 1 and distance > splines[index].length:
        distance -= splines[index].length
        index += 1
    return start + index, splines[index].parameter_at(distance)


# ---------------------------------------------------------------------------
# Single-progress value kinds: paths and Orientation
# ---------------------------------------------------------------------------
# A mask / shape path and an Orientation keyframe carry ONE ease per side
# (their value has no per-component speed to ease against), and AE drives
# the whole value along that single progress. Measured on AE 2026 across
# LINEAR, eased, asymmetric and mixed LINEAR/BEZIER key pairs: a path and
# an Orientation with the same ease yield the same progress curve, and
# every ease AE writes for these kinds stores a speed of 0.


def _single_progress(
    kf_left: Keyframe,
    kf_right: Keyframe,
    time: float,
    t0: float,
    t1: float,
) -> float:
    """The eased 0-1 parameter AE drives a path or Orientation segment with.

    These values have no scalar magnitude for a speed to be a rate OF, so
    a stored ease speed is dimensionless: 1 means the chord slope, which
    is exactly what AE reports for a LINEAR side. Unit time against unit
    arc length says exactly that, and leaves the handle at
    `speed * influence` - measured on AE 2026, where normalizing against
    the rotation arc instead is 33 degrees out on a 40 deg/s Orientation
    ease.

    Args:
        kf_left: The keyframe starting the segment.
        kf_right: The keyframe ending it.
        time: Evaluation time, in the owning layer's seconds.
        t0: `kf_left`'s layer time.
        t1: `kf_right`'s layer time.
    """
    # Bound to locals: `in/out_temporal_ease` re-derives its list on every
    # read, and this runs once per interpolated frame.
    out_ease = kf_left.out_temporal_ease
    in_ease = kf_right.in_temporal_ease
    easing = _spatial_progress_easing(
        1.0,
        1.0,
        out_ease[0] if out_ease else None,
        in_ease[0] if in_ease else None,
        out_linear=kf_left.out_interpolation_type == KeyframeInterpolationType.LINEAR,
        in_linear=kf_right.in_interpolation_type == KeyframeInterpolationType.LINEAR,
    )
    x = (time - t0) / (t1 - t0)
    return easing.get(x) if easing is not None else x


def _axis_quaternion(axis: int, degrees: float) -> tuple[float, float, float, float]:
    """A rotation of `degrees` about axis 0 (X), 1 (Y) or 2 (Z)."""
    half = math.radians(degrees) / 2.0
    parts = [0.0, 0.0, 0.0, math.cos(half)]
    parts[axis] = math.sin(half)
    return (parts[0], parts[1], parts[2], parts[3])


def _quaternion_multiply(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def euler_to_quaternion(angles: list[float]) -> tuple[float, float, float, float]:
    """Orientation angles in degrees as a quaternion.

    Uses AE's own composition order, `Rx . Ry . Rz` - the same one
    `build_local_matrix` applies an Orientation with.
    """
    q = (0.0, 0.0, 0.0, 1.0)
    for axis, angle in enumerate(angles[:3]):
        q = _quaternion_multiply(q, _axis_quaternion(axis, angle))
    return q


def quaternion_to_euler(q: tuple[float, float, float, float]) -> list[float]:
    """The `Rx . Ry . Rz` angles of `q`, in degrees wrapped into [0, 360).

    AE reports a rotation that runs backwards past zero as its positive
    equivalent - a Z orientation eased from 10 to 350 reads 357.5, not
    -2.5 (AE 2026).

    The extraction itself is `_euler_xyz`, which this feeds the quaternion's
    rotation matrix; only the elements it needs are built.
    """
    x, y, z, w = q
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm > 0:
        x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return [
        angle % 360.0
        for angle in _euler_xyz(
            1.0 - 2.0 * (y * y + z * z),  # m00
            2.0 * (x * y - z * w),  # m01
            2.0 * (x * z + y * w),  # m02
            2.0 * (x * y + z * w),  # m10
            1.0 - 2.0 * (x * x + z * z),  # m11
            2.0 * (y * z - x * w),  # m12
            1.0 - 2.0 * (x * x + y * y),  # m22
        )
    ]


def slerp_orientation(
    start: list[float], end: list[float], progress: float
) -> list[float]:
    """Interpolate two Orientation values the way After Effects does.

    AE turns both ends into quaternions, takes the shortest arc between
    them and reads it at `progress` - NOT a per-axis blend of the angles.
    Verified against AE 2026 to 1e-13 degrees: `[0,0,0]` to `[45,90,30]`
    reads `[22.0832, 42.8194, 22.0832]` at the midpoint, where a per-axis
    blend would give `[22.5, 45, 15]`.
    """
    q0 = euler_to_quaternion(start)
    q1 = euler_to_quaternion(end)
    dot = sum(a * b for a, b in zip(q0, q1))
    if dot < 0.0:
        # Opposite hemisphere: negate so the arc taken is the short one.
        q1 = (-q1[0], -q1[1], -q1[2], -q1[3])
        dot = -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > 0.9995:
        # Nearly parallel: sin(theta) underflows, and a normalized linear
        # blend is within float noise of the arc.
        blend = tuple(a + (b - a) * progress for a, b in zip(q0, q1))
        return quaternion_to_euler(cast("tuple[float, float, float, float]", blend))
    theta = math.acos(dot)
    sin_theta = math.sin(theta)
    s0 = math.sin((1.0 - progress) * theta) / sin_theta
    s1 = math.sin(progress * theta) / sin_theta
    return quaternion_to_euler(
        cast(
            "tuple[float, float, float, float]",
            tuple(a * s0 + b * s1 for a, b in zip(q0, q1)),
        )
    )


def _lerp_points(
    a: list[list[float]], b: list[list[float]], progress: float
) -> list[list[float]]:
    return [
        [p[0] + (q[0] - p[0]) * progress, p[1] + (q[1] - p[1]) * progress]
        for p, q in zip(a, b)
    ]


def _lerp_point(
    a: tuple[float, float], b: tuple[float, float], t: float
) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# A cubic bezier segment: start, its out handle, the end's in handle, end.
_Cubic = Tuple[
    Tuple[float, float],
    Tuple[float, float],
    Tuple[float, float],
    Tuple[float, float],
]


def _split_cubic(cubic: _Cubic, t: float) -> tuple[_Cubic, _Cubic]:
    """De Casteljau: the two halves of `cubic` either side of `t`.

    `split_spatial_path` above is the same subdivision, but it speaks the
    TANGENT representation and returns one side. Resampling chains splits
    and wants both halves as control points, which is what this returns -
    marshalling between the two costs more than the 6 lerps do.
    """
    p0, p1, p2, p3 = cubic
    a = _lerp_point(p0, p1, t)
    b = _lerp_point(p1, p2, t)
    c = _lerp_point(p2, p3, t)
    d = _lerp_point(a, b, t)
    e = _lerp_point(b, c, t)
    f = _lerp_point(d, e, t)
    return (p0, a, d, f), (f, e, c, p3)


def _subdivision_cuts(segment_count: int, target_count: int) -> list[list[float]]:
    """Where AE cuts each segment to reach `target_count` segments.

    After Effects bisects breadth-first: every segment once in path
    order, then every half in that same order, and so on, stopping the
    moment the counts match. Measured on AE 2026 over 22 source/target
    pairs from 2 to 12 vertices, open and closed - the distribution
    depends on the counts alone, not on either path's geometry (a target
    of a completely different shape, and a source with even rather than
    lopsided segments, both cut identically).
    """
    pieces = deque((index, 0.0, 1.0) for index in range(segment_count))
    while len(pieces) < target_count:
        index, start, end = pieces.popleft()
        middle = (start + end) / 2.0
        pieces.append((index, start, middle))
        pieces.append((index, middle, end))
    cuts: list[list[float]] = [[] for _ in range(segment_count)]
    for index, start, _end in pieces:
        if start > 0.0:
            cuts[index].append(start)
    for per_segment in cuts:
        per_segment.sort()
    return cuts


def _resample_path(
    vertices: list[list[float]],
    in_tangents: list[list[float]],
    out_tangents: list[list[float]],
    closed: bool,
    target: int,
) -> tuple[list[list[float]], list[list[float]], list[list[float]]]:
    """Add vertices to a path until it has `target` of them, shape intact.

    The new vertices land where a de Casteljau split puts them, so the
    outline is unchanged - only its parameterisation gains points.
    """
    count = len(vertices)
    segment_count = count if closed else count - 1
    if segment_count < 1:
        # A one-vertex open path: nothing to subdivide, so it cannot be
        # brought up to `target`. The caller checks the resulting length.
        return vertices, in_tangents, out_tangents
    cuts = _subdivision_cuts(segment_count, segment_count + target - count)

    chain: list[_Cubic] = []
    for index in range(segment_count):
        tail = (index + 1) % count
        start = (vertices[index][0], vertices[index][1])
        end = (vertices[tail][0], vertices[tail][1])
        out_t = out_tangents[index]
        in_t = in_tangents[tail]
        if not any(out_t) and not any(in_t):
            # AE keeps a straight segment straight: the new vertices land
            # on the line at the cut parameters and every handle stays
            # zero. Splitting it as the degenerate cubic instead would put
            # them at 0.15625 rather than 0.25 and hand each one a handle
            # a quarter of the segment long (AE 2026).
            bounds = [0.0, *cuts[index], 1.0]
            for low, high in zip(bounds, bounds[1:]):
                a = _lerp_point(start, end, low)
                b = _lerp_point(start, end, high)
                chain.append((a, a, b, b))
            continue
        cubic = (
            start,
            (start[0] + out_t[0], start[1] + out_t[1]),
            (end[0] + in_t[0], end[1] + in_t[1]),
            end,
        )
        consumed = 0.0
        for cut in cuts[index]:
            left, cubic = _split_cubic(cubic, (cut - consumed) / (1.0 - consumed))
            chain.append(left)
            consumed = cut
        chain.append(cubic)

    new_vertices = [[c[0][0], c[0][1]] for c in chain]
    new_out = [[c[1][0] - c[0][0], c[1][1] - c[0][1]] for c in chain]
    # Each piece's own IN handle, measured at the vertex it arrives at.
    arriving = [[c[2][0] - c[3][0], c[2][1] - c[3][1]] for c in chain]
    if closed:
        # Every vertex starts a piece, so its IN handle comes from the
        # piece before it - the last one wrapping around to vertex 0.
        new_in = arriving[-1:] + arriving[:-1]
    else:
        # The open path's final vertex ends the last piece rather than
        # starting one, so it is appended, and the first vertex keeps the
        # original path's own leading handles.
        new_vertices.append([chain[-1][3][0], chain[-1][3][1]])
        new_out.append(list(out_tangents[-1]))
        new_in = [list(in_tangents[0]), *arriving]
    return new_vertices, new_in, new_out


def interpolate_shapes(start: Shape, end: Shape, progress: float) -> Shape | None:
    """Blend two path values vertex by vertex.

    Vertices and both tangent sets move linearly at `progress`; `closed`
    is held at the left key's, as AE does. When the two keys hold
    different vertex counts the shorter path is resampled up to the
    longer one first, the way AE does it.

    `None` means "no blend is defined" - either path is empty, or the
    shorter one has no segment to subdivide - and the caller holds the
    left keyframe's value instead.
    """
    verts_a, in_a, out_a = start.vertices, start.in_tangents, start.out_tangents
    verts_b, in_b, out_b = end.vertices, end.in_tangents, end.out_tangents
    if not verts_a or not verts_b:
        return None
    target = max(len(verts_a), len(verts_b))
    if len(verts_a) < target:
        verts_a, in_a, out_a = _resample_path(
            verts_a, in_a, out_a, start.closed, target
        )
    elif len(verts_b) < target:
        verts_b, in_b, out_b = _resample_path(verts_b, in_b, out_b, end.closed, target)
    if len(verts_a) != len(verts_b):
        # `_resample_path` could not reach the target: a one-vertex open
        # path has no segment to subdivide.
        return None
    return Shape(
        _lerp_points(verts_a, verts_b, progress),
        _lerp_points(in_a, in_b, progress),
        _lerp_points(out_a, out_b, progress),
        closed=start.closed,
    )


def interpolate_keyframes(
    time: float,
    keyframes: list[Keyframe],
    is_spatial: bool,
    inert_dimensions: frozenset[int] = frozenset(),
    value_kind: ParallelKind | None = None,
    metric: ArcMetric = _DEFAULT_ARC_METRIC,
) -> list[float] | float | Shape | None:
    """Compute the interpolated value at `time` from a keyframe list.

    Args:
        time: Time in the owning LAYER's seconds, not composition seconds.
            AE evaluates the temporal bezier in layer time - its ease
            speeds are per layer second, and a negatively stretched layer's
            keyframes only ascend on this axis.
            [Property.value_at_time][py_aep.Property.value_at_time]
            converts before calling.
        keyframes: Keyframes in stored (layer time ascending) order.
        is_spatial: Whether the property is spatial.
        inert_dimensions: Indices the layer ignores, held at the left
            keyframe's value instead of interpolated - the Z of a 2-D
            layer's Scale, which AE never moves.
        value_kind: `SHAPE_KIND` or `ORIENTATION_KIND` for the two kinds
            AE blends as one eased quantity rather than per component;
            `None` for an ordinary numeric property.
        metric: How the property's motion path is measured, from its
            `tdb4`; only a spatial property reads it.

    Returns:
        Interpolated value, or `None` if no keyframes.
    """
    if not keyframes:
        return None

    n = len(keyframes)

    # Before first keyframe or single keyframe
    if n == 1 or time <= keyframes[0]._layer_time:
        return cast("list[float] | float | None", keyframes[0].value)

    # After last keyframe
    if time >= keyframes[-1]._layer_time:
        return cast("list[float] | float | None", keyframes[-1].value)

    # Find the segment
    right_idx = 0
    for i in range(1, n):
        if keyframes[i]._layer_time >= time:
            right_idx = i
            break

    left_idx = right_idx - 1
    kf_left = keyframes[left_idx]
    kf_right = keyframes[right_idx]

    t0 = kf_left._layer_time
    t1 = kf_right._layer_time

    # At exactly a keyframe time
    if abs(time - t0) < 1e-12:
        return cast("list[float] | float | None", kf_left.value)
    if abs(time - t1) < 1e-12:
        return cast("list[float] | float | None", kf_right.value)

    v0 = kf_left.value
    v1 = kf_right.value
    out_type = kf_left.out_interpolation_type
    in_type = kf_right.in_interpolation_type

    # A motion path is evaluated by distance, through AE's arc-length model.
    # A LINEAR key still follows the cubic its tangents define - only the
    # EASE is linear (AE 2026: a LINEAR/LINEAR segment from (50,50) to
    # (350,50) with tangents (100,200)/(-100,200) passes through (200,200),
    # not the straight line's (200,50)) - and a roving run is eased by its
    # anchors alone, whatever its roving keys' own interpolation says.
    if (
        is_spatial
        and value_kind is None
        and isinstance(v0, list)
        and isinstance(v1, list)
    ):
        tangents = _spatial_tangents(keyframes)
        index, u = spatial_location(time, keyframes, left_idx, metric, tangents)
        curve = _spatial_curve(
            cast("list[float]", keyframes[index].value),
            cast("list[float]", keyframes[index + 1].value),
            tangents[index][0],
            tangents[index + 1][1],
        )
        return _cubic_point(curve, u)

    # HOLD
    if out_type == KeyframeInterpolationType.HOLD:
        return cast("list[float] | float | None", v0)
    if in_type == KeyframeInterpolationType.HOLD:
        return cast("list[float] | float | None", v1)

    # A path and an Orientation blend as ONE eased quantity, so they skip
    # the per-dimension machinery below entirely.
    if value_kind is not None:
        progress = _single_progress(kf_left, kf_right, time, t0, t1)
        if value_kind is SHAPE_KIND and isinstance(v0, Shape) and isinstance(v1, Shape):
            blended = interpolate_shapes(v0, v1, progress)
            return blended if blended is not None else v0
        if (
            value_kind is ORIENTATION_KIND
            and isinstance(v0, list)
            and isinstance(v1, list)
        ):
            return slerp_orientation(v0, v1, progress)

    # AE stores a LINEAR side as a diagonal handle - speed equal to the
    # chord slope, influence 100/6 - so the ordinary bezier path below
    # reproduces it exactly, including the case AE cares about: a LINEAR out
    # side facing an EASED in side still gets that ease (measured on AE
    # 2026: Opacity 0->100 over 2 s with a LINEAR out and a 90 % influence in
    # side reaches 87.5 at t=1, where a lerp gives 50).
    if out_type in (
        KeyframeInterpolationType.BEZIER,
        KeyframeInterpolationType.LINEAR,
    ):
        # Non-spatial: per-dimension 1D bezier
        if isinstance(v0, list) and isinstance(v1, list):
            # One stored ease for a multi-dimensional value means AE drives
            # the whole value with a single progress rather than a bezier per
            # dimension - a colour, whose speed has no per-channel meaning.
            # Measured on AE 2026: the progress follows the INFLUENCES alone
            # (handles at `(out/100, 0)` and `(1 - in/100, 1)`), reproducing
            # five sampled colour segments to 4e-4, and the stored speed does
            # not shape it. Interpolating per channel instead drove the
            # unchanged channels out of gamut.
            # `min`, not both: AE stores exactly one ease per side on a
            # colour, but py's own key insertion can leave one side holding a
            # per-channel list, and a single ease on either side still means
            # one progress.
            if min(len(kf_left.out_temporal_ease), len(kf_right.in_temporal_ease)) == 1:
                progress = _get_bezier_easing(
                    kf_left.out_temporal_ease[0].influence / 100.0,
                    0.0,
                    1.0 - kf_right.in_temporal_ease[0].influence / 100.0,
                    1.0,
                ).get((time - t0) / (t1 - t0))
                return [v0[d] + (v1[d] - v0[d]) * progress for d in range(len(v0))]

            result: list[float] = []
            for d in range(len(v0)):
                if d in inert_dimensions:
                    # AE leaves an inert dimension alone: a 2-D layer's Scale
                    # Z reads exactly 100 across a segment whose live X and Y
                    # bow. (AE also refuses to STORE any other Z there, so the
                    # two keyframes always agree.)
                    result.append(v0[d])
                    continue
                out_e = (
                    kf_left.out_temporal_ease[d]
                    if d < len(kf_left.out_temporal_ease)
                    else kf_left.out_temporal_ease[0]
                )
                in_e = (
                    kf_right.in_temporal_ease[d]
                    if d < len(kf_right.in_temporal_ease)
                    else kf_right.in_temporal_ease[0]
                )
                result.append(
                    _interpolate_bezier_1d(
                        time,
                        t0,
                        t1,
                        v0[d],
                        v1[d],
                        out_e,
                        in_e,
                    )
                )
            return result

        if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
            out_e_1d = (
                kf_left.out_temporal_ease[0] if kf_left.out_temporal_ease else None
            )
            in_e_1d = (
                kf_right.in_temporal_ease[0] if kf_right.in_temporal_ease else None
            )
            if out_e_1d and in_e_1d:
                return _interpolate_bezier_1d(
                    time,
                    t0,
                    t1,
                    float(v0),
                    float(v1),
                    out_e_1d,
                    in_e_1d,
                )
            ratio = (time - t0) / (t1 - t0)
            return float(v0) + (float(v1) - float(v0)) * ratio

    # Fallback
    return cast("list[float] | float | None", v0)
