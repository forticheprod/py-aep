"""Layer specifications for layered-file composition imports.

When importing an Illustrator/PDF or Photoshop file as a composition, each
source layer becomes a footage item and a comp layer (layer groups become
nested compositions). These specs describe that structure as it is discovered
from the file, before the chunk tree is built. They are pure data carriers and
do not touch the binary layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from ..models.properties.shape import Shape
    from ..resolvers.psd_styles import PsdLayerStyles


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

    layer_id: int | None = None
    """Photoshop layer id (`lyid`) for the `sspc` layer binding; `None` for
    sources without one (AI/PDF layers, EPS, flattened documents)."""

    layer_index: int | None = None
    """0-based document index of the layer for the `sspc` layer binding;
    `None` for single-layer documents (EPS, flattened PSD)."""

    data_size: int = 0
    """Cached source data size for `sspc` byte 0xD0 (PSD: content-box pixel
    bytes; AI/PDF: file size). `0` lets AE re-derive it."""

    reserved_c8: bytes | None = None
    """Override for the `sspc` 0xC8 kind bytes (PSD layer-styles mode);
    `None` applies `FileSource._new`'s whole-file rule."""

    styles: PsdLayerStyles | None = None
    """Resolved layer styles to serialize on the comp layer (an
    editable-layer-styles PSD import); `None` writes the plain skeleton."""

    masks: tuple[Shape, ...] = ()
    """Mask shapes to create on the comp layer, one mask per shape (a PSD
    vector mask / shape layer path, one subpath each - AE creates `Mask N`
    per subpath)."""

    preserve_transparency: bool = False
    """Set the layer's preserve-transparency switch (a clipped PSD layer
    inside its auto-precomposed clipping run)."""


class LayerGroupSpec(NamedTuple):
    """A layer group, imported as a nested composition of its children.

    Also models a PSD clipping run (base layer + the clipped layers above
    it), which AE auto-precomposes: the run differs from a group only in
    naming, the uncollapsed parent layer, and the clipped children's
    preserve-transparency flag (psd_clipping_mask fixture)."""

    name: str
    """Group name (becomes the nested comp + parent-layer name)."""

    children: list[LayerSpec | LayerGroupSpec]
    """The group's contents, bottom layer first."""

    comp_name: str | None = None
    """Override for the nested comp's item name; `None` uses `name`. A
    clipping run's precomp is named `"<main comp> (n)"` by AE."""

    layer_name: str | None = None
    """Baked parent-layer display name with `name_set` kept OFF (a
    clipping run bakes the base layer's name); `None` leaves the name
    empty so it inherits the nested comp's name (groups)."""

    collapsed: bool = True
    """Collapse transformations on the parent layer (groups); clipping
    precomps stay uncollapsed."""
