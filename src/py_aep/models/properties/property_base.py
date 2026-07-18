from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

from py_aep.enums import PropertyType

from ...ae_version import get_ae_version_major
from ...binary.chunk import ListChunk
from ...binary.mutations import clone_chunk_tree
from ...binary.property_chunks import TDSN_SENTINEL, TdmnChunk
from ...binary.utils import find_by_type, index_by_identity
from ...data.match_names import MATCH_NAME_TO_AUTO_NAME
from ..descriptors import ChunkField
from ..validators import validate_bool, validate_name

if TYPE_CHECKING:
    from ...binary.chunk import Chunk
    from ...binary.misc_chunks import MkifChunk
    from ...binary.property_chunks import TdsbChunk
    from ...binary.scalar_chunks import Utf8Chunk
    from ..layers.layer import Layer
    from .mask_property_group import MaskPropertyGroup
    from .property import Property
    from .property_group import PropertyGroup


# Match names of groups that support add/remove/move/duplicate on children.
# "ADBE Vectors Group" is a nested shape group's own contents.
_INDEXED_GROUP_MATCH_NAMES: frozenset[str] = frozenset(
    {
        "ADBE Effect Parade",
        "ADBE Mask Parade",
        "ADBE Effect Mask Parade",
        "ADBE Text Animators",
        "ADBE Text Selectors",
        "ADBE Root Vectors Group",
        "ADBE Vectors Group",
    }
)


# Text animator + selectors expose an enable toggle (canSetEnabled).
_TEXT_ANIMATOR_TOGGLEABLE: frozenset[str] = frozenset(
    {
        "ADBE Text Animator",
        "ADBE Text Selector",
        "ADBE Text Wiggly Selector",
        "ADBE Text Expressible Selector",
    }
)


def _validate_enabled(value: bool, obj: PropertyBase) -> None:
    validate_bool(value)
    if not obj.can_set_enabled:
        raise AttributeError("'enabled' is read-only when 'can_set_enabled' is False.")


def _renumber_mask_auto_names(parent: PropertyGroup) -> None:
    """Reassign positional `Mask {i}` fallback names after a mutation.

    The parser numbers mask atoms by position, so a reparse after
    remove/move/duplicate would renumber them; keep the in-memory
    fallbacks consistent. Explicit user names (stored in tdsn) take
    precedence and are unaffected.
    """
    i = 1
    for child in parent._properties:
        if child._is_mask:
            child._auto_name = f"Mask {i}"
            i += 1


def _assign_duplicate_mask_identity(
    source: PropertyBase, new_mask: PropertyBase, parent: PropertyGroup
) -> None:
    """Give a duplicated mask a fresh per-layer id and matching name.

    AE assigns the copy the next free mask id (highest existing + 1) and
    names it `'{base} {new_id}'`, where `base` is the source name with any
    trailing number stripped (verified in AE 2026: `'Mask 1'` -> id 2
    `'Mask 2'`; `'Eyes'` -> id 2 `'Eyes 2'`; with ids `[1, 3]`, `'Mask 1'`
    -> id 4 `'Mask 4'`). A plain clone keeps the source's id and name,
    colliding with it.
    """
    siblings = [
        cast("MaskPropertyGroup", m)
        for m in parent._properties
        if m._is_mask and m is not new_mask
    ]
    new_id = max((m._mkif.mask_id for m in siblings), default=0) + 1
    cast("MaskPropertyGroup", new_mask)._mkif.mask_id = new_id
    base = re.sub(r" \d+$", "", source.name)
    new_mask.name = f"{base} {new_id}"


