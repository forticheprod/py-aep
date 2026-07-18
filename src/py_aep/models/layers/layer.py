from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from py_aep.enums import AutoOrientType, Label, LayerType

from ...binary.chunk import ListChunk
from ...binary.item_chunks import CmtaChunk
from ...binary.mutations import build_gide_list, clone_chunk_tree, rewrite_owner_tdpi
from ...binary.property_chunks import TdmnChunk, TdsbChunk, TdsnChunk
from ...binary.scalar_chunks import Utf8Chunk
from ...binary.utils import find_by_type, index_by_identity
from ...parsers.property import parse_properties
from ...parsers.utils import get_match_name_runs
from ...resolvers.transform import (
    Mat4,
    build_world_matrix,
    decompose_transform,
)
from ..descriptors import ChunkField
from ..naming import auto_name
from ..properties.property import Property
from ..properties.property_base import PropertyBase
from ..properties.property_group import PropertyGroup
from ..validators import (
    validate_int,
    validate_number,
    validate_string,
)

if TYPE_CHECKING:
    from ...binary.layer_chunks import LdtaChunk
    from ..items.composition import CompItem
    from ..properties.marker import MarkerValue


logger = logging.getLogger(__name__)


class Layer(PropertyGroup):
    """
    The `Layer` object provides access to layers within compositions.

    Info:
        `Layer` is a subclass of [PropertyGroup][], which is a subclass of
        [PropertyBase][py_aep.models.properties.property_base.PropertyBase]. All
        methods and attributes of [PropertyGroup][], in addition to those listed below,
        are available when working with `Layer` objects.

    Info:
        `Layer` is the base class for [CameraLayer][] object, [LightLayer][]
        object and [AVLayer][] object, so `Layer` attributes and methods are
        available when working with all layer types.

    See: https://ae-scripting.docsforadobe.dev/layer/layer/
    """

    _LAYER_MATCH_NAMES: dict[LayerType, str] = {
        LayerType.AV: "ADBE AV Layer",
        LayerType.LIGHT: "ADBE Light Layer",
        LayerType.CAMERA: "ADBE Camera Layer",
        LayerType.TEXT: "ADBE Text Layer",
        LayerType.SHAPE: "ADBE Vector Layer",
        LayerType.THREE_D_MODEL: "ADBE 3D Model Layer",
        LayerType.PARAMETRIC_MESH: "ADBE3D ParametricMeshLayer",
    }

    _LAYER_TYPE_NAMES: dict[LayerType, str] = {
        LayerType.AV: "AVLayer",
        LayerType.LIGHT: "LightLayer",
        LayerType.CAMERA: "CameraLayer",
        LayerType.TEXT: "Layer",
        LayerType.SHAPE: "Layer",
        LayerType.THREE_D_MODEL: "Layer",
        LayerType.PARAMETRIC_MESH: "ParametricMeshLayer",
    }

    enabled = ChunkField.bool(
        "_ldta",
        "enabled",
    )
    """When `True`, the layer is enabled. Overrides `PropertyBase.enabled`
    to read from the ldta chunk. Read / Write."""

    id = ChunkField[int]("_ldta", "layer_id", read_only=True)
    """Unique and persistent identification number used internally to
    identify a Layer between sessions. Read-only."""

    label = ChunkField.enum(Label, "_ldta", "label")
    """The label color. Colors are represented by their number (0 for None,
    or 1 to 16 for one of the preset colors in the Labels preferences).
    Read / Write."""

    locked = ChunkField.bool(
        "_ldta",
        "locked",
    )
    """When `True`, the layer is locked. This corresponds to the lock toggle
    in the Layer panel. Read / Write."""

    null_layer = ChunkField[bool]("_ldta", "null_layer", read_only=True)
    """When `True`, the layer was created as a null object. Read-only."""

    _parent_id = ChunkField[int]("_ldta", "parent_id")
    """The ID of the layer's parent layer. `0` if the layer has no parent."""

    shy = ChunkField.bool(
        "_ldta",
        "shy",
    )
    """When `True`, the layer is "shy", meaning that it is hidden in the
    Layer panel if the composition's "Hide all shy layers" option is
    toggled on. Read / Write."""

    solo = ChunkField.bool(
        "_ldta",
        "solo",
    )
    """When `True`, the layer is soloed. Read / Write."""

    start_time = ChunkField[float]("_ldta", "start_time")
    """The start time of the layer, expressed in composition time (seconds).
    Read / Write."""

    stretch = ChunkField[float]("_ldta", "stretch")
    """The layer's time stretch, expressed as a percentage. A value of 100
    means no stretch. Values between 0 and 1 are set to 1, and values
    between -1 and 0 (not including 0) are set to -1. Read / Write."""

    auto_orient = ChunkField.enum(
        AutoOrientType,
        "_ldta",
        "auto_orient",
    )
    """The type of automatic orientation to perform for the layer.
    Read / Write."""

    # Use identity-based equality to avoid comparing all fields recursively,
    # which could produce unexpected results or hit circular references.
    __eq__ = object.__eq__
    __hash__ = object.__hash__

    def __init__(
        self,
        *,
        _ldta: LdtaChunk,
        _cmta: CmtaChunk | None,
        _name_utf8: Utf8Chunk,
        _layer_list: ListChunk,
        containing_comp: CompItem,
        properties: list[Property | PropertyGroup],
        essential_property_uuids: list[str],
    ) -> None:
        self._ldta = _ldta
        self._cmta = _cmta
        self._layer_list = _layer_list
        self.essential_property_uuids: list[str] = essential_property_uuids
        """UUIDs of Essential Properties overrides on this layer.

        Each UUID corresponds to an [EssentialGraphicsController][] in
        the source composition's Essential Graphics panel.
        """

        try:
            layer_type_raw = _ldta.layer_type
            layer_type = LayerType(layer_type_raw)
            match_name = self._LAYER_MATCH_NAMES[layer_type]
        except (ValueError, KeyError):
            logger.warning(
                "Unknown layer type %d for layer '%s' in comp '%s'. Defaulting to 'ADBE AV Layer'.",
                layer_type_raw,
                _name_utf8.value,
                containing_comp.name,
            )
            match_name = "ADBE AV Layer"

        super().__init__(
            _tdsb=None,
            _name_utf8=_name_utf8,
            match_name=match_name,
            auto_name="",
            property_depth=0,
            properties=properties,
        )

        self._containing_comp = containing_comp

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        *,
        ldta: LdtaChunk,
        name: str,
        containing_comp: CompItem,
        root_tdgp_extra: list[Any] | None = None,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> Layer:
        from ...synthesis.core import synthesize_layer_properties  # noqa: PLC0415

        validate_string(name)

        name_utf8 = Utf8Chunk(value=name)
        tdgp_chunks: list[Any] = [
            TdsbChunk(),
            TdsnChunk.new(),
        ]
        if root_tdgp_extra:
            tdgp_chunks.extend(root_tdgp_extra)
        # AE terminates every tdgp match-name stream with ADBE Group End
        # and rejects layers whose root tdgp lacks it ("missing data in
        # file"). Synthesized children are inserted before this marker.
        tdgp_chunks.append(TdmnChunk(value="ADBE Group End"))
        root_tdgp = ListChunk(list_type="tdgp", chunks=tdgp_chunks)
        gide, _lhd3, _inner = build_gide_list()
        layer_list = ListChunk(
            list_type="Layr",
            chunks=[ldta, name_utf8, root_tdgp, gide],
        )

        layer = cls(
            _ldta=ldta,
            _cmta=None,
            _name_utf8=name_utf8,
            _layer_list=layer_list,
            containing_comp=containing_comp,
            properties=[],
            essential_property_uuids=[],
        )
        layer._tdgp = root_tdgp

        props = parse_properties(
            match_name_runs=get_match_name_runs(root_tdgp),
            child_depth=1,
            effect_param_defs=effect_param_defs or {},
            composition=containing_comp,
        )
        layer._properties = props
        for child in props:
            child._parent_property = layer

        synthesize_layer_properties(layer)
        return layer

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"enabled={self.enabled!r}, "
            f"match_name={self.match_name!r}, "
            f"name={self.name!r})"
        )

    @PropertyBase.name.setter  # type: ignore[attr-defined]
    def name(self, value: str) -> None:
        PropertyBase.name.fset(self, value)  # type: ignore[attr-defined]
        self._ldta.layer_name = value
        # AE sets _layer_flags_0 bit 0 only for a SOURCE-BACKED layer whose name
        # differs from the source item's name. It stays 0 for sourceless layers
        # (camera/light/text/shape) even when named, for an empty (source-
        # inherited) name, and when the name is set back to the source item's
        # own name (verified against the MyGroup precomp layer in
        # grouped_layers_comp.aep, where name == source comp name -> bit 0).
        # Parametric mesh layers are the exception among sourceless layers:
        # renaming one in AE 2026 sets the bit, and it STAYS set even when
        # renamed back to the original default name (headless rename
        # experiment on parametric_meshes.aep), matching addParametricMesh's
        # explicit-name behavior.
        source_id = self._ldta.source_id
        if self._ldta.layer_type == LayerType.PARAMETRIC_MESH:
            self._ldta.name_set = True
        elif not value or source_id == 0:
            self._ldta.name_set = False
        else:
            source_item = self.containing_comp._project.items.get(source_id)
            self._ldta.name_set = getattr(source_item, "name", None) != value

    @property
    def comment(self) -> str:
        """A descriptive comment for the layer. Read / Write."""
        if self._cmta is None:
            return ""
        return self._cmta.value

    @comment.setter
    def comment(self, value: str) -> None:
        validate_string(value)
        if self._cmta is not None:
            self._cmta.value = value
        elif value:
            chunk = CmtaChunk()
            chunk.value = value
            self._layer_list.chunks.append(chunk)
            self._cmta = chunk

    @property
    def containing_comp(self) -> CompItem:
        """The composition that contains this layer. Read-only."""
        return self._containing_comp

    @property
    def layer_type(self) -> str:
        """The type of layer. Matches ExtendScript `layerType` values:
        `"AVLayer"`, `"LightLayer"`, `"CameraLayer"`,
        `"ParametricMeshLayer"`, or `"Layer"`. Read-only."""
        return self._LAYER_TYPE_NAMES.get(LayerType(self._ldta.layer_type), "AVLayer")

    @property
    def time(self) -> float:
        """The current time of the layer, expressed in composition time
        (seconds). Read-only."""
        return self._containing_comp.time

    @property
    def frame_time(self) -> int:
        """The current time of the layer, expressed in composition time
        (frames). Read-only."""
        return self._containing_comp.frame_time

    @property
    def _stretch_factor(self) -> float:
        stretch = self.stretch
        return stretch / 100.0 if stretch != 0.0 else 1.0

    @property
    def in_point(self) -> float:
        """The "in" point of the layer, expressed in composition time
        (seconds). Read / Write."""
        return float(self.start_time + self._ldta.in_point * self._stretch_factor)

    @in_point.setter
    def in_point(self, value: float) -> None:
        validate_number(value)
        self._set_raw_in_point(value)

    @property
    def out_point(self) -> float:
        """The "out" point of the layer, expressed in composition time
        (seconds). Read / Write."""
        return float(self.start_time + self._ldta.out_point * self._stretch_factor)

    @out_point.setter
    def out_point(self, value: float) -> None:
        validate_number(value)
        self._set_raw_out_point(value)

    @property
    def frame_in_point(self) -> int:
        """The "in" point of the layer, expressed in composition time
        (frames). Read / Write."""
        return round(self.in_point * self.containing_comp.frame_rate)

    @frame_in_point.setter
    def frame_in_point(self, value: int) -> None:
        validate_int(value)
        self.in_point = value / self.containing_comp.frame_rate

    @property
    def frame_out_point(self) -> int:
        """The "out" point of the layer, expressed in composition time
        (frames). Read / Write."""
        return round(self.out_point * self.containing_comp.frame_rate)

    @frame_out_point.setter
    def frame_out_point(self, value: int) -> None:
        validate_int(value)
        self.out_point = value / self.containing_comp.frame_rate

    @property
    def frame_start_time(self) -> int:
        """The start time of the layer, expressed in composition time
        (frames). Read / Write."""
        return round(self.start_time * self.containing_comp.frame_rate)

    @frame_start_time.setter
    def frame_start_time(self, value: int) -> None:
        validate_int(value)
        self.start_time = value / self.containing_comp.frame_rate

    @property
    def index(self) -> int:
        """The 0-based index position of the layer in its containing comp.

        Warning:
            Unlike ExtendScript (1-based), this uses Python's 0-based
            convention so that `comp.layers[layer.index]` works directly.
        """
        return self.containing_comp.layers.index(self)

    @property
    def has_video(self) -> bool:
        """`True` if the layer has a video switch in the Timeline panel.

        Always `False` for [CameraLayer][] and [LightLayer][] objects.
        """
        return False

    @property
    def adjustment_layer(self) -> bool:
        """`True` if the layer is an adjustment layer.

        Always `False` for [CameraLayer][] and [LightLayer][] objects.
        Overridden in [AVLayer][] to read from the binary chunk.
        """
        return False

    @property
    def environment_layer(self) -> bool:
        """`True` if the layer is an environment layer.

        Always `False` for [CameraLayer][] and [LightLayer][] objects.
        Overridden in [AVLayer][] to read from the binary chunk.
        """
        return False

    @property
    def active(self) -> bool:
        """
        When `True`, the layer is active at the current time.

        Overrides [PropertyBase.active][] to evaluate
        [active_at_time][] at [time][].
        """
        return self.active_at_time(self.time)

    @property
    def marker(self) -> Property | None:
        """The layer's marker property.

        A [Property][py_aep.models.properties.property.Property] with
        `match_name="ADBE Marker"` whose keyframes hold marker values.
        `None` when the layer has no markers.
        """
        try:
            prop = self["ADBE Marker"]
        except KeyError:
            return None
        return cast("Property", prop)

    @property
    def markers(self) -> list[MarkerValue]:
        """A flat list of [MarkerValue][] objects for this layer.

        Shortcut for accessing marker data without navigating the property
        tree. Returns an empty list when the layer has no markers.

        Example:
            ```python
            for marker in layer.markers:
                print(marker.comment)
            ```
        """
        if self.marker is None:
            return []
        return cast(
            "list[MarkerValue]",
            [kf.value for kf in self.marker.keyframes],
        )

    def remove_all_markers(self) -> None:
        """Remove all markers from this layer.

        A no-op when the layer has no markers.
        """
        if self.marker is not None:
            self.marker.remove_all_keys()

    @property
    def transform(self) -> PropertyGroup:
        """
        Contains a layer's transform properties.

        This is the Transform `PropertyGroup` (match name
        `ADBE Transform Group`). Individual transform properties (Position,
        Scale, Rotation, etc.) are accessible via
        [properties][PropertyGroup.properties].
        """
        group = self["ADBE Transform Group"]
        assert isinstance(group, PropertyGroup)
        return group

    @property
    def effects(self) -> PropertyGroup | None:
        """
        Contains a layer's effects.

        This is the Effects `PropertyGroup` (match name `ADBE Effect Parade`).
        Each child in [properties][PropertyGroup.properties] is itself a
        [PropertyGroup][] representing one effect. `None` when the layer has no
        effects.
        """
        try:
            group = self["ADBE Effect Parade"]
        except KeyError:
            return None
        if not isinstance(group, PropertyGroup) or not group.properties:
            return None
        return group

    @property
    def masks(self) -> PropertyGroup | None:
        """
        Contains a layer's masks.

        This is the Masks `PropertyGroup` (match name `ADBE Mask Parade`).
        Each child in [properties][PropertyGroup.properties] is itself a
        [PropertyGroup][] representing one mask. `None` when the layer has no
        masks.
        """
        try:
            group = self["ADBE Mask Parade"]
        except KeyError:
            return None
        if not isinstance(group, PropertyGroup) or not group.properties:
            return None
        return group

    @property
    def text(self) -> PropertyGroup | None:
        """Contains a layer's text properties (if any)."""
        try:
            group = self["ADBE Text Properties"]
        except KeyError:
            return None
        if isinstance(group, PropertyGroup):
            return group
        return None

    def _validate_parent(self, new_parent: Layer | None) -> None:
        """Reject parent assignments ExtendScript refuses: a layer from
        another comp, the layer itself, or any of its own descendants
        (which would create a parenting cycle)."""
        if new_parent is None:
            return
        if not isinstance(new_parent, Layer):
            raise ValueError("parent must be a Layer or None")
        if new_parent.containing_comp is not self.containing_comp:
            raise ValueError("parent must be a layer in the same composition")
        # Walk up from the candidate; hitting self means a cycle. The
        # visited set keeps this terminating even on a file that already
        # contains a parenting cycle.
        seen = {id(self)}
        current: Layer | None = new_parent
        while current is not None:
            if id(current) in seen:
                raise ValueError(
                    "cannot parent a layer to itself or to one of its descendants"
                )
            seen.add(id(current))
            current = current.parent

    @property
    def parent(self) -> Layer | None:
        """The parent of this layer; can be `None`.

        Offset values are calculated to counterbalance any transforms above this layer
        in the hierarchy, so that when you set the parent there is no apparent jump in
        the layer's transform.

        For example, if the new parent has a rotation of 30 degrees, the child layer is
        assigned a rotation of -30 degrees.

        To set the parent without changing the child layer's transform values, use the
        set_parent_with_jump method.

        Read / Write."""
        if self._parent_id == 0:
            return None
        return self.containing_comp.layers_by_id.get(self._parent_id)

    @parent.setter
    def parent(self, value: Layer | None) -> None:
        self._validate_parent(value)
        old_parent = self.parent
        new_parent = value

        if old_parent is new_parent:
            return

        child_world = build_world_matrix(self)
        old_parent_world = (
            build_world_matrix(old_parent)
            if old_parent is not None
            else Mat4.identity()
        )
        new_parent_world = (
            build_world_matrix(new_parent)
            if new_parent is not None
            else Mat4.identity()
        )

        self._parent_id = value.id if value is not None else 0

        new_local = new_parent_world.inverse() @ child_world

        # Decompose into AE transform components, keeping anchor fixed.
        anchor = cast(
            "list[float]", cast("Property", self.transform["ADBE Anchor Point"]).value
        )

        new_pos, new_scale, new_rz, new_rx, new_ry = decompose_transform(
            new_local, anchor
        )

        transform = self.transform

        def write_compensation(match_name: str, new_value: Any) -> None:
            # Only write values that actually changed to avoid materializing
            # synthetic properties unnecessarily. Keyframed scale / rotation
            # values are left untouched, matching ExtendScript (the layer
            # may visually jump for those).
            prop = cast("Property", transform[match_name])
            if prop.keyframes:
                return
            if prop.value != new_value:
                prop.value = new_value

        # ExtendScript remaps every POSITION keyframe into the new parent's
        # space (measured in AE 2026); other keyframed properties keep
        # their values.
        pos = cast("Property", transform["ADBE Position"])
        if pos.keyframes:
            remap = new_parent_world.inverse() @ old_parent_world
            for kf in pos.keyframes:
                kf_value = cast("list[float]", kf.value)
                dims = len(kf_value)
                kf.value = remap.transform_point(kf_value)[:dims]
                for tangent_attr in ("in_spatial_tangent", "out_spatial_tangent"):
                    tangent = getattr(kf, tangent_attr)
                    if tangent:
                        setattr(
                            kf,
                            tangent_attr,
                            remap.transform_vector(tangent)[: len(tangent)],
                        )
        else:
            write_compensation("ADBE Position", new_pos)
        write_compensation("ADBE Scale", new_scale)
        write_compensation("ADBE Rotate Z", new_rz)

        # Only update 3D rotation properties if the layer is 3D.
        is_3d = getattr(self, "three_d_layer", False)
        if is_3d:
            write_compensation("ADBE Rotate X", new_rx)
            write_compensation("ADBE Rotate Y", new_ry)

    def set_parent_with_jump(self, new_parent: Layer | None) -> None:
        """Sets the parent of this layer to the specified layer, without changing the
        transform values of the child layer.

        There may be an apparent jump in the rotation, translation, or scale of the
        child layer, as this layer's transform values are combined with those of its
        ancestors.

        If you do not want the child layer to jump, set the parent attribute directly.
        In this case, an offset is calculated and set in the child layer's transform
        fields, to prevent the jump from occurring.

        Args:
            new_parent: The new parent layer, or `None` to unparent.

        Raises:
            ValueError: If `new_parent` is this layer itself, one of its
                descendants, or a layer in another composition.
        """
        self._validate_parent(new_parent)
        self._parent_id = new_parent.id if new_parent is not None else 0

    def active_at_time(self, time: float) -> bool:
        """Return whether the layer is active at the given time.

        For this method to return `True`, three conditions must be met:

        1. The layer must be `enabled`.
        2. No other layer in the [containing_comp][] may be soloed unless
           this layer is also [solo][].
        3. `time` must fall between [in_point][] (inclusive) and
           [out_point][] (exclusive).

        Args:
            time: The time in seconds.
        """
        validate_number(time)
        if not self.enabled:
            return False

        any_solo = bool(self.containing_comp.solo_layers)
        if any_solo and not self.solo:
            return False

        if time < self.in_point or time >= self.out_point:
            return False

        return True

    def _set_raw_in_point(self, value: float) -> None:
        """Write a new in_point (comp time) to the binary chunk."""
        layer_relative = (value - self.start_time) / self._stretch_factor
        self._ldta.in_point = layer_relative

    def _set_raw_out_point(self, value: float) -> None:
        """Write a new out_point (comp time) to the binary chunk."""
        layer_relative = (value - self.start_time) / self._stretch_factor
        self._ldta.out_point = layer_relative

    # ------------------------------------------------------------------
    # Structural mutations
    # ------------------------------------------------------------------

    def remove(self) -> None:
        """Deletes this layer from the composition.

        Layers that reference this layer as a parent become unparented
        (their transforms are recalculated to preserve world-space
        appearance).  AVLayers that use this layer as a track matte
        lose their matte reference.
        """
        from .av_layer import _unregister_source_usage  # noqa: PLC0415

        comp = self.containing_comp
        removed_id = self.id

        # Unparent children - triggers transform recalculation via the
        # parent setter so the child doesn't visually jump.
        for layer in comp.layers:
            if layer is not self and layer._parent_id == removed_id:
                layer.parent = None

        # Clean track matte refs on AV layers
        for layer in comp.av_layers:
            if layer is not self:
                ldta = layer._ldta
                if (
                    hasattr(ldta, "matte_layer_id")
                    and ldta.matte_layer_id == removed_id
                ):
                    ldta.matte_layer_id = 0

        # Update source _used_in if this layer references a source item
        comp._project._ensure_used_in_linked()
        source = getattr(self, "source", None)
        if source is not None and hasattr(source, "_used_in"):
            _unregister_source_usage(source, comp, exclude=self)  # type: ignore[arg-type]

        # Remove chunk block from comp's chunk list
        start, end = comp._layer_block_slice(self)
        del comp._item_list.chunks[start:end]

        # Remove from model list and rebuild caches
        comp._layers.remove(self)
        comp._invalidate_layer_cache()

    def duplicate(self) -> Layer:
        """Create a duplicate of this layer in the same composition.

        The duplicate is placed directly above (before) the original
        layer.

        Returns:
            The newly created [Layer][].
        """
        return self.copy_to_comp(self.containing_comp)

    def copy_to_comp(self, into_comp: CompItem) -> Layer:
        """Copy this layer into another composition.

        If the target is the same as this layer's [containing_comp][], the
        copy behaves like [duplicate][]: it is placed directly above the
        original and preserves parent and track matte references.

        If the target is a different composition, the copy is placed at the
        top of the target layer stack and parent and track matte references
        are cleared.

        Args:
            into_comp: The target [CompItem][].
        Returns:
            The newly created [Layer][] in the target composition.
        """
        # Circular: parsers.layer -> models.layers.av_layer -> layer
        from ...parsers.layer import parse_layer  # noqa: PLC0415
        from ..items.composition import CompItem  # noqa: PLC0415

        if not isinstance(into_comp, CompItem):
            raise ValueError("Target composition must be a CompItem.")

        same_comp = into_comp is self.containing_comp

        # Clone the full layer block (LIST:Layr + trailing view chunks)
        src_start, src_end = self.containing_comp._layer_block_slice(self)
        src_block = self.containing_comp._item_list.chunks[src_start:src_end]
        cloned_block = [clone_chunk_tree(c) for c in src_block]
        cloned_list = cast("ListChunk", cloned_block[0])

        # Patch layer ID
        cloned_ldta = cast(
            "LdtaChunk",
            find_by_type(
                chunks=cloned_list.chunks,
                chunk_type="ldta",
            ),
        )
        # Layer IDs are unique project-wide, not per-comp.
        cloned_ldta.layer_id = into_comp._project._allocate_id()
        # AE points every effect's hidden -0000 param tdpi at the owning
        # layer; retarget the clones at the fresh id (layer-reference
        # tdpi values keep pointing at the originally referenced layer).
        rewrite_owner_tdpi(cloned_list, cloned_ldta.layer_id)

        # Determine chunk insertion point
        if same_comp:
            model_idx = into_comp._layers.index(self)
            chunk_idx = src_start
        else:
            # Clear parent/matte when copying across compositions
            cloned_ldta.parent_id = 0
            cloned_ldta.matte_layer_id = 0
            model_idx = 0
            if into_comp.layers:
                chunk_idx = index_by_identity(
                    into_comp._item_list.chunks, into_comp.layers[0]._layer_list
                )
            else:
                chunk_idx = into_comp._find_first_layer_position()
        into_comp._item_list.chunks[chunk_idx:chunk_idx] = cloned_block

        # Re-parse cloned chunks into a model instance
        effect_defs = into_comp._project._effect_param_defs
        new_layer = parse_layer(cloned_list, into_comp, effect_defs)

        into_comp._layers.insert(model_idx, new_layer)

        # Increment user-defined name
        if new_layer.is_name_set:
            existing = {lyr.name for lyr in into_comp.layers}
            if new_layer.name in existing:
                new_layer.name = auto_name(new_layer.name, existing)

        into_comp._invalidate_layer_cache()

        # Register source _used_in for the cloned layer
        into_comp._project._ensure_used_in_linked()
        new_source = getattr(new_layer, "source", None)
        if new_source is not None and hasattr(new_source, "_used_in"):
            new_source._used_in.add(into_comp)

        return new_layer

    def move_after(self, layer: Layer) -> None:
        """Moves this layer to a position immediately after (below)
        the specified layer.

        Args:
            layer: The target layer in the same composition.
        """
        if not isinstance(layer, Layer):
            raise ValueError("Target must be a Layer.")

        comp = self.containing_comp
        if layer.containing_comp is not comp:
            raise ValueError("Target layer must be in the same composition.")
        self_idx = comp._layers.index(self)
        target_idx = comp._layers.index(layer)
        # After self is removed, target shifts left by 1 if self was before it
        effective = target_idx - (1 if self_idx < target_idx else 0)
        self._move_to(effective + 1)

    def move_before(self, layer: Layer) -> None:
        """Moves this layer to a position immediately before (above)
        the specified layer.

        Args:
            layer: The target layer in the same composition.
        """
        if not isinstance(layer, Layer):
            raise ValueError("Target must be a Layer.")

        comp = self.containing_comp
        if layer.containing_comp is not comp:
            raise ValueError("Target layer must be in the same composition.")
        self_idx = comp._layers.index(self)
        target_idx = comp._layers.index(layer)
        effective = target_idx - (1 if self_idx < target_idx else 0)
        self._move_to(effective)

    def move_to_beginning(self) -> None:
        """Moves this layer to the topmost position of the composition."""
        self._move_to(0)

    def move_to_end(self) -> None:
        """Moves this layer to the bottommost position of the composition."""
        self._move_to(len(self.containing_comp.layers))

    def _move_to(self, target_index: int) -> None:
        """Move this layer to the given model-list index.

        Uses direct chunk slice extraction and reinsertion, never
        `remove()`, so parent and track matte connections on other
        layers are preserved.
        """
        comp = self.containing_comp

        # Extract and remove chunk block
        start, end = comp._layer_block_slice(self)
        block = comp._item_list.chunks[start:end]
        del comp._item_list.chunks[start:end]

        comp._layers.remove(self)

        # Clamp target index
        target_index = min(target_index, len(comp._layers))

        # Find chunk insertion point
        if target_index < len(comp._layers):
            chunk_idx = index_by_identity(
                comp._item_list.chunks, comp._layers[target_index]._layer_list
            )
        elif comp._layers:
            _, last_end = comp._layer_block_slice(comp._layers[-1])
            chunk_idx = last_end
        else:
            chunk_idx = comp._find_first_layer_position()

        # Insert block and model entry
        comp._item_list.chunks[chunk_idx:chunk_idx] = block
        comp._layers.insert(target_index, self)

        comp._invalidate_layer_cache()
