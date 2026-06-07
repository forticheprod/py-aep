"""Gradient color data model for gradient fill/stroke properties."""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.etree.ElementTree import (
    Element,
    SubElement,
    tostring,
)

from ..validators import (
    validate_normalized_float,
    validate_positive_int,
    validate_rgb_color,
)

if TYPE_CHECKING:
    from typing import Any

    from ...binary.scalar_chunks import Utf8Chunk


class _GradientField:
    """Descriptor triggering gradient XML serialization on write.

    Used on `GradientColorStop`, `GradientAlphaStop`, and `Gradient` to
    automatically re-serialize gradient XML when a field is modified.
    """

    _VALIDATORS: dict[str, Any] = {
        "offset": validate_normalized_float,
        "midpoint": validate_normalized_float,
        "color": validate_rgb_color,
        "alpha": validate_normalized_float,
    }

    def __set_name__(self, owner: type, name: str) -> None:
        self._slot = "_" + name
        self._name = name

    def __get__(self, obj: object, objtype: type | None = None) -> Any:
        if obj is None:
            return self
        return object.__getattribute__(obj, self._slot)

    def __set__(self, obj: object, value: Any) -> None:
        validator = self._VALIDATORS.get(self._name)
        if validator is not None:
            validator(value, None)
        object.__setattr__(obj, self._slot, value)
        gradient = getattr(obj, "_gradient", obj)
        serialize = getattr(gradient, "_serialize", None)
        if serialize is not None:
            serialize()


class GradientColorStop:
    """A single color stop in a gradient.

    Each stop defines a color at a specific position along the gradient.
    The midpoint controls the interpolation bias between this stop and
    the next.
    """

    offset = _GradientField()
    """Position along the gradient (0.0 to 1.0)."""
    midpoint = _GradientField()
    """Interpolation midpoint to next stop (0.0 to 1.0)."""
    color = _GradientField()
    """RGB color as `(red, green, blue)` with values 0.0 to 1.0."""

    def __init__(
        self,
        offset: float,
        midpoint: float,
        color: tuple[float, float, float],
    ) -> None:
        validate_normalized_float(offset)
        validate_normalized_float(midpoint)
        validate_rgb_color(color)
        self._gradient: Gradient | None = None
        self._offset = offset
        self._midpoint = midpoint
        self._color = color

    def __repr__(self) -> str:
        r, g, b = self.color
        return (
            f"GradientColorStop(offset={self.offset}, midpoint={self.midpoint}, "
            f"color=({r}, {g}, {b}))"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GradientColorStop):
            return NotImplemented
        return (  # type: ignore[no-any-return]
            self.offset == other.offset
            and self.midpoint == other.midpoint
            and self.color == other.color
        )