class PropertyBase:
    """Abstract base class for both [Property][] and [PropertyGroup][].

    Info:
        `PropertyBase` is the base class for both [Property][] and
        [PropertyGroup][], so `PropertyBase` attributes and methods are available
        when working with properties and property groups.

    See: https://ae-scripting.docsforadobe.dev/property/propertybase/
    """

    enabled = ChunkField.bool(
        "_tdsb",
        "enabled",
        default=True,
        validate=_validate_enabled,
    )
    """Corresponds to the setting of the eyeball icon. Read / Write."""

    def __init__(
        self,
        *,
        _tdsb: TdsbChunk | None,
        _name_utf8: Utf8Chunk | None = None,
        parent_property: PropertyGroup | None = None,
        match_name: str,
        property_depth: int,
        auto_name: str | None = None,
    ) -> None:
        self._tdsb = _tdsb
        self._name_utf8 = _name_utf8
        self._match_name = match_name
        self._auto_name = auto_name
        self._property_depth = property_depth
        self._tdmn: TdmnChunk | None = None

        self._name: str | None = None

        self._elided = False
        self._is_effect = False
        self._is_mask = False
        self._parent_property = parent_property
        self._property_type = PropertyType.NAMED_GROUP

    def _ensure_materialized(self) -> None:
        """Flip synthetic flags so backing chunks become visible to write_aep().

        No-op on `PropertyBase`. Overridden by `Property` and
        `PropertyGroup` to flip synthetic flags on backing chunks on
        first user write.
        """

    def _chunk_body(self) -> Chunk | None:
        """The body chunk that follows this property's `tdmn` in the parent.

        `tdbs` for a [Property][], `tdgp` for a [PropertyGroup][].
        Overridden by subclasses; `None` on the base.
        """
        return None

    def _is_live(self) -> bool:
        """Whether this property's chunks are serialized (not synthetic)."""
        return self._tdsb is None or not self._tdsb.synthetic

    def _reposition_canonically(self) -> None:
        """Move this property's `(tdmn, body)` chunks to canonical order.

        Synthesized properties are appended just before the group-end
        marker at synthesis time, which does not match After Effects'
        canonical property order. When such a property is materialized,
        re-anchor its chunk pair right before the nearest following
        already-serialized (non-synthetic) sibling, so the written order
        is what AE expects. Synthetic siblings (skipped on write) are
        ignored as anchors.

        Anchoring uses the sibling's `tdmn` (unique per property) rather
        than its body chunk, because separation followers (e.g.
        `ADBE Position_0` / `_1`) alias the same body chunk.

        All chunk lookups use object identity, not `==`: attrs gives
        chunks structural equality, and an empty group body (e.g. a
        text animator's Selectors vs Properties tdgp) is structurally
        identical to a sibling's, so `.remove()`/`.index()` would act on
        the wrong chunk.
        """
        parent = self._parent_property
        if parent is None:
            return
        tdgp = getattr(parent, "_tdgp", None)
        tdmn = self._tdmn
        body = self._chunk_body()
        if tdgp is None or tdmn is None or body is None:
            return
        chunks = tdgp.chunks
        if not any(c is tdmn for c in chunks) or not any(c is body for c in chunks):
            return
        siblings = parent._properties
        idx = next((i for i, s in enumerate(siblings) if s is self), None)
        if idx is None:
            return
        chunks[:] = [c for c in chunks if c is not tdmn and c is not body]

        pos: int | None = None
        # Insert right before the nearest following live sibling's tdmn.
        for sib in siblings[idx + 1 :]:
            if sib._is_live() and sib._tdmn is not None:
                sib_pos = next(
                    (i for i, c in enumerate(chunks) if c is sib._tdmn), None
                )
                if sib_pos is not None:
                    pos = sib_pos
                    break
        if pos is None:
            # No live following sibling: insert before the group-end marker.
            pos = len(chunks)
            for i in range(len(chunks) - 1, -1, -1):
                c = chunks[i]
                if (
                    c.chunk_type == "tdmn"
                    and getattr(c, "value", None) == "ADBE Group End"
                ):
                    pos = i
                    break
        chunks.insert(pos, tdmn)
        chunks.insert(pos + 1, body)

    @property
    def selected(self) -> bool:
        """When `True`, the property is selected. Read / Write.

        Note:
            Property selection is stored in the `.aep` binary format but very complex.
            Parsed projects report `False` for now.
        """
        return False

    @property
    def match_name(self) -> str:
        """A special name for the property used to build unique naming
        paths. The match name is not displayed, but you can refer to it
        in scripts. Every property has a unique match-name identifier.
        Read-only."""
        return self._match_name

    @property
    def property_depth(self) -> int:
        """The number of levels of parent groups between this property
        and the containing layer. The value is 0 for a layer.
        Read-only."""
        return self._property_depth

    @property
    def elided(self) -> bool:
        """When `True`, the property is not shown in the UI. An elided
        property is still present in the timeline but hidden from view.
        Read-only."""
        return self._elided

    @property
    def is_effect(self) -> bool:
        """When `True`, this property is an effect [PropertyGroup][].
        Read-only."""
        return self._is_effect

    @property
    def is_mask(self) -> bool:
        """When `True`, this property is a mask [PropertyGroup][].
        Read-only."""
        return self._is_mask

    @property
    def property_type(self) -> PropertyType:
        """The type of this property. One of `PropertyType.PROPERTY`,
        `PropertyType.NAMED_GROUP`, or `PropertyType.INDEXED_GROUP`.
        Read-only."""
        return self._property_type

    @property
    def parent_property(self) -> PropertyGroup | None:
        """The parent [PropertyGroup][] of this property, or `None` for
        top-level layer property groups. Read-only."""
        return self._parent_property

    @property
    def auto_name(self) -> str:
        """The automatic (display) name derived from `match_name`."""
        if self._auto_name is not None:
            return self._auto_name
        return MATCH_NAME_TO_AUTO_NAME.get(self.match_name, self.match_name)

    @property
    def name(self) -> str:
        """Display name of the property. Read / Write."""
        if self._name is not None:
            return self._name
        if self._name_utf8 is not None:
            text: str = self._name_utf8.value.split("\0")[0]
            if text and text != TDSN_SENTINEL:
                return text
        return self.auto_name

    @name.setter
    def name(self, value: str) -> None:
        validate_name(value)

        self._ensure_materialized()
        self._name = value
        assert self._name_utf8 is not None
        self._name_utf8.value = value

    @property
    def is_name_set(self) -> bool:
        """`True` if the name has been explicitly set by the user. Read-only."""
        if self._name is not None:
            return True
        if self._name_utf8 is not None:
            text: str = self._name_utf8.value.split("\0")[0]
            return bool(text) and text != TDSN_SENTINEL
        return False

    @property
    def active(self) -> bool:
        """Same as enabled."""
        return self.enabled

    @property
    def property_index(self) -> int | None:
        """The 0-based position of this property within its parent group.

        Returns `None` for layers (property depth 0).

        Warning:
            Unlike ExtendScript (1-based), this uses Python's 0-based
            convention so that `group.properties[prop.property_index]`
            works directly.
        Read-only.
        """
        if self.property_depth == 0 or self.parent_property is None:
            return None
        return self.parent_property.properties.index(
            cast("Property | PropertyGroup", self)
        )

    @property
    def can_set_enabled(self) -> bool:
        """`True` if the `enabled` attribute value can be set.

        This is `True` for all layers, effect property groups, shape
        vector groups, text path options, and the Layer Styles group
        and its individual styles. Read-only.
        """
        if self.property_depth == 0:
            return True
        if self.is_effect:
            return True
        mn = self.match_name
        if mn == "ADBE Text Path Options":
            return True
        # A text animator and each text selector can be toggled.
        if mn in _TEXT_ANIMATOR_TOGGLEABLE:
            return True
        # The Layer Styles group and each individual style (match names
        # like "dropShadow/enabled") report canSetEnabled only when
        # applied to the layer. AE writes all ten styles as identical
        # empty groups, so the only "applied" signal is the enabled
        # flag: canSetEnabled tracks it exactly (group = any style
        # enabled). Blending Options ("ADBE Blend Options Group") is
        # excluded and always reports False.
        if mn == "ADBE Layer Styles" or mn.endswith("/enabled"):
            return self.enabled
        if mn.startswith("ADBE Vector") and mn not in (
            "ADBE Vectors Group",
            "ADBE Vector Transform Group",
            "ADBE Vector Repeater Transform",
            "ADBE Vector Wiggler Transform",
            "ADBE Vector Materials Group",
        ):
            return self.property_type in (
                PropertyType.NAMED_GROUP,
                PropertyType.INDEXED_GROUP,
            )
        return False

    @property
    def _containing_layer(self) -> Layer:
        """Walk up the parent_property chain to find the containing layer.

        Returns the Layer object (detected by having `_ldta`), or raises
        a ValueError if the property is not attached to a layer.
        """
        node = self.parent_property
        while node is not None:
            if hasattr(node, "_ldta"):
                return cast("Layer", node)
            node = node.parent_property
        raise ValueError("Property is not attached to a layer")

    def _is_in_effect(self) -> bool:
        """Check if this property is inside an effect PropertyGroup."""
        node = self.parent_property
        while node is not None:
            if node.is_effect:
                return True
            if hasattr(node, "_ldta"):
                break
            node = node.parent_property
        return False

    @property
    def is_modified(self) -> bool:
        """`True` if this property has been changed since its creation.

        A property is considered modified if its value differs from the
        default, if it has keyframes, or if an expression is enabled.
        A property group is modified if any of its children are modified,
        or if it is an indexed group with children (adding items to an
        indexed group like Effects or Masks is itself a modification).
        """
        return False

    def _can_mutate(self) -> tuple[PropertyGroup, ListChunk]:
        """Validate and return the parent group and its backing tdgp.

        Only children of indexed groups (effects, masks, shape contents,
        text animators) can be removed/moved/duplicated.
        """
        parent = self._parent_property
        if parent is None:
            raise ValueError("Cannot mutate a root property")
        if parent.property_type != PropertyType.INDEXED_GROUP:
            raise ValueError(
                f"Cannot mutate property in non-indexed group '{parent.match_name}'"
            )
        # Indexed groups always have a backing tdgp.
        return parent, cast("ListChunk", parent._tdgp)

    def _backing_list_chunk(self, parent_tdgp: ListChunk) -> ListChunk:
        """The LIST chunk in the parent's chunk list backing this property.

        For regular properties this is `_tdbs`, for regular groups `_tdgp`.
        For effects (where the model's `_tdgp` is inside a wrapping
        `LIST:sspc`), this returns the sspc chunk.
        """
        chunk: ListChunk | None = getattr(self, "_tdbs", None) or getattr(
            self, "_tdgp", None
        )
        assert chunk is not None
        # Identity check - attrs __eq__ is structural, so .index() / `in`
        # would give false positives for chunks with identical fields.
        if any(c is chunk for c in parent_tdgp.chunks):
            return chunk

        # Effect case: _tdgp is inside a LIST:sspc wrapper
        for c in parent_tdgp.chunks:
            if (
                isinstance(c, ListChunk)
                and c.list_type == "sspc"
                and any(inner is chunk for inner in c.chunks)
            ):
                return c

        return chunk

    def _find_chunk_span(self, parent_tdgp: ListChunk) -> tuple[int, int]:
        """Find the [start, end) index span of this property's chunks.

        Returns the index range covering the preceding `tdmn` chunk, any
        auxiliary chunks between it and the backing LIST chunk (e.g.
        `mkif` for masks), and the backing LIST chunk itself. The span
        is suitable for slice deletion.
        """
        start = index_by_identity(parent_tdgp.chunks, self._tdmn)
        backing = self._backing_list_chunk(parent_tdgp)
        end = index_by_identity(parent_tdgp.chunks, backing)
        return start, end + 1

    def remove(self) -> None:
        """Remove this property from its parent group.

        Only valid for children of indexed groups (effects, masks, shape
        contents, text animators).

        Raises:
            ValueError: If this property is not in an indexed group.
        """
        parent, parent_tdgp = self._can_mutate()
        start, end = self._find_chunk_span(parent_tdgp)
        del parent_tdgp.chunks[start:end]
        parent.properties.remove(cast("Property | PropertyGroup", self))
        if self._is_mask:
            _renumber_mask_auto_names(parent)

    def move_to(self, new_index: int) -> None:
        """Move this property to a new 0-based index within its parent group.

        Only valid for children of indexed groups.

        Args:
            new_index: The target 0-based position.

        Raises:
            ValueError: If this property is not in an indexed group.
            IndexError: If `new_index` is out of range.
        """
        parent, parent_tdgp = self._can_mutate()

        num_props = len(parent.properties)
        if not 0 <= new_index < num_props:
            raise IndexError(f"Index {new_index} out of range [0, {num_props})")

        child = cast("Property | PropertyGroup", self)
        current_index = parent.properties.index(child)
        if current_index == new_index:
            return

        # Extract chunk span
        start, end = self._find_chunk_span(parent_tdgp)
        chunk_span = parent_tdgp.chunks[start:end]
        del parent_tdgp.chunks[start:end]

        # Remove from model list
        parent.properties.remove(child)

        # Find chunk insertion point: before the target property's span
        if new_index >= len(parent.properties):
            parent_tdgp.chunks.extend(chunk_span)
            parent.properties.append(child)
        else:
            target = parent.properties[new_index]
            target_start, _ = target._find_chunk_span(parent_tdgp)
            for i, c in enumerate(chunk_span):
                parent_tdgp.chunks.insert(target_start + i, c)
            parent.properties.insert(new_index, child)
        if self._is_mask:
            _renumber_mask_auto_names(parent)

    def duplicate(self) -> PropertyBase:
        """Duplicate this property within its parent group.

        The duplicate is inserted immediately after the original.
        Only valid for children of indexed groups (see [PropertyType][]).

        Returns:
            The newly created [PropertyBase][].

        Raises:
            ValueError: If this property is not in an indexed group.
        """
        parent, parent_tdgp = self._can_mutate()

        # Clone the full chunk span: tdmn, auxiliary chunks (e.g. mkif
        # for masks) and the backing LIST chunk.
        start, end = self._find_chunk_span(parent_tdgp)
        cloned = [clone_chunk_tree(c) for c in parent_tdgp.chunks[start:end]]

        # Insert after original in parent's chunk list
        for i, c in enumerate(cloned):
            parent_tdgp.chunks.insert(end + i, c)

        # Re-parse the cloned chunks into a model
        new_prop = self._parse_clone(cloned, parent)

        # Insert in model list after original
        model_idx = parent.properties.index(cast("Property | PropertyGroup", self))
        parent.properties.insert(
            model_idx + 1, cast("Property | PropertyGroup", new_prop)
        )

        if self._is_mask:
            _assign_duplicate_mask_identity(self, new_prop, parent)
            _renumber_mask_auto_names(parent)
        return new_prop

    def _parse_clone(
        self,
        cloned: list[Chunk],
        parent: PropertyGroup,
    ) -> PropertyBase:
        """Re-parse cloned chunks into a model instance.

        Uses the parser infrastructure to rebuild the correct model
        hierarchy from cloned binary chunks.

        Args:
            cloned: The cloned chunk span - the `tdmn` first, the
                backing LIST chunk last, auxiliary chunks (e.g. `mkif`)
                in between.
            parent: The parent group of the clone.
        """
        from ...parsers.property import (  # noqa: PLC0415
            _parse_mask_atom,
            parse_property_group,
        )
        from ...parsers.property_value import parse_property  # noqa: PLC0415

        # Determine the composition context
        layer = self._containing_layer
        comp = layer.containing_comp

        # Get effect param defs from the project
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] = {}
        project = comp._project
        if project is not None:
            effect_param_defs = project._effect_param_defs

        tdmn = cast("TdmnChunk", cloned[0])
        list_chunk = cast("ListChunk", cloned[-1])
        if self._is_mask:
            mkif = cast(
                "MkifChunk",
                find_by_type(chunks=cloned, chunk_type="mkif"),
            )
            result: PropertyBase = _parse_mask_atom(
                tdgp_chunk=list_chunk,
                mkif_chunk=mkif,
                property_depth=self._property_depth,
                effect_param_defs=effect_param_defs,
                composition=comp,
                tdmn=tdmn,
            )
        elif list_chunk.list_type == "tdbs":
            result = parse_property(
                tdbs_chunk=list_chunk,
                match_name=self._match_name,
                composition=comp,
                property_depth=self._property_depth,
                tdmn=tdmn,
            )
        elif list_chunk.list_type == "sspc":
            from ...parsers.effect import parse_effect  # noqa: PLC0415

            result = parse_effect(
                sspc_chunk=list_chunk,
                group_match_name=self._match_name,
                property_depth=self._property_depth,
                effect_param_defs=effect_param_defs,
                composition=comp,
                tdmn=tdmn,
            )
        elif list_chunk.list_type == "tdgp":
            result = parse_property_group(
                tdgp_chunk=list_chunk,
                group_match_name=self._match_name,
                property_depth=self._property_depth,
                effect_param_defs=effect_param_defs,
                composition=comp,
                tdmn=tdmn,
            )
        else:
            raise ValueError(f"Unexpected backing chunk type '{list_chunk.list_type}'")
        # clone_chunk_tree strips synthetic chunks, so synthesized children
        # (e.g. Mask Feather/Opacity) are missing from the clone; re-arm
        # deferred synthesis to fill them on first access, like a fresh parse.
        from .property_group import PropertyGroup  # noqa: PLC0415

        if isinstance(result, PropertyGroup):
            result._deferred_ae_major = get_ae_version_major(comp)
        result._parent_property = parent
        return result
