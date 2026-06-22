"""Layer specifications for layered-file composition imports.

When importing an Illustrator/PDF or Photoshop file as a composition, each
source layer becomes a footage item and a comp layer (layer groups become
nested compositions). These specs describe that structure as it is discovered
from the file, before the chunk tree is built. They are pure data carriers and
do not touch the binary layer.
"""

from __future__ import annotations

from typing import NamedTuple


class LayerSpec(NamedTuple):
    """One per-layer footage item for a layered-file composition import."""

    name: str
    """Layer name (becomes the footage item and comp-layer name)."""

    opti_data: bytes
    """The per-layer `opti` asset-info bytes."""

    width: int
    """Footage pixel width (full canvas for COMP, content box for cropped)."""

    height: int
    """Footage pixel height (full canvas for COMP, content box for cropped)."""

    transform: tuple[tuple[float, float], tuple[float, float]] | None = None
    """`((anchor_x, anchor_y), (position_x, position_y))`, or `None` to leave
    the layer centered by `CompItem.add` (whole-canvas layers)."""

    full_frame: bool = True
    """`True` when the footage spans the full source frame; `False` for a layer
    cropped to its content box."""

    is_adjustment: bool = False
    """`True` when the comp layer should be marked as an adjustment layer."""


class LayerGroupSpec(NamedTuple):
    """A layer group, imported as a nested composition of its children."""

    name: str
    """Group name (becomes the nested comp + parent-layer name)."""

    children: list[LayerSpec | LayerGroupSpec]
    """The group's contents, bottom layer first."""
