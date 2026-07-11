from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

from py_aep.enums import LayerType, LightType

from ...binary.layer_chunks import LdtaChunk
from ..descriptors import ChunkField
from ..preferences import label_index
from .av_layer import AVLayer
from .layer import Layer

if TYPE_CHECKING:
    from ..items.composition import CompItem

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

    _auto_name: str = "Light"
    _fov_rad: float = 39.5978 * math.pi / 180
    # AE's default 50mm camera: zoom = width / 0.72 exactly
    # (2 * tan(fov/2) rounds to 0.72; AE uses the exact ratio).
    _zoom_dividend: float = 0.72

    light_type = ChunkField.enum(
        LightType,
        "_ldta",
        "light_and_mesh_type",
    )
    """The type of light. Read / Write."""

    _light_source_id = ChunkField[int](
        "_ldta",
        "source_id",
        transform=lambda v: 0 if v == _UNDEFINED_ID else v,
        reverse=lambda v: _UNDEFINED_ID if v == 0 else v,
    )
    """The ID of the layer used as a light source. `0` if none."""

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        *,
        name: str,
        layer_id: int,
        duration: float,
        containing_comp: CompItem,
        light_type: int = 1,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> LightLayer:
        ae_major = containing_comp._project._head.ae_version_major
        ldta = LdtaChunk(
            layer_id=layer_id,
            source_id=_UNDEFINED_ID,
            label=label_index(
                containing_comp._project._preferences, "Light Label Index 2", 6
            ),
            layer_type=LayerType.LIGHT,
            light_and_mesh_type=light_type,
            layer_flags_2=0x01,
            matte_layer_id=0 if ae_major >= 23 else None,
            layer_name=name[:31] if len(name) > 31 else name,
        )
        ldta.out_point = duration
        ldta.three_d_layer = True
        return cast(
            "LightLayer",
            super()._new(
                ldta=ldta,
                name=name,
                containing_comp=containing_comp,
                effect_param_defs=effect_param_defs,
            ),
        )

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

        if not isinstance(value, Layer):
            raise ValueError("light_source must be a Layer or None")
        if isinstance(value, AVLayer) and value.three_d_layer:
            raise ValueError(
                "Invalid light source specified: 3D layers cannot be used as a light source."
            )
        self._light_source_id = value.id
