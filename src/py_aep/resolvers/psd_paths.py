"""Decode Photoshop vector-mask path records into AE mask shapes.

A `vmsk`/`vsms` block body is a 4-byte version (3) + 4-byte flags + a run of
26-byte path records. Knot coordinates are signed 8.24 fixed-point fractions
of the CANVAS dimensions, vertical first. After Effects converts them to
layer-pixel bezier vertices with tangents relative to the anchor (pinned by
the psd_vector_mask/psd_shape_layer fixtures).
"""

from __future__ import annotations

import struct

from ..models.properties.shape import Shape

# Path record selectors (PSD spec "Path resource format").
_CLOSED_LENGTH = 0
_OPEN_LENGTH = 3
_KNOT_SELECTORS = frozenset({1, 2, 4, 5})


def _knot(record: bytes, canvas_w: int, canvas_h: int) -> list[list[float]]:
    """Decode a knot record to `[in_point, anchor, out_point]` pixel coords."""
    points = []
    for i in range(3):
        vert, horiz = struct.unpack(">ii", record[2 + i * 8 : 10 + i * 8])
        points.append([horiz / 0x1000000 * canvas_w, vert / 0x1000000 * canvas_h])
    return points


def parse_vector_mask(block: bytes, canvas_w: int, canvas_h: int) -> list[Shape]:
    """Decode a `vmsk`/`vsms` block into one [Shape][] per subpath.

    Args:
        block: The raw tagged-block body (version + flags + path records).
        canvas_w: Document canvas width in pixels.
        canvas_h: Document canvas height in pixels.

    Returns:
        The subpaths in file order (usually one). A malformed block yields
        the subpaths decoded so far.
    """
    shapes: list[Shape] = []
    vertices: list[list[float]] = []
    in_tangents: list[list[float]] = []
    out_tangents: list[list[float]] = []
    closed = True

    def flush() -> None:
        if vertices:
            shapes.append(
                Shape(
                    vertices=list(vertices),
                    in_tangents=list(in_tangents),
                    out_tangents=list(out_tangents),
                    closed=closed,
                )
            )
            vertices.clear()
            in_tangents.clear()
            out_tangents.clear()

    pos = 8  # version (3) + flags
    while pos + 26 <= len(block):
        record = block[pos : pos + 26]
        selector = struct.unpack(">H", record[:2])[0]
        if selector in (_CLOSED_LENGTH, _OPEN_LENGTH):
            flush()
            closed = selector == _CLOSED_LENGTH
        elif selector in _KNOT_SELECTORS:
            in_point, anchor, out_point = _knot(record, canvas_w, canvas_h)
            vertices.append(anchor)
            in_tangents.append([in_point[0] - anchor[0], in_point[1] - anchor[1]])
            out_tangents.append([out_point[0] - anchor[0], out_point[1] - anchor[1]])
        pos += 26
    flush()
    return shapes
