"""Resolve a precomp layer's Essential Properties overrides to the source
composition's Essential Graphics controllers.

The override<->controller link is a shared UUID: a precomp layer's
`LIST:OvG2` carries one UUID per override (`Layer.essential_property_uuids`),
each equal to an `EssentialGraphicsController.uuid` on the source composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums.general import PropertyType

if TYPE_CHECKING:
    from ..models.essential_graphics import (
        EssentialGraphicsController,
        SourcePropertyRef,
    )
    from ..models.layers.av_layer import AVLayer
    from ..models.project import Project
    from ..models.properties.property import Property
    from ..models.properties.property_group import PropertyGroup

# Essential Graphics controller type for a Media Replacement slot.
_MEDIA_REPLACEMENT_CONTROLLER_TYPE = 14


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


def _resolve_controller_source_layer(
    project: Project,
    controller: EssentialGraphicsController,
) -> AVLayer | None:
    """Resolve the source-composition `AVLayer` that owns a controller's
    controlled property, via the controller's `CCId`/`CLId`.

    Returns `None` when the controller stores no source comp/layer, the comp
    is missing, or no layer matches the stored `layer_id`.
    """
    from ..models.items.composition import CompItem  # noqa: PLC0415
    from ..models.layers.av_layer import AVLayer  # noqa: PLC0415

    if controller.source_comp_id is None or controller.source_layer_id is None:
        return None
    comp = project.items.get(controller.source_comp_id)
    if not isinstance(comp, CompItem):
        return None
    layer = comp.layers_by_id.get(controller.source_layer_id)
    return layer if isinstance(layer, AVLayer) else None


def _resolve_indexed_child(
    group: PropertyGroup,
    ref: SourcePropertyRef,
    project: Project,
) -> Property | PropertyGroup | None:
    """Resolve an indexed path node, or `None` to fall back to by-name.

    AE's index model (verified against AE 2026 output - see
    `resolvers/motion_graphics`): a param inside an EFFECT is addressed by
    its parT position, where slot 0 is the hidden parameter-group header,
    so visible params map to `index - 1` in the project's parT-ordered
    param defs; a child of any other INDEXED group (the Effect Parade,
    Mask Parade, shape Vectors groups, Text Animators) by its plain
    0-based child position. The resolved child must carry the stored match
    name - a disagreement (stale index) returns `None` so the caller falls
    back to by-name resolution.
    """
    if ref.prop_index is None:
        return None
    if group.is_effect:
        defs = project._effect_param_defs.get(group.match_name)
        if defs:
            keys = list(defs)
            pos = ref.prop_index - 1
            if 0 <= pos < len(keys) and keys[pos] == ref.match_name:
                try:
                    return group.property(ref.match_name)
                except KeyError:
                    return None
        return None
    if group.property_type == PropertyType.INDEXED_GROUP:
        children = group.properties
        if 0 <= ref.prop_index < len(children):
            child = children[ref.prop_index]
            if child.match_name == ref.match_name:
                return child
    return None


def _walk_source_property(
    source_layer: AVLayer,
    path: list[SourcePropertyRef],
) -> Property | PropertyGroup | None:
    """Walk a controller's source-property `path` from `source_layer` to the
    exposed leaf.

    A node with `prop_index=None` (AE's by-name marker, `0xFFFFFFFF`)
    resolves by match name. An indexed node resolves through
    `_resolve_indexed_child`, which disambiguates duplicate match names
    (e.g. the same effect applied twice); when the index cannot be
    interpreted it falls back to the first match-name hit, the pre-index
    behavior. Returns `None` if any node fails to resolve (missing child,
    or the path descends past a leaf).
    """
    from ..models.properties.property_group import PropertyGroup  # noqa: PLC0415

    project = source_layer.containing_comp._project
    cur: Property | PropertyGroup = source_layer
    for ref in path:
        if not isinstance(cur, PropertyGroup):
            return None
        child: Property | PropertyGroup | None = None
        if ref.prop_index is not None:
            child = _resolve_indexed_child(cur, ref, project)
        if child is None:
            try:
                child = cur.property(ref.match_name)
            except KeyError:
                return None
        cur = child
    return cur


def _preorder_index(root: PropertyGroup, target: Property) -> int | None:
    """Pre-order position of `target` among all descendants (groups + leaves)
    of `root`, or `None` if not found. Matches the flat OvG2 UUID ordering."""
    from ..models.properties.property_group import PropertyGroup  # noqa: PLC0415

    counter = [0]

    def rec(group: PropertyGroup) -> int | None:
        for child in group.properties:
            pos = counter[0]
            counter[0] += 1
            if child is target:
                return pos
            if isinstance(child, PropertyGroup):
                found = rec(child)
                if found is not None:
                    return found
        return None

    return rec(root)


def resolve_essential_property_controller(
    prop: Property,
) -> EssentialGraphicsController | None:
    """Resolve an Essential Property override leaf to its source-comp controller.

    Walks up to the `ADBE Layer Overrides` root, computes the leaf's PRE-ORDER
    position in the override subtree (groups + leaves) - which aligns 1:1 with
    the flat OvG2 UUID list, the `ADBE Layer Overrides Group` container consuming
    the type-10 Group controller's slot - and matches that UUID to a controller
    on the precomp's source composition. Returns `None` when `prop` is not an
    override leaf or the controller cannot be resolved (e.g. it was removed).
    """
    from ..models.items.composition import CompItem  # noqa: PLC0415
    from ..models.layers.av_layer import AVLayer  # noqa: PLC0415

    root = prop._parent_property
    while root is not None and root.match_name != "ADBE Layer Overrides":
        root = root._parent_property
    if root is None:
        return None
    layer = root._parent_property
    if not isinstance(layer, AVLayer):
        return None
    idx = _preorder_index(root, prop)
    if idx is None:
        return None
    uuids = layer.essential_property_uuids
    if idx >= len(uuids):
        return None
    source = layer.source
    if not isinstance(source, CompItem):
        return None
    return next(
        (c for c in source.motion_graphics_controllers if c.uuid == uuids[idx]),
        None,
    )


def resolve_essential_property_source(
    prop: Property,
) -> Property | PropertyGroup | AVLayer | None:
    """Resolve an Essential Property override leaf to its originating source.

    For a media-replacement override (`ADBE Layer Source Alternate`, controller
    type 14) this returns the source-composition `AVLayer` the slot points at -
    matched via the override's controller `source_comp_id` (`CCId`) and
    `source_layer_id` (`CLId`). For a Property-source controller (created from a
    Property rather than Media Replacement Footage) it walks the controller's
    source-property path by match name and returns the source `Property` (or
    `PropertyGroup` for a grouped controller).

    Returns `None` when the property is not such an override or the source
    cannot be resolved.
    """
    controller = resolve_essential_property_controller(prop)
    if controller is None or prop._composition is None:
        return None
    source_layer = _resolve_controller_source_layer(
        prop._composition._project, controller
    )
    if source_layer is None:
        return None
    if controller.controller_type == _MEDIA_REPLACEMENT_CONTROLLER_TYPE:
        return source_layer
    # Property-source controller: the exposed leaf is the tail of the
    # controlled-property path, resolved by match name from the source layer.
    if not controller.source_property_path:
        return None
    return _walk_source_property(source_layer, controller.source_property_path)
