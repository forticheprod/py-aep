"""Resolve a precomp layer's Essential Properties overrides to the source
composition's Essential Graphics controllers.

The override<->controller link is a shared UUID: a precomp layer's
`LIST:OvG2` carries one UUID per override (`Layer.essential_property_uuids`),
each equal to an `EssentialGraphicsController.uuid` on the source composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.essential_graphics import EssentialGraphicsController
    from ..models.layers.av_layer import AVLayer


def resolve_essential_property_controllers(
    layer: AVLayer,
) -> list[EssentialGraphicsController]:
    """Return the source-comp controllers a precomp layer's Essential
    Properties overrides reference, matched by UUID, in override order.

    Returns `[]` when the layer is not a precomp (no `CompItem` source, e.g.
    a text layer or a footage layer), when the source composition has no
    controllers, or when the layer has no overrides. A UUID with no matching
    controller (e.g. a controller removed after the override was created) is
    skipped; the raw UUIDs remain on `Layer.essential_property_uuids`.
    """
    # Local import: models/ have proven layer<->comp circular references.
    from ..models.items.composition import CompItem  # noqa: PLC0415

    uuids = layer.essential_property_uuids
    if not uuids:
        return []
    source = layer.source
    if not isinstance(source, CompItem):
        return []
    by_uuid = {c.uuid: c for c in source.motion_graphics_controllers}
    return [by_uuid[uuid] for uuid in uuids if uuid in by_uuid]