class GradientAlphaStop:
    """A single alpha (opacity) stop in a gradient.

    Each stop defines an opacity at a specific position along the gradient.
    """

    offset = _GradientField()
    """Position along the gradient (0.0 to 1.0)."""
    midpoint = _GradientField()
    """Interpolation midpoint to next stop (0.0 to 1.0)."""
    alpha = _GradientField()
    """Opacity value (0.0 to 1.0)."""

    def __init__(self, offset: float, midpoint: float, alpha: float) -> None:
        validate_normalized_float(offset)
        validate_normalized_float(midpoint)
        validate_normalized_float(alpha)
        self._gradient: Gradient | None = None
        self._offset = offset
        self._midpoint = midpoint
        self._alpha = alpha

    def __repr__(self) -> str:
        return (
            f"GradientAlphaStop(offset={self.offset}, midpoint={self.midpoint}, "
            f"alpha={self.alpha})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GradientAlphaStop):
            return NotImplemented
        return (  # type: ignore[no-any-return]
            self.offset == other.offset
            and self.midpoint == other.midpoint
            and self.alpha == other.alpha
        )


class Gradient:
    """Parsed gradient color data from a gradient fill/stroke property.

    Contains ordered lists of color stops and alpha stops that define
    the gradient appearance.
    """

    version = _GradientField()
    """Gradient data format version."""

    def __init__(
        self,
        color_stops: list[GradientColorStop],
        alpha_stops: list[GradientAlphaStop],
        _utf8: Utf8Chunk,
        version: str = "1.0",
    ) -> None:
        self._version = version
        self._utf8 = _utf8
        self._color_stops = tuple(color_stops)
        self._alpha_stops = tuple(alpha_stops)
        for stop in self._color_stops:
            stop._gradient = self
        for astop in self._alpha_stops:
            astop._gradient = self

    @property
    def color_stops(self) -> tuple[GradientColorStop, ...]:
        """Ordered color stops defining the gradient."""
        return self._color_stops

    @color_stops.setter
    def color_stops(
        self,
        value: list[GradientColorStop] | tuple[GradientColorStop, ...],
    ) -> None:
        if not all(isinstance(stop, GradientColorStop) for stop in value):
            raise ValueError("All color stops must be GradientColorStop instances")
        for stop in self._color_stops:
            stop._gradient = None
        self._color_stops = tuple(value)
        for stop in self._color_stops:
            stop._gradient = self
        self._serialize()

    @property
    def alpha_stops(self) -> tuple[GradientAlphaStop, ...]:
        """Ordered alpha stops defining opacity along the gradient."""
        return self._alpha_stops

    @alpha_stops.setter
    def alpha_stops(
        self,
        value: list[GradientAlphaStop] | tuple[GradientAlphaStop, ...],
    ) -> None:
        if not all(isinstance(stop, GradientAlphaStop) for stop in value):
            raise ValueError("All alpha stops must be GradientAlphaStop instances")
        for stop in self._alpha_stops:
            stop._gradient = None
        self._alpha_stops = tuple(value)
        for astop in self._alpha_stops:
            astop._gradient = self
        self._serialize()

    def add_color_stop(
        self, offset: float, midpoint: float, color: tuple[float, float, float]
    ) -> None:
        """Add a color stop."""
        stop = GradientColorStop(offset, midpoint, color)
        stop._gradient = self
        self._color_stops = (*self._color_stops, stop)
        self._serialize()

    def remove_color_stop(self, stop: int) -> None:
        """Remove a color stop by index."""
        validate_positive_int(stop)
        self._color_stops[stop]._gradient = None
        self._color_stops = tuple(
            s for i, s in enumerate(self._color_stops) if i != stop
        )
        self._serialize()

    def add_alpha_stop(self, offset: float, midpoint: float, alpha: float) -> None:
        """Add an alpha stop."""
        stop = GradientAlphaStop(offset, midpoint, alpha)
        stop._gradient = self
        self._alpha_stops = (*self._alpha_stops, stop)
        self._serialize()

    def remove_alpha_stop(self, stop: int) -> None:
        """Remove an alpha stop by index."""
        validate_positive_int(stop)
        self._alpha_stops[stop]._gradient = None
        self._alpha_stops = tuple(
            s for i, s in enumerate(self._alpha_stops) if i != stop
        )
        self._serialize()

    def _serialize(self) -> None:
        """Re-serialize gradient data to the backing Utf8 chunk."""
        root = Element("prop.map", version="4")
        prop_list = SubElement(root, "prop.list")

        # Gradient Color Data
        _add_pair_open(prop_list, "Gradient Color Data")
        data_list = SubElement(prop_list[-1], "prop.list")

        # Color stops
        _add_pair_open(data_list, "Color Stops")
        color_list = SubElement(data_list[-1], "prop.list")
        _add_pair_open(color_list, "Stops List")
        stops_list = SubElement(color_list[-1], "prop.list")
        for i, stop in enumerate(self._color_stops):
            _add_pair_open(stops_list, f"Stop-{i}")
            stop_list = SubElement(stops_list[-1], "prop.list")
            r, g, b = stop.color
            _add_float_array_pair(
                stop_list,
                "Stops Color",
                [stop.offset, stop.midpoint, r, g, b, 1.0],
            )

        # Alpha stops
        _add_pair_open(data_list, "Alpha Stops")
        alpha_list = SubElement(data_list[-1], "prop.list")
        _add_pair_open(alpha_list, "Stops List")
        alpha_stops_list = SubElement(alpha_list[-1], "prop.list")
        for i, astop in enumerate(self._alpha_stops):
            _add_pair_open(alpha_stops_list, f"Stop-{i}")
            stop_list = SubElement(alpha_stops_list[-1], "prop.list")
            _add_float_array_pair(
                stop_list,
                "Stops Alpha",
                [astop.offset, astop.midpoint, astop.alpha],
            )

        # Version
        pair = SubElement(prop_list, "prop.pair")
        SubElement(pair, "key").text = "Gradient Colors"
        SubElement(pair, "string").text = self.version

        self._utf8.value = tostring(root, encoding="unicode")

    def __repr__(self) -> str:
        return (
            f"Gradient(color_stops={len(self.color_stops)}, "
            f"alpha_stops={len(self.alpha_stops)}, version={self.version!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Gradient):
            return NotImplemented  # type: ignore[no-any-return]
        return (
            self.color_stops == other.color_stops
            and self.alpha_stops == other.alpha_stops
            and self.version == other.version
        )


def _add_pair_open(parent: Element, key_text: str) -> None:
    """Add a prop.pair with a key; caller appends the value element."""
    pair = SubElement(parent, "prop.pair")
    SubElement(pair, "key").text = key_text


def _add_float_array_pair(parent: Element, key_text: str, values: list[float]) -> None:
    """Add a prop.pair containing a float array."""
    pair = SubElement(parent, "prop.pair")
    SubElement(pair, "key").text = key_text
    array = SubElement(pair, "array")
    for v in values:
        SubElement(array, "float").text = str(v)
