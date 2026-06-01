from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ...binary.chunk import ContainerChunk, ListChunk
from ...binary.property_chunks import TdmnChunk, TdsbChunk
from ...binary.scalar_chunks import Utf8Chunk
from ...enums import LayerType
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
                ContainerChunk(chunk_type="tdsn", chunks=[Utf8Chunk(value="")]),
                tdmn,
                btds,
                btgu,
            ],
        )

        layer = cast("TextLayer", super()._new(
            name=name,
            layer_id=layer_id,
            duration=duration,
            containing_comp=containing_comp,
            root_tdgp_extra=[text_props_tdmn, text_props_tdgp],
            effect_param_defs=effect_param_defs,
        ))
        layer._ldta.layer_type = LayerType.TEXT
        layer._ldta.label = 5
        return layer
