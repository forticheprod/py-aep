from __future__ import annotations

from py_aep.enums import LightType

from ...kaitai.descriptors import ChunkField
from .av_layer import AVLayer
from .layer import Layer

#: Sentinel value indicating an undefined source id in the binary format.
_UNDEFINED_ID = 0xFFFFFFFF


class LightLayer(Layer):
    """
    The `LightLayer` object represents a light layer within a composition.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        light = comp.light_layers[0]
        print(light.light_type)
        ```

    Info:
        `LightLayer` is a subclass of [Layer][] object. All methods and
        attributes of [Layer][] are available when working with `LightLayer`.

    See: https://ae-scripting.docsforadobe.dev/layer/lightlayer/
    """

    light_type = ChunkField.enum(
        LightType,
        "_ldta",
        "light_type",
    )
    """The type of light. Read / Write."""

    _light_source_id = ChunkField[int](
        "_ldta",
        "source_id",
        transform=lambda v: 0 if v == _UNDEFINED_ID else v,
        reverse_seq_field=lambda v: _UNDEFINED_ID if v == 0 else v,
    )
    """The ID of the layer used as a light source. `0` if none."""

    @property
    def light_source(self) -> Layer | None:
        """The layer used as a light source when `light_type` is
        `LightType.ENVIRONMENT`. Returns `None` if no source is assigned.
        Read / Write.

        The light source can be any 2D video, still, or pre-composition
        layer in the same composition. Assigning a 3D layer raises
        `ValueError`.

        Warning:
            Added in After Effects 24.3.
        """
        if self._light_source_id == 0:
            return None
        return self.containing_comp.layers_by_id.get(self._light_source_id)

    @light_source.setter
    def light_source(self, value: Layer | None) -> None:
        if value is None:
            self._light_source_id = 0
            return

        if isinstance(value, AVLayer) and value.three_d_layer:
            raise ValueError(
                "Invalid light source specified: 3D layers cannot be used as a light source."
            )
        self._light_source_id = value.id
