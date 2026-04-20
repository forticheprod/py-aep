"""Keyframe ease model."""

from __future__ import annotations

import typing

from ...kaitai.utils import propagate_check

if typing.TYPE_CHECKING:
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

    def __init__(
        self,
        *,
        speed: float = 0.0,
        influence: float = 0.0,
        _kf_data: Any = None,
        _dimension_index: int = 0,
        _direction: str = "",
        _speed_factor: float = 1.0,
    ) -> None:
        self._kf_data = _kf_data
        self._dimension_index = _dimension_index
        self._direction = _direction
        self._speed_factor = _speed_factor
        if _kf_data is None:
            self._speed = speed
            self._influence = influence

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
        if self._kf_data is None:
            self._speed = value
            return
        field_name = f"{self._direction}_speed"
        binary_value = value / self._speed_factor if self._speed_factor else value
        if self._is_array():
            getattr(self._kf_data, field_name)[self._dimension_index] = binary_value
        else:
            setattr(self._kf_data, field_name, binary_value)
        propagate_check(self._kf_data)

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
        if value < 0.1 or value > 100.0:
            raise ValueError(f"influence must be between 0.1 and 100.0, got {value}")
        if self._kf_data is None:
            self._influence = value
            return
        field_name = f"{self._direction}_influence"
        binary_value = value / 100
        if self._is_array():
            getattr(self._kf_data, field_name)[self._dimension_index] = binary_value
        else:
            setattr(self._kf_data, field_name, binary_value)
        propagate_check(self._kf_data)
