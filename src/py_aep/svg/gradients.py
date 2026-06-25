"""Gradient definitions and resolution to absolute `GradientPaint`.

`collect_gradients` indexes `<linearGradient>` / `<radialGradient>`
elements by id (following `href` inheritance for stops and geometry).
`resolve_gradient` maps a referenced gradient into absolute viewBox
coordinates given the referencing element's bounding box and transform.

Note: the mapping of a `GradientPaint` onto After Effects' gradient-fill
chunks is the import builder's concern and is not yet AE-validated; this
module only produces the geometric/stop representation.
"""

from __future__ import annotations

import math
from xml.etree.ElementTree import Element

from ._util import NUMBER_RE, local_name
from .colors import parse_color
from .transform import Affine, parse_transform
from .types import GradientPaint, GradientStop


def _href(elem: Element) -> str | None:
    for key in ("href", "{http://www.w3.org/1999/xlink}href"):
        ref = elem.get(key)
        if ref:
            return ref[1:] if ref.startswith("#") else ref
    return None


class GradientDef:
    """Raw gradient element plus its (href-resolved) stops and attrs."""

    def __init__(self, elem: Element) -> None:
        self.elem = elem
        self.kind = "radial" if local_name(elem.tag) == "radialGradient" else "linear"
        self.attrs: dict[str, str] = dict(elem.attrib)
        self.stops: list[GradientStop] = _parse_stops(elem)
        self.href = _href(elem)

    def attr(self, name: str, default: str) -> str:
        return self.attrs.get(name, default)


def collect_gradients(root: Element) -> dict[str, GradientDef]:
    """Index every gradient in the document by id, resolving `href`
    inheritance of stops and geometry attributes."""
    defs: dict[str, GradientDef] = {}
    for elem in root.iter():
        if local_name(elem.tag) in ("linearGradient", "radialGradient"):
            gid = elem.get("id")
            if gid:
                defs[gid] = GradientDef(elem)
    # Resolve href inheritance (stops + missing geometry attrs).
    for gd in defs.values():
        seen = set()
        ref = gd.href
        while ref and ref in defs and ref not in seen:
            seen.add(ref)
            parent = defs[ref]
            if not gd.stops:
                gd.stops = list(parent.stops)
            for k, v in parent.attrs.items():
                gd.attrs.setdefault(k, v)
            ref = parent.href
    return defs


def _parse_stops(elem: Element) -> list[GradientStop]:
    stops: list[GradientStop] = []
    for child in elem:
        if local_name(child.tag) != "stop":
            continue
        # SVG spec clamps stop offsets to [0, 1] (offsets > 100% round down).
        offset = _parse_ratio(child.get("offset", "0"), allow_over_one=False)
        style = _stop_style(child)
        color = parse_color(style.get("stop-color", "#000000")) or (0.0, 0.0, 0.0, 1.0)
        opacity = _parse_ratio(style.get("stop-opacity", "1"), allow_over_one=False)
        stops.append(
            GradientStop(
                offset=offset, color=(color[0], color[1], color[2], color[3] * opacity)
            )
        )
    stops.sort(key=lambda s: s.offset)
    return stops


def _stop_style(elem: Element) -> dict[str, str]:
    out = {k: v for k, v in elem.attrib.items() if k in ("stop-color", "stop-opacity")}
    inline = elem.get("style", "")
    for decl in inline.split(";"):
        if ":" in decl:
            k, _, v = decl.partition(":")
            out[k.strip()] = v.strip()
    return out


def _parse_ratio(text: str, allow_over_one: bool = True) -> float:
    text = text.strip()
    if text.endswith("%"):
        val = float(text[:-1]) / 100.0
    else:
        val = float(text) if text else 0.0
    if val < 0:
        return 0.0
    if not allow_over_one and val > 1:
        return 1.0
    return val


def _num(text: str) -> float:
    """Leading numeric value of `text`, ignoring any unit suffix (e.g.
    `"40px"` -> `40.0`); `0.0` if no number is present."""
    m = NUMBER_RE.search(text)
    return float(m.group()) if m else 0.0


def _coord(text: str, span: float, origin: float, object_bbox: bool) -> float:
    """Resolve a gradient coordinate to absolute (bbox or userspace)."""
    text = text.strip()
    if text.endswith("%"):
        frac = _num(text) / 100.0
        return origin + frac * span if object_bbox else frac * span
    val = _num(text)
    return origin + val * span if object_bbox else val


def resolve_gradient(
    gd: GradientDef,
    bbox: tuple[float, float, float, float],
    ctm: Affine,
) -> GradientPaint:
    """Resolve a gradient to absolute viewBox geometry.

    Args:
        gd: The gradient definition.
        bbox: The referencing element's absolute bounding box
            `(min_x, min_y, max_x, max_y)`.
        ctm: The element's current transform (applied for
            `userSpaceOnUse`; for `objectBoundingBox` the bbox is already
            absolute so only `gradientTransform` is applied).

    Returns:
        A `GradientPaint` with absolute `start`/`end` points and stops.
    """
    units = gd.attr("gradientUnits", "objectBoundingBox")
    object_bbox = units != "userSpaceOnUse"
    min_x, min_y, max_x, max_y = bbox
    bw, bh = (max_x - min_x), (max_y - min_y)
    gt = parse_transform(gd.attr("gradientTransform", ""))
    # In objectBoundingBox the bbox is absolute, so user-space CTM is not
    # re-applied; in userSpaceOnUse the CTM maps local coords to absolute.
    base = gt if object_bbox else ctm.multiply(gt)

    if gd.kind == "linear":
        x1 = _coord(gd.attr("x1", "0%"), bw, min_x, object_bbox)
        y1 = _coord(gd.attr("y1", "0%"), bh, min_y, object_bbox)
        x2 = _coord(gd.attr("x2", "100%"), bw, min_x, object_bbox)
        y2 = _coord(gd.attr("y2", "0%"), bh, min_y, object_bbox)
        start = base.apply(x1, y1)
        end = base.apply(x2, y2)
        return GradientPaint(kind=gd.kind, stops=gd.stops, start=start, end=end)

    cx = _coord(gd.attr("cx", "50%"), bw, min_x, object_bbox)
    cy = _coord(gd.attr("cy", "50%"), bh, min_y, object_bbox)
    # Radius as a fraction of the bbox diagonal-ish span.
    r_text = gd.attr("r", "50%").strip()
    if r_text.endswith("%"):
        r = _num(r_text) / 100.0 * (bw if object_bbox else 1.0)
    else:
        r = _num(r_text)
    start = base.apply(cx, cy)
    end = base.apply(cx + r, cy)
    # `start`/`end` only carry the x-radius, so a `gradientTransform` that
    # stretches the gradient vertically (e.g. `matrix(1 0 0 4 ...)`, common
    # for SVG wing/petal gradients) would collapse to a circle. Recover the
    # ellipse: AE stores the y/x aspect ratio in Grad Scale and the x-axis
    # angle in Grad Rotation (with 360 as the un-rotated radial baseline).
    edge_y = base.apply(cx, cy + r)
    x_radius = math.hypot(end[0] - start[0], end[1] - start[1])
    y_radius = math.hypot(edge_y[0] - start[0], edge_y[1] - start[1])
    scale_y = 100.0 * y_radius / x_radius if x_radius else 100.0
    angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
    rotation = angle if abs(angle) > 1e-6 else 360.0
    return GradientPaint(
        kind=gd.kind,
        stops=gd.stops,
        start=start,
        end=end,
        scale=(100.0, scale_y),
        rotation=rotation,
    )
