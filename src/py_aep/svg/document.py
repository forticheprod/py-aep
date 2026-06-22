"""SVG root parsing: canvas size and the viewBox origin transform."""

from __future__ import annotations

from xml.etree.ElementTree import Element

from ._util import NUMBER_RE
from .transform import Affine


def _length(value: str | None, default: float) -> float:
    """Parse an SVG length, dropping a trailing unit (treated as px)."""
    if not value:
        return default
    m = NUMBER_RE.match(value.strip())
    return float(m.group()) if m else default


def canvas(root: Element) -> tuple[float, float, Affine]:
    """Return `(width, height, root_transform)` for the SVG root.

    After Effects sizes the comp from the viewBox dimensions (falling
    back to the `width`/`height` attributes). The root transform shifts
    a non-zero viewBox origin to `(0, 0)` so geometry lands in comp
    space.
    """
    view_box = root.get("viewBox")
    if view_box:
        nums = [float(n) for n in NUMBER_RE.findall(view_box)]
        if len(nums) == 4:
            min_x, min_y, vb_w, vb_h = nums
            # AE 2026 sizes the comp from the viewBox dimensions and only
            # shifts geometry by the viewBox origin (verified on the sample
            # SVG; a width/height that differs from the viewBox would add a
            # preserveAspectRatio scale - deferred until AE-validated).
            return vb_w, vb_h, Affine(e=-min_x, f=-min_y)
    width = _length(root.get("width"), 0.0)
    height = _length(root.get("height"), 0.0)
    return width, height, Affine()
