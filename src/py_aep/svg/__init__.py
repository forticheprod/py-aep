"""SVG reading for `ImportAsType.COMP_CROPPED_LAYERS`.

After Effects converts an imported SVG into a single shape layer whose
Contents hold one vector group per leaf drawable, with every ancestor
`<g>` transform baked into the geometry and SMIL animation discarded.
This package mirrors that: `read_svg()` flattens an SVG document into a
list of absolute-coordinate [SvgDrawable][py_aep.svg.types.SvgDrawable]
objects that the import builder turns into shape groups.
"""

from __future__ import annotations

from .errors import UnsupportedSVGError
from .reader import read_svg
from .types import (
    GradientPaint,
    GradientStop,
    SolidPaint,
    StrokeStyle,
    Subpath,
    SvgDocument,
    SvgDrawable,
)

__all__ = [
    "read_svg",
    "UnsupportedSVGError",
    "SvgDocument",
    "SvgDrawable",
    "Subpath",
    "SolidPaint",
    "GradientPaint",
    "GradientStop",
    "StrokeStyle",
]
