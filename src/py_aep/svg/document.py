"""SVG root parsing: canvas size and the viewBox origin transform."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING
from xml.etree.ElementTree import Element

from ._util import NUMBER_RE, parse_length
from .transform import Affine

if TYPE_CHECKING:
    ViewBox = tuple[float, float, float, float]


def _view_box(value: str | None) -> ViewBox | None:
    """The `(min_x, min_y, width, height)` of a viewBox attribute, or `None`
    when it is absent or invalid (not four finite numbers, or a size that is
    not positive: SVG treats those as an error / no viewBox)."""
    if not value:
        return None
    nums = [float(n) for n in NUMBER_RE.findall(value)]
    if len(nums) != 4 or not all(math.isfinite(n) for n in nums):
        return None
    if nums[2] <= 0 or nums[3] <= 0:
        return None
    return nums[0], nums[1], nums[2], nums[3]


def canvas(root: Element) -> tuple[float, float, Affine]:
    """Return `(width, height, root_transform)` for the SVG root.

    After Effects sizes the comp from the viewBox dimensions (falling
    back to the `width`/`height` attributes). The root transform shifts
    a non-zero viewBox origin to `(0, 0)` so geometry lands in comp
    space.
    """
    view_box = _view_box(root.get("viewBox"))
    if view_box is not None:
        min_x, min_y, vb_w, vb_h = view_box
        # AE 2026 sizes the comp from the viewBox dimensions and only
        # shifts geometry by the viewBox origin (verified on the sample
        # SVG). Where width/height differ from the viewBox, AE also scales
        # the geometry by them while keeping the viewBox-sized comp;
        # py_aep keeps the drawing in viewBox units, so it fills the comp.
        return vb_w, vb_h, Affine(e=-min_x, f=-min_y)
    width = parse_length(root.get("width"))
    height = parse_length(root.get("height"))
    if not (math.isfinite(width) and math.isfinite(height)):
        return 0.0, 0.0, Affine()
    return width, height, Affine()


def viewport_transform(
    view_box: str | None,
    preserve_aspect_ratio: str | None,
    x: float,
    y: float,
    width: float,
    height: float,
) -> tuple[Affine, tuple[float, float]]:
    """Map a nested viewport's content onto its `x / y / width / height`
    box (SVG 1.1 7.7-7.9).

    Returns the transform from the viewport's user space to its parent's
    and the viewport size its percentages resolve against (the viewBox
    size when there is one).
    """
    vb = _view_box(view_box)
    if vb is None:
        return Affine(e=x, f=y), (width, height)
    min_x, min_y, vb_w, vb_h = vb
    sx, sy = width / vb_w, height / vb_h
    tokens = [t for t in (preserve_aspect_ratio or "").split() if t != "defer"]
    align = tokens[0] if tokens else "xMidYMid"
    if align != "none":
        s = max(sx, sy) if tokens[1:2] == ["slice"] else min(sx, sy)
        sx = sy = s
        ax = {"xMin": 0.0, "xMid": 0.5, "xMax": 1.0}.get(align[:4], 0.5)
        ay = {"YMin": 0.0, "YMid": 0.5, "YMax": 1.0}.get(align[4:], 0.5)
        x += (width - vb_w * s) * ax
        y += (height - vb_h * s) * ay
    return Affine(a=sx, d=sy, e=x - min_x * sx, f=y - min_y * sy), (vb_w, vb_h)
