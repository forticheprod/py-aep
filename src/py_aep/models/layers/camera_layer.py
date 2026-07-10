from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

from ...binary.layer_chunks import LdtaChunk
from ...enums import LayerType
from ..preferences import label_index
from .layer import Layer

if TYPE_CHECKING:
    from ..items.composition import CompItem


class CameraLayer(Layer):
    """
    The CameraLayer object represents a camera layer within a composition.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        camera = comp.camera_layers[0]
        print(camera.name)
        ```

    Info:
        `CameraLayer` is a subclass of [Layer][] object. All methods and
        attributes of [Layer][] are available when working with `CameraLayer`.

    See: https://ae-scripting.docsforadobe.dev/layer/cameralayer/
    """

    _auto_name: str = "Camera"
    _fov_rad: float = 39.5978 * math.pi / 180
    # AE's default 50mm camera: zoom = width / 0.72 exactly
    # (2 * tan(fov/2) rounds to 0.72; AE uses the exact ratio).
    _zoom_dividend: float = 0.72

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        *,
        name: str,
        layer_id: int,
        duration: float,
        containing_comp: CompItem,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> CameraLayer:
        ae_major = containing_comp._project._head.ae_version_major
        ldta = LdtaChunk(
            layer_id=layer_id,
            label=label_index(
                containing_comp._project._preferences, "Camera Label Index 2", 4
            ),
            layer_type=LayerType.CAMERA,
            layer_flags_2=0x01,
            matte_layer_id=0 if ae_major >= 23 else None,
            layer_name=name[:31] if len(name) > 31 else name,
        )
        ldta.out_point = duration
        ldta.three_d_layer = True
        return cast(
            "CameraLayer",
            super()._new(
                ldta=ldta,
                name=name,
                containing_comp=containing_comp,
                effect_param_defs=effect_param_defs,
            ),
        )
