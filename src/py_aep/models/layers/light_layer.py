from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

from py_aep.enums import LayerType, LightType

from ...binary.layer_chunks import LdtaChunk
from ..descriptors import ChunkField
from ..preferences import label_index
from .av_layer import AVLayer
from .layer import _UNDEFINED_ID, Layer, _no_source_id

if TYPE_CHECKING:
    from ..items.composition import CompItem


def _require_environment_lights(comp: CompItem, what: str) -> None:
    """Environment lights and their light source arrived in AE 24.3."""
    head = comp._project._head
    if (head.ae_version_major, head.ae_version_minor) < (24, 3):
        raise AttributeError(
            f"{what} requires AE 24.3+ file format (file is AE "
            f"{head.ae_version_major}.{head.ae_version_minor})."
        )


def _validate_light_type(value: Any, obj: LightLayer) -> None:
    if value == LightType.ENVIRONMENT:
        _require_environment_lights(obj.containing_comp, "LightType.ENVIRONMENT")


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

    @property
    def is_3d(self) -> bool:
        """Always `True`: a camera / light layer only exists in 3D space.
        Read-only."""
        return True

    light_type = ChunkField.enum(
        LightType,
        "_ldta",
        "light_and_mesh_type",
        validate=_validate_light_type,
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
        ldta = LdtaChunk(
            layer_id=layer_id,
            source_id=_no_source_id(containing_comp),
            label=label_index(
                containing_comp._project._preferences, "Light Label Index 2", 6
            ),
            layer_type=LayerType.LIGHT,
            light_and_mesh_type=light_type,
            layer_flags_2=0x01,
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

        The light source can be any 2D video, still, pre-composition, text
        or shape layer in the same composition. Like After Effects 2026,
        assigning a camera or light, a null, an adjustment or a 3D layer, a
        layer of another composition, or a source on a spot or point light
        raises `ValueError`.

        Warning:
            Added in After Effects 24.3.
        """
        if self._light_source_id == 0:
            return None
        return self.containing_comp.layers_by_id.get(self._light_source_id)

    @light_source.setter
    def light_source(self, value: Layer | None) -> None:
        comp = self.containing_comp
        if value is None:
            self._ldta.source_id = _no_source_id(comp)
            return
        _require_environment_lights(comp, "light_source")

        if not isinstance(value, Layer):
            raise ValueError("light_source must be a Layer or None")
        if not isinstance(value, AVLayer):
            raise ValueError("Can't set a non-AV layer as a light source.")
        if value.containing_comp is not comp:
            raise ValueError("light_source must be a layer in the same composition")
        if self.light_type in (LightType.SPOT, LightType.POINT):
            # AE 2026 refuses these two ("Invalid light source specified")
            # and stores a source on a parallel light.
            raise ValueError(
                "Invalid light source specified for a spot or point light."
            )
        if value.three_d_layer or value.null_layer or value.adjustment_layer:
            raise ValueError(
                "Invalid light source specified: 3D, null and adjustment layers "
                "cannot be used as a light source."
            )
        self._light_source_id = value.id
