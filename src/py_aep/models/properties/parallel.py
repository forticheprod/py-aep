"""Per-kind descriptors for complex (parallel-container) properties.

Orientation, marker, shape, gradient and text properties store their
per-keyframe values outside the keyframe `ldat` items, in a sibling
container inside a wrapper LIST (`otst`/`otky`, `mrst`/`mrky`,
`om-s`/`omks`, `GCst`/`GCky`, `btds`/btdk COS). The kinds differ in a
small set of facts and conversions; each [ParallelKind][] subclass
centralizes one kind so the generic keyframe mutation algorithms in
[Property][py_aep.models.properties.property.Property] are written once.

All binary forms were reverse-engineered from AE 2026 static-vs-keyed
output pairs (`aep-compare` ground-truth workflow).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ...binary.chunk import Chunk, ListChunk
from ...binary.ldat_chunks import LdatItemType
from ...binary.mutations import (
    build_parallel_ldat_item,
    clone_chunk_tree,
    set_orientation_item_values,
)
from ...binary.property_chunks import CdatChunk, OtdaChunk
from ...binary.scalar_chunks import Utf8Chunk
from ...enums import PropertyControlType, PropertyValueType
from .gradient import Gradient
from .marker import MarkerValue
from .shape import Shape

if TYPE_CHECKING:
    from typing import Any

    from ...binary.ldat_chunks import LdatItem
    from .keyframe import Keyframe
    from .property import Property

_EMPTY_CDAT_PAD = b"\x00\x00\x00\x00"


class ParallelKind:
    """Descriptor for one complex property kind. Stateless singleton.

    Subclasses override the class attributes and the conversions that
    differ for their kind; the defaults implement the most common
    behavior (held value, no model wrapping, empty static cdat).
    """

    name: str
    wrapper_type: str
    """The wrapper LIST type holding the tdbs + value container."""

    container_type: str | None
    """The per-keyframe value container LIST type (None for text,
    whose values live in the shared btdk COS blob)."""

    header_item_type: LdatItemType
    """The ldat item type of the keyframe header entries."""

    keeps_value_on_revert: bool = True
    """Whether the container keeps the removed keyframe's value chunk
    as the static value when the last keyframe is removed (markers
    have no static value)."""

    aliases_static_value: bool = False
    """Whether `Property.value` stays aliased to the first keyframe's
    model after animating (matches the shape parser)."""

    can_materialize_wrapper: bool = False
    """Whether the wrapper subtree can be created from scratch when the
    binary stores nothing for the property."""

    def held_value(self, prop: Property, time: float) -> Any:
        """The value a new keyframe takes at `time` when none is given.

        Most kinds cannot be interpolated: hold the nearest existing
        keyframe's value, or the static value.
        """
        if not prop.keyframes:
            return prop._value
        return prop.keyframes[prop.nearest_key_index(time)].value

    def coerce(self, value: Any) -> Any:
        """Normalize a user-supplied value to the kind's value object."""
        return value

    def build_value_chunk(self, prop: Property, value: Any) -> Chunk:
        """Build the parallel-container value chunk holding `value`."""
        raise NotImplementedError

    def wrap_value_chunk(self, prop: Property, value_chunk: Chunk) -> Any:
        """Wrap a freshly built value chunk as its model view, or None.

        The returned model reads and writes `value_chunk` directly, so
        a newly added keyframe can be edited in place (the source model
        passed to `build_value_chunk` is backed by a different chunk).
        """
        return None

    def bind_keyframe(self, value: Any, kf: Keyframe) -> None:
        """Attach kind-specific back-references after a value is set."""

    def build_header_item(self, value: Any) -> LdatItem:
        """Build the keyframe header ldat item for `value`."""
        return build_parallel_ldat_item(self.header_item_type)

    def update_header_item(self, item: LdatItem, value: Any) -> None:
        """Refresh value data mirrored into an existing header item."""

    def static_cdat(self, removed_value: Any) -> CdatChunk:
        """The cdat AE writes when the property reverts to static."""
        return CdatChunk(pad=_EMPTY_CDAT_PAD)

    def on_wrap(self, prop: Property) -> None:
        """Kind-specific tdb4 / model fixups after wrapping a bare tdbs."""


class _OrientationKind(ParallelKind):
    name = "orientation"
    wrapper_type = "otst"
    container_type = "otky"
    header_item_type = LdatItemType.orientation
    can_materialize_wrapper = True

    def held_value(self, prop: Property, time: float) -> Any:
        # Orientation values interpolate numerically.
        return prop.value_at_time(time)

    def build_value_chunk(self, prop: Property, value: Any) -> Chunk:
        vals = [float(v) for v in value] if isinstance(value, list) else [0.0, 0.0, 0.0]
        return OtdaChunk(values=vals)

    def build_header_item(self, value: Any) -> LdatItem:
        return build_parallel_ldat_item(
            self.header_item_type,
            orientation_values=(
                [float(v) for v in value] if isinstance(value, list) else None
            ),
        )

    def update_header_item(self, item: LdatItem, value: Any) -> None:
        if isinstance(value, list):
            set_orientation_item_values(item, [float(v) for v in value])

    def static_cdat(self, removed_value: Any) -> CdatChunk:
        # Inside an otst the cdat doubles are little-endian and hold the
        # actual angles.
        if isinstance(removed_value, list):
            return CdatChunk(values=[float(v) for v in removed_value[:3]], is_le=True)
        return CdatChunk(pad=_EMPTY_CDAT_PAD)

    def apply_model_metadata(self, prop: Property) -> None:
        """Override parsed metadata with what ExtendScript reports for
        orientation (angle dial, 3D spatial vector), regardless of the
        binary tdb4 values. Shared by `parse_orientation` and `on_wrap`.
        """
        prop._property_control_type = PropertyControlType.ANGLE
        prop._property_value_type = PropertyValueType.ThreeD_SPATIAL
        prop.__dict__["dimensions"] = 3
        prop.__dict__["_vector"] = True

    def on_wrap(self, prop: Property) -> None:
        prop._tdb4.dimensions = 1
        # 0x6000 (24 fps) is the fallback when the containing comp is
        # unknown; _ensure_time_base overrides it with the comp's timebase.
        prop._tdb4._time_base = 0x6000
        prop._ensure_time_base()
        self.apply_model_metadata(prop)


