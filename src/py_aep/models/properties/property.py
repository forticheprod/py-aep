from __future__ import annotations

import copy
import logging
import math
import re
from typing import TYPE_CHECKING, ClassVar, Union, cast

from py_aep.cos import cos_get
from py_aep.data.spatial_flags import EFFECT_PARAM_SPATIAL_FLAGS
from py_aep.enums import (
    KeyframeInterpolationType,
    LayerType,
    PropertyControlType,
    PropertyType,
    PropertyValueType,
)
from py_aep.resolvers.can_set_expression import resolve_can_set_expression
from py_aep.resolvers.interpolation import (
    _DEFAULT_INFLUENCE,
    _BezierPathData,
    _tangents_are_zero,
    interpolate_keyframes,
    path_parameter_at_progress,
    roving_keyframe_times,
    segment_value_slope,
    split_segment_influences,
    split_spatial_path,
)

from ...binary.chunk import ContainerChunk, ListChunk
from ...binary.ldat_chunks import (
    LHD3_BLOCK_KEYFRAMES,
    LdatItemType,
    ShapePoint,
    set_lhd3_count,
)
from ...binary.misc_chunks import EnumPardChunk
from ...binary.mutations import (
    ITEM_SIZE_BY_TYPE,
    build_keyframe_list,
    build_kf_data,
    build_ldat_item,
    build_parallel_ldat_item,
    build_shap,
)
from ...binary.property_chunks import (
    TDSN_SENTINEL,
    CdatChunk,
    Tdb4Chunk,
    TdmnChunk,
    TdsbChunk,
    TdsnChunk,
    TdumChunk,
    VfdnChunk,
    tdb4_apply_animated_template,
    tdb4_apply_static_template,
)
from ...binary.scalar_chunks import S4Chunk, Utf8Chunk
from ...binary.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
    index_by_identity,
)
from ...data.match_names import VF_AXIS_PREFIX
from ...data.units import UNITS_TEXT_MAP
from ...resolvers.motion_graphics import can_add_property
from ...synthesis.property import _USE_VALUE
from ..descriptors import ChunkField
from ..text.text_document import TextDocument
from ..validators import (
    _validate_number,
    validate_bool,
    validate_enum,
    validate_name,
    validate_number,
    validate_sequence,
    validate_string,
)
from .gradient import Gradient
from .keyframe import Keyframe, _timebase_units
from .keyframe_ease import KeyframeEase
from .marker import MarkerValue
from .overrides import (
    _ALWAYS_MODIFIED,
    _CANVARY_OVERRIDES,
    _ISSPATIAL_OVERRIDES,
    _NAME_OVERRIDES,
    _PLACEHOLDER_UNBOUNDED,
    _UNBOUNDED_MATCH_NAMES,
)
from .parallel import (
    GRADIENT_KIND,
    MARKER_KIND,
    ORIENTATION_KIND,
    SHAPE_KIND,
    TEXT_KIND,
    ParallelKind,
)
from .property_base import PropertyBase
from .shape import Shape

if TYPE_CHECKING:
    from typing import Any

    from ...binary.chunk import Chunk
    from ...binary.ldat_chunks import LdatChunk, Lhd3Chunk
    from ...binary.misc_chunks import ShphChunk
    from ...binary.scalar_chunks import U4Chunk
    from ...synthesis.property import PropSpec
    from ..items.av_item import AVItem
    from ..items.composition import CompItem
    from ..items.folder import FolderItem
    from ..items.footage import FootageItem
    from ..layers.av_layer import AVLayer
    from ..project import Project
    from .property_group import PropertyGroup

    _ValueType = Union[
        list[float],
        float,
        int,
        Gradient,
        MarkerValue,
        Shape,
        TextDocument,
        None,
    ]

logger = logging.getLogger(__name__)

_UNSET = object()  # sentinel for unset min/max fallback

# Match names whose binary values are stored as 0-1 fractions but
# ExtendScript reports as 0-100 percentages.
_PERCENT_MATCH_NAMES: set[str] = {
    "ADBE Opacity",
    "ADBE Scale",
    "ADBE Mask Opacity",
}

_SEPARATION_LEADER = "ADBE Position"
_SEPARATION_FOLLOWERS: list[str] = [
    "ADBE Position_0",
    "ADBE Position_1",
    "ADBE Position_2",
]


def _get_max(prop: Property) -> float | None:
    v = prop.max_value
    if not isinstance(v, (int, float)):
        return None
    # A max of exactly 0.0 is, across the whole sample corpus, always AE's
    # [0.0] placeholder for an unbounded/runtime-grown bound (Time Remapping,
    # and Light/Camera props that carry a [0.0] tduM) - never a genuine
    # enforceable maximum. So do not enforce it on the value setter. (A
    # hypothetical effect param with a real max of 0 is unsampled.)
    if v == 0.0:
        return None
    return v


def _get_min(prop: Property) -> float | None:
    v = prop.min_value
    return v if isinstance(v, (int, float)) else None


_NUMERIC_VALUE_TYPES: set[PropertyValueType] = {
    PropertyValueType.OneD,
    PropertyValueType.TwoD,
    PropertyValueType.TwoD_SPATIAL,
    PropertyValueType.ThreeD,
    PropertyValueType.ThreeD_SPATIAL,
    PropertyValueType.COLOR,
}


def _get_dimensions(prop: Property) -> int:
    d: int = prop.dimensions
    # Color properties use dimensions=1 but store 4-element lists.
    if prop._color:
        return 4
    return d


_validate_scalar = _validate_number(min=_get_min, max=_get_max)
_validate_list = validate_sequence(length=_get_dimensions, min=_get_min, max=_get_max)


def _validate_value(prop: Property, value: Any) -> None:
    """Validate type, length and bounds of a property value."""
    if value is None:
        return
    # Variable-font axis properties are 2-dimensional in the binary
    # ([value, tag]) but scalar in ExtendScript. They carry the
    # VARIABLE_FONT_AXIS value type, which is NOT in _NUMERIC_VALUE_TYPES,
    # so this must run BEFORE the numeric-type gate below - otherwise the
    # gate returns early and axis values skip finite/range validation
    # entirely (a NaN/inf or out-of-[min,max] weight would be written).
    if prop._is_vf_axis and isinstance(value, (int, float)):
        _validate_scalar(value, prop)
        return
    if prop.property_value_type not in _NUMERIC_VALUE_TYPES:
        return
    expects_list = prop.dimensions > 1 or prop._color
    if expects_list:
        _validate_list(value, prop)
    else:
        _validate_scalar(value, prop)


# Standard OpenType design-axis display names (AE shows the axis name from
# the font itself; these cover the registered tags, custom tags fall back
# to the raw tag).
_VF_AXIS_STANDARD_NAMES = {
    "wght": "Weight",
    "wdth": "Width",
    "slnt": "Slant",
    "ital": "Italic",
    "opsz": "Optical Size",
}


def _vf_tag_to_str(raw: float) -> str | None:
    """Decode a variable-font axis tag stored as a 4CC number.

    The axis property's second dimension holds the tag packed big-endian
    (e.g. 2003265652.0 = 0x77676874 = `wght`). Returns `None` for values
    that do not decode to four printable ASCII characters.
    """
    n = int(raw)
    if n <= 0 or n > 0xFFFFFFFF:
        return None
    chars = [(n >> shift) & 0xFF for shift in (24, 16, 8, 0)]
    if any(c < 0x20 or c > 0x7E for c in chars):
        return None
    return "".join(chr(c) for c in chars)


def _vf_tag_from_str(tag: str) -> int:
    """Encode a 4-character axis tag to its packed 4CC number."""
    n = 0
    for c in tag:
        n = (n << 8) | ord(c)
    return n


def _values_equal(a: Any, b: Any) -> bool:
    """Compare two property values with float tolerance.

    Handles scalars, lists/tuples, booleans, and None.
    Uses [math.isclose][] for numeric comparisons.
    """
    if a is None or b is None:
        return a is b
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a == b)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_values_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, abs_tol=1e-6)
    return bool(a == b)


