"""The content box of a Photoshop layer's footage on a layered import.

After Effects sizes each per-layer footage item of a layered PSD/PSB import
(and a single layer imported at Layer Size) to the layer's content box: the
`opti` stores it, the footage's data size follows it, and a
`COMP_CROPPED_LAYERS` import crops the layer to it. Rules measured on After
Effects 2026 with byte-patched PSDs:

- A raster layer's content is its record bounds (its pixels are not
  trimmed to their alpha); a fill layer's (solid color, gradient, pattern:
  shape layers) is the whole canvas.
- An enabled raster layer mask crops the content to the pixels where the
  layer's alpha and the mask are both non-zero (`PsdLayer.mask_box`), in
  either Layer Options mode.
- Merging (`layer_styles="merge"`) also bakes an enabled, non-inverted
  vector mask: the content is cut to the path's extent - its curves' true
  extrema, rounded out to whole pixels after snapping inward to a 1/64 px
  grid (an edge reaching 1/64 px into a pixel column counts, less does
  not). A fill layer takes the path's extent whole, even past the canvas.
  Editable mode keeps the vector mask as an AE mask and leaves the content
  alone.
- Merged layer styles then grow the content box
  (`psd_styles.merged_styles_bounds`).
"""

from __future__ import annotations

import math
import struct
from typing import TYPE_CHECKING

from .psd_paths import parse_vector_mask
from .psd_styles import merged_styles_bounds
from .shape_bounds import cubic_range

if TYPE_CHECKING:
    from .psd_layers import PsdLayer

    _Box = tuple[int, int, int, int]

# AE measures a vector mask's extent on a 1/64 px grid.
_SUBPIXEL = 64


def psd_layer_box(
    layer: PsdLayer,
    canvas_w: int,
    canvas_h: int,
    layer_styles: str,
    global_angle: float,
) -> _Box:
    """The `(left, top, right, bottom)` content box AE gives `layer`'s
    footage, in canvas pixels (see the module rules).

    Args:
        layer: The Photoshop layer.
        canvas_w: Document width in pixels.
        canvas_h: Document height in pixels.
        layer_styles: The Layer Options choice: `"merge"`, `"editable"` or
            `"ignore"`. Only merging bakes vector masks and styles.
        global_angle: The document's global light angle, for merged styles.

    Raises:
        NotImplementedError: For merged styles whose rasterized bounds are
            not known (see `psd_styles.merged_styles_bounds`).
    """
    merge = layer_styles == "merge"
    path = _path_box(layer, canvas_w, canvas_h) if merge else None
    if layer.is_fill:
        box = path if path is not None else (0, 0, canvas_w, canvas_h)
        if layer.mask_box is not None:
            box = _intersect(box, layer.mask_box)
    else:
        box = layer.mask_box if layer.mask_box is not None else layer.bounds
        if path is not None:
            box = _intersect(box, path)
    if merge and box[2] > box[0] and box[3] > box[1]:
        # Merged styles are rasterized into the footage, whose content box
        # grows to hold them, from the masked content.
        box = merged_styles_bounds(layer._replace(bounds=box), global_angle)
    return box


def _path_box(layer: PsdLayer, canvas_w: int, canvas_h: int) -> _Box | None:
    """The pixel extent of an enabled, non-inverted vector mask, or `None`."""
    block = layer.vector_mask
    if block is None or len(block) < 8:
        return None
    flags = struct.unpack(">I", block[4:8])[0]
    if flags & 0x05:
        # Inverted (bit 0) or disabled (bit 2): nothing is cut away.
        return None
    xs: list[float] = []
    ys: list[float] = []
    for shape in parse_vector_mask(block, canvas_w, canvas_h):
        vertices = shape.vertices
        count = len(vertices)
        for i in range(count):
            j = (i + 1) % count
            p0 = vertices[i]
            p3 = vertices[j]
            if j == 0 and not shape.closed:
                # Filling closes an open subpath with a straight edge.
                p1, p2 = p0, p3
            else:
                out, in_ = shape.out_tangents[i], shape.in_tangents[j]
                p1 = [p0[0] + out[0], p0[1] + out[1]]
                p2 = [p3[0] + in_[0], p3[1] + in_[1]]
            xs.extend(cubic_range(p0[0], p1[0], p2[0], p3[0]))
            ys.extend(cubic_range(p0[1], p1[1], p2[1], p3[1]))
    if not xs:
        return None
    return (
        _floor_edge(min(xs)),
        _floor_edge(min(ys)),
        _ceil_edge(max(xs)),
        _ceil_edge(max(ys)),
    )


def _floor_edge(value: float) -> int:
    return math.floor(math.ceil(value * _SUBPIXEL) / _SUBPIXEL)


def _ceil_edge(value: float) -> int:
    return math.ceil(math.floor(value * _SUBPIXEL) / _SUBPIXEL)


def _intersect(a: _Box, b: _Box) -> _Box:
    box = (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))
    if box[2] <= box[0] or box[3] <= box[1]:
        return (0, 0, 0, 0)
    return box
