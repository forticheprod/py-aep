from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...enums import LayerType
from ..preferences import label_index
from .av_layer import AVLayer

if TYPE_CHECKING:
    from ..items.composition import CompItem


class ShapeLayer(AVLayer):
    """
    The `ShapeLayer` object represents a shape layer within a composition.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        shape_layer = comp.shape_layers[0]
        print(shape_layer.content)
        ```

    Info:
        `ShapeLayer` is a subclass of [AVLayer][] object. All methods and
        attributes of [AVLayer][] are available when working with `ShapeLayer`.

    See: https://ae-scripting.docsforadobe.dev/layer/shapelayer/
    """

    _auto_name: str = "Shape Layer"

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        *,
        name: str,
        layer_id: int,
        duration: float,
        containing_comp: CompItem,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> ShapeLayer:
        layer = cast(
            "ShapeLayer",
            super()._new(
                name=name,
                layer_id=layer_id,
                duration=duration,
                containing_comp=containing_comp,
                effect_param_defs=effect_param_defs,
            ),
        )
        layer._ldta.layer_type = LayerType.SHAPE
        layer._ldta.label = label_index(
            containing_comp._project._preferences, "Shape Label Index 2", 8
        )
        layer._ldta.collapse_transformation = True
        return layer