class Property(PropertyBase):
    """
    The `Property` object contains value, keyframe, and expression information
    about a particular AE property of a layer. An AE property is a value,
    often animatable, of an effect, mask, or transform within an individual
    layer.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        prop = comp.layers[0].transform.property("ADBE Position")
        print(prop.value)
        ```

    Info:
        `Property` is a subclass of [PropertyBase][]. All methods and attributes
        of [PropertyBase][] are available when working with `Property`.

    See: https://ae-scripting.docsforadobe.dev/property/property/
    """

    keyframes: list[Keyframe]
    """The list of keyframes for this property. Read-only."""

    default_value: Any
    """The default value of the property."""

    dimensions = ChunkField[int](
        "_tdb4",
        "dimensions",
        default=1,
        read_only=True,
    )
    """The number of dimensions in the property value (1, 2, 3, or 4). Read-only."""

    expression_error: str
    """Contains the error, if any, generated by evaluation of the string
    most recently set in [expression][]. If no expression string has been
    specified, or if the last expression string evaluated without error,
    contains the empty string (`""`).

    Warning:
        The parser cannot evaluate expressions, so this attribute is
        always an empty string. After Effects computes expression errors
        at runtime when it evaluates the expression engine; this
        information is not stored in the binary `.aep` file.
    Read-only."""

    last_value: Any
    """The last value of the property (before animation)."""

    nb_options: int | None
    """The number of options in a dropdown property."""

    _animated = ChunkField[bool]("_tdb4", "animated")

    _color = ChunkField[bool]("_tdb4", "color")

    _integer = ChunkField[bool]("_tdb4", "integer")

    _no_value = ChunkField[bool]("_tdb4", "no_value")

    _vector = ChunkField[bool]("_tdb4", "vector")

    locked_ratio = ChunkField[bool]("_tdsb", "locked_ratio", read_only=True)
    """When `True`, the property's X/Y ratio is locked. Read-only."""

    _is_spatial_raw = ChunkField[bool]("_tdb4", "is_spatial")

    @property
    def is_spatial(self) -> bool:
        """When `True`, the named property defines a spatial value.

        Examples are position and effect point controls. Read-only.
        """
        override = _ISSPATIAL_OVERRIDES.get(self.match_name)
        if override is not None:
            return override
        if self._color:
            # ExtendScript reports every color property as spatial, but AE
            # leaves the tdb4 spatial bit clear on them (an edited effect
            # color writes `_spatial_static_flags` 0x07, measured in AE
            # 2026), so the raw bit would say otherwise.
            return True
        return bool(self._is_spatial_raw)

    @property
    def _has_motion_path(self) -> bool:
        """Whether the property interpolates along a spatial motion path.

        `is_spatial` also reports `True` for colors, to match what
        ExtendScript says; a color has no motion path, so the keyframe
        binary (`temporal_flags`, ldat item layout), the speed math and
        the roving guard ask this instead.
        """
        return self.is_spatial and not self._color

    @property
    def name(self) -> str:
        """Display name of the property. Read / Write."""
        override = _NAME_OVERRIDES.get(self.match_name)
        if override is not None:
            return override
        # Active variable-font axes display as e.g. "Font Axis Weight".
        # AE stores the name (from the font's axis name table) in a vfdn
        # sibling chunk; fall back to mapping the registered OpenType
        # tags, with custom tags showing the raw tag.
        if self._is_vf_axis:
            if self._vfdn is not None:
                try:
                    return self._vfdn.utf8.value
                except ChunkNotFoundError:
                    pass
            tag = self.axis_tag
            if tag is not None:
                return "Font Axis " + _VF_AXIS_STANDARD_NAMES.get(tag, tag)
        base_name = super().name
        # NO_VALUE effect properties that store the match_name in tdsn
        # are unnamed separators/group headers - ExtendScript returns "".
        if (
            self.property_value_type == PropertyValueType.NO_VALUE
            and base_name == self.match_name
            and self._is_in_effect()
        ):
            return ""
        return base_name

    @name.setter
    def name(self, value: str) -> None:
        PropertyBase.__dict__["name"].fset(self, value)

    @classmethod
    def _new(
        cls,
        spec: PropSpec,
        property_depth: int,
        *,
        parent_property: PropertyGroup,
        value: Any = _USE_VALUE,
        default_value: Any = _USE_VALUE,
        synthetic: bool = False,
        control_type: PropertyControlType | None = None,
    ) -> Property:
        """Create a Property from a `PropSpec`.

        Used to synthesize properties expected by ExtendScript but absent
        from the binary.

        Args:
            spec: The property specification describing the property.
            property_depth: The depth of the property in the tree.
            parent_property: The container that owns the synthesized property.
            value: Override for the property value. When omitted, uses
                `spec.value`.
            default_value: Override for the default value. When omitted,
                uses the spec's `default_value` logic.
            synthetic: If True, mark backing chunks as synthetic
                (skipped during serialization).
            control_type: Override for the property control type. When
                omitted, defaults to `PropertyControlType.UNKNOWN`.
        """
        final_value = spec.value if value is _USE_VALUE else value
        no_value = spec.pvt == PropertyValueType.NO_VALUE
        if spec.can_vary_over_time is not None:
            can_vary = spec.can_vary_over_time
        else:
            can_vary = not no_value

        _tdsb = TdsbChunk(synthetic=synthetic)

        _tdb4 = Tdb4Chunk(synthetic=synthetic, dimensions=spec.dimensions)
        if spec.has_time_base:
            binary_nv = no_value or (spec.is_spatial and not spec.color)
            _tdb4._time_base = 0x7800
            _tdb4._spatial_marker = spec.is_spatial
            _tdb4.no_value = binary_nv
            if spec.spatial_flags is not None:
                _tdb4._spatial_static_flags = spec.spatial_flags
            if spec.integer:
                _tdb4.integer = True
                _tdb4._cvot_flags = spec.cvot if spec.cvot is not None else 0x04
                _tdb4._property_category = 0x04
                _tdb4._value_hint_type = (
                    spec.value_hint_type if spec.value_hint_type is not None else 0xFFFF
                )
            elif spec.color:
                _tdb4.color = True
                _tdb4._cvot_flags = spec.cvot if spec.cvot is not None else 0xFF
                _tdb4._property_category = 0x01
                _tdb4._value_hint_type = (
                    spec.value_hint_type if spec.value_hint_type is not None else 1
                )
                _tdb4._value_hint_flag = 0xFF
            elif binary_nv:
                _tdb4._type_flags = 0x18 if spec.is_spatial else 0x08
                _tdb4._cvot_flags = spec.cvot if spec.cvot is not None else 0x04
                _tdb4._value_hint_type = (
                    spec.value_hint_type if spec.value_hint_type is not None else 1
                )
            else:
                _tdb4.vector = True
                _tdb4._cvot_flags = spec.cvot if spec.cvot is not None else 0xFF
                _tdb4._property_category = 0x09
                _tdb4._value_hint_type = (
                    spec.value_hint_type if spec.value_hint_type is not None else 1
                )
                _tdb4._value_hint_flag = 0xFF
        else:
            if spec.spatial_flags is not None:
                _tdb4._spatial_static_flags = spec.spatial_flags
            else:
                _tdb4.is_spatial = spec.is_spatial
            _tdb4.no_value = no_value
            _tdb4.color = spec.color
            _tdb4.integer = spec.integer
            _tdb4.vector = spec.dimensions > 1
            _tdb4.can_vary_over_time = can_vary

        if spec.property_category is not None:
            _tdb4._property_category = spec.property_category
        if spec.pad2a is not None:
            _tdb4._pad2a = spec.pad2a

        # AE writes the unnamed sentinel; the display name resolves
        # from auto_name on the model.
        tdsn = TdsnChunk.new(TDSN_SENTINEL, synthetic=synthetic)
        name_utf8 = tdsn.utf8
        _tdbs = ListChunk(
            list_type="tdbs",
            chunks=[_tdsb, tdsn, _tdb4],
            synthetic=synthetic,
        )

        # Pre-create cdat for numeric values so _ensure_materialized
        # only needs to flip synthetic flags.
        _cdat: CdatChunk | None = None
        if final_value is not None and isinstance(final_value, (int, float, list)):
            if isinstance(final_value, list):
                raw_vals = [float(v) for v in final_value]
            else:
                raw_vals = [float(final_value)]
            _cdat = CdatChunk(values=raw_vals, synthetic=synthetic)
            _tdbs.chunks.append(_cdat)

        # Insert into parent's chunk tree (before parent's group end).
        _tdmn = TdmnChunk(
            value=spec.match_name,
            synthetic=synthetic,
        )
        tdgp = parent_property._tdgp
        if tdgp is not None:
            from .property_group import _insert_before_group_end  # noqa: PLC0415

            _insert_before_group_end(tdgp, _tdmn)
            _insert_before_group_end(tdgp, _tdbs)

        prop = cls(
            _tdmn=_tdmn,
            _tdsb=_tdsb,
            _tdb4=_tdb4,
            _tdbs=_tdbs,
            _name_utf8=name_utf8,
            _cdat=_cdat,
            keyframes=[],
            match_name=spec.match_name,
            auto_name=spec.auto_name,
            parent_property=parent_property,
            property_control_type=control_type or PropertyControlType.UNKNOWN,
            property_depth=property_depth,
            property_value_type=spec.pvt,
            value=final_value,
            can_vary_over_time=spec.can_vary_over_time,
            units_text=spec.units_text,
        )
        if default_value is not _USE_VALUE:
            prop.default_value = default_value
        else:
            prop.default_value = (
                final_value if spec.default_value is _USE_VALUE else spec.default_value
            )
        if spec.chunk_bounds_are_hints:
            # tdum/tduM hold UI slider hints, not real bounds: the spec is
            # authoritative (None = unbounded).
            prop._min_value_fallback = spec.min_value
            prop._max_value_fallback = spec.max_value
        else:
            if spec.min_value is not None:
                prop._min_value_fallback = spec.min_value
            if spec.max_value is not None:
                prop._max_value_fallback = spec.max_value
        if spec.hint_bounds is not None:
            prop._hint_bounds = spec.hint_bounds
        if spec.bound_chunks is not None:
            prop._bound_chunks_hint = spec.bound_chunks
        else:
            prop._bound_chunks_hint = (
                (spec.min_value is not None or spec.max_value is not None)
                and not spec.integer
                and not spec.color
                and not spec.is_spatial
            )

        return prop

    def __init__(
        self,
        *,
        _tdmn: TdmnChunk,
        _tdsb: TdsbChunk,
        _tdb4: Tdb4Chunk,
        _expression_utf8: Utf8Chunk | None = None,
        _name_utf8: Utf8Chunk,
        _tdbs: ListChunk,
        _tdum: TdumChunk | None = None,
        _tduM: TdumChunk | None = None,
        _cdat: CdatChunk | None = None,
        _tdpi: S4Chunk | None = None,
        _composition: CompItem | None = None,
        parent_property: PropertyGroup | None = None,
        match_name: str,
        property_depth: int,
        auto_name: str | None = None,
        keyframes: list[Keyframe],
        value: Any,
        expression_enabled: bool | None = None,
        expression: str | None = None,
        property_control_type: PropertyControlType | None = None,
        property_value_type: PropertyValueType | None = None,
        dimensions_separated: bool | None = None,
        units_text: str | None = None,
        can_vary_over_time: bool | None = None,
    ) -> None:
        super().__init__(
            _tdsb=_tdsb,
            _name_utf8=_name_utf8,
            parent_property=parent_property,
            match_name=match_name,
            auto_name=auto_name,
            property_depth=property_depth,
        )
        self._tdmn = _tdmn
        self._tdb4 = _tdb4
        self._expression_utf8 = _expression_utf8
        self._tdbs = _tdbs
        self._tdum = _tdum
        self._tduM = _tduM
        self._cdat = _cdat
        self._tdpi = _tdpi
        self._composition = _composition

        # Whether AE writes tdum/tduM placeholder bounds for this property
        # when materialized. Set from the synthesis spec in `_new`.
        self._bound_chunks_hint = False

        # Parallel per-keyframe value container for complex value types
        # (otky / mrky / omks / GCky). Set by the specialized parsers.
        # Holds one value chunk per keyframe, aligned with `keyframes`.
        self._kf_value_container: ListChunk | None = None

        # The wrapper LIST holding this property's tdbs + value container
        # (otst / mrst / om-s / GCst / btds). Set by the specialized
        # parsers; None for ordinary numeric properties and for complex
        # properties whose pristine state stores a bare tdbs.
        self._wrapper: ListChunk | None = None

        # Media-replacement slot chunks (blsv/blsi), siblings of this leaf's
        # tdbs inside an `ADBE Layer Source Alternate` group run. Set by the
        # tdbs dispatcher only for that match name; None otherwise. `blsi` is
        # the alternate-source item id (0 = no replacement set).
        self._blsv: U4Chunk | None = None
        self._blsi: U4Chunk | None = None

        self._can_vary_over_time = can_vary_over_time

        # Expressions can never be set on this parameter (from the pard
        # definition header flag; set by _apply_param_def_metadata).
        self._expressions_disabled = False

        self._dimensions_separated = dimensions_separated

        self._expression_enabled = expression_enabled
        self._expression = expression

        self.keyframes = keyframes
        self._link_keyframes()

        self._property_control_type = property_control_type

        self._property_value_type = property_value_type

        self._value: _ValueType = value

        self._units_text = units_text

        self.default_value = None

        self.expression_error = ""

        self.last_value = None

        self._min_value_fallback: Any = _UNSET
        self._max_value_fallback: Any = _UNSET
        # The pard UI slider range (effect params only; None elsewhere).
        self._slider_min: float | None = None
        self._slider_max: float | None = None
        self._scale_z_override: float | None = None

        self.nb_options = None

        self._property_parameters: list[str] | None = None

        self._property_type = PropertyType.PROPERTY

        # Cached raw axis-tag number for variable-font axis properties;
        # survives de-animation (the tag lives in the value data, which
        # keyframe removal deletes before `_deanimate` re-writes it).
        self._vf_tag_cache: float | None = None

        self._vfdn: VfdnChunk | None = None
        """The axis display-name container AE writes after an active
        variable-font axis slot's tdbs (set by the parser)."""

    @property
    def _is_vf_axis(self) -> bool:
        """`True` for a variable-font axis slot property."""
        return self.match_name.startswith(VF_AXIS_PREFIX)

    def _vf_axis_tag_raw(self) -> float | None:
        """The raw 4CC tag number of an ACTIVE axis property, else `None`.

        Read from the static value's second dimension or the first
        keyframe's, then cached (see `_vf_tag_cache`).
        """
        if not self._is_vf_axis:
            return None
        if self._vf_tag_cache is not None:
            return self._vf_tag_cache
        raw: float | None = None
        if self._cdat is not None and len(self._cdat.values) >= 2:
            raw = self._cdat.values[1]
        elif self.keyframes:
            kf_raw = self.keyframes[0]._extract_raw_value()
            if isinstance(kf_raw, list) and len(kf_raw) >= 2:
                raw = kf_raw[1]
        if raw:
            self._vf_tag_cache = raw
            return raw
        return None

    @property
    def axis_tag(self) -> str | None:
        """The 4-character variable-font axis tag (e.g. `wght`) bound to
        this `ADBE Text VF Axis` property. `None` for non-axis properties
        and for unused axis slots. Read-only.

        Warning:
            `axis_tag` does not exist in the ExtendScript API. It has
            been added for convenience (ExtendScript surfaces the tag
            only through the property's display name).
        """
        raw = self._vf_axis_tag_raw()
        if raw is None:
            return None
        return _vf_tag_to_str(raw)

    @property
    def _speed_factor(self) -> float:
        """Speed unit factor for ease objects: 100 for percent properties."""
        if self.match_name in _PERCENT_MATCH_NAMES:
            return 100.0
        return 1.0

    @property
    def _effect_point_speed_factor(self) -> float | None:
        """Speed unit factor for an effect point's ease, or `None`.

        AE stores an effect point's ease speed normalized against the
        composition height, and ExtendScript reports it in pixel units. The
        same scalar applies to both the in and out directions and is
        independent of the width - verified in AE 2026 on 300x300, 400x300,
        800x200 and 1920x1080 comps, which all report an identical speed for
        identical eases. `ADBE Anchor Point` is excluded: its speed is
        already in pixels.

        Resolved when the ease is read rather than pushed onto every
        keyframe: `_effect_scale` is unavailable while the property is still
        being constructed, and re-deriving it per value read used to rescan
        every keyframe, which is quadratic in the keyframe count.
        """
        if self.match_name == "ADBE Anchor Point":
            return None
        scale = self._effect_scale
        if scale is None or not scale[1]:
            return None
        return float(scale[1])

    def _link_keyframes(self) -> None:
        """Set back-references on keyframes after construction.

        Each keyframe gets a reference to its owning property and to its
        prev/next neighbours for lazy ease computation.
        """
        # Assign None explicitly at the boundaries: after a removal or a
        # reorder the previous links are stale, and boundary keyframes
        # must read prev/next as None (ease resolution depends on it).
        for i, kf in enumerate(self.keyframes):
            kf._bind_property(self)
            kf._prev = self.keyframes[i - 1] if i > 0 else None
            kf._next = self.keyframes[i + 1] if i < len(self.keyframes) - 1 else None

    def _link_inserted_key(self, idx: int) -> None:
        """Re-link only the keyframe inserted at `idx` and its neighbours.

        Equivalent to `_link_keyframes` after a single insertion, but O(1)
        so bulk additions (`set_values_at_times`) stay linear.
        """
        kf = self.keyframes[idx]
        if idx > 0:
            kf._prev = self.keyframes[idx - 1]
            self.keyframes[idx - 1]._next = kf
        if idx + 1 < len(self.keyframes):
            kf._next = self.keyframes[idx + 1]
            self.keyframes[idx + 1]._prev = kf

    def _guard_keyframe_move(self, kf: Keyframe, new_units: int) -> None:
        """Reject moving `kf` onto another keyframe's exact time.

        Compares raw timebase units rather than frame indices: two
        keyframes can legitimately share a frame while sitting at
        different sub-frame times, and rounding would reject that as a
        collision.

        Only applies to a keyframe already in `keyframes`: during
        `add_key` construction the time is assigned before insertion, and
        landing on an existing time legitimately returns that keyframe's
        index instead.
        """
        try:
            index_by_identity(self.keyframes, kf)
        except ValueError:
            return
        if any(k is not kf and k.time_units == new_units for k in self.keyframes):
            raise ValueError(
                f"another keyframe already exists at time {new_units} units"
            )

    def _reposition_keyframe(self, kf: Keyframe) -> None:
        """Restore sorted keyframe order after `kf`'s time changed.

        The binary and the model pair several structures positionally
        with `keyframes`: the ldat header items, the parallel value
        container's chunks (otda / Nmrd / shap / Utf8) and a text
        property's COS document array. Moving a keyframe past a
        neighbour must move all of them together and re-link the
        prev/next chain (LINEAR ease speeds and `value_at_time` read
        neighbours by order). No-op for a keyframe not (yet) in
        `keyframes` or whose sorted position is unchanged.
        """
        try:
            old = index_by_identity(self.keyframes, kf)
        except ValueError:
            return
        new_units = kf.time_units
        new = sum(1 for k in self.keyframes if k is not kf and k.time_units < new_units)
        if new == old:
            return
        _lhd3, ldat = self._ensure_animated()
        self.keyframes.insert(new, self.keyframes.pop(old))
        ldat.items.insert(new, ldat.items.pop(old))
        container = self._kf_value_container
        if container is not None and old < len(container.chunks):
            container.chunks.insert(new, container.chunks.pop(old))
        if self._parallel_kind() is TEXT_KIND:
            td = kf.value
            if isinstance(td, TextDocument):
                doc_array = cos_get(td._cos_data, "1", "1")
                if old < len(doc_array):
                    doc_array.insert(new, doc_array.pop(old))
                td._propagate_cos()
        self._link_keyframes()

    def _redistribute_roving_keyframes(self) -> None:
        """Re-derive every roving keyframe's time from the spatial path.

        Called after any mutation that can reshape a roving run: a value
        edit (the path changed), a bounding keyframe's time moving (the
        span changed), or a roving flag flip. Writes directly to the
        backing time field to avoid recursion through `_set_time_units`.
        """
        if not self._has_motion_path:
            return
        # Orientation is spatial-valued but inert under roving: AE's
        # menu accepts the command (26.3x87) yet the keyframe keeps its
        # time and ease unchanged.
        if self.match_name == "ADBE Orientation":
            return
        keyframes = self.keyframes
        if len(keyframes) < 3:
            return
        # This runs on every value, time and tangent write, so a property
        # with no roving keyframes must not pay for a full pass. The flag is
        # read off the chunk rather than through the `roving` descriptor:
        # that hop was four fifths of the cost.
        if not any(kf._ldat_item.roving for kf in keyframes):
            return
        targets = roving_keyframe_times(keyframes)
        if not targets:
            return
        occupied = {kf.time_units for kf in keyframes}
        for index, time in targets.items():
            kf = keyframes[index]
            # `roving_keyframe_times` works in layer time, which is what the
            # ticks count, so there is no composition-time offset or stretch
            # to undo here. Converting scaled the run by the stretch factor
            # and displaced it by the layer's start time, pushing roving keys
            # outside their own anchors (AE 2026: a run bounded at comp 2 and
            # 8 on a 200 % layer put a roving key at -0.017).
            units = round(time * kf._timebase)
            if units == kf.time_units:
                continue
            # A degenerate path (coincident keyframes) can map two keys
            # onto the same unit; leave those where they are.
            if units in occupied:
                continue
            occupied.discard(kf.time_units)
            occupied.add(units)
            kf._ldat_item.time_units = units

    def _ensure_materialized(self) -> None:
        """Flip synthetic flags so backing chunks become visible to write_aep().

        Called automatically by `ChunkField.__set__` on first end-user write
        to a synthesized property. After this method, the property is
        indistinguishable from one that was parsed from binary.
        """
        assert self._tdsb is not None
        if not self._tdsb.synthetic:
            return

        parent = self.parent_property
        if parent is not None:
            parent._ensure_materialized()

        self._set_subtree_synthetic(False)

        self._ensure_time_base()
        self._complete_static_value_chunks()
        self._reposition_canonically()
        self._ensure_bound_chunks()
        self._materialize_static_orientation()
        self._ensure_mask_index_chunks()

    def _set_subtree_synthetic(self, value: bool) -> None:
        """Flip the synthetic flag on `tdmn` and the whole `tdbs` subtree.

        `write_aep` skips synthetic chunks, so this is what hides a
        property from the writer or reveals it: `False` materializes,
        `True` un-materializes (see `_revert_to_synthetic`).
        """
        if self._tdmn is not None:
            self._tdmn.synthetic = value
        self._tdbs.synthetic = value
        for chunk in self._tdbs.chunks:
            chunk.synthetic = value
            if hasattr(chunk, "chunks"):
                for nested in chunk.chunks:
                    nested.synthetic = value

    def _ensure_mask_index_chunks(self) -> None:
        """Append the `tdli` index chunk AE requires for a materialized
        MASK_INDEX effect param (e.g. a Path Text path selector).

        AE stores a mask-index param's value in a `tdli` (S4Chunk) after the
        cdat (the cdat itself stays all-zeros, see
        `_complete_static_value_chunks`), and rejects a materialized tdbs
        lacking it with "missing data in file".
        """
        if self.property_value_type != PropertyValueType.MASK_INDEX:
            return
        if any(getattr(c, "chunk_type", "") == "tdli" for c in self._tdbs.chunks):
            return
        index = self._value if isinstance(self._value, int) else 0
        self._tdbs.chunks.append(S4Chunk(chunk_type="tdli", value=index))

    def _ensure_time_base(self) -> None:
        """Stamp the containing comp's timebase into a py-created tdb4.

        AE writes `cdta.internal_timebase` (e.g. 24576 for 24 fps) into
        every layer-level tdb4 and rejects the file with "zero denominator
        converting ratio denominators" when the field is 0. Synthesized
        tdb4 chunks start at 0 (or the 30 fps placeholder 0x7800), so fix
        them up the moment they become visible to `write_aep`. Chunks
        parsed from a real file never reach this method (the synthetic
        early-return above), preserving byte identity.
        """
        if self._tdb4 is None:
            return
        comp = self._owning_comp()
        if comp is not None:
            # The layer's own base, not the comp's: a stretched layer counts
            # its keyframe ticks against `internal_timebase * |stretch|`.
            self._tdb4._time_base = int(
                self._layer_timebase or comp._cdta.internal_timebase
            )
            if (
                self._tdb4._spatial_marker
                and not self._tdb4.color
                and not self._tdb4.no_value
            ):
                # AE writes the comp's pixel aspect into spatial point
                # tdb4s (not orientation / color).
                self._tdb4.pixel_aspect = comp._cdta.pixel_aspect

    def _ensure_bound_chunks(self) -> None:
        """Append the `tdum`/`tduM` min/max chunks AE requires for
        multi-dimensional non-spatial vector properties (e.g. Scale) and
        for bounded scalar properties (percentage coefficients, position
        followers, time remap).

        After Effects writes these `[0.0]` placeholder bounds for such
        properties and rejects the materialized property ("missing data
        in file") when they are absent. Spatial (Position, Anchor Point),
        unbounded 1D (Rotation), integer and color properties do not
        need them.
        """
        if self._tdum is not None or self._tduM is not None:
            return
        if self._hint_bounds is not None:
            # Layer Styles scalars: AE writes the UI slider hints (not the
            # real clamp) as the bound values (psd_layer_styles fixtures).
            low, high = self._hint_bounds
            self._tdbs.chunks.append(TdumChunk(chunk_type="tdum", values=[low]))
            self._tdbs.chunks.append(TdumChunk(chunk_type="tduM", values=[high]))
            return
        # Synthetic EFFECT params: AE writes [0.0] tdum/tduM for SCALAR /
        # INTEGER / SLIDER control types (RE'd vs AE 2026) regardless of
        # can_vary, and omits them for ANGLE / POINT / 3D / COLOR / BOOLEAN /
        # ENUM / LAYER. This bypasses the can_vary / fallback gating below,
        # which only governs layer/shape props.
        effect_bounded = (
            self._is_in_effect()
            and self._property_control_type in self._EFFECT_BOUNDED_CONTROL_TYPES
        )
        if not effect_bounded:
            # AE writes [0.0] bounds only on ANIMATABLE bounded leaves; it omits
            # them on bounded menu/dropdown leaves (Line Cap, Fill Rule, Grad
            # Type, ...) which report can_vary_over_time=False. Match that.
            if self._can_vary_over_time is False:
                return
            multi_dim_vector = (
                not self._color
                and not self.is_spatial
                and self._vector
                and self.dimensions > 1
            )
            fallback_bounded = (
                (
                    self._min_value_fallback is not _UNSET
                    or self._max_value_fallback is not _UNSET
                )
                and not self._color
                and not self.is_spatial
                and not self._tdb4.integer
                and not self._is_in_effect()
            )
            # AE persists the [0.0] placeholder tdum/tduM for the props in
            # _PLACEHOLDER_UNBOUNDED (e.g. Light Intensity) even though
            # ExtendScript reports hasMin/hasMax=False, and rejects a
            # materialized one that lacks them ("missing data in file").
            placeholder_unbounded = self.match_name in _PLACEHOLDER_UNBOUNDED
            if (
                not multi_dim_vector
                and not self._bound_chunks_hint
                and not fallback_bounded
                and not placeholder_unbounded
            ):
                return
        if any(c.chunk_type in ("tdum", "tduM") for c in self._tdbs.chunks):
            return
        # Integer-typed effect params (SCALAR/INTEGER) use u4-encoded bounds;
        # vector params (SLIDER) and layer/shape props use double-encoded ones.
        is_int = self._tdb4 is not None and self._tdb4.integer
        self._tdbs.chunks.append(
            TdumChunk(chunk_type="tdum", values=[0.0], is_integer=is_int)
        )
        self._tdbs.chunks.append(
            TdumChunk(chunk_type="tduM", values=[0.0], is_integer=is_int)
        )

    # The tdum/tduM values AE writes for this property at materialization
    # (UI slider hints); set from `PropSpec.hint_bounds` in `_new`, `None`
    # (the class default, covering parsed properties) keeps the family
    # behavior in `_ensure_bound_chunks`.
    _hint_bounds: tuple[float, float] | None = None

    _NUMERIC_PVTS = frozenset(
        {
            PropertyValueType.OneD,
            PropertyValueType.TwoD,
            PropertyValueType.ThreeD,
            PropertyValueType.TwoD_SPATIAL,
            PropertyValueType.ThreeD_SPATIAL,
            PropertyValueType.COLOR,
            PropertyValueType.NO_VALUE,
        }
    )

    # Effect-param control types AE writes [0.0] tdum/tduM bounds for when a
    # synthesized param is materialized (RE'd vs AE 2026 references; see
    # scripts/_tmp_a6re). The other control types (ANGLE / POINT / 3D / COLOR /
    # BOOLEAN / ENUM / LAYER) get no bounds. A SCALAR / INTEGER / SLIDER effect
    # param materialized WITHOUT these placeholders is rejected by AE ("missing
    # data in file"). AE's full per-control-type tdb4 canon is NOT reproduced -
    # AE tolerates the synthesis-default flags on open, and matching the canon's
    # integer bit would wrongly flip can_set_expression for point/scalar params.
    _EFFECT_BOUNDED_CONTROL_TYPES: ClassVar[frozenset[PropertyControlType]] = frozenset(
        {
            PropertyControlType.SCALAR,
            PropertyControlType.INTEGER,
            PropertyControlType.SLIDER,
        }
    )

    def _complete_static_value_chunks(self) -> None:
        """Give a materialized property the `cdat` AE writes: present,
        padded to AE's canonical length, and in raw binary units.

        AE pads cdat to `5 * dims` doubles for scalar / vector
        properties and `3 * dims` for color and spatial ones, and
        refuses materialized properties without a value chunk
        ("missing data in file"). Complex kinds (orientation, marker,
        shape, gradient, text) manage their own value containers.
        """
        if self._parallel_kind() is not None or self._tdb4 is None:
            return
        if self.property_value_type == PropertyValueType.MASK_INDEX:
            # MASK_INDEX cdat is 5 zero doubles (like OneD); the index value
            # lives in a separate `tdli` chunk (see _ensure_mask_index_chunks),
            # NOT in the cdat, which stays all-zeros.
            if self._cdat is None:
                cdat = CdatChunk(values=[0.0] * 5)
                self._tdbs.chunks.insert(
                    index_by_identity(self._tdbs.chunks, self._tdb4) + 1, cdat
                )
                self._cdat = cdat
            elif len(self._cdat.values) < 5:
                self._cdat.values = [0.0] * 5
            return
        if self.property_value_type not in self._NUMERIC_PVTS:
            return
        if self._tdb4.no_value:
            # No-value properties (e.g. Layer Source Alternate) carry a
            # 4-zero-byte empty cdat; a padded double block makes AE fail
            # with "chunk in file too big".
            if self._cdat is None:
                cdat = CdatChunk(pad=b"\x00\x00\x00\x00")
                self._tdbs.chunks.insert(
                    index_by_identity(self._tdbs.chunks, self._tdb4) + 1, cdat
                )
                self._cdat = cdat
            return
        if self.match_name in ("ADBE Anchor Point", "ADBE Position"):
            # AE writes static transform spatials with vector-style flags
            # (measured on addCamera / addLight output, AE 2026).
            self._tdb4._spatial_static_flags = 0x0F
            self._tdb4._value_hint_type = 0xFFFF
            self._tdb4._value_hint_flag = 0xFF
            self._tdb4._cvot_flags = 0xFF
            self._tdb4._type_flags = 0x08
            self._tdb4._property_category = 0x09
            self._tdb4._spatial_marker = True
        elif self.match_name in (
            "ADBE Vector Position",
            "ADBE Vector Anchor",
            "ADBE Vector Grad Start Pt",
            "ADBE Vector Grad End Pt",
        ):
            # Static shape spatials (measured on an AE 2026 SVG-cropped
            # import: group transform Position/Anchor + gradient-fill
            # Start/End points share one canon). Same vector-style flags as
            # a layer transform plus pad2a=3; without them AE silently
            # ignores the materialized value (reads 0,0).
            self._tdb4._spatial_static_flags = 0x0F
            self._tdb4._pad2a = 3
            self._tdb4._value_hint_type = 0xFFFF
            self._tdb4._value_hint_flag = 0xFF
            self._tdb4._cvot_flags = 0xFF
            self._tdb4._type_flags = 0x08
            self._tdb4._property_category = 0x09
            self._tdb4._spatial_marker = True
        elif (
            self._color
            and not self._is_in_effect()
            and self._tdb4._value_hint_type == 0
        ):
            # Static color canon (measured on a script-modified vector
            # fill color, AE 2026); with the synthesis-default flags AE
            # silently ignores the materialized value.
            self._tdb4._spatial_static_flags = 0x07
            self._tdb4._value_hint_type = 2
            self._tdb4._value_hint_flag = 0xFF
            self._tdb4._cvot_flags = 0xFF
            self._tdb4._type_flags = 0x01
            self._tdb4._property_category = 0x01
            self._tdb4._spatial_marker = True
        elif (
            not self._color
            and not self.is_spatial
            and not self._tdb4.integer
            and not self._is_in_effect()
            and self._tdb4._value_hint_type == 0
            and self._tdb4._property_category == 0
        ):
            # Plain numeric properties synthesized without a time base
            # carry default flag bytes; AE writes them with the standard
            # vector canon (Scale, Rotate Z, Opacity, Z Position...).
            self._tdb4._value_hint_type = 1
            self._tdb4._value_hint_flag = 0xFF
            self._tdb4._cvot_flags = 0xFF
            self._tdb4._type_flags |= 0x08
            self._tdb4._property_category = 0x09
        dims = self._tdb4.dimensions
        value = self._value
        if not isinstance(value, (int, float, list)):
            value = self.default_value
        if not isinstance(value, (int, float, list)):
            value = 0.0 if dims <= 1 else [0.0] * dims
        mult = 3 if (self._color or self.is_spatial) else 5
        target = dims * mult
        if self._cdat is None:
            cdat = CdatChunk(values=[0.0] * target)
            self._tdbs.chunks.insert(
                index_by_identity(self._tdbs.chunks, self._tdb4) + 1, cdat
            )
            self._cdat = cdat
        elif len(self._cdat.values) < target:
            self._cdat.values = list(self._cdat.values) + [0.0] * (
                target - len(self._cdat.values)
            )
        self._write_cdat(value)

    def _materialize_static_orientation(self) -> None:
        """Wrap a materialized static Orientation in the `otst` subtree
        AE writes: `otst[tdbs(cdat le) + otky[otda]]` with a 1-dim tdb4.

        AE rejects a bare big-endian Orientation tdbs with "missing data
        in file".
        """
        kind = self._parallel_kind()
        if kind is None or kind.name != "orientation":
            return
        if self._wrapper is not None or self.keyframes:
            return
        value = self._value
        if not isinstance(value, list):
            value = (
                self.default_value
                if isinstance(self.default_value, list)
                else [0.0, 0.0, 0.0]
            )
        container = self._materialize_parallel_container(kind)
        container.chunks.append(kind.build_value_chunk(self, value))
        new_cdat = kind.static_cdat(value)
        if self._cdat is not None and any(c is self._cdat for c in self._tdbs.chunks):
            self._tdbs.chunks[index_by_identity(self._tdbs.chunks, self._cdat)] = (
                new_cdat
            )
        else:
            self._tdbs.chunks.insert(
                index_by_identity(self._tdbs.chunks, self._tdb4) + 1, new_cdat
            )
        self._cdat = new_cdat

    def _chunk_body(self) -> ListChunk | None:
        return self._tdbs

    def _is_placeholder_bound(self, body: TdumChunk) -> bool:
        """`True` when this property's tdum/tduM is an all-zero `[0.0]`
        placeholder that ExtendScript reports as no bound.

        AE writes `[0.0]` bound chunks for Scale and the separated-Position
        followers even though ExtendScript reports no min/max; the bytes are
        kept on disk for round-trip but must not surface as a real bound.
        Scoped to `_PLACEHOLDER_UNBOUNDED` so genuinely-bounded props (and
        Time Remapping, whose `maxValue=0` ExtendScript does report) are
        untouched.
        """
        return self.match_name in _PLACEHOLDER_UNBOUNDED and all(
            v == 0.0 for v in body.values
        )

    @staticmethod
    def _read_tdum(body: TdumChunk) -> int | float | list[float]:
        """Extract value from a tdum/tduM chunk body."""
        if body.is_color:
            return list(body.values)
        if body.is_integer:
            return int(body.values[0])
        if len(body.values) == 1:
            return body.values[0]
        return list(body.values)

    def _read_cdat_raw(self) -> float | list[float] | None:
        """Read the raw value from the cdat chunk body.

        Returns a scalar for 1D non-color properties, a list for
        multi-dimensional or color properties, or `None` when the
        chunk has no data.
        """
        if self._cdat is None:
            return None
        values = self._cdat.values[: self.dimensions]
        if not values:
            return None
        if self.dimensions == 1 and not self._color:
            return values[0]
        return values

    def _resolve_value(self, raw: list[float] | float | int | None) -> _ValueType:
        """Forward-transform a raw binary value to user-facing units.

        Applied in order: percent scaling, color conversion, effect point
        denormalization.
        """
        if raw is None:
            return None
        # 0. Variable-font axis: the binary stores [value, tag4cc] but
        #    ExtendScript exposes only the scalar axis value.
        if self._is_vf_axis and isinstance(raw, list) and len(raw) >= 2:
            if self._vf_tag_cache is None and raw[1]:
                self._vf_tag_cache = raw[1]
            return raw[0]
        # 1. Percent scaling (0-1 fraction -> 0-100 percentage)
        if self.match_name in _PERCENT_MATCH_NAMES:
            if isinstance(raw, (int, float)):
                raw = raw * 100.0
            elif isinstance(raw, list):
                raw = [v * 100.0 for v in raw]
            # For 2D layers, Z-Scale is stored as 0.01 in the binary
            # (irrelevant axis). ES always normalizes it to 100.
            if (
                self._scale_z_override is not None
                and isinstance(raw, list)
                and len(raw) >= 3
            ):
                raw[2] = self._scale_z_override
        # 2. Color (ARGB 0-255 -> RGBA 0-1)
        if self._color:
            if isinstance(raw, list) and len(raw) == 4:
                a, r, g, b = raw
                raw = [r / 255.0, g / 255.0, b / 255.0, a / 255.0]
        # 3. Effect point (0-1 fraction -> pixel coordinates)
        if self._effect_scale is not None:
            if isinstance(raw, list) and len(raw) >= 2:
                raw = self._apply_effect_scale(raw)
        return raw

    def _unresolve_value(self, value: _ValueType) -> _ValueType:
        """Reverse-transform a user-facing value to raw binary units.

        Applied in reverse order: effect point normalization, color
        conversion, then percent scaling.
        """
        if value is None:
            return None
        if not isinstance(value, (int, float, list)):
            return value
        if isinstance(value, list) and value and not isinstance(value[0], (int, float)):
            return value
        # 0. Variable-font axis: re-attach the tag dimension to a scalar
        #    ExtendScript-style value (raw 2-dim lists pass through).
        if self._is_vf_axis and isinstance(value, (int, float)):
            tag = self._vf_axis_tag_raw()
            if tag is not None:
                return [float(value), tag]
            return value
        # 3. Reverse effect point (pixel coordinates -> 0-1 fraction)
        if self._effect_scale is not None:
            if isinstance(value, list) and len(value) >= 2:
                value = self._apply_effect_scale(value, invert=True)
        # 2. Reverse color (RGBA 0-1 -> ARGB 0-255)
        if self._color:
            if isinstance(value, list) and len(value) == 4:
                r, g, b, a = value
                value = [a * 255.0, r * 255.0, g * 255.0, b * 255.0]
        # 1. Reverse percent (0-100 -> 0-1 fraction)
        if self.match_name in _PERCENT_MATCH_NAMES:
            if isinstance(value, (int, float)):
                value = value / 100.0
            elif isinstance(value, list):
                value = [v / 100.0 for v in value]
        return value

    def _write_cdat(self, value: Any) -> None:
        """Write a user-facing value to the cdat chunk body.

        Applies `_unresolve_value` to convert back to raw binary units
        before writing.
        """
        if self._cdat is None:
            return
        if not isinstance(value, (int, float, list)):
            return
        if isinstance(value, list) and value and not isinstance(value[0], (int, float)):
            return
        raw_value = self._unresolve_value(value)
        raw = list(self._cdat.values)
        if isinstance(raw_value, list):
            raw[: len(raw_value)] = raw_value
        elif isinstance(raw_value, (int, float)):
            raw[0] = raw_value
        self._cdat.values = raw

    def _separated_value(self, time: float | None = None) -> list[float] | None:
        """The leader's value composed from its followers, or `None`.

        While `dimensions_separated` is on, the leader's own `cdat` is dead:
        AE resets it to the comp-centre default on separate and drives the
        layer from the X / Y / Z followers instead. Reading the stored value
        reports that default - `keyframe_separated_dimensions.aep` stores
        `[100, 100, 0]` on a 200x200 comp where AE reports `[0, 200, 0]`.

        With a `time`, each follower is sampled there instead: the leader
        holds no keyframes while separated, so `value_at_time` would
        otherwise report the same frozen value for the whole timeline.
        """
        followers = self._separation_followers()
        if followers is None:
            return None
        composed: list[float] = []
        for follower in followers:
            component = follower.value if time is None else follower.value_at_time(time)
            if not isinstance(component, (int, float)):
                return None
            composed.append(float(component))
        return composed

    def _separation_followers(self) -> list[Property] | None:
        """This leader's X / Y / Z followers while dimensions are separated.

        `None` when the property is not a separated leader, and while the
        followers have not been synthesized yet - they are created after
        the leader, so the leader is briefly separated with nothing to
        drive.
        """
        if not self.is_separation_leader or not self.dimensions_separated:
            return None
        followers = [self.get_separation_follower(dim) for dim in range(3)]
        if any(follower is None for follower in followers):
            return None
        return cast("list[Property]", followers)

    @property
    def value(self) -> _ValueType:
        """The value of the named property at the current time.

        If `expression_enabled` is `True`, returns the evaluated expression
        value. If there are keyframes, returns the keyframed value at the
        current time. Otherwise, returns the static value. Read / Write.

        The type depends on `property_value_type`:
        `list[float]`, `float`, `int`, [Gradient][], [MarkerValue][],
        [Shape][], [TextDocument][], or `None`.

        Mutations on complex value types (TextDocument, Shape,
        MarkerValue, Gradient) write through to the backing chunks
        automatically, so re-assignment is not needed:

        ```python
        text_doc = prop.value
        text_doc.font_size = 72  # persists automatically
        # prop.value = text_doc  # unnecessary - same object
        ```
        """
        if self._tdpi is not None and self._composition is not None:
            layer_id = self._tdpi.value
            if layer_id == 0:
                return 0
            return self._composition._layer_id_to_index.get(layer_id, -1) + 1
        separated = self._separated_value()
        if separated is not None:
            return separated
        if self._value is not None:
            if (
                self.match_name == "ADBE Mask Shape"
                and isinstance(self._value, Shape)
                and self._value._layer is None
            ):
                # Mask space is LAYER space, but the cached parse Shape
                # (from `_parse_shape_shap`) only knows the comp. Stamp the
                # owning layer so its vertices/tangents denormalize by the
                # layer's source size, matching the write and parallel-read
                # paths (a mask on a layer smaller than its comp would
                # otherwise read comp-scaled coordinates).
                self._value._layer = self._containing_layer
            return self._wire_text_version(self._value)
        if self.keyframes:
            return self.value_at_time(0)
        if self._cdat is not None:
            return self._resolve_value(self._read_cdat_raw())
        return None

    @value.setter
    def value(self, value: _ValueType) -> None:
        if self._separation_followers() is not None:
            raise ValueError(
                f"cannot set the value of {self.match_name!r} while its "
                f"dimensions are separated; write its X / Y / Z followers "
                f"instead (get_separation_follower)"
            )
        self._set_own_value(value)

    def _set_separated_value(
        self, value: _ValueType, followers: list[Property]
    ) -> None:
        """Write a separated leader's value through its X / Y / Z followers.

        Not reachable from the public setter, which rejects a separated
        leader as After Effects does. This is the path AE takes *itself*
        when it reparents a layer: it compensates the followers even though
        `setValue` on the leader errors. `Layer.parent` is the caller.

        While `dimensions_separated` is on the leader's own `cdat` is dead -
        AE drives the layer from the followers - so a write that landed
        there would read back as the stale default and never reach what AE
        renders. This is the write-side counterpart of `_separated_value`.

        Only components that actually change are written, which leaves an
        untouched Z follower synthetic on a 2D layer (as AE does) and
        avoids materializing it for nothing.
        """
        _validate_value(self, value)
        if not isinstance(value, (list, tuple)):
            raise ValueError(
                "a dimension-separated property's value must be a sequence "
                f"of {len(followers)} numbers"
            )
        for follower, component in zip(followers, value):
            if follower.value != component:
                follower.value = component

    def _set_own_value(self, value: _ValueType) -> None:
        """Write this property's own value, bypassing any separation fan-out.

        The raw path under the `value` setter, for the deliberate "park the
        leader on its default" writes in `_separate_static` /
        `_separate_animated`, which target the dead leader on purpose.
        """
        # Re-assigning the identical complex value object (TextDocument,
        # Shape, MarkerValue, Gradient) is a no-op: those types write through
        # to the backing chunks via their own descriptors. Plain numeric/list
        # values have no write-through, so a value read, mutated in place, and
        # re-assigned must still be written to the cdat chunk.
        if value is self._value and not isinstance(value, (int, float, list)):
            return
        if self.keyframes:
            # ExtendScript: "Can not call setValue() on a property with
            # keyframes." Writing a static value alongside keyframe data
            # produces a file AE refuses to open.
            raise ValueError(
                "Cannot set value on a property with keyframes. "
                "Use set_value_at_time() instead."
            )
        _validate_value(self, value)
        complex_value = not isinstance(value, (int, float, list, type(None)))
        # Arbitrary-data params (CUSTOM_VALUE, e.g. an effect's Curves /
        # ARBITRARY_DATA leaf) store their data in a separate blob, not the
        # numeric cdat. Writing a scalar/list into the cdat overflows it
        # (AE: "chunk in file too big") or crashes on the empty buffer; reject
        # it. Complex value objects (a mask Shape, also CUSTOM_VALUE-seeded)
        # take the write-through path below and are unaffected.
        if (
            not complex_value
            and self.property_value_type == PropertyValueType.CUSTOM_VALUE
        ):
            raise ValueError(
                "Cannot set a numeric value on a CUSTOM_VALUE (arbitrary-data) "
                "property; its data is not stored in the numeric value chunk."
            )
        # A freshly-added mask has no Mask Shape om-s container yet. Build AE's
        # default full-frame path with the mask-specific builder BEFORE
        # `_ensure_materialized` runs: it replaces the still-synthetic Mask
        # Shape placeholder in place, whereas materializing first leaves the
        # placeholder behind and AE rejects the duplicate ("missing data").
        if (
            complex_value
            and self.match_name == "ADBE Mask Shape"
            and self._kf_value_container is None
        ):
            from .mask_property_group import MaskPropertyGroup

            parent = self._parent_property
            if isinstance(parent, MaskPropertyGroup):
                parent._materialize_mask_shape()
        self._ensure_materialized()
        if complex_value:
            # A new complex value object (Shape, Gradient, TextDocument,
            # MarkerValue) assigned to a static property: `_write_cdat`
            # only writes numeric values, so the static value container
            # must be rebuilt.
            self._value = self._write_static_complex_value(value)
            return
        if self.property_value_type == PropertyValueType.MASK_INDEX:
            # The mask index lives in the `tdli` chunk, not the cdat (which
            # stays all-zeros); _ensure_materialized has appended one.
            index = int(value) if isinstance(value, (int, float)) else 0
            for chunk in self._tdbs.chunks:
                if getattr(chunk, "chunk_type", "") == "tdli":
                    cast("S4Chunk", chunk).value = index
                    break
            self._value = value
            return
        self._write_cdat(value)
        self._value = value

    def _cache_value(self, value: _ValueType) -> None:
        """Cache a value decoded from chunks (parser-only).

        Unlike the public `value` setter this never rebuilds value
        containers, never enforces the keyframe guard, and skips
        validation: the value comes from the file and the chunks
        already hold it. `_write_cdat` keeps the numeric path
        byte-faithful (a no-op write-back of the values just read).
        """
        self._write_cdat(value)
        self._value = value

    def _write_static_complex_value(self, value: Any) -> Any:
        """Rebuild a static complex property's value container chunk.

        Static shapes / gradients store their single value chunk as the
        only entry of the parallel container (omks / GCky); rebuild it
        from `value` and return the model rebound to the inserted chunk
        (so later in-place edits reach the serialized form, not the
        caller's chunk). Orientation stores its value in the
        (little-endian) cdat, which `_write_cdat` handles, so it is left
        to the numeric path. Text (byte-format-sensitive btdk COS) and
        markers (no static value) have no clean from-scratch container
        build and are rejected.
        """
        kind = self._parallel_kind()
        if kind is None or kind.name == "orientation":
            self._write_cdat(value)
            return value
        if kind.name == "text":
            raise ValueError(
                "Cannot replace a static text value with a new TextDocument. "
                "Mutate the existing prop.value in place (e.g. prop.value.text = ...)."
            )
        if kind.name == "marker":
            raise ValueError("Markers have no static value to set.")
        container = self._kf_value_container
        if container is None:
            # A synthesized complex property (e.g. a freshly added gradient
            # fill) has no wrapper/container yet; build it the same way
            # animating would, then seed the static value.
            if not kind.can_materialize_wrapper:
                raise ValueError(
                    f"static {self.match_name!r} property has no value "
                    "container to update"
                )
            container = self._materialize_parallel_container(kind)
            # AE keeps an (empty) cdat in the static tdbs; a synthesized
            # gradient leaf has none, which AE rejects as "missing data".
            if self._cdat is None and self._tdbs is not None and self._tdb4 is not None:
                cdat = kind.static_cdat(value)
                self._tdbs.chunks.insert(
                    index_by_identity(self._tdbs.chunks, self._tdb4) + 1, cdat
                )
                self._cdat = cdat
        value_chunk = kind.build_value_chunk(self, value)
        if container.chunks:
            container.chunks[0] = value_chunk
        else:
            container.chunks.append(value_chunk)
        wrapped = kind.wrap_value_chunk(self, value_chunk)
        return wrapped if wrapped is not None else value

    def _wire_text_version(self, value: _ValueType) -> _ValueType:
        """Give a [TextDocument][] value a path to the project head so its
        version-gated attributes can resolve the AE major version. No-op for
        other value types or when the containing comp is unknown."""
        if isinstance(value, TextDocument) and self._composition is not None:
            value._head = self._composition._project._head
        return value

    @property
    def min_value(self) -> Any:
        """
        The minimum permitted value of the named property. Only valid if
        `has_min` is `True`. Read-only.
        """
        if self.match_name in _UNBOUNDED_MATCH_NAMES:
            return None
        if self._min_value_fallback is not _UNSET:
            return self._min_value_fallback
        if self._tdum is not None:
            if self._is_placeholder_bound(self._tdum):
                return None
            return self._read_tdum(self._tdum)
        return None

    @property
    def max_value(self) -> Any:
        """
        The maximum permitted value of the named property. Only valid if
        `has_max` is `True`. Read-only.
        """
        if self.match_name in _UNBOUNDED_MATCH_NAMES:
            return None
        if self._max_value_fallback is not _UNSET:
            return self._max_value_fallback
        if self._tduM is not None:
            if self._is_placeholder_bound(self._tduM):
                return None
            return self._read_tdum(self._tduM)
        return None

    @property
    def units_text(self) -> str:
        """
        The text description of the units in which the value is expressed.

        Common values include `"pixels"`, `"degrees"`, `"percent"`,
        `"seconds"`, and `"dB"`. An empty string indicates the property
        has no specific unit. Read-only.
        """
        if self._units_text is not None:
            return self._units_text
        if self._property_control_type == PropertyControlType.ANGLE:
            return "degrees"
        # The map holds the spatial-valued exceptions (e.g. ADBE Orientation
        # is 3D-spatial but degrees), so it must win over the pixels heuristic.
        mapped = UNITS_TEXT_MAP.get(self.match_name)
        if mapped is not None:
            return mapped
        if self._property_value_type in (
            PropertyValueType.TwoD_SPATIAL,
            PropertyValueType.ThreeD_SPATIAL,
        ):
            return "pixels"
        return ""

    @property
    def value_text(self) -> str | None:
        """The text string of the currently-selected item in a dropdown
        menu property.

        Only custom dropdown menus are supported (the `Menu` property of
        a Dropdown Menu Control, whose item strings are stored in the
        project file); returns `None` for every other property.
        ExtendScript additionally covers built-in dropdowns, but their
        item strings are application resources absent from the file.
        Read-only.

        Note:
            This functionality was added in After Effects 26.0.
        """
        params = self.property_parameters
        if not params:
            return None
        value = self.value
        if not isinstance(value, (int, float)):
            return None
        # Dropdown values are 1-based indices into the menu strings.
        index = int(value) - 1
        if 0 <= index < len(params):
            return params[index]
        return None

    @property
    def property_parameters(self) -> list[str] | None:
        """An array of all item strings in a dropdown menu property. This
        attribute applies to dropdown menu properties of effects and
        layers, including custom strings in the Menu property of the
        Dropdown Menu Control. Read / Write.

        Writing is only supported on the Menu property of a Dropdown
        Menu Control (see `is_dropdown_effect`; mirrors ExtendScript
        `Property.setPropertyParameters()`): the new items replace the
        existing menu entries in the project file. Items must be
        non-empty unique strings without `\\` or `|` characters; the
        string `(-` inserts a separator line (and may repeat).
        """
        return self._property_parameters

    @property_parameters.setter
    def property_parameters(self, items: list[str]) -> None:
        effect = self._parent_property
        if not (
            self.is_dropdown_effect
            and effect is not None
            and effect.match_name.startswith("Pseudo/")
        ):
            raise ValueError(
                "property_parameters can only be set on the Menu property "
                "of a Dropdown Menu Control."
            )
        if not isinstance(items, (list, tuple)) or not items:
            raise ValueError("items must be a non-empty list of strings.")
        seen = set()
        for item in items:
            if not isinstance(item, str) or not item:
                raise ValueError("menu items must be non-empty strings.")
            # The items are stored pipe-delimited, so "|" is as
            # unencodable as ExtendScript's forbidden "\".
            if "\\" in item or "|" in item:
                raise ValueError(
                    "menu items must not contain the '\\' or '|' characters."
                )
            if item != "(-":
                if item in seen:
                    raise ValueError(f"duplicate menu item {item!r}.")
                seen.add(item)
        items = list(items)
        self._write_dropdown_items(items)
        self._property_parameters = items
        self.nb_options = len(items)
        self._max_value_fallback = len(items)

    def _dropdown_param_defs(self) -> list[ListChunk]:
        """The `parT` containers holding this Menu param's definition.

        A dropdown's parameter definition lives in the owning effect's
        layer-level `sspc` and is mirrored in the project-level
        `LIST:EfdG`; both copies must stay in sync when the menu items
        change.
        """
        effect = self._parent_property
        assert effect is not None
        parts: list[ListChunk] = []
        parade = effect._parent_property
        if parade is not None:
            if parade._tdgp is not None:
                sspc = effect._backing_list_chunk(parade._tdgp)
                if sspc.list_type == "sspc":
                    try:
                        parts.append(
                            find_by_list_type(chunks=sspc.chunks, list_type="parT")
                        )
                    except ChunkNotFoundError:
                        pass
            # The project-level EfdG mirror, via the parade's cached
            # definitions lookup. Effect params can parse without a
            # composition ref, leaving the project unreachable.
            try:
                entry = parade._installed_effect_def(effect.match_name)
            except ValueError:
                entry = None
            if entry is not None:
                try:
                    parts.append(
                        find_by_list_type(chunks=entry[2].chunks, list_type="parT")
                    )
                except ChunkNotFoundError:
                    pass
        return parts

    def _write_dropdown_items(self, items: list[str]) -> None:
        """Write new menu items into every copy of this param's definition."""
        joined = "|".join(items)
        written = False
        for part in self._dropdown_param_defs():
            current: str | None = None
            for chunk in part.chunks:
                if chunk.chunk_type == "tdmn":
                    current = cast("TdmnChunk", chunk).value
                elif current == self.match_name:
                    if isinstance(chunk, EnumPardChunk):
                        # The option count lives in the high 16 bits; AE
                        # keeps the low 16 bits unchanged.
                        chunk.nb_options = (len(items) << 16) | (
                            chunk.nb_options & 0xFFFF
                        )
                    elif chunk.chunk_type == "pdnm":
                        utf8 = find_by_type(
                            chunks=cast("ContainerChunk", chunk).chunks,
                            chunk_type="Utf8",
                        )
                        cast("Utf8Chunk", utf8).value = joined
                        written = True
        if not written:
            raise ValueError(
                "No stored menu definition (pdnm) found for this property."
            )
        # Keep the synthesis-side parameter definitions in sync. Effect
        # params parse without a composition ref; reach the project
        # through the owning layer instead.
        effect = self._parent_property
        assert effect is not None
        comp = self._composition
        if comp is None:
            try:
                comp = self._containing_layer.containing_comp
            except ValueError:
                comp = None
        if comp is not None:
            param_def = comp._project._effect_param_defs.get(effect.match_name, {}).get(
                self.match_name
            )
            if param_def is not None:
                param_def["property_parameters"] = list(items)
                param_def["nb_options"] = len(items)
                param_def["max_value"] = len(items)

    @property
    def can_vary_over_time(self) -> bool:
        """
        When `True`, the named property can vary over time - that is, keyframe
        values or expressions can be written to this property.

        Note:
            A small subset of effect dropdown / menu parameters may report
            `can_vary_over_time` as `False` in the binary even though After
            Effects allows keyframing them.
        Read-only.
        """
        if self._can_vary_over_time is not None:
            return self._can_vary_over_time
        if self.match_name in _CANVARY_OVERRIDES:
            return _CANVARY_OVERRIDES[self.match_name]
        # NO_VALUE properties always report canVaryOverTime=True in AE,
        # even though the binary byte says otherwise.
        return bool(self._tdb4.can_vary_over_time or self._no_value)

    @property
    def dimensions_separated(self) -> bool:
        """
        When `True`, the property's dimensions are represented as separate
        properties. For example, if the layer's position is represented as X
        Position and Y Position properties in the Timeline panel, the Position
        property has this attribute set to `True`. This attribute applies only
        when the property is a "separation leader" (a multidimensional property
        that can be separated). Read / Write.
        """
        if self._dimensions_separated is not None:
            return self._dimensions_separated
        if self.match_name == "ADBE Position":
            # Camera and Light positions separate like any other 3-D layer's:
            # AE 2026 reports `dimensionsSeparated` false on a fresh one,
            # accepts the write, and reads back true with the position intact.
            #
            assert self._tdsb is not None
            return bool(self._tdsb.dimensions_separated)
        return False

    @dimensions_separated.setter
    def dimensions_separated(self, value: bool) -> None:
        validate_bool(value)
        if not self.is_separation_leader:
            # AE silently ignores this on a non-leader; raising keeps a
            # caller's mistake visible instead of swallowing the write.
            raise ValueError(
                f"dimensions_separated is only settable on the separation "
                f"leader, not {self.match_name!r}"
            )
        if value == self.dimensions_separated:
            # AE's dimensionsSeparated is idempotent. Re-running the transfer
            # would re-seed the followers from a leader that the first call
            # already reset to its default, destroying the separated values.
            return

        followers = [self.get_separation_follower(dim) for dim in range(3)]
        if any(follower is None for follower in followers):
            raise ValueError(
                f"{self.match_name!r} has no separation followers to transfer to"
            )
        live = cast("list[Property]", followers)
        animated = bool(self.keyframes) or any(follower.keyframes for follower in live)
        if value:
            if animated:
                self._separate_animated(live)
            else:
                self._separate_static(live)
        elif animated:
            self._recombine_animated(live)
        else:
            self._recombine_static(live)

    def _separate_static(self, followers: list[Property]) -> None:
        """Hand the leader's components to its followers.

        AE seeds X / Y / Z from the leader, materializes them, and resets the
        leader's own `cdat` to the property default - while separated the
        leader is dead and the followers drive the layer. Z is materialized
        only on a 3D layer, matching AE (`transform_separated.aep` leaves it
        synthetic on a 2D one).
        """
        components = cast("list[float]", self.value)
        default = cast("list[float]", self.default_value)
        self._ensure_materialized()
        assert self._tdsb is not None
        self._tdsb.dimensions_separated = True
        # AE writes the group collapsed alongside it (enable byte 0x3,
        # lock byte 0x8 on every separated position it authored).
        self._tdsb.collapsed = True
        self._dimensions_separated = True
        three_d = self._containing_layer.is_3d
        for dimension, follower in enumerate(followers):
            if dimension == 2 and not three_d:
                continue
            follower.value = components[dimension]
        # The leader keeps a value AE never reads again; AE parks it on the
        # default rather than leaving the old position there.
        self._set_own_value(list(default))

    def _recombine_static(self, followers: list[Property]) -> None:
        """Fold the followers back into the leader.

        AE writes the composed value onto the leader and reverts the
        followers to their dead, unserialized state.
        """
        composed = [float(cast("float", follower.value)) for follower in followers]
        self._ensure_materialized()
        assert self._tdsb is not None
        self._tdsb.dimensions_separated = False
        self._dimensions_separated = False
        self.value = composed
        for follower in followers:
            _deactivate_follower(follower)

    @staticmethod
    def _segment_spans(times: list[float]) -> tuple[list[float], list[float]]:
        """Incoming and outgoing segment durations for each keyframe."""
        incoming = [0.0] + [times[i] - times[i - 1] for i in range(1, len(times))]
        outgoing = [times[i + 1] - times[i] for i in range(len(times) - 1)] + [0.0]
        return incoming, outgoing

    def _separate_animated(self, followers: list[Property]) -> None:
        """Move the leader's keyframes onto its followers.

        AE turns each spatial tangent into a per-dimension temporal ease:
        `speed = |tangent| * 100` and `influence = 1 / dt` percent, where
        `dt` is that side's segment duration. Measured on AE 2026 over
        segment durations of 0.5, 2.5, 5 and 12 s - 16 components, all
        matching. The in-side tangent points backwards, so its speed takes
        the opposite sign.

        Interpolation types are copied across rather than derived from
        whether a tangent is non-zero, which is what AE does: AE flattens a
        HOLD keyframe to LINEAR here, and this project prefers not to mirror
        that loss.
        """
        keyframes = list(self.keyframes)
        times = [keyframe.time for keyframe in keyframes]
        values = [cast("list[float]", keyframe.value) for keyframe in keyframes]
        in_tangents = [keyframe.in_spatial_tangent or [] for keyframe in keyframes]
        out_tangents = [keyframe.out_spatial_tangent or [] for keyframe in keyframes]
        interpolation = [
            (keyframe.in_interpolation_type, keyframe.out_interpolation_type)
            for keyframe in keyframes
        ]
        incoming, outgoing = self._segment_spans(times)

        self.remove_all_keys()
        self._ensure_materialized()
        assert self._tdsb is not None
        self._tdsb.dimensions_separated = True
        # AE writes the group collapsed alongside it (enable byte 0x3,
        # lock byte 0x8 on every separated position it authored).
        self._tdsb.collapsed = True
        self._dimensions_separated = True
        self._set_own_value(list(cast("list[float]", self.default_value)))

        three_d = self._containing_layer.is_3d
        for dimension, follower in enumerate(followers):
            if dimension == 2 and not three_d:
                continue
            for index, time in enumerate(times):
                added = follower._add_key(time, values[index][dimension])
                keyframe = follower.keyframes[added]
                keyframe.in_interpolation_type = interpolation[index][0]
                keyframe.out_interpolation_type = interpolation[index][1]
                # Before the ease, not after: the continuity flag ties the
                # out speed to the in speed, and AE's own separated keyframes
                # carry tC=True with *different* speeds on each side.
                keyframe.temporal_continuous = True
                for direction, tangents, spans in (
                    ("in", in_tangents, incoming),
                    ("out", out_tangents, outgoing),
                ):
                    span = spans[index]
                    tangent = tangents[index]
                    if span <= 0 or dimension >= len(tangent):
                        # An outer side has no segment to ease along; AE
                        # parks it on zero speed and the default influence.
                        keyframe._apply_ease(
                            [KeyframeEase(speed=0.0, influence=_DEFAULT_INFLUENCE)],
                            direction,
                        )
                        continue
                    speed = tangent[dimension] * 100.0
                    if direction == "in":
                        speed = -speed
                    # Clamped: influence is a percentage, and a segment
                    # shorter than 0.01 s (sub-frame keys, or one frame of a
                    # very high frame rate) drives `1/dt` past the 100% the
                    # field can mean.
                    keyframe._apply_ease(
                        [KeyframeEase(speed=speed, influence=min(1.0 / span, 100.0))],
                        direction,
                    )

    def _recombine_animated(self, followers: list[Property]) -> None:
        """Fold the followers' keyframes back into the leader.

        The inverse of `_separate_animated`: a tangent component is
        `speed * (influence / 100) * dt`, which round-tripped exactly in the
        AE probe.

        The leader gets a keyframe at the union of the followers' times, not
        at one follower's: separation exists so each axis can be keyed on its
        own, and pairing the lists positionally wrote X's second value beside
        Y's second value however far apart in time they sat. A dimension with
        no keyframe of its own at a given time contributes its interpolated
        value there, and no tangent.
        """
        if not any(follower.keyframes for follower in followers):
            self._recombine_static(followers)
            return
        keys_at: list[dict[float, Keyframe]] = [
            {keyframe.time: keyframe for keyframe in follower.keyframes}
            for follower in followers
        ]
        times = sorted({time for per_dimension in keys_at for time in per_dimension})
        incoming, outgoing = self._segment_spans(times)
        dimensions = len(followers)
        composed = [[0.0] * dimensions for _ in times]
        in_tangents = [[0.0] * dimensions for _ in times]
        out_tangents = [[0.0] * dimensions for _ in times]
        # Interpolation is per keyframe, not per dimension: take it from the
        # first dimension that has a keyframe at that time.
        interpolation = [
            next(
                (
                    (
                        per_dimension[time].in_interpolation_type,
                        per_dimension[time].out_interpolation_type,
                    )
                    for per_dimension in keys_at
                    if time in per_dimension
                ),
                (KeyframeInterpolationType.LINEAR, KeyframeInterpolationType.LINEAR),
            )
            for time in times
        ]

        for dimension, follower in enumerate(followers):
            for index, time in enumerate(times):
                keyframe = keys_at[dimension].get(time)
                if keyframe is None:
                    sampled = follower.value_at_time(time)
                    composed[index][dimension] = (
                        float(sampled) if isinstance(sampled, (int, float)) else 0.0
                    )
                    continue
                composed[index][dimension] = float(cast("float", keyframe.value))
                for direction, target, spans in (
                    ("in", in_tangents, incoming),
                    ("out", out_tangents, outgoing),
                ):
                    span = spans[index]
                    if span <= 0:
                        continue
                    ease = (
                        keyframe.in_temporal_ease
                        if direction == "in"
                        else keyframe.out_temporal_ease
                    )
                    if not ease:
                        continue
                    magnitude = ease[0].speed * (ease[0].influence / 100.0) * span
                    target[index][dimension] = (
                        -magnitude if direction == "in" else magnitude
                    )

        for follower in followers:
            _deactivate_follower(follower)

        self._ensure_materialized()
        assert self._tdsb is not None
        self._tdsb.dimensions_separated = False
        self._dimensions_separated = False
        for index, time in enumerate(times):
            self._add_key(time, composed[index])
        for index, keyframe in enumerate(self.keyframes):
            if index >= len(times):
                break
            keyframe.in_interpolation_type = interpolation[index][0]
            keyframe.out_interpolation_type = interpolation[index][1]
            if keyframe.in_spatial_tangent is not None:
                keyframe.in_spatial_tangent = in_tangents[index][
                    : len(keyframe.in_spatial_tangent)
                ]
            if keyframe.out_spatial_tangent is not None:
                keyframe.out_spatial_tangent = out_tangents[index][
                    : len(keyframe.out_spatial_tangent)
                ]

    def _revert_to_synthetic(self) -> None:
        """Hide this property's chunks from `write_aep` again.

        The inverse of `_ensure_materialized`'s flag flip, for a property AE
        un-materializes - a separation follower once its leader is
        recombined. Chunk order is left alone: synthetic chunks are skipped
        on write, and `_reposition_canonically` runs again if the property is
        ever materialized anew.
        """
        if self._tdsb is None or self._tdsb.synthetic:
            return
        self._set_subtree_synthetic(True)

    @property
    def expression(self) -> str:
        """
        The expression for the named property. Writeable only when
        `can_set_expression` for the named property is `True`.
        Read / Write.
        """
        if self._expression is not None:
            return self._expression
        if self._expression_utf8 is not None:
            return self._expression_utf8.value
        return ""

    @expression.setter
    def expression(self, value: str) -> None:
        if value and not self.can_set_expression:
            raise AttributeError(
                f"expression cannot be set on property {self.match_name!r}"
            )
        validate_string(value)
        if not value:
            # Empty string clears the expression (chunk + tdb4 markers).
            self._clear_expression()
            return
        self._ensure_materialized()
        if self._expression_utf8 is not None:
            self._expression_utf8.value = value
        else:
            chunk = Utf8Chunk(value=value)
            # AE stores the expression Utf8 immediately after the value
            # container (cdat or the keyframe LIST:list), BEFORE any
            # tdum/tduM bounds - the order is positional, so appending at
            # the tail makes AE reject the file ("missing data in file").
            chunks = self._tdbs.chunks
            anchor = self._cdat if self._cdat is not None else self._keyframe_inner()
            if anchor is not None:
                chunks.insert(index_by_identity(chunks, anchor) + 1, chunk)
            else:
                chunks.insert(index_by_identity(chunks, self._tdb4) + 1, chunk)
            self._expression_utf8 = chunk
        self._expression = value
        # Assigning an expression enables it (AE semantics): clear any stale
        # disabled state so the cache recomputes True (mirrors _clear_expression).
        self._expression_enabled = None
        if self._tdb4 is not None:
            # AE marks an expression-bearing parameter in tdb4._pad10; the
            # inverse of _clear_expression so a created expression round-trips.
            self._tdb4.has_expression = True
            self._tdb4._expr_flags = 0

    @property
    def expression_enabled(self) -> bool:
        """
        When `True`, the named property uses its associated expression to
        generate a value. When `False`, the keyframe information or static
        value of the property is used. Read / Write.
        """
        if self._expression_enabled is not None:
            return self._expression_enabled
        disabled = getattr(self._tdb4, "expression_disabled", True)
        return not disabled and bool(self.expression)

    @expression_enabled.setter
    def expression_enabled(self, value: bool) -> None:
        validate_bool(value)
        if value and not self.can_set_expression:
            # AE refuses the same write: "Can not set expression with this
            # property, because the property or a parent property is
            # hidden." Without the guard the write also materializes the
            # property, which for MARKER / NO_VALUE kinds emits chunks AE
            # rejects.
            raise ValueError(f"property {self.match_name!r} cannot take an expression")
        if value and not self.expression:
            # AE silently no-ops here, leaving expressionEnabled false. Doing
            # the same would clear the tdb4 disabled bit for an expression
            # that does not exist - a byte AE never writes, which the getter
            # then masks behind `bool(self.expression)`. Raising instead of
            # mirroring the no-op keeps the caller's mistake visible.
            raise ValueError(
                f"property {self.match_name!r} has no expression to enable"
            )
        self._ensure_materialized()
        self._expression_enabled = value
        self._tdb4.expression_disabled = not value

    @property
    def can_set_expression(self) -> bool:
        """
        When `True`, an expression can be set for the named property. Read-only.
        """
        return resolve_can_set_expression(self)

    @property
    def property_control_type(self) -> PropertyControlType:
        """The control type of the property (e.g., scalar, color, boolean). Read-only."""
        if self._property_control_type is not None:
            return self._property_control_type
        pct, _ = self._determine_property_types()
        return pct

    @property
    def property_value_type(self) -> PropertyValueType:
        """
        The type of value stored in the named property. Each type of data is
        stored and retrieved in a different kind of structure. For example,
        a 3D spatial property (such as a layer's position) is stored as an
        array of three floating-point values. Read-only.
        """
        if self._property_value_type is not None:
            return self._property_value_type
        _, pvt = self._determine_property_types()
        return pvt

    def _determine_property_types(
        self,
    ) -> tuple[PropertyControlType, PropertyValueType]:
        """Determine property control and value types from tdb4 flags."""
        pct = PropertyControlType.UNKNOWN
        pvt = PropertyValueType.UNKNOWN

        if self._no_value:
            pvt = PropertyValueType.NO_VALUE
        if self._color:
            pct = PropertyControlType.COLOR
            pvt = PropertyValueType.COLOR
        elif self._integer and self.dimensions <= 1:
            pct = PropertyControlType.BOOLEAN
            pvt = PropertyValueType.OneD
        elif self._vector or (self._integer and self.dimensions > 1):
            if self.dimensions == 1:
                pct = PropertyControlType.SCALAR
                pvt = PropertyValueType.OneD
            elif self.dimensions == 2:
                pct = PropertyControlType.TWO_D
                pvt = (
                    PropertyValueType.TwoD_SPATIAL
                    if self.is_spatial
                    else PropertyValueType.TwoD
                )
            elif self.dimensions == 3:
                pct = PropertyControlType.THREE_D
                pvt = (
                    PropertyValueType.ThreeD_SPATIAL
                    if self.is_spatial
                    else PropertyValueType.ThreeD
                )
        elif self.dimensions == 1:
            # A plain 1-D scalar: AE clears the tdb4 vector bit for single
            # value properties (Opacity, Rotation, the last separation
            # follower, effect sliders), so they miss the vector branch
            # above. They are still OneD scalars.
            pct = PropertyControlType.SCALAR
            pvt = PropertyValueType.OneD

        # Flag-based inference is a fallback for when the authoritative type
        # is not cached (e.g. transiently during synthesis, before the parser
        # populates it). Types that tdb4 flags cannot express - markers,
        # custom-value slots - come from the parser instead, so a miss here is
        # expected and not user-actionable: log at debug, not warning.
        if pct == PropertyControlType.UNKNOWN:
            logger.debug(
                "Could not determine type for property %s"
                " | dimensions: %s"
                " | integer: %s"
                " | is_spatial: %s"
                " | vector: %s"
                " | no_value: %s"
                " | color: %s",
                self.match_name,
                self.dimensions,
                self._integer,
                self.is_spatial,
                self._vector,
                self._no_value,
                self._color,
            )

        return pct, pvt

    @property
    def is_separation_leader(self) -> bool:
        """`True` if the property is a multidimensional property that
        can be separated.
        """
        return self.match_name == _SEPARATION_LEADER

    @property
    def is_separation_follower(self) -> bool:
        """`True` if the property is a component of a separated
        multidimensional property (e.g. X Position, Y Position,
        Z Position).
        """
        return self.match_name in _SEPARATION_FOLLOWERS

    @property
    def separation_dimension(self) -> int | None:
        """For a separated follower, the dimension it represents.

        Returns 0, 1, or 2 for X, Y, or Z. Returns `None` for
        properties that are not separation followers.
        """
        if not self.is_separation_follower:
            return None
        return _SEPARATION_FOLLOWERS.index(self.match_name)

    @property
    def separation_leader(self) -> Property | None:
        """For a separation follower, the leader property.

        Returns the [Property][] that acts as the separation leader
        (e.g. Position) for this follower (e.g. X Position).
        Returns `None` when this property is not a follower or the
        leader cannot be found.
        """
        if self.match_name not in _SEPARATION_FOLLOWERS:
            return None
        parent = self.parent_property
        if parent is None or not hasattr(parent, "properties"):
            return None
        return cast("Property | None", parent.property(_SEPARATION_LEADER))

    def get_separation_follower(self, dim: int) -> Property | None:
        """
        Retrieve a specific follower property for a separated,
        multidimensional property.

        For example, you can use this method on the Position property
        to access the separated X Position and Y Position properties.

        Args:
            dim: The dimension number (starting at 0).
        """
        if not self.is_separation_leader:
            return None
        parent = self.parent_property
        if parent is None or not hasattr(parent, "properties"):
            return None
        if dim < 0 or dim >= len(_SEPARATION_FOLLOWERS):
            raise ValueError(
                f"dim must be in range [0, {len(_SEPARATION_FOLLOWERS) - 1}], got {dim}"
            )
        match_name = _SEPARATION_FOLLOWERS[dim]
        try:
            return cast("Property | None", parent.property(match_name))
        except KeyError:
            # `property()` reaches `PropertyGroup.__getitem__`, which
            # raises rather than returning None. A separated leader on a
            # 2D layer genuinely has no Z follower.
            return None

    def nearest_key_index(self, time: float) -> int:
        """
        Returns the index of the keyframe nearest to the specified time.

        Args:
            time: The time in seconds; a floating-point value. The beginning
                of the composition is 0.
        """
        return min(
            range(len(self.keyframes)),
            key=lambda i: abs(self.keyframes[i].time - time),
        )

    def nearest_key(self, time: float) -> Keyframe:
        """
        Returns the keyframe nearest to the specified time.

        Args:
            time: The time in seconds; a floating-point value. The beginning
                of the composition is 0.
        """
        index = self.nearest_key_index(time)
        return self.keyframes[index]

    @property
    def is_modified(self) -> bool:
        """`True` if the property value differs from its default.

        A property is considered modified when it has keyframes, has an
        expression (enabled or disabled), or when its current value
        differs from `default_value`.
        """
        if self._animated:
            return True
        if self.expression:
            return True
        # A separation follower of an UNSEPARATED leader (e.g. Z Position
        # while Position is not dimension-separated) is an inactive
        # placeholder whose stored value is a meaningless 0. AE still reports
        # the Z follower as modified on camera and light layers, which are
        # always positioned in depth (probed AE 2026: camera/light Z follower
        # is True; regular layers are False). X/Y followers and every regular
        # layer fall through to the value/default comparison below, which
        # already matches AE for their comp-centered defaults.
        if self.is_separation_follower and self.separation_dimension == 2:
            leader = self.separation_leader
            if leader is not None and not leader.dimensions_separated:
                layer = self._containing_layer
                if layer._ldta.layer_type in (LayerType.CAMERA, LayerType.LIGHT):
                    return True
        # Source Text has no meaningful default - always modified when it
        # has a value (text is always user-authored).
        if self.match_name == "ADBE Text Document" and self.value is not None:
            return True
        # NO_VALUE (button/separator/group header) properties inside effects
        # are always reported as modified in ExtendScript.
        if self.property_value_type == PropertyValueType.NO_VALUE:
            return self._is_in_effect()
        # Mask reference properties that exist in the binary are always
        # modified - their presence indicates user interaction even when
        # the value is 0 (no mask).  Synthesized default slots (synthetic)
        # remain unmodified.
        if (
            self.property_value_type == PropertyValueType.MASK_INDEX
            and self._is_in_effect()
            and self._tdsb is not None
            and not self._tdsb.synthetic
        ):
            return True
        if self.match_name in _ALWAYS_MODIFIED:
            return True
        if self.default_value is not None:
            return not _values_equal(self.value, self.default_value)
        # Effect properties with no known default are considered modified
        # when they have a value - ExtendScript treats the absence of a
        # default as "always modified". LAYER_INDEX is excluded because
        # its binary default (0 = "None" layer) is not stored in pard;
        # layer references should report False when unset.
        if (
            self.value is not None
            and self._is_in_effect()
            and self.property_value_type != PropertyValueType.LAYER_INDEX
        ):
            return True
        return False

    @property
    def can_set_alternate_source(self) -> bool:
        """`True` if this is an Essential Property that supports Media
        Replacement (its alternate source can be set). Read-only.

        Decoded from the `blsi` chunk beside an `ADBE Layer Source Alternate`
        slot: a non-zero item id means a replacement source is configured.
        """
        return self._blsi is not None and self._blsi.value != 0

    @property
    def alternate_source(self) -> AVItem | None:
        """The alternate source item set for a Media Replacement slot, or
        `None` when unset / unsupported. Read / Write.

        After Effects wraps the replacement footage in a composition, so this
        resolves to that wrapper item (the `blsi` item id).
        """
        if self._blsi is None or self._blsi.value == 0 or self._composition is None:
            return None
        return cast(
            "AVItem | None",
            self._composition._project.items.get(self._blsi.value),
        )

    @alternate_source.setter
    def alternate_source(self, source: AVItem) -> None:
        """Set the alternate (replacement) source for a Media Replacement
        slot.

        `source` must be an item already in the project, and must itself be
        media-replacement compatible - AE requires both sides: "The Property
        object and the input parameters for the AVItem that is being called
        needs to be Media Replacement compatible for the action to go
        through." When `source` is a `FootageItem`, After Effects wraps it in
        a composition - placed in a root-level `Media Replacement Comps`
        folder and sized to the host comp - and points the slot at that
        wrapper; py_aep matches this. A `CompItem` is used directly (it is
        assumed to already be a wrapper).

        Raises `ValueError` when this property is not a media-replacement slot
        (`can_set_alternate_source` is `False`), when `source` is not in the
        project, or when `source.is_media_replacement_compatible` is `False`,
        and `TypeError` when `source` is not an `AVItem`.
        """
        from ..items.av_item import AVItem  # noqa: PLC0415
        from ..items.footage import FootageItem  # noqa: PLC0415

        if not self.can_set_alternate_source or self._blsi is None:
            raise ValueError(
                "This property does not support media replacement "
                "(can_set_alternate_source is False)."
            )
        if not isinstance(source, AVItem):
            raise TypeError(
                f"alternate source must be an AVItem, not {type(source).__name__}"
            )
        if (
            self._composition is None
            or source.id not in self._composition._project.items
        ):
            raise ValueError(
                f"Item {source.name!r} (id={source.id}) is not in the project."
            )
        # Checked on the passed item, not the wrapper: wrapping an audio-only
        # footage in a comp would make the slot look compatible.
        if not source.is_media_replacement_compatible:
            raise ValueError(
                f"Item {source.name!r} (id={source.id}) cannot be used as an "
                "alternate source (is_media_replacement_compatible is False)."
            )
        if isinstance(source, FootageItem):
            self._blsi.value = self._build_replacement_wrapper(source).id
        else:
            self._blsi.value = source.id

    def _build_replacement_wrapper(self, footage: FootageItem) -> CompItem:
        """Build the AE-faithful wrapper `CompItem` for a footage media
        replacement: a host-sized comp in a root-level `Media Replacement Comps`
        folder holding `footage` as its single layer, named
        `{this property's name}_{unique footage basename}`.
        """
        host = self._composition
        assert host is not None  # guarded by the caller's project check
        project = host._project
        folder = _find_or_create_wrapper_folder(project)
        name = f"{self.name}_{_unique_wrapper_suffix(footage, project)}"
        wrapper = folder.add_comp(
            name,
            host.width,
            host.height,
            host.pixel_aspect,
            host.duration,
            host.frame_rate,
        )
        # AE's wrapper comp shares the host comp's cdta exactly (timebase,
        # shutter phase, work area) - `add_comp`'s fresh skeleton diverges on
        # time_divisor/work_area_start_divisor/shutter_phase, so clone the host
        # cdta over it. idta/iide (the item ids) are separate chunks and stay
        # the wrapper's own.
        new_cdta = copy.deepcopy(host._cdta)
        chunks = wrapper._item_list.chunks
        chunks[chunks.index(wrapper._cdta)] = new_cdta
        wrapper._cdta = new_cdta
        wrapper.add(footage)
        return wrapper

    @property
    def essential_property_source(self) -> Property | PropertyGroup | AVLayer | None:
        """The originating source an Essential Property points at - a
        `Property`/`PropertyGroup` (created from a Property) or an `AVLayer`
        (Media Replacement Footage), or `None`. Read-only.

        Media-replacement overrides resolve to the source composition's
        `AVLayer` (matched by the controller's `CCId`/`CLId`). Property-source
        essential properties resolve to the source `Property` (or
        `PropertyGroup` for a grouped controller) by walking the controller's
        source-property path by match name.
        """
        from ...resolvers.essential_properties import (  # noqa: PLC0415
            resolve_essential_property_source,
        )

        return resolve_essential_property_source(self)

    @property
    def is_dropdown_effect(self) -> bool:
        """`True` if the property is the Menu property of a Dropdown Menu Control effect."""
        return self._property_control_type == PropertyControlType.ENUM

    @property
    def is_time_varying(self) -> bool:
        """`True` if the named property has keyframes or an enabled expression."""
        return bool((self.expression and self.expression_enabled) or self._animated)

    @property
    def has_max(self) -> bool:
        """`True` if there is a maximum permitted value for the named property."""
        return self.max_value is not None

    @property
    def has_min(self) -> bool:
        """`True` if there is a minimum permitted value for the named property."""
        return self.min_value is not None

    def value_at_time(self, time: float, pre_expression: bool = True) -> _ValueType:
        """Get the value of the named property at the given time.

        If the property has keyframes, the value is computed by
        interpolating between surrounding keyframes using the stored
        interpolation type and temporal ease.

        If the property is not animated, returns the static
        [value][Property.value].

        Args:
            time: The composition time in seconds at which to evaluate
                the property.
            pre_expression: When `True` the value is evaluated before
                any expression is applied (the only mode supported by
                the parser).

        Raises:
            ValueError: If `time` is NaN.
            NotImplementedError: If `pre_expression` is `False`,
                because the parser cannot evaluate expressions.
        """
        if not pre_expression:
            raise NotImplementedError(
                "Expression evaluation is not supported by the parser."
            )
        if isinstance(time, float) and math.isnan(time):
            # AE 2026: "Unable to call valueAtTime because of parameter 1.
            # NaN is not a number." Infinity IS accepted (it evaluates to the
            # last keyframe's value), so only NaN is rejected here.
            raise ValueError("time must be a number, got NaN")
        if not self.keyframes:
            separated = self._separated_value(time)
            if separated is not None:
                return separated
            return self.value

        return interpolate_keyframes(
            self._layer_time_from_comp(time),
            self.keyframes,
            self._has_motion_path,
            self._inert_dimensions(),
        )

    def _layer_time_from_comp(self, time: float) -> float:
        """Composition seconds to the owning layer's own seconds.

        The inverse of the mapping [Keyframe.time][py_aep.Keyframe.time]
        applies. Interpolation runs on this axis because AE's ease speeds
        are per layer second and a negatively stretched layer's keyframes
        only ascend here.
        """
        return (time - self._start_time_offset) / self._time_stretch

    def _inert_dimensions(self) -> frozenset[int]:
        """Value indices the owning layer ignores.

        A 2-D layer's Scale still carries a Z component, and AE holds it
        flat across a segment whose X and Y bow - it will not even store a
        Z other than 100 there.
        """
        if self.match_name != "ADBE Scale":
            return frozenset()
        layer = self._containing_layer
        if layer is None or getattr(layer, "three_d_layer", False):
            return frozenset()
        return frozenset((2,))

    def is_interpolation_type_valid(
        self, type: int | KeyframeInterpolationType
    ) -> bool:
        """Returns `True` if the named property can be interpolated using
        the specified keyframe interpolation type.

        `KeyframeInterpolationType.HOLD` is valid for every property that
        can vary over time. `LINEAR` and `BEZIER` are additionally invalid
        for hold-only properties: markers, text documents, and
        checkbox/dropdown effect parameters. When the property cannot vary
        over time (e.g. a Layer Control parameter), every type is invalid.
        (Truth table probed against AE 2026; integer effect sliders DO
        accept all three types.)

        Args:
            type: A `KeyframeInterpolationType` value.

        Raises:
            ValueError: If `type` is not a `KeyframeInterpolationType`
                member (After Effects raises a parameter error rather than
                returning `False`).
        """
        validate_enum(KeyframeInterpolationType)(type)
        interp = KeyframeInterpolationType(type)
        if not self.can_vary_over_time:
            return False
        if interp == KeyframeInterpolationType.HOLD:
            return True
        if self.property_value_type in (
            PropertyValueType.MARKER,
            PropertyValueType.TEXT_DOCUMENT,
        ):
            return False
        # Only the pard-derived control type is authoritative for the
        # checkbox/dropdown test: the tdb4 flag fallback in
        # _determine_property_types maps any 1-D integer scalar to BOOLEAN,
        # but integer sliders (e.g. Mosaic blocks) interpolate in AE.
        return self._property_control_type not in (
            PropertyControlType.BOOLEAN,
            PropertyControlType.ENUM,
        )

    # -- Keyframe mutation -------------------------------------------------

    def _time_units(self) -> tuple[float, float]:
        """Return `(time_scale, frame_rate)` for keyframe time conversion."""
        if self.keyframes:
            kf = self.keyframes[0]
            return kf._time_scale, kf._frame_rate
        comp = self._composition
        if comp is None:
            comp = self._containing_layer.containing_comp
        return comp.time_scale, comp.frame_rate

    def _keyframe_inner(self) -> ListChunk | None:
        """The `LIST:list` holding the keyframe header chunks, or None."""
        try:
            return find_by_list_type(chunks=self._tdbs.chunks, list_type="list")
        except ChunkNotFoundError:
            return None

    def _parallel_kind(self) -> ParallelKind | None:
        """The complex-value kind storing keyframe values in a parallel
        container, or `None` for ordinary numeric properties.
        """
        if self.match_name == "ADBE Orientation":
            return ORIENTATION_KIND
        if self.match_name == "ADBE Marker":
            return MARKER_KIND
        # By match name as well as by value: a never-edited gradient has no
        # Gradient value to sample (no GCst data in the binary).
        if self.match_name in (
            "ADBE Vector Grad Colors",
            # The Layer Styles gradients (a synthesized one has no pard and
            # a NO_VALUE seed, so only the match name identifies the kind).
            "outerGlow/gradient",
            "innerGlow/gradient",
            "gradientFill/gradient",
        ):
            return GRADIENT_KIND
        # A freshly-synthesized mask path is seeded as CUSTOM_VALUE (not
        # SHAPE), so guard it by match name or its value write silently no-ops.
        if self.match_name == "ADBE Mask Shape":
            return SHAPE_KIND
        pvt = self.property_value_type
        if pvt == PropertyValueType.SHAPE:
            return SHAPE_KIND
        if pvt == PropertyValueType.TEXT_DOCUMENT:
            return TEXT_KIND
        sample = self.keyframes[0].value if self.keyframes else self._value
        if isinstance(sample, Gradient):
            return GRADIENT_KIND
        return None

    def _keyframe_item_type(self) -> LdatItemType:
        """The `LdatItemType` for this property's keyframe header data."""
        kind = self._parallel_kind()
        if kind is not None:
            return kind.header_item_type
        if self._color:
            return LdatItemType.color
        if self._no_value:
            return LdatItemType.no_value
        dims = self.dimensions
        if dims >= 3:
            return (
                LdatItemType.three_d_spatial
                if self.is_spatial
                else LdatItemType.three_d
            )
        if dims == 2:
            return LdatItemType.two_d_spatial if self.is_spatial else LdatItemType.two_d
        return LdatItemType.one_d

    def _animate_tdb4(self) -> None:
        """Set tdb4 metadata to AE's animated-property state.

        Static and animated properties differ in several `tdb4` fields, not
        just the `animated` bit; After Effects rejects (drops) the layer when
        they are inconsistent. Values were reverse-engineered from AE 2026
        output across 1D / 2D / 3D / spatial / color properties.

        Complex (parallel-container) properties keep their value-hint
        metadata as-is: AE only flips the static / animated / spatial-marker
        fields (verified against AE 2026 static-vs-one-keyframe pairs for
        text / shape / orientation / marker / gradient).
        """
        t = self._tdb4
        if self._parallel_kind() is not None:
            t.static = False
            t.animated = True
            t._spatial_marker = False
            # AE clears the opaque interpolation residue it leaves in these
            # fields when a complex property went static.
            t._pad7b = 0
            t._pad7c = 0
            return
        # AE keeps a variable-font axis's value-hint flag, cvot flags
        # and time base unchanged across the static<->animated
        # transition (verified against the variable_font_axis_animated
        # AE 2026 fixture).
        preserved = (
            (t._value_hint_flag, t._cvot_flags, t._time_base)
            if self._is_vf_axis
            else None
        )
        tdb4_apply_animated_template(
            t, color=bool(self._color), spatial=self._has_motion_path
        )
        # The template cannot know the comp's timebase or pixel aspect.
        # `_ensure_materialized` stamps them, but only for a synthesized
        # property - one parsed from a real file returns early there, so
        # animating it needs the stamp applied here too.
        self._ensure_time_base()
        if preserved is not None:
            t._value_hint_flag, t._cvot_flags, t._time_base = preserved

    def _ensure_animated(self) -> tuple[Lhd3Chunk, LdatChunk]:
        """Return the keyframe `(lhd3, ldat)`, creating them if static.

        Transitioning a static property to animated replaces its `cdat`
        with a `LIST:list` keyframe container and rewrites the `tdb4`
        metadata to AE's animated state.
        """
        inner = self._keyframe_inner()
        if inner is None:
            item_type = self._keyframe_item_type()
            inner, lhd3, ldat = build_keyframe_list(
                item_type, ITEM_SIZE_BY_TYPE[item_type]
            )
            self._animate_tdb4()
            chunks = self._tdbs.chunks
            if self._cdat is not None:
                chunks[index_by_identity(chunks, self._cdat)] = inner
                self._cdat = None
            else:
                chunks.insert(index_by_identity(chunks, self._tdb4) + 1, inner)
            return lhd3, ldat
        lhd3 = cast("Lhd3Chunk", find_by_type(chunks=inner.chunks, chunk_type="lhd3"))
        ldat = cast("LdatChunk", find_by_type(chunks=inner.chunks, chunk_type="ldat"))
        return lhd3, ldat

    def _keyframe_insert_index(self, time_units: int) -> tuple[int, bool]:
        """Locate `time_units` among the keyframes.

        Returns `(index, exists)`: when a keyframe already sits at
        `time_units`, `exists` is True and `index` is its position;
        otherwise `exists` is False and `index` is the sorted insertion
        point. Keyed on raw units rather than frame indices so two
        sub-frame keyframes inside one frame stay distinct.
        """
        for i, kf in enumerate(self.keyframes):
            units = kf.time_units
            if units == time_units:
                return i, True
            if units > time_units:
                return i, False
        return len(self.keyframes), False

    def _keyframe_units_at(self, time: float) -> int:
        """Layer-relative keyframe units for a composition `time` in seconds."""
        timebase = self._layer_timebase or _timebase_units(*self._time_units())
        return round((time - self._start_time_offset) / self._time_stretch * timebase)

    def can_add_to_motion_graphics_template(self, comp: CompItem) -> bool:
        """Test whether this property can be added to `comp`'s Essential
        Graphics panel (a Motion Graphics template).

        Gates on what py_aep can produce: the supported control types are
        Checkbox, Color, single-value numeric Slider and Source Text (a
        Dropdown param reports `False` - AE would build a type-13 Dropdown
        controller, which py_aep does not). Paths through indexed groups -
        effects, masks, shape contents, text animators - are addressed by AE's
        child index (validated against AE 2026 output), so their children are
        addable, including on duplicate siblings. Reports `False` for an effect
        param whose parT definitions are unavailable, children of `ADBE Effect
        Built In Params`, a by-name node ambiguous among its siblings, a
        property already exposed, or a layer not in `comp`.

        Args:
            comp: The composition whose Essential Graphics panel to test.
        """
        return can_add_property(self, comp)

    def add_to_motion_graphics_template(self, comp: CompItem) -> bool:
        """Add this property to `comp`'s Essential Graphics panel, using the
        property's own name for the controller.

        Returns `True` on success, or `False` when the property cannot be added
        (see `can_add_to_motion_graphics_template`).

        Args:
            comp: The composition to add the property to.
        """
        return comp._add_property_controller(self, None)

    def add_to_motion_graphics_template_as(self, comp: CompItem, name: str) -> bool:
        """Add this property to `comp`'s Essential Graphics panel with an
        explicit controller `name`.

        Returns `True` on success, or `False` when the property cannot be
        added (see `can_add_to_motion_graphics_template`).

        Args:
            comp: The composition to add the property to.
            name: The controller name to show in the Essential Graphics panel.
        """
        validate_name(name)
        return comp._add_property_controller(self, name)

    def add_key(self, time: float) -> int:
        """Add a keyframe at the given time and return its 0-based index.

        The new keyframe takes the property's value at `time` (the
        interpolated value when already animated, or the static value
        otherwise), matching ExtendScript `Property.addKey()`. Adding the
        first keyframe converts a static property to an animated one.

        Args:
            time: The composition time, in seconds.

        Raises:
            ValueError: If the property cannot vary over time, or has no
                value to keyframe.
        """
        return self._add_key(time)

    def _add_key(self, time: float, value: Any = _USE_VALUE) -> int:
        """Add a keyframe at `time`, seeding its value when supplied.

        When `value` is omitted, the keyframe takes the property's value at
        `time` (interpolated when animated, the static value otherwise).
        """
        validate_number(time)
        if not self.can_vary_over_time:
            raise ValueError(f"property {self.match_name!r} cannot vary over time")
        kind = self._parallel_kind()
        if kind is not None:
            return self._add_parallel_key(time, kind, value=value)
        # A no-value numeric property has no value slot to keyframe; building
        # a numeric keyframe item for it produces a wrong-size ldat item.
        # (Complex kinds above store their value in a sibling container and
        # legitimately report no_value=True, so this only guards the numeric
        # path.)
        if self._no_value:
            raise ValueError(f"property {self.match_name!r} has no value to keyframe")
        new_value = self.value_at_time(time) if value is _USE_VALUE else value
        time_scale, frame_rate = self._time_units()
        self._ensure_materialized()
        lhd3, ldat = self._ensure_animated()

        item_type = self._keyframe_item_type()
        kf_data = build_kf_data(item_type, self.dimensions)
        ldat_item = build_ldat_item(kf_data, spatial=self._has_motion_path)

        kf = Keyframe(
            _ldat_item=ldat_item,
            _time_scale=time_scale,
            _frame_rate=frame_rate,
        )
        kf._bind_property(self)
        kf.time = time

        idx, exists = self._keyframe_insert_index(kf.time_units)
        if exists:
            return idx
        ldat.items.insert(idx, ldat_item)
        self.keyframes.insert(idx, kf)
        set_lhd3_count(lhd3, len(self.keyframes), LHD3_BLOCK_KEYFRAMES)
        kf.value = new_value
        self._link_inserted_key(idx)
        self._preserve_curve_on_insert(idx)
        # The static value is now dead: `value` reads the keyframes, but its
        # cache short-circuits ahead of that check, so animating a property
        # that had been read (or written) statically kept reporting the old
        # number. Complex kinds keep their cached object - callers rely on
        # mutating it in place - and they animate through other paths.
        if isinstance(self._value, (int, float, list)):
            self._value = None
        return idx

    def _preserve_curve_on_insert(self, idx: int) -> None:
        """Give a freshly inserted keyframe the interpolation AE gives it.

        `addKey` must not change the animation: AE inserts the key with the
        surrounding segment's interpolation type and the ease that keeps the
        curve identical (measured on AE 2026 - every sampled `valueAtTime`
        is unchanged across BEZIER, LINEAR and HOLD segments). Without this
        the key lands LINEAR with a default ease and silently reshapes the
        animation.

        Rules, one per segment type:

        - BEZIER: the new key takes the curve's slope at that time, and the
          influences come from a De Casteljau split of the time handles
          (a 5 s 0->100 segment eased 0/75 both sides, split at 2.5 s, gives
          speed 80 and influences 75 / 12.5 / 12.5 / 75).
        - LINEAR: the new key and both facing neighbour handles take the
          segment's slope with AE's default influence.
        - HOLD: speed 0 with the default influence; the value is held either
          way.
        """
        if idx <= 0 or idx >= len(self.keyframes) - 1:
            # Outside the keyed range there is no segment to preserve.
            return
        kf = self.keyframes[idx]
        prev_kf = self.keyframes[idx - 1]
        next_kf = self.keyframes[idx + 1]

        components = _segment_components(prev_kf, next_kf)
        if components is None:
            return
        pairs, dims = components

        out_type = prev_kf.out_interpolation_type
        in_type = next_kf.in_interpolation_type
        # Either side holding makes the whole segment hold, so the inserted
        # key has to hold on both sides to leave the value where it was.
        if KeyframeInterpolationType.HOLD in (out_type, in_type):
            out_type = in_type = KeyframeInterpolationType.HOLD
        kf.in_interpolation_type = out_type
        kf.out_interpolation_type = in_type

        # Layer time: the speeds synthesized below are stored per layer
        # second, and on a reversed layer only this axis ascends.
        t0, t1, t = prev_kf._layer_time, next_kf._layer_time, kf._layer_time
        if not t0 < t < t1:
            return

        prev_out = list(prev_kf.out_temporal_ease)
        next_in = list(next_kf.in_temporal_ease)
        new_in: list[KeyframeEase] = []
        new_out: list[KeyframeEase] = []
        left_out: list[KeyframeEase] = []
        right_in: list[KeyframeEase] = []

        # A spatial property stores ONE ease for the whole vector (its speed
        # is along the path), where a plain vector stores one per dimension.
        n_ease = min(len(prev_out), len(next_in)) or 1
        spatial = n_ease == 1 and dims > 1
        if spatial:
            # A spatial ease's speed is measured along the PATH, so the split
            # runs once over the segment's arc length - the chord would be
            # short wherever the tangents bow the curve.
            pairs = [(0.0, self._segment_arc_length(prev_kf, next_kf))]

        for d in range(n_ease):
            v0, v1 = pairs[d] if d < len(pairs) else pairs[0]
            o_ease = prev_out[d] if d < len(prev_out) else prev_out[0]
            i_ease = next_in[d] if d < len(next_in) else next_in[0]
            if out_type == KeyframeInterpolationType.HOLD:
                slope = 0.0
                infl = (o_ease.influence, _DEFAULT_INFLUENCE, _DEFAULT_INFLUENCE)
                infl_next = i_ease.influence
                o_speed, i_speed = o_ease.speed, i_ease.speed
            elif out_type == KeyframeInterpolationType.LINEAR:
                slope = (v1 - v0) / (t1 - t0)
                infl = (_DEFAULT_INFLUENCE, _DEFAULT_INFLUENCE, _DEFAULT_INFLUENCE)
                infl_next = _DEFAULT_INFLUENCE
                o_speed = i_speed = slope
            else:
                slope = segment_value_slope(t0, t1, v0, v1, o_ease, i_ease, t)
                lo, ni, no, ri = split_segment_influences(
                    t0, t1, v0, v1, o_ease, i_ease, t
                )
                infl = (lo, ni, no)
                infl_next = ri
                o_speed, i_speed = o_ease.speed, i_ease.speed
            left_out.append(KeyframeEase(o_speed, infl[0]))
            new_in.append(KeyframeEase(slope, infl[1]))
            new_out.append(KeyframeEase(slope, infl[2]))
            right_in.append(KeyframeEase(i_speed, infl_next))

        kf.in_temporal_ease = new_in
        kf.out_temporal_ease = new_out
        prev_kf.out_temporal_ease = left_out
        next_kf.in_temporal_ease = right_in

        if spatial:
            self._split_motion_path(prev_kf, kf, next_kf)

    def _segment_arc_length(self, prev_kf: Keyframe, next_kf: Keyframe) -> float:
        """Arc length of the motion path between two keyframes."""
        v0 = prev_kf.value
        v1 = next_kf.value
        if not isinstance(v0, list) or not isinstance(v1, list):
            return 0.0
        ndim = len(v0)
        out_tangent = prev_kf.out_spatial_tangent or [0.0] * ndim
        in_tangent = next_kf.in_spatial_tangent or [0.0] * ndim
        if _tangents_are_zero(out_tangent) and _tangents_are_zero(in_tangent):
            return math.sqrt(sum((v1[d] - v0[d]) ** 2 for d in range(ndim)))
        return _BezierPathData(v0, v1, out_tangent, in_tangent).segment_length

    def _split_motion_path(
        self, prev_kf: Keyframe, kf: Keyframe, next_kf: Keyframe
    ) -> None:
        """Split the motion path so the inserted key does not reshape it.

        Without this the new keyframe carries no spatial tangents and the
        single curve becomes two straight-ish halves.
        """
        v0 = prev_kf.value
        v1 = next_kf.value
        if not isinstance(v0, list) or not isinstance(v1, list):
            return
        ndim = len(v0)
        out_tangent = prev_kf.out_spatial_tangent or [0.0] * ndim
        in_tangent = next_kf.in_spatial_tangent or [0.0] * ndim
        if _tangents_are_zero(out_tangent) and _tangents_are_zero(in_tangent):
            return
        data = _BezierPathData(v0, v1, out_tangent, in_tangent)
        if data.segment_length <= 0:
            return
        # The split sits where the key landed: the arc-length fraction of the
        # path that the new keyframe's value corresponds to.
        progress = _progress_of_point(data, cast("list[float]", kf.value))
        u = path_parameter_at_progress(data, progress)
        left_out, new_in, _split, new_out, right_in = split_spatial_path(
            v0, v1, out_tangent, in_tangent, u
        )
        prev_kf.out_spatial_tangent = left_out
        kf.in_spatial_tangent = new_in
        kf.out_spatial_tangent = new_out
        next_kf.in_spatial_tangent = right_in

    def remove_key(self, key_index: int) -> None:
        """Remove the keyframe at `key_index` (0-based).

        Removing the last remaining keyframe reverts the property to a
        static value (the removed keyframe's value), matching ExtendScript
        `Property.removeKey()`. Markers have no static value: removing the
        last marker leaves the property empty.

        Args:
            key_index: The 0-based index of the keyframe to remove.

        Raises:
            IndexError: If the property has no keyframes.
            ValueError: If `key_index` is out of range.
        """
        if not self.keyframes:
            raise IndexError("property has no keyframes")
        _validate_number(integer=True, min=0, max=len(self.keyframes) - 1)(key_index)
        kind = self._parallel_kind()
        if kind is not None:
            if len(self.keyframes) == 1:
                self._deanimate_parallel(kind)
                return
            self._remove_parallel_key(key_index, kind)
            return
        self._ensure_materialized()
        lhd3, ldat = self._ensure_animated()
        removed = self.keyframes[key_index]
        removed_value = removed.value
        del ldat.items[key_index]
        del self.keyframes[key_index]
        set_lhd3_count(lhd3, len(self.keyframes), LHD3_BLOCK_KEYFRAMES)
        self._link_keyframes()
        if not self.keyframes:
            self._deanimate(removed_value)

    def remove_all_keys(self) -> None:
        """Remove every keyframe from this property.

        Equivalent to calling `remove_key` for each keyframe: the
        property reverts to a static value (the first keyframe's value).
        Markers have no static value: the property is left empty. A
        no-op when the property has no keyframes.
        """
        if self._parallel_kind() is not None:
            while self.keyframes:
                self.remove_key(len(self.keyframes) - 1)
            return
        if not self.keyframes:
            return
        # Bulk path: clearing key-by-key would re-link the remaining
        # keyframes after every removal (quadratic) and decode values
        # that are thrown away.
        self._ensure_materialized()
        lhd3, ldat = self._ensure_animated()
        first_value = self.keyframes[0].value
        del ldat.items[:]
        del self.keyframes[:]
        set_lhd3_count(lhd3, 0, LHD3_BLOCK_KEYFRAMES)
        self._deanimate(first_value)

    def _static_tdb4(self) -> None:
        """Revert tdb4 metadata to AE's static (non-animated) state.

        Inverse of `_animate_tdb4`. `_type_flags` is left untouched because
        its non-`animated` bits (vector / color) are property-intrinsic and
        differ per type.
        """
        t = self._tdb4
        if self._parallel_kind() is not None:
            # AE re-derives _spatial_marker when a complex property goes
            # static: observed 1 for shape / orientation / gradient (whose
            # _spatial_static_flags carry bit 1) and 0 for text / marker.
            t.static = True
            t.animated = False
            t._spatial_marker = bool(t._spatial_static_flags & 0x02)
            return
        # Mirror `_animate_tdb4`: the axis keeps its value-hint flag,
        # cvot flags and time base across the transition too.
        preserved = (
            (t._value_hint_flag, t._cvot_flags, t._time_base)
            if self._is_vf_axis
            else None
        )
        tdb4_apply_static_template(
            t, color=bool(self._color), spatial=self._has_motion_path
        )
        control_type = self._property_control_type
        if control_type is not None and self._is_in_effect():
            # `tdb4_apply_static_template` wrote the LAYER-property byte (9
            # for spatial, 6 for colour). An effect parameter needs the
            # instance-value bits on top, without which AE ignores the tdbs
            # and falls back to the parT default - so the same AE-measured
            # table the parse path synthesizes from decides the byte here.
            effect_flags = EFFECT_PARAM_SPATIAL_FLAGS.get(control_type)
            if effect_flags is not None:
                t._spatial_static_flags = effect_flags
        if preserved is not None:
            t._value_hint_flag, t._cvot_flags, t._time_base = preserved

    def _deanimate(self, value: _ValueType) -> None:
        """Revert an emptied animated property to a static `value`."""
        inner = self._keyframe_inner()
        chunks = self._tdbs.chunks
        self._static_tdb4()
        raw = (
            self._unresolve_value(value)
            if isinstance(value, (int, float, list))
            else None
        )
        if isinstance(raw, (int, float)):
            raw_vals = [float(raw)]
        elif isinstance(raw, list):
            raw_vals = [float(v) for v in raw]
        else:
            raw_vals = [0.0]
        cdat = CdatChunk(values=raw_vals)
        if inner is not None:
            chunks[index_by_identity(chunks, inner)] = cdat
        else:
            chunks.insert(index_by_identity(chunks, self._tdb4) + 1, cdat)
        self._cdat = cdat
        self._value = None

    def _clear_expression(self) -> None:
        """Remove any expression, reverting to a plain (non-expression) property.

        Drops the expression `Utf8` chunk from the `tdbs` and clears the
        tdb4 expression flag, so `expression` becomes `""` and
        `expression_enabled` `False`. A no-op when no expression is set.
        """
        if self._expression_utf8 is None and not self._expression:
            return
        if self._expression_utf8 is not None:
            self._tdbs.chunks[:] = [
                c for c in self._tdbs.chunks if c is not self._expression_utf8
            ]
            self._expression_utf8 = None
        self._expression = None
        self._expression_enabled = None
        if self._tdb4 is not None:
            # `_expr_flags` (bit 0 = disabled) and the `_pad10` high-byte
            # marker (`has_expression`) are AE's expression-present flags;
            # clear both so the tdb4 matches a plain static parameter.
            self._tdb4._expr_flags = 0
            self._tdb4.has_expression = False

    # -- Complex (parallel-container) keyframe mutation ------------------

    def _build_shap_chunk(self, shape: Shape) -> Chunk:
        """Build a `shap` LIST chunk from a [Shape][].

        For a mask property, a pixel-space (from-scratch) shape is
        converted to the normalized `[0, 1]`-of-LAYER bounding box AE uses
        (mask space is layer space: the psd_vector_mask_cropped fixture
        pins the divisor as the layer source size, not the comp size).
        Dividing the box leaves the points, which are normalized to that
        box, unchanged. A shape already in mask space (parsed) is used
        as-is.
        """
        points = [ShapePoint(x=p.x, y=p.y) for p in (shape._points or [])]
        src = shape._shph
        if src is not None:
            bbox = [
                src.top_left_x,
                src.top_left_y,
                src.bottom_right_x,
                src.bottom_right_y,
            ]
        else:
            bbox = [0.0, 0.0, 0.0, 0.0]
        if self.match_name == "ADBE Mask Shape" and not shape._is_mask:
            layer = cast("AVLayer", self._containing_layer)
            w, h = float(layer.width), float(layer.height)
            bbox = [bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h]
        shap = build_shap(
            (bbox[0], bbox[1], bbox[2], bbox[3]),
            open_path=not shape.closed,
            points=points,
        )
        if src is not None:
            # Carry over the source header's unknown flag bits; build_shap
            # only knows the open/closed bit.
            new_shph = cast(
                "ShphChunk", find_by_type(chunks=shap.chunks, chunk_type="shph")
            )
            new_shph._flags = src._flags
            new_shph.open = not shape.closed
        return shap

    def _build_text_view(self, doc: Any, template: TextDocument) -> TextDocument:
        """Wrap a COS doc dict as a [TextDocument][] sharing `template`'s
        COS data / btdk chunk."""
        char = cos_get(doc, "0", "6", "0", 0, "0", "0", "6")
        para = cos_get(doc, "0", "5", "0", 0, "0", "0", "5")
        view = TextDocument._from_binary(
            _char_style=char if isinstance(char, dict) else None,
            _para_style=para if isinstance(para, dict) else None,
            _doc=doc,
            _fonts=template._fonts,
            _cos_data=template._cos_data,
            _btdk_body=template._btdk_body,
        )
        if template._siblings is not None:
            template._siblings.append(view)
            view._siblings = template._siblings
        # The clone copies the template's text AND its (possibly stale)
        # layout cache, so it inherits the template's staleness verdict.
        view._layout_dirty = template._layout_dirty
        view._composition_calibrated = template._composition_calibrated
        return cast("TextDocument", self._wire_text_version(view))

    def _animate_static_text(self, time: float, value: Any = _USE_VALUE) -> int:
        """Add the first Source Text keyframe to a static text property.

        The static document already lives in the shared `btdk` COS blob
        (`cos["1"]["1"][0]`) and becomes the keyframe's value as-is; AE
        only swaps the empty `cdat` for a keyframe `LIST:list` and flips
        the tdb4 static / animated flags (the COS blob is byte-identical
        between the static and one-keyframe states in AE 2026 output).
        """
        template = self._value
        if not isinstance(template, TextDocument):
            raise NotImplementedError(
                "text property has no TextDocument value to animate"
            )
        time_scale, frame_rate = self._time_units()
        self._ensure_materialized()
        lhd3, ldat = self._ensure_animated()
        ldat_item = build_parallel_ldat_item(self._keyframe_item_type())
        kf = Keyframe(
            _ldat_item=ldat_item, _time_scale=time_scale, _frame_rate=frame_rate
        )
        kf._bind_property(self)
        kf.time = time
        ldat.items.append(ldat_item)
        self.keyframes.append(kf)
        set_lhd3_count(lhd3, 1, LHD3_BLOCK_KEYFRAMES)
        kf._value = template
        self._value = None
        if isinstance(value, str):
            template.text = value
        elif isinstance(value, TextDocument):
            template.text = value.text
        self._link_keyframes()
        return 0

    def _add_text_key(self, time: float, value: Any = _USE_VALUE) -> int:
        """Add a Source Text keyframe.

        Text keyframes share a single `btdk` COS blob holding one document
        per keyframe (`cos["1"]["1"]`). A new keyframe deep-copies the
        nearest document (inheriting its styling); pass a string or
        [TextDocument][] to override the text content. After Effects
        recomputes the per-keyframe box-frame / glyph caches on open, so
        they are left untouched.
        """
        if self._keyframe_inner() is None or not self.keyframes:
            return self._animate_static_text(time, value)
        lhd3, ldat = self._ensure_animated()
        time_scale, frame_rate = self._time_units()
        nearest = self.nearest_key_index(time)
        template = self.keyframes[nearest].value
        if not isinstance(template, TextDocument):
            raise NotImplementedError("text keyframe value is not a TextDocument")
        doc_array = cos_get(template._cos_data, "1", "1")
        new_doc = copy.deepcopy(doc_array[nearest])

        ldat_item = build_parallel_ldat_item(self._keyframe_item_type())
        kf = Keyframe(
            _ldat_item=ldat_item, _time_scale=time_scale, _frame_rate=frame_rate
        )
        kf._bind_property(self)
        kf.time = time
        idx, exists = self._keyframe_insert_index(kf.time_units)
        if exists:
            return idx
        self._ensure_materialized()
        ldat.items.insert(idx, ldat_item)
        doc_array.insert(idx, new_doc)
        self.keyframes.insert(idx, kf)
        td = self._build_text_view(new_doc, template)
        kf._value = td
        if isinstance(value, str):
            td.text = value
        elif isinstance(value, TextDocument):
            td.text = value.text
        else:
            # The text setter above already re-serializes the COS blob; when
            # no text was supplied, propagate the structural insert ourselves.
            td._propagate_cos()
        set_lhd3_count(lhd3, len(self.keyframes), LHD3_BLOCK_KEYFRAMES)
        self._link_inserted_key(idx)
        return idx

    def _remove_text_key(self, key_index: int) -> None:
        """Remove a Source Text keyframe (its COS document + header item).

        The per-keyframe box-frame / glyph caches are left untouched -
        After Effects recomputes them on open.
        """
        lhd3, ldat = self._ensure_animated()
        removed = self.keyframes[key_index].value
        if not isinstance(removed, TextDocument):
            raise NotImplementedError("text keyframe value is not a TextDocument")
        doc_array = cos_get(removed._cos_data, "1", "1")
        self._ensure_materialized()
        del ldat.items[key_index]
        if key_index < len(doc_array):
            del doc_array[key_index]
        del self.keyframes[key_index]
        set_lhd3_count(lhd3, len(self.keyframes), LHD3_BLOCK_KEYFRAMES)
        removed._propagate_cos()
        self._link_keyframes()

    def _materialize_parallel_container(self, kind: ParallelKind) -> ListChunk:
        """Create the missing wrapper subtree / value container for a
        complex property that stores nothing in the binary.

        AE omits the wrapper entirely for pristine state (a never-marked
        layer, a never-edited gradient, a never-modified orientation);
        the property is backed by a bare `tdbs` (synthesized, or parsed
        directly for orientation). Keying it wraps the `tdbs` in the
        kind's wrapper LIST holding the per-keyframe value container,
        with kind-specific `tdb4` baselines (AE 2026 output).
        """
        if not kind.can_materialize_wrapper or kind.container_type is None:
            raise NotImplementedError(
                f"animating a static {self.match_name!r} property is not yet supported"
            )
        # Materialize while the bare tdbs is still the property's body in
        # the parent tdgp, so canonical repositioning can anchor it.
        self._ensure_materialized()
        parent = self.parent_property
        assert parent is not None and parent._tdgp is not None
        chunks = parent._tdgp.chunks
        container = ListChunk(list_type=kind.container_type, chunks=[])
        wrapper = self._wrapper
        if wrapper is None:
            wrapper = next(
                (
                    c
                    for c in chunks
                    if isinstance(c, ListChunk)
                    and any(cc is self._tdbs for cc in c.chunks)
                ),
                None,
            )
        if wrapper is not None:
            # The wrapper exists but has no value container: add it after
            # the tdbs.
            wrapper.chunks.insert(
                index_by_identity(wrapper.chunks, self._tdbs) + 1, container
            )
        elif any(c is self._tdbs for c in chunks):
            wrapper = ListChunk(
                list_type=kind.wrapper_type, chunks=[self._tdbs, container]
            )
            chunks[index_by_identity(chunks, self._tdbs)] = wrapper
            # AE writes the unnamed sentinel into tdsn when it wraps the
            # property (synthesis seeds the auto-name; a pristine
            # orientation stores its real name).
            if self._name_utf8 is not None:
                self._name_utf8.value = TDSN_SENTINEL
            kind.on_wrap(self)
        else:
            raise NotImplementedError(
                f"animating a static {self.match_name!r} property is not yet supported"
            )
        self._wrapper = wrapper
        self._kf_value_container = container
        return container

    def _add_parallel_key(
        self, time: float, kind: ParallelKind, value: Any = _USE_VALUE
    ) -> int:
        """Add a keyframe to a complex (parallel-container) property.

        When `value` is omitted, the value is taken from the kind's
        `held_value` (interpolated for orientation, held otherwise).
        """
        if kind is TEXT_KIND:
            return self._add_text_key(time, value)
        container = self._kf_value_container
        if container is None:
            container = self._materialize_parallel_container(kind)
        time_scale, frame_rate = self._time_units()
        # Resolve the held value before _ensure_animated: for a static
        # orientation it reads the cdat that the swap removes.
        new_value = kind.held_value(self, time) if value is _USE_VALUE else value
        new_value = kind.coerce(new_value)
        ldat_item = kind.build_header_item(new_value)
        value_chunk = kind.build_value_chunk(self, new_value)

        kf = Keyframe(
            _ldat_item=ldat_item, _time_scale=time_scale, _frame_rate=frame_rate
        )
        kf._bind_property(self)
        kf.time = time
        idx, exists = self._keyframe_insert_index(kf.time_units)
        if exists:
            return idx
        was_static = not self.keyframes
        self._ensure_materialized()
        lhd3, ldat = self._ensure_animated()
        ldat.items.insert(idx, ldat_item)
        self.keyframes.insert(idx, kf)
        if was_static and container.chunks:
            # A static property's container already holds its single value
            # chunk; the first keyframe takes its place.
            container.chunks[0] = value_chunk
        else:
            container.chunks.insert(idx, value_chunk)
        set_lhd3_count(lhd3, len(self.keyframes), LHD3_BLOCK_KEYFRAMES)
        # The header item already carries the value (`build_header_item`) and
        # the container chunk is inserted above, so set the shadow directly:
        # the public `kf.value` setter would re-route complex kinds back into
        # the container write path, rebuilding the just-inserted chunk.
        kf._value = new_value
        # Re-bind the keyframe's model to the chunk just inserted (when the
        # kind wraps); new_value (held or user-supplied) is backed by a
        # different chunk, so edits to it would never reach the serialized
        # keyframe.
        wrapped = kind.wrap_value_chunk(self, value_chunk)
        if wrapped is not None:
            kf._value = wrapped
        kind.bind_keyframe(kf._value, kf)
        if was_static:
            # Match the parsers: an animated shape keeps `value` aliased to
            # the first keyframe's Shape; other kinds read through keyframes.
            self._value = (
                cast("_ValueType", kf._value) if kind.aliases_static_value else None
            )
        self._link_inserted_key(idx)
        return idx

    def _remove_parallel_key(self, key_index: int, kind: ParallelKind) -> None:
        """Remove a keyframe from a complex (parallel-container) property."""
        if kind is TEXT_KIND:
            self._remove_text_key(key_index)
            return
        lhd3, ldat = self._ensure_animated()
        container = self._kf_value_container
        self._ensure_materialized()
        del ldat.items[key_index]
        del self.keyframes[key_index]
        if container is not None and key_index < len(container.chunks):
            del container.chunks[key_index]
        set_lhd3_count(lhd3, len(self.keyframes), LHD3_BLOCK_KEYFRAMES)
        self._link_keyframes()

    def _deanimate_parallel(self, kind: ParallelKind) -> None:
        """Revert a complex property with one keyframe to its static state.

        Mirrors AE 2026 output for removing the last keyframe: the keyframe
        `LIST:list` is replaced by a `cdat` (the empty 4-byte form for most
        kinds, the angle values for orientation) and the parallel container
        keeps the removed keyframe's value chunk as the static value (a
        text property's COS document likewise stays in place). Markers have
        no static value, so the container entry is removed, leaving the
        zero-marker state AE writes. AE itself also discards a gradient's
        value (reverting it to the default gradient); keeping it matches
        the persisted static-gradient form and `removeKey` semantics.
        """
        removed_value = self.keyframes[0].value
        self._ensure_materialized()
        inner = self._keyframe_inner()
        del self.keyframes[0]
        self._link_keyframes()
        container = self._kf_value_container
        if (
            not kind.keeps_value_on_revert
            and container is not None
            and container.chunks
        ):
            del container.chunks[0]
        cdat = kind.static_cdat(removed_value)
        # Assign the static value before _static_tdb4: _parallel_kind()
        # detects gradients by sampling it once the keyframes are gone.
        self._value = removed_value if kind.keeps_value_on_revert else None
        self._static_tdb4()
        chunks = self._tdbs.chunks
        if inner is not None:
            chunks[index_by_identity(chunks, inner)] = cdat
        else:
            chunks.insert(index_by_identity(chunks, self._tdb4) + 1, cdat)
        self._cdat = cdat

    def set_value_at_time(self, time: float, new_value: _ValueType) -> None:
        """Set the property's value at `time`, adding a keyframe if needed.

        If a keyframe already exists at `time` its value is replaced;
        otherwise a new keyframe is created (via [add_key][]). Matches
        ExtendScript `Property.setValueAtTime()`.

        Args:
            time: The composition time, in seconds.
            new_value: The value to set at that time.
        """
        validate_number(time)
        if self._separation_followers() is not None:
            # AE 2026 rejects this on a separated leader for the same reason
            # `setValue` is rejected: the followers hold the animation.
            raise ValueError(
                f"cannot set a value on {self.match_name!r} while its "
                f"dimensions are separated; key its X / Y / Z followers "
                f"instead (get_separation_follower)"
            )
        kind = self._parallel_kind()
        if kind is not None:
            self._set_parallel_value_at(time, new_value, kind)
            return
        idx, exists = self._keyframe_insert_index(self._keyframe_units_at(time))
        if exists:
            self.keyframes[idx].value = new_value
            return
        self._add_key(time, new_value)

    def _set_parallel_value_at(
        self, time: float, value: _ValueType, kind: ParallelKind
    ) -> None:
        """Set / replace the value at `time` for a complex property.

        Unlike numeric properties, the value lives in the parallel
        container, so an existing key's value chunk is rebuilt rather than
        written through a descriptor.
        """
        target_units = self._keyframe_units_at(time)
        if kind is TEXT_KIND:
            new_text = value.text if isinstance(value, TextDocument) else value
            for kf in self.keyframes:
                if kf.time_units == target_units:
                    td = kf.value
                    if isinstance(td, TextDocument) and isinstance(new_text, str):
                        # The text setter already re-serializes the COS blob.
                        td.text = new_text
                        self._ensure_materialized()
                    return
            self._add_text_key(time, value)
            return
        value = cast("_ValueType", kind.coerce(value))
        for kf in self.keyframes:
            if kf.time_units == target_units:
                self._write_parallel_kf_value(kf, value, kind)
                return
        self._add_parallel_key(time, kind, value=value)

    def _write_parallel_kf_value(
        self, kf: Keyframe, value: Any, kind: ParallelKind
    ) -> None:
        """Persist `value` into an existing complex keyframe's container
        chunk and mirrored header item, then rebind the keyframe model.

        Shared by `set_value_at_time` (targeting an existing key) and the
        `Keyframe.value` setter (BUG 3): a complex keyframe's real value
        lives in the parallel container, so writing through `kf_data`
        alone never reaches the serialized form.
        """
        kind.update_header_item(kf._ldat_item, value)
        container = self._kf_value_container
        if container is not None:
            try:
                i = index_by_identity(self.keyframes, kf)
            except ValueError:
                i = -1
            if 0 <= i < len(container.chunks):
                value_chunk = kind.build_value_chunk(self, value)
                container.chunks[i] = value_chunk
                # Re-bind the keyframe's model to the chunk actually
                # inserted (mirrors `_add_parallel_key`); `value` is backed
                # by a different chunk, so editing the keyframe's value
                # afterwards would otherwise reach the caller's chunk -
                # corrupting any other keyframe that shares it.
                wrapped = kind.wrap_value_chunk(self, value_chunk)
                kf._value = wrapped if wrapped is not None else value
            else:
                kf._value = value
        else:
            kf._value = value
        kind.bind_keyframe(kf._value, kf)
        self._ensure_materialized()

    def set_values_at_times(
        self,
        times: list[float],
        new_values: list[_ValueType],
    ) -> None:
        """Set values at multiple times, adding keyframes as needed.

        Matches ExtendScript `Property.setValuesAtTimes()`.

        Args:
            times: Composition times, in seconds.
            new_values: Values to set, one per entry in `times`.

        Raises:
            ValueError: If `times` and `new_values` differ in length.
        """
        if len(times) != len(new_values):
            raise ValueError("times and new_values must have the same length")
        validate_sequence()(times)
        for time, value in zip(times, new_values):
            self.set_value_at_time(time, value)

    @property
    def _start_time_offset(self) -> float:
        """Seconds between layer-relative keyframe times and composition time.

        The binary stores keyframe times relative to the layer's start;
        ExtendScript reports them in composition time. Kept in seconds
        rather than whole frames so a sub-frame keyframe survives the
        conversion - AE leaves a layer start off the frame grid after a
        frame-rate change, which a rounded offset would then quantize.
        """
        stretch = self._time_stretch
        if stretch >= 0:
            return self._containing_layer.start_time
        # A reversed layer starts a hair before its nominal start: AE offsets
        # it by `|stretch| / 100 / 3000` seconds. Measured on AE 2026 at
        # -50 / -100 / -150 / -200 % and 24 / 25 / 30 fps - twelve readings,
        # all matching, and frame-rate independent (so it is a layer-time
        # constant of 1/3000 s, not a frame or tick).
        return self._containing_layer.start_time - abs(stretch) / 3000.0

    @property
    def _time_stretch(self) -> float:
        """Composition seconds per second of the owning layer's own time.

        `layer.stretch / 100`, signed: a negative stretch plays the layer
        backwards, so its keyframes run down the composition timeline.
        """
        try:
            stretch = self._containing_layer.stretch
        except (ValueError, AttributeError):
            return 1.0
        if not stretch:
            return 1.0
        return float(stretch) / 100.0

    @property
    def _layer_timebase(self) -> float:
        """Keyframe time units per second of the owning LAYER's time.

        AE stores `floor(cdta.internal_timebase * max(1, |stretch| / 100))`
        in every `tdb4` and counts keyframe ticks against it, so a stretched
        layer's ticks stay in its own time (measured on AE 2026: a 150 %
        layer at 24 fps stores 36864 and a key at layer-second 1 holds
        36864 ticks, which AE reports at composition second 1.5). Derived
        rather than read back so the read and write paths cannot disagree.
        """
        comp = self._owning_comp()
        if comp is None:
            return 0.0
        base = comp._cdta.internal_timebase
        if not base:
            return 0.0
        return float(math.floor(base * max(1.0, abs(self._time_stretch))))

    def _owning_comp(self) -> CompItem | None:
        """The composition this property belongs to.

        `_composition` is unset on a freshly synthesized property, whose
        comp is only reachable by walking up to the layer.
        """
        comp = self._composition
        if comp is not None:
            return comp
        node = self.parent_property
        while node is not None:
            comp = getattr(node, "_containing_comp", None)
            if comp is not None:
                return cast("CompItem", comp)
            node = node.parent_property
        return None

    def _apply_effect_scale(
        self, values: list[float], *, invert: bool = False
    ) -> list[float]:
        """Move a normalized vector into the space values are reported in.

        An effect point (and a footage layer's Anchor Point) stores its
        value and its spatial tangents normalized against the layer, while
        ExtendScript reports both in pixels. `invert` divides instead, for
        the write path.

        A component with no matching scale factor passes through, so the
        vector keeps its length rather than being truncated to the scale's.
        """
        scale = self._effect_scale
        if scale is None:
            return list(values)
        result = []
        for index, component in enumerate(values):
            factor = scale[index] if index < len(scale) else None
            if factor is None:
                result.append(component)
            elif invert:
                result.append(component / factor if factor else 0.0)
            else:
                result.append(component * factor)
        return result

    @property
    def _effect_scale(self) -> list[float] | None:
        """Scale factors for denormalizing 0-1 binary values to pixel coordinates.

        Lazily computed from context:
        - Effect point properties (TWO_D inside an effect): layer
          dimensions (`Layer.width` / `height`, which already fall back to
          the comp for a source-less layer).
        - Anchor Point: layer source dimensions, but ONLY when the layer
          has a source. Source-less layers (shape, text, null) store the
          anchor in raw pixels - AE does not normalize it - so applying a
          scale (which would fall back to comp size) corrupts the value.
        - All others: `None`.
        """
        # Allow explicit override via __dict__ (e.g. from tests).
        if "_effect_scale" in self.__dict__:
            result: list[float] | None = self.__dict__["_effect_scale"]
            return result

        scale: list[float] | None = None

        if self.match_name == "ADBE Anchor Point":
            # Only footage/comp layers normalize the anchor to source size;
            # source-less layers (shape, text, null) store it in raw pixels.
            if getattr(self._containing_layer, "source", None) is not None:
                size = self._layer_pixel_size()
                if size is not None:
                    scale = [size[0], size[1], 1.0]
        elif (
            self._property_control_type
            in (PropertyControlType.TWO_D, PropertyControlType.THREE_D)
            and self._is_in_effect()
        ):
            # An effect point is stored normalized against the LAYER, not
            # the composition. Measured on AE 2026: a Ramp start point set to
            # 100 on a 200x200 solid in an 800x600 comp stores 0.5, which
            # only 100/200 produces - comp normalization would store 0.125.
            # `Layer.width` already falls back to the comp for source-less
            # layers, which is what AE uses there.
            #
            # A 3D point's Z shares the HEIGHT divisor: a Point3D Control set
            # to [100, 50, 7] on a 200x100 layer stores [0.5, 0.5, 0.07], and
            # only 7/100 gives 0.07 (probed in AE 2026 across three
            # comp/layer size pairs).
            size = self._layer_pixel_size()
            if size is not None:
                scale = list(size)
                if self._property_control_type == PropertyControlType.THREE_D:
                    scale.append(size[1])

        return scale

    @_effect_scale.setter
    def _effect_scale(self, value: list[float] | None) -> None:
        if value is not None and (
            not isinstance(value, (list, tuple)) or len(value) < 2
        ):
            raise ValueError("_effect_scale must be a list of at least 2 floats")
        self.__dict__["_effect_scale"] = value

    def _layer_pixel_size(self) -> tuple[float, float] | None:
        """The containing layer's pixel dimensions, or `None`.

        `None` while the property has no layer at all - an effect
        definition parsed out of `LIST:EfdG` is a free-standing template,
        so there is nothing to normalize against yet.
        """
        try:
            return self._containing_layer._pixel_size
        except ValueError:
            return None


