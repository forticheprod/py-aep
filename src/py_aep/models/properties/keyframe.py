from __future__ import annotations

import math
from typing import TYPE_CHECKING, cast

from py_aep.enums import KeyframeInterpolationType, Label

from ..descriptors import ChunkField
from ..text.text_document import TextDocument
from ..validators import validate_bool, validate_int, validate_number, validate_sequence
from .gradient import Gradient
from .marker import MarkerValue
from .parallel import TEXT_KIND
from .shape import Shape

if TYPE_CHECKING:
    from typing import Union

    from ...binary.ldat_chunks import LdatItem
    from .keyframe_ease import KeyframeEase
    from .property import Property

    _ValueType = Union[
        list[float], float, Gradient, MarkerValue, Shape, TextDocument, None
    ]


_DEFAULT_INFLUENCE = 100.0 / 6.0

_VALUE_FROM_CHUNK = object()  # sentinel: read value from _ldat_item


def _validate_interpolation_type(
    value: KeyframeInterpolationType, keyframe: Keyframe
) -> None:
    """Reject an interpolation type the owning property cannot use.

    Hold-only properties (markers, source text, checkbox/dropdown effect
    params) would otherwise accept a LINEAR/BEZIER byte AE never writes.
    An unbound keyframe has no property to ask, so it is left alone.
    """
    prop = keyframe._property
    if prop is None:
        return
    # Raises for an out-of-enum value before the descriptor's own
    # membership check gets a chance to.
    if not prop.is_interpolation_type_valid(value):
        raise ValueError(
            f"{KeyframeInterpolationType(value).name} is not a valid "
            f"interpolation type for {prop.name!r}."
        )


