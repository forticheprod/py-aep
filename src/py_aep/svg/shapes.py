"""Convert SVG shape elements to cubic subpaths and to AE Shape form.

`element_subpaths` turns a basic shape (`rect`, `circle`, `ellipse`,
`line`, `polyline`, `polygon`) or a `path` into untransformed cubic
[RawSubpath][py_aep.svg.path_data.RawSubpath]s. `cubics_to_subpath`
applies the accumulated transform and extracts After Effects vertices +
in/out tangents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from ._util import NUMBER_RE, LengthContext, parse_length
from .errors import UnsupportedSVGError
from .path_data import RawSubpath, parse_path
from .transform import Affine
from .types import Subpath

if TYPE_CHECKING:
    from .path_data import CubicSeg

# Control-point distance for a 90-degree circular arc as a cubic bezier.
_KAPPA = 0.5522847498307936

# The viewport dimension (`LengthContext` attribute) a percentage of each
# geometry attribute refers to (SVG 1.1 7.10): the width, the height, or the
# normalized diagonal.
_PERCENT_AXIS = {
    "x": "width",
    "width": "width",
    "cx": "width",
    "rx": "width",
    "x1": "width",
    "x2": "width",
    "y": "height",
    "height": "height",
    "cy": "height",
    "ry": "height",
    "y1": "height",
    "y2": "height",
    "r": "diagonal",
}


def _f(
    attrs: dict[str, str],
    key: str,
    ctx: LengthContext | None,
    default: float = 0.0,
) -> float:
    """A geometry attribute in user units: units converted and a percentage
    resolved against `ctx` (kept as the bare number without one)."""
    if ctx is None:
        return parse_length(attrs.get(key), default)
    ref = getattr(ctx, _PERCENT_AXIS[key])
    return parse_length(attrs.get(key), default, ref, ctx.font_size)


def _is_auto(raw: str | None) -> bool:
    """An absent or `auto` corner radius, which takes the other radius."""
    return raw is None or raw.strip() in ("", "auto")


def element_subpaths(
    tag: str, attrs: dict[str, str], ctx: LengthContext | None = None
) -> list[RawSubpath]:
    """Return untransformed cubic subpaths for a drawable element.

    Args:
        tag: Local element name (no namespace), e.g. `rect`, `path`.
        attrs: Element attributes.
        ctx: The viewport and font size percentage and `em` lengths
            resolve against.

    Raises:
        UnsupportedSVGError: For an element that is not a basic shape.
    """
    if tag == "path":
        return parse_path(attrs.get("d", ""))
    if tag == "rect":
        return _rect(attrs, ctx)
    if tag in ("circle", "ellipse"):
        return _ellipse(tag, attrs, ctx)
    if tag == "line":
        x1, y1 = _f(attrs, "x1", ctx), _f(attrs, "y1", ctx)
        x2, y2 = _f(attrs, "x2", ctx), _f(attrs, "y2", ctx)
        return [RawSubpath([(x1, y1, x1, y1, x2, y2, x2, y2)], False)]
    if tag in ("polyline", "polygon"):
        return _poly(attrs, closed=(tag == "polygon"))
    raise UnsupportedSVGError(f"Unsupported drawable element: <{tag}>")


def _rect(attrs: dict[str, str], ctx: LengthContext | None) -> list[RawSubpath]:
    x, y = _f(attrs, "x", ctx), _f(attrs, "y", ctx)
    w, h = _f(attrs, "width", ctx), _f(attrs, "height", ctx)
    if w <= 0 or h <= 0:
        return []
    rx, ry = _f(attrs, "rx", ctx), _f(attrs, "ry", ctx)
    if _is_auto(attrs.get("rx")):
        rx = ry
    if _is_auto(attrs.get("ry")):
        ry = rx
    rx = min(max(rx, 0.0), w / 2.0)
    ry = min(max(ry, 0.0), h / 2.0)
    if rx == 0 or ry == 0:
        # Sharp corners: 4 straight segments.
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        segs: list[CubicSeg] = []
        for i in range(4):
            p0 = pts[i]
            p3 = pts[(i + 1) % 4]
            segs.append((p0[0], p0[1], p0[0], p0[1], p3[0], p3[1], p3[0], p3[1]))
        return [RawSubpath(segs, True)]
    # Rounded rect: straight edges + quarter-ellipse corners (clockwise
    # from the top edge, starting after the top-left corner).
    cx_k, cy_k = rx * _KAPPA, ry * _KAPPA
    x2, y2 = x + w, y + h
    segs = []

    Pt = Tuple[float, float]

    def line(p0: Pt, p3: Pt) -> None:
        segs.append((p0[0], p0[1], p0[0], p0[1], p3[0], p3[1], p3[0], p3[1]))

    def arc(p0: Pt, c1: Pt, c2: Pt, p3: Pt) -> None:
        segs.append((p0[0], p0[1], c1[0], c1[1], c2[0], c2[1], p3[0], p3[1]))

    line((x + rx, y), (x2 - rx, y))
    arc((x2 - rx, y), (x2 - rx + cx_k, y), (x2, y + ry - cy_k), (x2, y + ry))
    line((x2, y + ry), (x2, y2 - ry))
    arc((x2, y2 - ry), (x2, y2 - ry + cy_k), (x2 - rx + cx_k, y2), (x2 - rx, y2))
    line((x2 - rx, y2), (x + rx, y2))
    arc((x + rx, y2), (x + rx - cx_k, y2), (x, y2 - ry + cy_k), (x, y2 - ry))
    line((x, y2 - ry), (x, y + ry))
    arc((x, y + ry), (x, y + ry - cy_k), (x + rx - cx_k, y), (x + rx, y))
    return [RawSubpath(segs, True)]


def _ellipse(
    tag: str, attrs: dict[str, str], ctx: LengthContext | None
) -> list[RawSubpath]:
    cx, cy = _f(attrs, "cx", ctx), _f(attrs, "cy", ctx)
    if tag == "circle":
        r = _f(attrs, "r", ctx)
        rx = ry = r
    else:
        rx, ry = _f(attrs, "rx", ctx), _f(attrs, "ry", ctx)
        # `auto` takes the other radius (SVG 2). AE 2026 reads it as 0 and
        # imports `rx="auto" ry="20"` as a zero-width ellipse.
        if (attrs.get("rx") or "").strip() == "auto":
            rx = ry
        elif (attrs.get("ry") or "").strip() == "auto":
            ry = rx
    if rx <= 0 or ry <= 0:
        return []
    kx, ky = rx * _KAPPA, ry * _KAPPA
    # Top, right, bottom, left (clockwise): AE 2026 starts an imported
    # circle/ellipse at the top vertex.
    right = (cx + rx, cy)
    bottom = (cx, cy + ry)
    left = (cx - rx, cy)
    top = (cx, cy - ry)
    segs = [
        (top[0], top[1], cx + kx, cy - ry, cx + rx, cy - ky, right[0], right[1]),
        (right[0], right[1], cx + rx, cy + ky, cx + kx, cy + ry, bottom[0], bottom[1]),
        (bottom[0], bottom[1], cx - kx, cy + ry, cx - rx, cy + ky, left[0], left[1]),
        (left[0], left[1], cx - rx, cy - ky, cx - kx, cy - ry, top[0], top[1]),
    ]
    return [RawSubpath(segs, True)]


def _poly(attrs: dict[str, str], closed: bool) -> list[RawSubpath]:
    nums = [float(n) for n in NUMBER_RE.findall(attrs.get("points", ""))]
    pts = list(zip(nums[0::2], nums[1::2]))
    if len(pts) < 2:
        return []
    segs: list[CubicSeg] = []
    for i in range(len(pts) - 1):
        p0, p3 = pts[i], pts[i + 1]
        segs.append((p0[0], p0[1], p0[0], p0[1], p3[0], p3[1], p3[0], p3[1]))
    if closed:
        p0, p3 = pts[-1], pts[0]
        if p0 != p3:
            segs.append((p0[0], p0[1], p0[0], p0[1], p3[0], p3[1], p3[0], p3[1]))
    return [RawSubpath(segs, closed)]


def cubics_to_subpath(raw: RawSubpath, transform: Affine) -> Subpath | None:
    """Apply `transform` to a raw subpath and extract AE vertices/tangents.

    Returns `None` for an empty subpath.
    """
    segs = raw.segments
    if not segs:
        return None
    # Transform every control point of every segment.
    tsegs: list[CubicSeg] = []
    for x0, y0, c1x, c1y, c2x, c2y, x3, y3 in segs:
        p0 = transform.apply(x0, y0)
        c1 = transform.apply(c1x, c1y)
        c2 = transform.apply(c2x, c2y)
        p3 = transform.apply(x3, y3)
        tsegs.append((p0[0], p0[1], c1[0], c1[1], c2[0], c2[1], p3[0], p3[1]))

    vertices: list[list[float]] = []
    in_t: list[list[float]] = []
    out_t: list[list[float]] = []

    if raw.closed:
        n = len(tsegs)
        for i in range(n):
            vx, vy = tsegs[i][0], tsegs[i][1]
            vertices.append([vx, vy])
            out_t.append([tsegs[i][2] - vx, tsegs[i][3] - vy])
            prev = tsegs[(i - 1) % n]
            in_t.append([prev[4] - vx, prev[5] - vy])
    else:
        # N segments -> N+1 vertices.
        first = tsegs[0]
        vertices.append([first[0], first[1]])
        out_t.append([first[2] - first[0], first[3] - first[1]])
        in_t.append([0.0, 0.0])
        for i, seg in enumerate(tsegs):
            vx, vy = seg[6], seg[7]
            vertices.append([vx, vy])
            in_t.append([seg[4] - vx, seg[5] - vy])
            if i + 1 < len(tsegs):
                nxt = tsegs[i + 1]
                out_t.append([nxt[2] - vx, nxt[3] - vy])
            else:
                out_t.append([0.0, 0.0])
    return Subpath(
        vertices=vertices, in_tangents=in_t, out_tangents=out_t, closed=raw.closed
    )