def _deactivate_follower(follower: Property) -> None:
    """Revert a separation follower to its dead, unserialized state.

    Its chunks stop being written and its value goes back to the 0 AE reports
    for an inactive follower (measured: AE's own export of a never-separated
    layer gives X / Y / Z = 0 even for a position of [960, 540, 0]). Without
    the value reset the model keeps reporting the separated numbers while the
    file - and any re-parse of it - reads 0.
    """
    follower.remove_all_keys()
    follower._revert_to_synthetic()
    follower._value = 0.0


def _progress_of_point(data: _BezierPathData, point: list[float]) -> float:
    """Arc-length fraction of the sampled path nearest to `point`."""
    best_index = 0
    best_dist = float("inf")
    for i, sample in enumerate(data.points):
        dist = sum((sample[d] - point[d]) ** 2 for d in range(len(point)))
        if dist < best_dist:
            best_dist = dist
            best_index = i
    travelled = sum(data.partial_lengths[: best_index + 1])
    if data.segment_length <= 0:
        return 0.0
    return min(max(travelled / data.segment_length, 0.0), 1.0)


def _segment_components(
    prev_kf: Keyframe, next_kf: Keyframe
) -> tuple[list[tuple[float, float]], int] | None:
    """Per-dimension `(v0, v1)` pairs for the segment, or `None` if not numeric."""
    v0 = prev_kf.value
    v1 = next_kf.value
    if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
        return [(float(v0), float(v1))], 1
    if isinstance(v0, list) and isinstance(v1, list) and len(v0) == len(v1):
        if not all(isinstance(x, (int, float)) for x in [*v0, *v1]):
            return None
        return [(float(a), float(b)) for a, b in zip(v0, v1)], len(v0)
    return None