class _MarkerKind(ParallelKind):
    name = "marker"
    wrapper_type = "mrst"
    container_type = "mrky"
    header_item_type = LdatItemType.marker
    keeps_value_on_revert = False
    can_materialize_wrapper = True

    def held_value(self, prop: Property, time: float) -> Any:
        return MarkerValue()

    def coerce(self, value: Any) -> Any:
        if isinstance(value, str):
            return MarkerValue(comment=value)
        return value

    def build_value_chunk(self, prop: Property, value: Any) -> Chunk:
        if not isinstance(value, MarkerValue):
            raise TypeError("marker value must be a MarkerValue or str comment")
        # Clone every embedded chunk: a caller may reuse one MarkerValue for
        # several keyframes, and the model's chunks may already be bound to
        # another Nmrd. Sharing them would alias one set of bytes into two
        # markers (an edit or a param splice on one corrupts the other). The
        # keyframe's own editable model is rebound to these clones in
        # `wrap_value_chunk` (mirrors `_GradientKind`).
        source: list[Chunk] = [
            value._nmhd,
            value._comment_utf8,
            value._chapter_utf8,
            value._url_utf8,
            value._frame_target_utf8,
            value._cue_point_name_utf8,
            *value._param_utf8s,
        ]
        return ListChunk(list_type="Nmrd", chunks=[clone_chunk_tree(c) for c in source])

    def wrap_value_chunk(self, prop: Property, value_chunk: Chunk) -> Any:
        # Deferred import: models <-> parsers is a cycle.
        from ...parsers.marker import parse_marker

        return parse_marker(cast("ListChunk", value_chunk))

    def bind_keyframe(self, value: Any, kf: Keyframe) -> None:
        if isinstance(value, MarkerValue):
            value._keyframe = kf

    def on_wrap(self, prop: Property) -> None:
        t = prop._tdb4
        t.dimensions = 1
        t._time_base = 0x6000
        t._type_flags = 0x08
        t._no_value_flags = 0x01
        t._property_category = 0
        t._spatial_static_flags = 0x01
        t._cvot_flags = 0x04
        t._value_hint_type = 1
        t._value_hint_flag = 0
        t._spatial_marker = False


class _ShapeKind(ParallelKind):
    name = "shape"
    wrapper_type = "om-s"
    container_type = "omks"
    header_item_type = LdatItemType.no_value
    aliases_static_value = True

    def build_value_chunk(self, prop: Property, value: Any) -> Chunk:
        if not isinstance(value, Shape):
            raise TypeError("shape value must be a Shape")
        return prop._build_shap_chunk(value)

    def wrap_value_chunk(self, prop: Property, value_chunk: Chunk) -> Any:
        # Deferred import: models <-> parsers is a cycle.
        from ...parsers.specialized_properties import _parse_shape_shap

        comp = prop._containing_layer.containing_comp
        is_mask = prop.match_name == "ADBE Mask Shape"
        shape = _parse_shape_shap(cast("ListChunk", value_chunk), comp, is_mask)
        if is_mask:
            # Mask space is LAYER space: denormalize by the layer source
            # size, not the comp (psd_vector_mask_cropped fixture).
            shape._layer = prop._containing_layer
        return shape


class _GradientKind(ParallelKind):
    name = "gradient"
    wrapper_type = "GCst"
    container_type = "GCky"
    header_item_type = LdatItemType.no_value
    can_materialize_wrapper = True

    def build_value_chunk(self, prop: Property, value: Any) -> Chunk:
        if value is None:
            # A never-edited gradient has no parsed Gradient model;
            # AE's default gradient seeds the first keyframe.
            return Gradient()._utf8
        if not isinstance(value, Gradient):
            raise TypeError("gradient value must be a Gradient")
        # Clone the serialized XML so keyframes do not share a chunk.
        return Utf8Chunk(value=value._utf8.value)

    def wrap_value_chunk(self, prop: Property, value_chunk: Chunk) -> Any:
        # Deferred import: models <-> parsers is a cycle.
        from ...parsers.gradient import parse_gradient_xml

        return parse_gradient_xml(cast("Utf8Chunk", value_chunk))

    def on_wrap(self, prop: Property) -> None:
        t = prop._tdb4
        t.dimensions = 1
        t._time_base = 0x6000
        t._type_flags = 0x08
        t._no_value_flags = 0x01
        t._property_category = 0
        t._spatial_static_flags = 0x07
        t._cvot_flags = 0xFF
        t._value_hint_type = 0xFFFF
        t._value_hint_flag = 0xFF
        t._spatial_marker = True


class _TextKind(ParallelKind):
    """Source Text. Values live in the shared btdk COS blob (one document
    per keyframe), so the add / remove / animate algorithms are the
    dedicated text paths on [Property][], not the generic container ones.
    """

    name = "text"
    wrapper_type = "btds"
    container_type = None
    header_item_type = LdatItemType.marker


ORIENTATION_KIND = _OrientationKind()
MARKER_KIND = _MarkerKind()
SHAPE_KIND = _ShapeKind()
GRADIENT_KIND = _GradientKind()
TEXT_KIND = _TextKind()
