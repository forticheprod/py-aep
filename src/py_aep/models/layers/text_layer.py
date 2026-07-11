from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...binary.chunk import ListChunk
from ...binary.property_chunks import TdmnChunk, TdsbChunk, TdsnChunk
from ...enums import LayerType
from ..preferences import label_index
from .av_layer import AVLayer

if TYPE_CHECKING:
    from ..items.composition import CompItem


class TextLayer(AVLayer):
    """
    The `TextLayer` object represents a text layer within a composition.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        text_layer = comp.text_layers[0]
        print(text_layer.text)
        ```

    Info:
        `TextLayer` is a subclass of [AVLayer][] object. All methods and
        attributes of [AVLayer][] are available when working with `TextLayer`.

    See: https://ae-scripting.docsforadobe.dev/layer/textlayer/
    """

    _auto_name: str = "Text"

    @classmethod
    def _new(  # type: ignore[override]
        cls,
        *,
        name: str,
        layer_id: int,
        duration: float,
        containing_comp: CompItem,
        btds: ListChunk,
        btgu: ListChunk,
        tdmn: TdmnChunk,
        effect_param_defs: dict[str, dict[str, dict[str, Any]]] | None = None,
    ) -> TextLayer:
        text_props_tdmn = TdmnChunk(value="ADBE Text Properties")
        text_props_tdgp = ListChunk(
            list_type="tdgp",
            chunks=[
                TdsbChunk(),
                TdsnChunk.new(),
                tdmn,
                btds,
                btgu,
                # AE terminates the group's match-name stream; without it
                # the file fails with "missing data in file".
                TdmnChunk(value="ADBE Group End"),
            ],
        )

        layer = cast(
            "TextLayer",
            super()._new(
                name=name,
                layer_id=layer_id,
                duration=duration,
                containing_comp=containing_comp,
                root_tdgp_extra=[text_props_tdmn, text_props_tdgp],
                effect_param_defs=effect_param_defs,
            ),
        )
        layer._ldta.layer_type = LayerType.TEXT
        # AE labels scripted text layers with the "Text Label Index"
        # preference (factory value 1, probed in AE 2026).
        layer._ldta.label = label_index(
            containing_comp._project._preferences, "Text Label Index", 1
        )
        return layer