class _EssentialOverrideProperty(Property):
    """An Essential Properties override leaf (a child of `ADBE Layer Overrides`).

    Its `value` is its own override (the leaf `cdat`), but its derived metadata
    - `enabled`, `min_value`/`max_value` (hence `has_min`/`has_max`),
    `is_modified`, `is_spatial`, `units_text`, `can_vary_over_time` and
    `can_set_expression` - reflects the Essential Graphics *source* property
    the override points at, matching After Effects: the override leaf's own
    `tdsb` enable bit, `tdum`/`tduM` bounds and `tdb4` flags are the EGP
    slider state, not what ExtendScript reports (the leaf has no `pard`, so
    e.g. a checkbox override's own `tdb4` reports it cannot vary over time
    while ExtendScript reports the source checkbox's `True`). Leaves are
    re-classed to this type after the override group is parsed (see
    `parsers/property.py::_dispatch_ovg2`); this keeps the base `Property`
    accessors - and round-trip serialization - untouched.
    """

    def _override_source(self) -> Property | None:
        """The resolved source `Property`, or `None` when it does not resolve
        (e.g. a Media Replacement leaf whose source is an `AVLayer`). Cached."""
        cached = self.__dict__.get("_ov_src", _UNSET)
        if cached is not _UNSET:
            return cast("Property | None", cached)
        src = self.essential_property_source
        resolved = src if isinstance(src, Property) else None
        self.__dict__["_ov_src"] = resolved
        return resolved

    def _override_controller_name(self) -> str | None:
        """The name of the override leaf's Essential Graphics controller, or
        `None` when it does not resolve. Cached. This is the display name AE
        shows for the override - the leaf's own `tdsn` may be empty."""
        cached = self.__dict__.get("_ov_ctrl_name", _UNSET)
        if cached is not _UNSET:
            return cast("str | None", cached)
        from ...resolvers.essential_properties import (  # noqa: PLC0415
            resolve_essential_property_controller,
        )

        controller = resolve_essential_property_controller(self)
        name = controller.name if controller is not None else None
        self.__dict__["_ov_ctrl_name"] = name
        return name

    @property
    def name(self) -> str:
        ctrl_name = self._override_controller_name()
        return ctrl_name if ctrl_name is not None else super().name

    @name.setter
    def name(self, value: str) -> None:
        PropertyBase.__dict__["name"].fset(self, value)

    @property
    def enabled(self) -> bool:
        src = self._override_source()
        return src.enabled if src is not None else super().enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        PropertyBase.__dict__["enabled"].__set__(self, value)

    @property
    def min_value(self) -> Any:
        src = self._override_source()
        return src.min_value if src is not None else super().min_value

    @property
    def max_value(self) -> Any:
        src = self._override_source()
        return src.max_value if src is not None else super().max_value

    @property
    def is_modified(self) -> bool:
        src = self._override_source()
        if src is not None:
            return not _values_equal(self.value, src.value)
        return super().is_modified

    @property
    def is_spatial(self) -> bool:
        src = self._override_source()
        return src.is_spatial if src is not None else super().is_spatial

    @property
    def units_text(self) -> str:
        src = self._override_source()
        return src.units_text if src is not None else super().units_text

    @property
    def can_vary_over_time(self) -> bool:
        src = self._override_source()
        return src.can_vary_over_time if src is not None else super().can_vary_over_time

    @property
    def can_set_expression(self) -> bool:
        src = self._override_source()
        return src.can_set_expression if src is not None else super().can_set_expression

    @property
    def _effect_scale(self) -> list[float] | None:
        """Inherit the source parameter's denormalization scale.

        An override leaf stores its value in the raw 0-1 form AE keeps, but
        the leaf is not inside an effect, so its own `_effect_scale` is `None`
        and the value would stay normalized. Borrowing the source's scale puts
        `value` in the same units the source reports (e.g. source-comp pixels
        for a point control), matching ExtendScript and making `is_modified`
        compare like for like. `None` for non-point sources and for
        media-replacement overrides (whose source is an `AVLayer`, not a
        `Property`), which fall back to the base (also `None`).
        """
        if "_effect_scale" in self.__dict__:
            result: list[float] | None = self.__dict__["_effect_scale"]
            return result
        src = self._override_source()
        if src is not None:
            return src._effect_scale
        return super()._effect_scale

    @_effect_scale.setter
    def _effect_scale(self, value: list[float] | None) -> None:
        if value is not None and (
            not isinstance(value, (list, tuple)) or len(value) < 2
        ):
            raise ValueError("_effect_scale must be a list of at least 2 floats")
        self.__dict__["_effect_scale"] = value


def _find_or_create_wrapper_folder(project: Project) -> FolderItem:
    """The root-level `Media Replacement Comps` folder, reused if present
    (matching AE) or created at the project root."""
    from ..items.folder import FolderItem  # noqa: PLC0415

    root = project.root_folder
    for item in project.items.values():
        if (
            isinstance(item, FolderItem)
            and item.name == "Media Replacement Comps"
            and item.parent_folder is root
        ):
            return item
    return root.add_folder("Media Replacement Comps")


def _unique_wrapper_suffix(footage: FootageItem, project: Project) -> str:
    """The placed footage's basename, made unique against existing item names
    with AE's ` N` scheme (bare if free, else the first free integer >= 2)."""
    base = _strip_sequence_basename(footage.name)
    names = {item.name for item in project.items.values()}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def _strip_sequence_basename(name: str) -> str:
    """Footage display name -> AE wrapper basename: drop the extension and any
    trailing image-sequence frame range (`foo_[001-003].gif` -> `foo`)."""
    stem = name.rsplit(".", 1)[0] if "." in name else name
    return re.sub(r"[ _]?\[\d+-\d+\]$", "", stem)
