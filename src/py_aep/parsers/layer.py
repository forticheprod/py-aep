from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any, cast

from ..binary.item_chunks import CmtaChunk
from ..binary.layer_chunks import LdtaChunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
)
from ..enums import LayerType
from ..models.descriptors import _suppress_materialization
from ..models.layers.av_layer import AVLayer
from ..models.layers.camera_layer import CameraLayer
from ..models.layers.light_layer import LightLayer
from ..models.layers.parametric_mesh_layer import ParametricMeshLayer
from ..models.layers.shape_layer import ShapeLayer
from ..models.layers.text_layer import TextLayer
from ..models.layers.three_d_model_layer import ThreeDModelLayer

if TYPE_CHECKING:
    from ..binary.chunk import ListChunk
    from ..models.items.composition import CompItem
    from ..models.layers.layer import Layer

_LAYER_CLASSES: dict[int, type[Layer]] = {
    LayerType.AV: AVLayer,
    LayerType.LIGHT: LightLayer,
    LayerType.CAMERA: CameraLayer,
    LayerType.TEXT: TextLayer,
    LayerType.SHAPE: ShapeLayer,
    LayerType.THREE_D_MODEL: ThreeDModelLayer,
    LayerType.PARAMETRIC_MESH: ParametricMeshLayer,
}


@_suppress_materialization()
def parse_layer(
    layer_chunk: ListChunk,
    composition: CompItem,
    effect_param_defs: dict[str, dict[str, dict[str, Any]]],
) -> Layer:
    """
    Parse a composition layer.

    This layer is an instance of an item in a composition. Some information can
    only be found on the source item. To access it, use `source_item = layer.source`.

    Args:
        layer_chunk: The LIST chunk to parse.
        composition: The composition.
        effect_param_defs: Project-level effect parameter definitions, used as
            fallback when layer-level parT chunks are missing.

    Returns:
        An [AVLayer][] for most layers, a [LightLayer][] for light layers, or a
        [ParametricMeshLayer][] for parametric mesh layers.
    """
    child_chunks = layer_chunk.chunks

    try:
        cmta = cast("CmtaChunk", find_by_type(chunks=child_chunks, chunk_type="cmta"))
    except ChunkNotFoundError:
        cmta = None

    ldta = cast("LdtaChunk", find_by_type(chunks=child_chunks, chunk_type="ldta"))
    name_utf8 = cast("Utf8Chunk", find_by_type(chunks=child_chunks, chunk_type="Utf8"))

    layer_type = ldta.layer_type

    try:
        layer_cls = _LAYER_CLASSES[layer_type]
    except KeyError:
        warnings.warn(
            f"Failed to create layer type {layer_type}, falling back to AVLayer",
            stacklevel=2,
        )
        layer_cls = AVLayer

    layer = layer_cls(
        _ldta=ldta,
        _cmta=cmta,
        _name_utf8=name_utf8,
        _layer_list=layer_chunk,
        containing_comp=composition,
    )
    layer._tdgp = find_by_list_type(chunks=child_chunks, list_type="tdgp")
    # The property tree is built on first access (`Layer._tree_param_defs`).
    del layer._properties
    layer._tree_param_defs = effect_param_defs
    return layer
