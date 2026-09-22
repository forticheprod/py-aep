from __future__ import annotations

import math
from typing import TYPE_CHECKING, cast

from py_aep.enums import KeyframeInterpolationType, Label

from ...resolvers.interpolation import (
    _DEFAULT_INFLUENCE,
    auto_spatial_tangents,
    auto_temporal_speeds,
)
from ..descriptors import ChunkField
from ..text.text_document import TextDocument
from ..validators import validate_bool, validate_int, validate_number, validate_sequence
from .gradient import Gradient
from .keyframe_ease import KeyframeEase
from .marker import MarkerValue
from .parallel import TEXT_KIND
from .shape import Shape

if TYPE_CHECKING:
    from typing import Union

    from ...binary.ldat_chunks import LdatItem
    from .property import Property

    _ValueType = Union[
        list[float], float, Gradient, MarkerValue, Shape, TextDocument, None
    ]


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


def _timebase_units(time_scale: float, frame_rate: float) -> float:
    """Keyframe units per second: `frame_rate * 256 * time_scale`.

    Rounded to an integer because AE derives and stores
    `cdta.internal_timebase` exactly that way, and the frame rate
    reconstructed from the file is a hair off for NTSC rates (29.97
    gives 23976.0008, where AE stores 23976).
    """
    return float(round(time_scale * 256.0 * frame_rate) or 1)