class Keyframe:
    """
    The `Keyframe` object represents a keyframe of a property.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        position = comp.layers[0].transform.property("ADBE Position")
        keyframe = position.keyframes[0]
        print(keyframe.time)
        ```

    Warning:
        `Keyframe` object does not exist in ExtendScript API. It has been added
        for convenience.
    """

    in_interpolation_type = ChunkField.enum(
        KeyframeInterpolationType,
        "_ldat_item",
        "in_interpolation_type",
        validate=_validate_interpolation_type,
    )
    """The "in" interpolation type for the keyframe. Read / Write.

    Raises `ValueError` if the type is not valid for the owning property
    (see [is_interpolation_type_valid][py_aep.models.properties.property.Property.is_interpolation_type_valid]).
    """

    label = ChunkField.enum(Label, "_ldat_item", "label")
    """
    The label color. Colors are represented by their number (0 for None, or 1
    to 16 for one of the preset colors in the Labels preferences).
    Read / Write.
    """

    out_interpolation_type = ChunkField.enum(
        KeyframeInterpolationType,
        "_ldat_item",
        "out_interpolation_type",
        validate=_validate_interpolation_type,
    )
    """The "out" interpolation type for the keyframe. Read / Write.

    Raises `ValueError` if the type is not valid for the owning property
    (see [is_interpolation_type_valid][py_aep.models.properties.property.Property.is_interpolation_type_valid]).
    """

    roving = ChunkField.bool(
        "_ldat_item",
        "roving",
    )
    """
    `True` if the keyframe is roving. The first and last keyframe in
    a property cannot rove. Read / Write.
    """

    temporal_auto_bezier = ChunkField.bool(
        "_ldat_item",
        "temporal_auto_bezier",
    )
    """
    `True` if the keyframe has temporal auto-Bezier interpolation. Temporal
    auto-Bezier interpolation affects this keyframe only if the keyframe
    interpolation type is `KeyframeInterpolationType.BEZIER` for both
    `in_interpolation_type` and `out_interpolation_type`. Read / Write.
    """

    temporal_continuous = ChunkField.bool(
        "_ldat_item",
        "temporal_continuous",
    )
    """
    `True` if the keyframe has temporal continuity. Temporal continuity affects
    this keyframe only if the keyframe interpolation type is
    `KeyframeInterpolationType.BEZIER` for both `in_interpolation_type` and
    `out_interpolation_type`. Read / Write.
    """

    def __init__(
        self,
        *,
        _ldat_item: LdatItem,
        _time_scale: float,
        _frame_rate: float,
    ) -> None:
        self._ldat_item = _ldat_item
        self._time_scale = _time_scale
        self._frame_rate = _frame_rate
        self._property: Property | None = None
        self._prev: Keyframe | None = None
        self._next: Keyframe | None = None

        self._in_temporal_ease: list[KeyframeEase] | None = None
        self._out_temporal_ease: list[KeyframeEase] | None = None

        self._value: _ValueType | object = _VALUE_FROM_CHUNK

    def _bind_property(self, prop: Property) -> None:
        """Set the owning property and propagate speed factor to ease."""
        self._property = prop
        factor = prop._speed_factor
        # Propagate to already-created ease objects
        if self._in_temporal_ease is not None:
            for ease in self._in_temporal_ease:
                ease._speed_factor = factor
        if self._out_temporal_ease is not None:
            for ease in self._out_temporal_ease:
                ease._speed_factor = factor

    def _extract_raw_value(
        self,
    ) -> list[float] | float | None:
        """Read raw value from the binary chunk data.

        Returns a scalar for 1-dimensional properties, a list for
        multi-dimensional or color properties, and `None` when the
        keyframe type carries no value (e.g. markers).
        """
        kf_data = self._ldat_item.kf_data
        if not hasattr(kf_data, "value"):
            return None
        values: list[float] = list(kf_data.value)
        if len(values) == 1:
            return values[0]
        return values

    def _create_ease(
        self,
    ) -> tuple[list[KeyframeEase], list[KeyframeEase]]:
        """Create in/out temporal ease objects from the binary chunk data.

        Returns:
            A `(in_ease, out_ease)` tuple. Each element is a list of
            [KeyframeEase][] objects - one per dimension for
            multi-dimensional properties, or a single element for scalar /
            spatial types. Returns `([], [])` when the keyframe type
            carries no ease data (e.g. markers).
        """
        from .keyframe_ease import KeyframeEase

        kf_data = self._ldat_item.kf_data
        if not hasattr(kf_data, "in_speed"):
            return [], []

        factor = self._property._speed_factor if self._property else 1.0

        if isinstance(kf_data.in_speed, list):
            in_ease = [
                KeyframeEase._from_binary(kf_data, i, "in", factor)
                for i in range(len(kf_data.in_speed))
            ]
            out_ease = [
                KeyframeEase._from_binary(kf_data, i, "out", factor)
                for i in range(len(kf_data.out_speed))
            ]
        else:
            in_ease = [KeyframeEase._from_binary(kf_data, 0, "in", factor)]
            out_ease = [KeyframeEase._from_binary(kf_data, 0, "out", factor)]
        return in_ease, out_ease

    def _ensure_ease(self) -> None:
        """Lazily create ease objects on first access."""
        if self._in_temporal_ease is None:
            self._in_temporal_ease, self._out_temporal_ease = self._create_ease()

    @property
    def in_spatial_tangent(self) -> list[float] | None:
        """
        The incoming spatial tangent for the keyframe, if the named
        property is spatial (that is, the value type is `TwoD_SPATIAL` or
        `ThreeD_SPATIAL`).

        - If the property value type is `PropertyValueType.TwoD_SPATIAL`, the
          list contains 2 floating-point values.
        - If the property value type is `PropertyValueType.ThreeD_SPATIAL`, the
          list contains 3 floating-point values.
        - If the property value type is neither of these types, returns `None`.
        """
        kf_data = self._ldat_item.kf_data
        if hasattr(kf_data, "in_spatial_tangents"):
            return list(kf_data.in_spatial_tangents)
        return None

    @in_spatial_tangent.setter
    def in_spatial_tangent(self, value: list[float]) -> None:
        if value is None or self.in_spatial_tangent is None:
            return
        validate_sequence(length=len(self.in_spatial_tangent))(value)
        kf_data = self._ldat_item.kf_data
        if hasattr(kf_data, "in_spatial_tangents"):
            kf_data.in_spatial_tangents = value

    @property
    def out_spatial_tangent(self) -> list[float] | None:
        """
        The outgoing spatial tangent for the keyframe, if the named
        property is spatial (that is, the value type is `TwoD_SPATIAL` or
        `ThreeD_SPATIAL`).

        - If the property value type is `PropertyValueType.TwoD_SPATIAL`, the
          list contains 2 floating-point values.
        - If the property value type is `PropertyValueType.ThreeD_SPATIAL`, the
          list contains 3 floating-point values.
        - If the property value type is neither of these types, returns `None`.
        """
        kf_data = self._ldat_item.kf_data
        if hasattr(kf_data, "out_spatial_tangents"):
            return list(kf_data.out_spatial_tangents)
        return None

    @out_spatial_tangent.setter
    def out_spatial_tangent(self, value: list[float] | None) -> None:
        if value is None or self.out_spatial_tangent is None:
            return
        validate_sequence(length=len(self.out_spatial_tangent))(value)
        kf_data = self._ldat_item.kf_data
        if value is not None and hasattr(kf_data, "out_spatial_tangents"):
            kf_data.out_spatial_tangents = value

    @property
    def value(
        self,
    ) -> _ValueType:
        """
        The value of the keyframe. For a 1D property (e.g. Opacity, Rotation),
        this is a single `float`. For a multi-dimensional property (e.g.
        Position, Scale), this is a `list[float]`. For shape/mask path
        properties, this is a [Shape][]. For text properties, this is a
        [TextDocument][]. For marker properties, this is a [MarkerValue][].
        For properties that carry no value, this is `None`.
        """
        val = (
            self._value
            if self._value is not _VALUE_FROM_CHUNK
            else self._extract_raw_value()
        )
        if self._property is not None and isinstance(val, (int, float, list)):
            return cast("_ValueType", self._property._resolve_value(val))
        return cast("_ValueType", val)

    @value.setter
    def value(
        self,
        value: _ValueType,
    ) -> None:
        if not isinstance(
            value,
            (int, float, list, Gradient, MarkerValue, Shape, TextDocument, type(None)),
        ):
            raise ValueError(
                "value must be a number, list of numbers, Gradient, MarkerValue, Shape, TextDocument, or None"
            )
        prop = self._property
        if prop is not None:
            # Reuse the property's value validation (numeric bounds + finite
            # check); it is a no-op for complex value types. Keeps NaN/inf and
            # out-of-range values out of keyframe floats just as `.value=` does.
            from .property import _validate_value

            _validate_value(prop, value)
            # Replacing a TEXT keyframe's value must mutate the EXISTING
            # btdk-wired TextDocument in place (text documents live in the
            # shared btdk COS blob, not a per-keyframe container). Storing a
            # fresh, disconnected TextDocument leaves the real btdk with fewer
            # COS docs than the keyframe count, so AE rejects the file ("error
            # reading text layer from index"). Mirror `_set_parallel_value_at`.
            if isinstance(value, TextDocument) and prop._parallel_kind() is TEXT_KIND:
                current = self.value
                if isinstance(current, TextDocument):
                    current.text = value.text
                    prop._ensure_materialized()
                else:
                    self._value = value
                return
        # Complex (parallel-container) properties store their real value in a
        # sibling container chunk (otda / Nmrd / shap / Utf8), not in kf_data;
        # route the write through the property so the container - and any
        # mirrored header bytes - are updated. Text (no container) keeps the
        # shadow path: its documents live in the shared btdk COS blob.
        if prop is not None and prop._kf_value_container is not None:
            kind = prop._parallel_kind()
            if kind is not None and kind is not TEXT_KIND:
                prop._write_parallel_kf_value(self, kind.coerce(value), kind)
                return
        if prop is not None and isinstance(value, (int, float, list)):
            raw = cast(
                "list[float] | float | int | None",
                prop._unresolve_value(value),
            )
            self._write_kf_value(raw)
            self._value = raw
        else:
            self._value = value

    def _cache_value(self, value: _ValueType) -> None:
        """Cache a value decoded from chunks (parser-only).

        Unlike the public `value` setter this never writes the
        parallel value container: the chunks already hold the value,
        only the in-memory shadow needs filling. Numeric values are
        stored unresolved, matching `_extract_raw_value`; the write
        through `_write_kf_value` is a no-op for parallel-kind
        properties (component-count mismatch) and byte-faithful
        otherwise.
        """
        prop = self._property
        if prop is not None and isinstance(value, (int, float, list)):
            raw = cast(
                "list[float] | float | int | None",
                prop._unresolve_value(value),
            )
            self._write_kf_value(raw)
            self._value = raw
        else:
            self._value = value

    def _write_kf_value(self, raw: list[float] | float | int | None) -> None:
        """Persist a raw numeric value into the backing kf_data chunk.

        Serialization reads from `kf_data`, not the in-memory `_value`
        shadow, so numeric / color / spatial keyframe values must be
        written through here to round-trip.

        The write is skipped when the kf_data carries no value (markers)
        or when the property keeps its real value in a parallel container
        (orientation keeps a 1-component kf_data but a 3-component otda
        value; the parser also assigns that 3-component value here at parse
        time). For an ordinary numeric property a length mismatch is a
        genuine dimension error from the caller and is raised.
        """
        kf_data = self._ldat_item.kf_data
        if not hasattr(kf_data, "value"):
            return
        new = [float(raw)] if isinstance(raw, (int, float)) else None
        if new is None and isinstance(raw, list):
            new = [float(v) for v in raw]
        if new is None:
            return
        if len(new) != len(kf_data.value):
            if (
                self._property is not None
                and self._property._parallel_kind() is not None
            ):
                return
            raise ValueError(
                f"value has {len(new)} component(s) but this keyframe "
                f"expects {len(kf_data.value)}"
            )
        kf_data.value = new

    @property
    def in_temporal_ease(self) -> list[KeyframeEase]:
        """
        The incoming temporal ease for the keyframe.

        Array of [KeyframeEase][] objects:
        - If the property value type is `PropertyValueType.TwoD`, the list
          contains 2 objects.
        - If the property value type is `PropertyValueType.ThreeD`, the list
          contains 3 objects.
        - For any other value type, the list contains 1 object.
        """
        self._ensure_ease()
        assert self._in_temporal_ease is not None
        return self._resolve_ease(self._in_temporal_ease, "in")

    @in_temporal_ease.setter
    def in_temporal_ease(self, value: list[KeyframeEase]) -> None:
        from .keyframe_ease import KeyframeEase

        if not isinstance(value, (list, tuple)):
            raise ValueError("in_temporal_ease must be a list of KeyframeEase objects")
        if not all(isinstance(e, KeyframeEase) for e in value):
            raise ValueError("in_temporal_ease must be a list of KeyframeEase objects")
        self._in_temporal_ease = value

    @property
    def out_temporal_ease(self) -> list[KeyframeEase]:
        """
        The outgoing temporal ease for the keyframe.

        Array of [KeyframeEase][] objects:
        - If the property value type is `PropertyValueType.TwoD`, the list
          contains 2 objects.
        - If the property value type is `PropertyValueType.ThreeD`, the list
          contains 3 objects.
        - For any other value type, the list contains 1 object.
        """
        self._ensure_ease()
        assert self._out_temporal_ease is not None
        return self._resolve_ease(self._out_temporal_ease, "out")

    @out_temporal_ease.setter
    def out_temporal_ease(self, value: list[KeyframeEase]) -> None:
        from .keyframe_ease import KeyframeEase

        if not isinstance(value, (list, tuple)):
            raise ValueError("out_temporal_ease must be a list of KeyframeEase objects")
        if not all(isinstance(e, KeyframeEase) for e in value):
            raise ValueError("out_temporal_ease must be a list of KeyframeEase objects")
        self._out_temporal_ease = value

    def _resolve_ease(
        self, raw_ease: list[KeyframeEase], direction: str
    ) -> list[KeyframeEase]:
        """Apply interpolation-type overrides to temporal ease.

        For BEZIER keyframes the binary-backed ease objects are returned
        directly (with `_speed_factor` already set).  For LINEAR
        keyframes the speed is computed from the segment between adjacent
        keyframes.  For HOLD keyframes the speed is always 0.
        """
        from .keyframe_ease import KeyframeEase

        if not raw_ease:
            return [KeyframeEase(speed=0.0, influence=0.0)]

        if direction == "in":
            interp = self.in_interpolation_type
        else:
            interp = self.out_interpolation_type

        if interp == KeyframeInterpolationType.LINEAR:
            if direction == "out":
                other = self._next
            else:
                other = self._prev
            if other is None:
                return [
                    KeyframeEase(speed=0.0, influence=_DEFAULT_INFLUENCE)
                    for _ in raw_ease
                ]
            # A HOLD on the adjacent keyframe's connecting side means
            # the segment holds - speed is 0.
            if direction == "out":
                adjacent_interp = other.in_interpolation_type
            else:
                adjacent_interp = other.out_interpolation_type
            if adjacent_interp == KeyframeInterpolationType.HOLD:
                return [
                    KeyframeEase(speed=0.0, influence=_DEFAULT_INFLUENCE)
                    for _ in raw_ease
                ]
            speeds = _segment_speed(
                self if direction == "out" else other,
                other if direction == "out" else self,
                self._property.is_spatial if self._property else False,
                self._frame_rate,
            )
            return [KeyframeEase(speed=s, influence=_DEFAULT_INFLUENCE) for s in speeds]

        if interp == KeyframeInterpolationType.HOLD:
            return [
                KeyframeEase(speed=0.0, influence=_DEFAULT_INFLUENCE) for _ in raw_ease
            ]

        # BEZIER - boundary keyframes get zeroed speed on the side with
        # no adjacent keyframe.  Keep original influence so the
        # interpolation solver that reads the adjacent direction is
        # unaffected.
        if direction == "in" and self._prev is None:
            return [KeyframeEase(speed=0.0, influence=e.influence) for e in raw_ease]
        if direction == "out" and self._next is None:
            return [KeyframeEase(speed=0.0, influence=e.influence) for e in raw_ease]
        return raw_ease

    @property
    def spatial_auto_bezier(self) -> bool:
        """
        `True` if the keyframe has spatial auto-Bezier interpolation. This type
        of interpolation affects this keyframe only if [spatial_continuous][] is
        also `True`. If the property value type is neither `TwoD_SPATIAL` nor
        `ThreeD_SPATIAL`, the value is `False`.
        """
        return getattr(self._ldat_item.kf_data, "spatial_auto_bezier", False)

    @spatial_auto_bezier.setter
    def spatial_auto_bezier(self, value: bool) -> None:
        # Only spatial kf_data carries this flag. Non-spatial kinds (e.g.
        # Orientation, whose kf_data is KfMultiDimensional) have no slot for
        # it; the getter tolerantly reads False there, but a write must not
        # silently vanish (ExtendScript's setSpatialAutoBezierAtKey errors).
        validate_bool(value)
        if not hasattr(self._ldat_item.kf_data, "spatial_auto_bezier"):
            raise ValueError("spatial_auto_bezier can only be set on spatial keyframes")
        self._ldat_item.kf_data.spatial_auto_bezier = value

    @property
    def spatial_continuous(self) -> bool:
        """
        `True` if the keyframe has spatial continuity. If the property value
        type is neither `TwoD_SPATIAL` nor `ThreeD_SPATIAL`, the value is
        `False`.
        """
        return getattr(self._ldat_item.kf_data, "spatial_continuous", False)

    @spatial_continuous.setter
    def spatial_continuous(self, value: bool) -> None:
        # See spatial_auto_bezier: non-spatial kf_data has no such slot.
        validate_bool(value)
        if not hasattr(self._ldat_item.kf_data, "spatial_continuous"):
            raise ValueError("spatial_continuous can only be set on spatial keyframes")
        self._ldat_item.kf_data.spatial_continuous = value

    @property
    def frame_time(self) -> int:
        """Time of the keyframe, in composition frames.

        The binary stores times relative to the layer's start.
        The `_frame_offset` on the owning [Property][] shifts the
        value to composition time.
        """
        # time_units holds internal-timebase units (= frames * time_scale
        # * 256, measured on AE 2026).
        raw = int(round(self._ldat_item.time_units / (self._time_scale * 256.0)))
        if self._property is not None:
            return raw + self._property._frame_offset
        return raw

    @frame_time.setter
    def frame_time(self, value: int) -> None:
        validate_int(value)
        offset = self._property._frame_offset if self._property is not None else 0
        units = round((value - offset) * self._time_scale * 256.0)
        if not -0x80000000 <= units <= 0x7FFFFFFF:
            raise ValueError(
                f"keyframe time out of supported range: frame {value} "
                f"does not fit the 32-bit keyframe time field"
            )
        prop = self._property
        if prop is not None:
            prop._guard_keyframe_move(self, value)
        self._ldat_item.time_units = units
        if prop is not None:
            prop._reposition_keyframe(self)

    @property
    def time(self) -> float:
        """Time of the keyframe, in seconds.

        Writable: moving a keyframe past a neighbour re-sorts the
        property's keyframes (and their backing chunks). Spatial/temporal
        tangents are left as-is, like dragging a keyframe in AE's
        timeline.

        Raises:
            ValueError: When another keyframe already sits at the target
                time.
        """
        return self.frame_time / self._frame_rate

    @time.setter
    def time(self, value: float) -> None:
        validate_number(value)
        self.frame_time = round(value * self._frame_rate)


def _segment_speed(
    kf_a: Keyframe,
    kf_b: Keyframe,
    is_spatial: bool,
    frame_rate: float,
) -> list[float]:
    """Compute the constant speed between two adjacent keyframes.

    For spatial properties a single scalar speed (magnitude of the velocity
    vector) is returned.  For non-spatial multi-dimensional properties a
    per-dimension speed list is returned.  For 1-D properties a single-element
    list is returned.
    """
    frame_delta = kf_b.frame_time - kf_a.frame_time
    if frame_delta == 0:
        return [0.0]

    time_seconds = frame_delta / frame_rate
    val_a = kf_a.value
    val_b = kf_b.value

    if not isinstance(val_a, (int, float, list)):
        return [0.0]
    if not isinstance(val_b, (int, float, list)):
        return [0.0]

    if isinstance(val_a, (int, float)) and isinstance(val_b, (int, float)):
        return [(float(val_b) - float(val_a)) / time_seconds]

    if isinstance(val_a, list) and isinstance(val_b, list):
        if is_spatial:
            distance = math.sqrt(sum((b - a) ** 2 for a, b in zip(val_a, val_b)))
            return [distance / time_seconds]
        return [(b - a) / time_seconds for a, b in zip(val_a, val_b)]

    return [0.0]
