"""Keyframe ease model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..validators import _validate_number, validate_number

if TYPE_CHECKING:
    from typing import Any


class KeyframeEase:
    """
    The `KeyframeEase` object encapsulates the keyframe ease settings of a
    layer's AE property. Keyframe ease is determined by the `speed` and
    `influence` values.

    See: https://ae-scripting.docsforadobe.dev/other/keyframeease/

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        position = comp.layers[0].transform.property("ADBE Position")
        keyframe = position.keyframes[0]
        print(keyframe.out_temporal_ease[0].speed)
        print(keyframe.out_temporal_ease[0].influence)
        ```
    """

    def __init__(self, speed: float = 0.0, influence: float = 0.0) -> None:
        validate_number(speed)
        # The setter enforces the 0.1-100 user range, but 0.0 is the
        # "no ease" sentinel the parser constructs with, so allow it here.
        _validate_number(min=0.0, max=100.0)(influence)
        self._kf_data: Any = None
        self._dimension_index = 0
        self._direction = ""
        self._speed_factor = 1.0
        self._speed = speed
        self._influence = influence

    @classmethod
    def _from_binary(
        cls,
        kf_data: Any,
        dimension_index: int,
        direction: str,
        speed_factor: float = 1.0,
    ) -> KeyframeEase:
        """Wrap binary keyframe data as a `KeyframeEase` view.

        Args:
            kf_data: The backing keyframe-data chunk body.
            dimension_index: Index into per-dimension speed/influence arrays.
            direction: Either `"in"` or `"out"`.
            speed_factor: Unit-conversion factor applied to the raw speed.
        """
        obj = cls.__new__(cls)
        obj._kf_data = kf_data
        obj._dimension_index = dimension_index
        obj._direction = direction
        obj._speed_factor = speed_factor
        return obj

    def _is_array(self) -> bool:
        """Whether the backing kf_data stores speed/influence as arrays."""
        return isinstance(getattr(self._kf_data, f"{self._direction}_speed"), list)

    @property
    def speed(self) -> float:
        """The speed value of the keyframe. The units depend on the type of
        keyframe, and are displayed in the Keyframe Velocity dialog box.
        Read / Write."""
        if self._kf_data is None:
            return self._speed
        raw = getattr(self._kf_data, f"{self._direction}_speed")
        if isinstance(raw, list):
            return float(raw[self._dimension_index]) * self._speed_factor
        return float(raw) * self._speed_factor

    @speed.setter
    def speed(self, value: float) -> None:
        validate_number(value)
        if self._kf_data is None:
            self._speed = value
            return
        field_name = f"{self._direction}_speed"
        binary_value = value / self._speed_factor if self._speed_factor else value
        if self._is_array():
            getattr(self._kf_data, field_name)[self._dimension_index] = binary_value
        else:
            setattr(self._kf_data, field_name, binary_value)

    @property
    def influence(self) -> float:
        """The influence value of the keyframe, as shown in the Keyframe
        Velocity dialog box. This is a percentage value between 0.1 and
        100. Read / Write."""
        if self._kf_data is None:
            return self._influence
        raw = getattr(self._kf_data, f"{self._direction}_influence")
        if isinstance(raw, list):
            return float(raw[self._dimension_index]) * 100
        return float(raw) * 100

    @influence.setter
    def influence(self, value: float) -> None:
        _validate_number(min=0.1, max=100.0)(value)
        if self._kf_data is None:
            self._influence = value
            return
        field_name = f"{self._direction}_influence"
        binary_value = value / 100
        if self._is_array():
            getattr(self._kf_data, field_name)[self._dimension_index] = binary_value
        else:
            setattr(self._kf_data, field_name, binary_value)
