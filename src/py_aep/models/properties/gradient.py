"""Gradient color data model for gradient fill/stroke properties."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar, overload

from ...binary.bin_utils import to_f4
from ...binary.scalar_chunks import Utf8Chunk
from ..validators import (
    validate_normalized_float,
    validate_positive_int,
    validate_rgb_color,
)

if TYPE_CHECKING:
    from typing import Callable

T = TypeVar("T")


class _GradientField(Generic[T]):
    """Descriptor triggering gradient XML serialization on write.

    Used on `GradientColorStop`, `GradientAlphaStop`, and `Gradient` to
    automatically re-serialize gradient XML when a field is modified.
    """

    _VALIDATORS: dict[str, Callable[..., None]] = {
        "offset": validate_normalized_float,
        "midpoint": validate_normalized_float,
        "color": validate_rgb_color,
        "alpha": validate_normalized_float,
    }

    def __set_name__(self, owner: type, name: str) -> None:
        self._slot = "_" + name
        self._name = name

    @overload
    def __get__(self, obj: None, objtype: type) -> _GradientField[T]: ...

    @overload
    def __get__(self, obj: object, objtype: type | None = None) -> T: ...

    def __get__(
        self, obj: object, objtype: type | None = None
    ) -> T | _GradientField[T]:
        if obj is None:
            return self
        value: T = object.__getattribute__(obj, self._slot)
        return value

    def __set__(self, obj: object, value: T) -> None:
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

    offset: _GradientField[float] = _GradientField()
    """Position along the gradient (0.0 to 1.0)."""
    midpoint: _GradientField[float] = _GradientField()
    """Interpolation midpoint to next stop (0.0 to 1.0)."""
    color: _GradientField[tuple[float, float, float]] = _GradientField()
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
        return (
            self.offset == other.offset
            and self.midpoint == other.midpoint
            and self.color == other.color
        )


class GradientAlphaStop:
    """A single alpha (opacity) stop in a gradient.

    Each stop defines an opacity at a specific position along the gradient.
    """

    offset: _GradientField[float] = _GradientField()
    """Position along the gradient (0.0 to 1.0)."""
    midpoint: _GradientField[float] = _GradientField()
    """Interpolation midpoint to next stop (0.0 to 1.0)."""
    alpha: _GradientField[float] = _GradientField()
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
        return (
            self.offset == other.offset
            and self.midpoint == other.midpoint
            and self.alpha == other.alpha
        )


class Gradient:
    """Gradient color data for a gradient fill/stroke property.

    Contains ordered lists of color stops and alpha stops that define
    the gradient appearance. Constructing a `Gradient` without
    arguments creates After Effects' default gradient (white to black,
    full alpha).
    """

    version: _GradientField[str] = _GradientField()
    """Gradient data format version."""

    def __init__(
        self,
        color_stops: list[GradientColorStop] | None = None,
        alpha_stops: list[GradientAlphaStop] | None = None,
        version: str = "1.0",
    ) -> None:
        if color_stops is None:
            color_stops = [
                GradientColorStop(0.0, 0.5, (1.0, 1.0, 1.0)),
                GradientColorStop(1.0, 0.5, (0.0, 0.0, 0.0)),
            ]
        if alpha_stops is None:
            alpha_stops = [
                GradientAlphaStop(0.0, 0.5, 1.0),
                GradientAlphaStop(1.0, 0.5, 1.0),
            ]
        if not all(isinstance(stop, GradientColorStop) for stop in color_stops):
            raise ValueError("All color stops must be GradientColorStop instances")
        if not all(isinstance(stop, GradientAlphaStop) for stop in alpha_stops):
            raise ValueError("All alpha stops must be GradientAlphaStop instances")
        self._version = version
        self._utf8 = Utf8Chunk()
        self._color_stops = tuple(color_stops)
        self._alpha_stops = tuple(alpha_stops)
        for stop in self._color_stops:
            stop._gradient = self
        for astop in self._alpha_stops:
            astop._gradient = self
        self._serialize()

    @classmethod
    def _from_binary(
        cls,
        *,
        color_stops: list[GradientColorStop],
        alpha_stops: list[GradientAlphaStop],
        _utf8: Utf8Chunk,
        version: str = "1.0",
    ) -> Gradient:
        """Wrap a parsed gradient XML chunk as a `Gradient`.

        Does not re-serialize, so the backing chunk keeps its original
        bytes (parse / save round-trips stay byte-identical).
        """
        obj = cls.__new__(cls)
        obj._version = version
        obj._utf8 = _utf8
        obj._color_stops = tuple(color_stops)
        obj._alpha_stops = tuple(alpha_stops)
        for stop in obj._color_stops:
            stop._gradient = obj
        for astop in obj._alpha_stops:
            astop._gradient = obj
        return obj

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
        if stop >= len(self._color_stops):
            raise ValueError(
                f"color stop index {stop} out of range "
                f"(gradient has {len(self._color_stops)} color stops)"
            )
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
        if stop >= len(self._alpha_stops):
            raise ValueError(
                f"alpha stop index {stop} out of range "
                f"(gradient has {len(self._alpha_stops)} alpha stops)"
            )
        self._alpha_stops[stop]._gradient = None
        self._alpha_stops = tuple(
            s for i, s in enumerate(self._alpha_stops) if i != stop
        )
        self._serialize()

    def _serialize(self) -> None:
        """Re-serialize gradient data to the backing Utf8 chunk.

        The output matches After Effects' own gradient XML byte for
        byte (XML declaration, one tag per line, single quotes, alpha
        stops before color stops, float32-rounded values printed at 8
        significant digits).
        """
        lines: list[str] = [
            "<?xml version='1.0'?>",
            "<prop.map version='4'>",
            "<prop.list>",
            "<prop.pair>",
            "<key>Gradient Color Data</key>",
            "<prop.list>",
        ]
        lines.extend(
            _stops_lines(
                "Alpha",
                [[s.offset, s.midpoint, s.alpha] for s in self._alpha_stops],
            )
        )
        lines.extend(
            _stops_lines(
                "Color",
                [[s.offset, s.midpoint, *s.color, 1.0] for s in self._color_stops],
            )
        )
        lines.extend(
            [
                "</prop.list>",
                "</prop.pair>",
                "<prop.pair>",
                "<key>Gradient Colors</key>",
                f"<string>{self._version}</string>",
                "</prop.pair>",
                "</prop.list>",
                "</prop.map>",
            ]
        )
        self._utf8.value = "\n".join(lines) + "\n"

    def __repr__(self) -> str:
        return (
            f"Gradient(color_stops={len(self.color_stops)}, "
            f"alpha_stops={len(self.alpha_stops)}, version={self.version!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Gradient):
            return NotImplemented
        return (
            self.color_stops == other.color_stops
            and self.alpha_stops == other.alpha_stops
            and self.version == other.version
        )


def _format_float(value: float) -> str:
    """Format a float the way AE writes gradient XML.

    AE stores stop values as float32 and prints them at up to 8
    significant digits (e.g. `0.83` becomes `0.82999998`).
    """
    return f"{to_f4(value):.8g}"


def _stops_lines(kind: str, stops: list[list[float]]) -> list[str]:
    """XML lines for one `Alpha Stops` / `Color Stops` prop.pair."""
    lines = [
        "<prop.pair>",
        f"<key>{kind} Stops</key>",
        "<prop.list>",
        "<prop.pair>",
        "<key>Stops List</key>",
        "<prop.list>",
    ]
    # AE stores stops in a string-keyed map and serializes them in
    # LEXICOGRAPHIC key order (Stop-0, Stop-1, Stop-10, ..., Stop-15,
    # Stop-2, ...), not numeric order. Match that so gradients with >9
    # stops are byte-identical (identical for <=10 stops).
    for i in sorted(range(len(stops)), key=lambda n: str(n)):
        values = stops[i]
        lines.extend(
            [
                "<prop.pair>",
                f"<key>Stop-{i}</key>",
                "<prop.list>",
                "<prop.pair>",
                f"<key>Stops {kind}</key>",
                "<array>",
                "<array.type><float/></array.type>",
            ]
        )
        lines.extend(f"<float>{_format_float(v)}</float>" for v in values)
        lines.extend(
            [
                "</array>",
                "</prop.pair>",
                "</prop.list>",
                "</prop.pair>",
            ]
        )
    lines.extend(
        [
            "</prop.list>",
            "</prop.pair>",
            "<prop.pair>",
            "<key>Stops Size</key>",
            f"<int type='unsigned' size='32'>{len(stops)}</int>",
            "</prop.pair>",
            "</prop.list>",
            "</prop.pair>",
        ]
    )
    return lines