def _validate_roving(value: bool, keyframe: Keyframe) -> None:
    """Reject a roving flag After Effects would not accept.

    AE raises for a non-spatial property ("This property does not have a
    spatial PropertyValueType"). For the first or last keyframe it silently
    does nothing and leaves the flag false; py-aep raises instead, so the
    caller sees the mistake rather than getting a write that appears to
    succeed and does not.
    """
    validate_bool(value)
    if not value:
        return
    prop = keyframe._property
    if prop is None:
        return
    if not prop._has_motion_path:
        raise ValueError(
            f"roving can only be set on a spatial property, not {prop.match_name!r}"
        )
    if keyframe._prev is None or keyframe._next is None:
        raise ValueError("the first and last keyframe of a property cannot rove")


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
        validate=_validate_roving,
        post_set="_on_roving_set",
    )
    """
    `True` if the keyframe is roving. The first and last keyframe in
    a property cannot rove. Read / Write.

    Setting this on a spatial property re-times the run of roving
    keyframes so the speed the bounding keyframes ask for is held
    across the whole span.  Editing a spatial keyframe's
    [value][Keyframe.value] or [time][Keyframe.time] re-times the
    adjacent runs automatically.

    Raises:
        ValueError: When the property is not spatial, or the keyframe
            is the first or last in its property.
    """

    temporal_auto_bezier = ChunkField.bool(
        "_ldat_item",
        "temporal_auto_bezier",
        post_set="_on_temporal_auto_bezier_set",
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
        post_set="_on_temporal_continuous_set",
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

    def _on_roving_set(self) -> None:
        """Re-space the property's roving keyframes after the flag changed."""
        if self._property is not None:
            self._property._redistribute_roving_keyframes()

    def _force_bezier_both_sides(self) -> None:
        """Set both interpolation types to BEZIER, skipping no-op writes."""
        if self.in_interpolation_type != KeyframeInterpolationType.BEZIER:
            self.in_interpolation_type = KeyframeInterpolationType.BEZIER
        if self.out_interpolation_type != KeyframeInterpolationType.BEZIER:
            self.out_interpolation_type = KeyframeInterpolationType.BEZIER

    def _on_temporal_auto_bezier_set(self) -> None:
        """Materialize the ease AE derives, and its two companion flags.

        Setting temporal auto-bezier makes AE rewrite the stored ease to the
        through-slope with the default influence, force temporal continuity
        on, and force both interpolation types to BEZIER. Measured on AE
        2026; the flag alone left a keyframe carrying ease AE would never
        pair with it.
        """
        if not self.temporal_auto_bezier:
            # AE keeps the derived ease when the flag is cleared.
            return
        # The raw byte, deliberately not the `temporal_continuous` setter:
        # its hook ties the out speed to the in speed, and the derived ease
        # written below is per-side.
        self._ldat_item.temporal_continuous = True
        self._force_bezier_both_sides()
        speeds = self._auto_temporal_speeds()
        if speeds is None:
            return
        self._ensure_ease()
        for direction, values, backing in (
            ("in", speeds[0], self._in_temporal_ease),
            ("out", speeds[1], self._out_temporal_ease),
        ):
            if backing is None or len(backing) != len(values):
                continue
            self._apply_ease(
                [
                    KeyframeEase(speed=speed, influence=_DEFAULT_INFLUENCE)
                    for speed in values
                ],
                direction,
            )

    def _on_temporal_continuous_set(self) -> None:
        """Force both sides to BEZIER and match the out speed to the in one.

        Measured on AE 2026 over five in/out interpolation pairings: setting
        temporal continuity rewrites BOTH interpolation types to BEZIER and
        then ties the speeds, keeping both influences - `(10, 75) /
        (90, 25)` becomes `(10, 75) / (10, 25)` whatever the types were
        beforehand. Forcing BEZIER is what makes the STORED in speed the
        right one to copy: under LINEAR the getter reports the segment
        slope instead, and AE reports 10 here, not the slope.

        Note the spatial equivalent is NOT symmetric: `spatial_continuous`
        genuinely leaves the tangents alone.
        """
        if not self.temporal_continuous:
            return
        self._force_bezier_both_sides()
        self._ensure_ease()
        incoming, outgoing = self._in_temporal_ease, self._out_temporal_ease
        if incoming is None or outgoing is None:
            return
        for out_ease, in_ease in zip(outgoing, incoming):
            out_ease.speed = in_ease.speed

    def _rescale_tangent(self, tangent: list[float], *, invert: bool) -> list[float]:
        """Move a raw spatial tangent into the space its value is reported in.

        An effect point stores both its value and its tangents normalized
        against the layer, and ExtendScript reports both in pixels. Reading
        the tangent raw while the value came back resolved left the two in
        different spaces - a raw -0.5 on a 200-wide layer is AE's -100.
        `invert` divides instead, for the write path.
        """
        prop = self._property
        if prop is None:
            return list(tangent)
        return prop._apply_effect_scale(tangent, invert=invert)

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
        if not hasattr(kf_data, "in_spatial_tangents"):
            return None
        if self.spatial_auto_bezier:
            derived = self._auto_spatial_tangents()
            if derived is not None:
                return self._rescale_tangent(derived[1], invert=False)
        return self._rescale_tangent(list(kf_data.in_spatial_tangents), invert=False)

    @in_spatial_tangent.setter
    def in_spatial_tangent(self, value: list[float]) -> None:
        if value is None or self.in_spatial_tangent is None:
            return
        validate_sequence(length=len(self.in_spatial_tangent))(value)
        kf_data = self._ldat_item.kf_data
        if hasattr(kf_data, "in_spatial_tangents"):
            kf_data.in_spatial_tangents = self._rescale_tangent(value, invert=True)
            if self._property is not None:
                self._property._redistribute_roving_keyframes()

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
        if not hasattr(kf_data, "out_spatial_tangents"):
            return None
        if self.spatial_auto_bezier:
            derived = self._auto_spatial_tangents()
            if derived is not None:
                return self._rescale_tangent(derived[0], invert=False)
        return self._rescale_tangent(list(kf_data.out_spatial_tangents), invert=False)

    @out_spatial_tangent.setter
    def out_spatial_tangent(self, value: list[float] | None) -> None:
        if value is None or self.out_spatial_tangent is None:
            return
        validate_sequence(length=len(self.out_spatial_tangent))(value)
        kf_data = self._ldat_item.kf_data
        if value is not None and hasattr(kf_data, "out_spatial_tangents"):
            kf_data.out_spatial_tangents = self._rescale_tangent(value, invert=True)
            if self._property is not None:
                self._property._redistribute_roving_keyframes()

    def _neighbour_window(self) -> tuple[list[Keyframe], int]:
        """This keyframe plus its immediate neighbours, and its own index.

        One to three keyframes. The interpolation resolvers clamp at the
        ends themselves, so a boundary keyframe simply yields a shorter
        window rather than a special case here.
        """
        window = [kf for kf in (self._prev, self, self._next) if kf is not None]
        return window, 1 if self._prev is not None else 0

    def _auto_spatial_tangents(self) -> tuple[list[float], list[float]] | None:
        """AE's derived tangents for a spatial auto-bezier keyframe.

        AE recomputes these from the flag and ignores whatever is stored,
        so its own files legitimately carry stale or zero tangents on an
        auto-bezier keyframe - reading the chunk back verbatim disagrees
        with what AE reports for the same file.

        Derived in the raw chunk space, matching what these accessors
        return. Returns `None` when the keyframe carries no spatial data.
        """
        if not hasattr(self._ldat_item.kf_data, "in_spatial_tangents"):
            return None
        window, index = self._neighbour_window()
        values = [list(kf._ldat_item.kf_data.value) for kf in window]
        return auto_spatial_tangents(values, index)

    def _auto_temporal_speeds(self) -> tuple[list[float], list[float]] | None:
        """AE's derived per-dimension ease speeds for a temporal auto-bezier
        keyframe, as `(in_speeds, out_speeds)`.

        Returns `None` when the value is not numeric, so the caller can fall
        back to the stored ease.
        """

        def as_vector(keyframe: Keyframe) -> list[float] | None:
            value = keyframe.value
            if isinstance(value, (int, float)):
                return [float(value)]
            if isinstance(value, list) and all(
                isinstance(component, (int, float)) for component in value
            ):
                return [float(component) for component in value]
            return None

        window, index = self._neighbour_window()
        values = [as_vector(kf) for kf in window]
        if any(value is None for value in values):
            return None
        times = [kf._layer_time for kf in window]
        return auto_temporal_speeds(cast("list[list[float]]", values), times, index)

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
            prop._redistribute_roving_keyframes()
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

        The write is skipped when the kf_data carries no value slot at all -
        markers, and the parallel (complex) kinds, whose real value lives in
        a sibling container (an orientation item is a valueless ease item;
        its angles are in `otky`). For an ordinary numeric property a length
        mismatch is a genuine dimension error from the caller and is raised.
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
        self._apply_ease(value, "in")

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
        self._apply_ease(value, "out")

    def _apply_ease(self, value: list[KeyframeEase], direction: str) -> None:
        """Copy `value`'s speed/influence into the chunk-backed ease objects.

        A user-constructed [KeyframeEase][] is detached (it carries its own
        `speed`/`influence` and no chunk), so assigning the list itself
        would keep the numbers in Python only and lose them on save. The
        binary-backed objects live in `_in_temporal_ease` / `_out_temporal_ease`;
        the *getter* may return computed copies (LINEAR, HOLD and boundary
        keyframes), so the write has to go through these, not through
        whatever the getter last returned.
        """
        field = f"{direction}_temporal_ease"
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"{field} must be a list of KeyframeEase objects")
        if not all(isinstance(e, KeyframeEase) for e in value):
            raise ValueError(f"{field} must be a list of KeyframeEase objects")
        self._ensure_ease()
        backing = (
            self._in_temporal_ease if direction == "in" else self._out_temporal_ease
        )
        assert backing is not None
        if not backing:
            # Marker and other ease-less keyframe types have nowhere to
            # store it; ExtendScript's setTemporalEaseAtKey rejects them too.
            raise ValueError("this keyframe type has no temporal ease")
        # A colour keyframe stores ONE shared ease but the getter resolves
        # one per component (the LINEAR speed is computed per dimension), so
        # accept either length - assigning back what the getter returned has
        # to work. Extra entries have no slot to land in; the first wins,
        # matching what the format can hold.
        resolved = len(self._resolve_ease(backing, direction))
        if len(value) not in (len(backing), resolved):
            expected = (
                str(len(backing))
                if resolved == len(backing)
                else f"{len(backing)} or {resolved}"
            )
            raise ValueError(
                f"{field} expects {expected} KeyframeEase object(s), got {len(value)}"
            )
        for target, source in zip(backing, value):
            target._write_from(source)

    def _resolve_ease(
        self, raw_ease: list[KeyframeEase], direction: str
    ) -> list[KeyframeEase]:
        """Apply interpolation-type overrides to temporal ease.

        For BEZIER keyframes the binary-backed ease objects are returned
        directly (with `_speed_factor` already set).  For LINEAR
        keyframes the speed is computed from the segment between adjacent
        keyframes.  For HOLD keyframes the speed is always 0.
        """
        if not raw_ease:
            return [KeyframeEase(speed=0.0, influence=0.0)]

        # Auto-bezier wins over the stored bytes and over the interpolation
        # type. AE recomputes the ease from the flag (and forces the type
        # to BEZIER when the flag is set), so its own files carry stale ease
        # on an auto-bezier keyframe. Colour properties report a single ease
        # whose derivation is not known, so a dimension mismatch falls
        # through to the stored values rather than guessing.
        if self.temporal_auto_bezier:
            auto_speeds = self._auto_temporal_speeds()
            if auto_speeds is not None:
                chosen = auto_speeds[0] if direction == "in" else auto_speeds[1]
                if len(chosen) == len(raw_ease):
                    return [
                        KeyframeEase(speed=speed, influence=_DEFAULT_INFLUENCE)
                        for speed in chosen
                    ]

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
            kind = self._property._parallel_kind() if self._property else None
            if kind is not None and kind.linear_ease_speed is not None:
                # A path and an Orientation have no scalar magnitude for a
                # speed to measure, so AE reports a LINEAR side's speed as
                # the unit chord slope rather than a rate. Measured on AE
                # 2026 across three Orientation segments of different
                # rotation and duration, and on a mask path: always 1.
                # Reporting only - `_single_progress` forces the LINEAR
                # control points and never reads the speed back.
                return [
                    KeyframeEase(
                        speed=kind.linear_ease_speed, influence=_DEFAULT_INFLUENCE
                    )
                    for _ in raw_ease
                ]
            speeds = _segment_speed(
                self if direction == "out" else other,
                other if direction == "out" else self,
                self._property._has_motion_path if self._property else False,
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
        # An effect point stores speed normalized against the comp height.
        # Applied here because the factor needs a fully constructed property,
        # and because `_bind_property` resets ease back to the property-level
        # factor whenever the keyframes are re-linked.
        if self._property is not None:
            factor = self._property._effect_point_speed_factor
            if factor is not None:
                for ease in raw_ease:
                    ease._speed_factor = factor
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
        # Orientation, whose kf_data is a valueless KfNoValue) have no slot
        # for it; the getter tolerantly reads False there, but a write must not
        # silently vanish (ExtendScript's setSpatialAutoBezierAtKey errors).
        validate_bool(value)
        kf_data = self._ldat_item.kf_data
        if not hasattr(kf_data, "spatial_auto_bezier"):
            raise ValueError("spatial_auto_bezier can only be set on spatial keyframes")
        kf_data.spatial_auto_bezier = value
        if not value:
            # AE keeps the tangents it derived: turning auto-bezier off does
            # not restore whatever was there before.
            return
        # Enabling it forces spatial continuity on and materializes the
        # derived tangents into the chunk. AE recomputes them on read anyway,
        # but it also WRITES them, and a later edit that clears the flag
        # leaves whatever is stored in force.
        if hasattr(kf_data, "spatial_continuous"):
            kf_data.spatial_continuous = True
        derived = self._auto_spatial_tangents()
        if derived is not None:
            kf_data.out_spatial_tangents, kf_data.in_spatial_tangents = derived

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
    def _timebase(self) -> float:
        """Keyframe units per second, in the owning LAYER's own time.

        A time-stretched layer counts its ticks against a stretched base
        (`cdta.internal_timebase * max(1, |stretch| / 100)`), so the comp's
        own base only applies at 100 %. Falls back to the cached comp rates
        when the keyframe has no property yet (construction).
        """
        prop = self._property
        if prop is not None:
            base = prop._layer_timebase
            if base:
                return base
        return _timebase_units(self._time_scale, self._frame_rate)

    @property
    def _layer_time(self) -> float:
        """Time of the keyframe in the owning LAYER's own seconds.

        The binary stores ticks against the layer's timebase, so this is
        what the stored value means before any stretch is applied. Every
        interpolation runs here rather than in composition time: After
        Effects evaluates the temporal bezier in layer time, its ease
        speeds are per layer second, and a negatively stretched layer's
        keys only ascend on this axis (see [time][]).
        """
        return self._ldat_item.time_units / self._timebase

    @property
    def time_units(self) -> int:
        """Raw keyframe time, as the binary stores it.

        An integer count of composition timebase units, relative to the
        owning layer's start. Read-only; assign to [time][] instead.
        """
        return self._ldat_item.time_units

    def _set_time_units(self, units: int) -> None:
        """Move this keyframe to `units`, re-sorting the property if needed."""
        if not -0x80000000 <= units <= 0x7FFFFFFF:
            raise ValueError(
                f"keyframe time out of supported range: {units} units "
                f"does not fit the 32-bit keyframe time field"
            )
        prop = self._property
        if prop is not None:
            prop._guard_keyframe_move(self, units)
        self._ldat_item.time_units = units
        if prop is not None:
            prop._reposition_keyframe(self)
            prop._redistribute_roving_keyframes()

    @property
    def frame_time(self) -> int:
        """Time of the keyframe, in whole composition frames.

        A rounded view of [time][]. After Effects places keyframes off the
        frame grid freely, so this is lossy for those - read [time][] when
        precision matters.
        """
        return round(self.time * self._frame_rate)

    @frame_time.setter
    def frame_time(self, value: int) -> None:
        validate_int(value)
        self.time = value / self._frame_rate

    @property
    def time(self) -> float:
        """Time of the keyframe, in seconds.

        Exact: the binary stores an integer count of composition timebase
        units relative to the layer's start, and AE places keyframes
        between frames freely - `setValueAtTime(1.5)` in a 25 fps comp
        lands on frame 37.5, and every roving keyframe is positioned by
        arc length rather than snapped to the grid.

        Writable: moving a keyframe past a neighbour re-sorts the
        property's keyframes (and their backing chunks). Spatial/temporal
        tangents are left as-is, like dragging a keyframe in AE's
        timeline.

        A roving keyframe has no time of its own - it is derived from the
        spatial path - so it cannot be assigned one. Clear
        [roving][Keyframe.roving] first.

        Raises:
            ValueError: When another keyframe already sits at the target
                time, or when this keyframe is roving.
        """
        seconds = self._layer_time
        prop = self._property
        if prop is not None:
            # Ticks are layer time; a stretched layer maps them onto the
            # composition timeline by its stretch factor.
            seconds = seconds * prop._time_stretch + prop._start_time_offset
        return seconds

    @time.setter
    def time(self, value: float) -> None:
        validate_number(value)
        if self.roving:
            # The redistribution that follows every time write would
            # immediately re-derive this keyframe's time from the path, so
            # accepting the value would silently discard it.
            raise ValueError(
                "a roving keyframe's time is derived from the spatial path; "
                "set roving to False before moving it"
            )
        prop = self._property
        offset = prop._start_time_offset if prop is not None else 0.0
        stretch = prop._time_stretch if prop is not None else 1.0
        self._set_time_units(round((value - offset) / stretch * self._timebase))


def _segment_speed(
    kf_a: Keyframe,
    kf_b: Keyframe,
    is_spatial: bool,
) -> list[float]:
    """Compute the constant speed between two adjacent keyframes.

    For spatial properties a single scalar speed (magnitude of the velocity
    vector) is returned.  For non-spatial multi-dimensional properties a
    per-dimension speed list is returned.  For 1-D properties a single-element
    list is returned.
    """
    # Seconds rather than whole frames: two keyframes can sit inside the
    # same frame at different sub-frame times, and rounding them together
    # would report a zero-length segment. LAYER seconds, because AE stores
    # ease speeds per layer second - a 150 % layer whose keys are 3 comp
    # seconds apart reports 25 %/s where the comp-time span gives 16.667.
    time_seconds = kf_b._layer_time - kf_a._layer_time
    if time_seconds == 0:
        return [0.0]
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
