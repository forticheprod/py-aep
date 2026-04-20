from __future__ import annotations

import typing
import warnings
from typing import Any

from ..kaitai.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
)
from ..models.layers.av_layer import AVLayer
from ..models.layers.camera_layer import CameraLayer
from ..models.layers.light_layer import LightLayer
from ..models.layers.shape_layer import ShapeLayer
from ..models.layers.text_layer import TextLayer
from ..models.layers.three_d_model_layer import ThreeDModelLayer
from .property import parse_properties
from .synthesis import synthesize_layer_properties
from .utils import (
    get_chunks_by_match_name,
)

if typing.TYPE_CHECKING:
    from ..kaitai import Aep
    from ..models.items.composition import CompItem
    from ..models.layers.layer import Layer


def parse_layer(
    layer_chunk: Aep.Chunk,
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
        An [AVLayer][] for most layers, or a [LightLayer][] for light layers.
    """
    child_chunks = layer_chunk.body.chunks

    try:
        cmta_body = find_by_type(chunks=child_chunks, chunk_type="cmta").body
    except ChunkNotFoundError:
        cmta_body = None

    ldta_body = find_by_type(chunks=child_chunks, chunk_type="ldta").body
    name_body = find_by_type(chunks=child_chunks, chunk_type="Utf8").body

    layer_type_name = ldta_body.layer_type.name

    _LAYER_CLASSES: dict[str, type[Layer]] = {
        "avlayer": AVLayer,
        "light": LightLayer,
        "camera": CameraLayer,
        "shape": ShapeLayer,
        "text": TextLayer,
        "three_d_model": ThreeDModelLayer,
    }
    try:
        layer_cls = _LAYER_CLASSES[layer_type_name]
    except KeyError:
        warnings.warn(
            f"Failed to create {layer_type_name}, falling back to AVLayer",
            stacklevel=2,
        )
        layer_cls = AVLayer

    layer = layer_cls(
        _ldta=ldta_body,
        _cmta=cmta_body,
        _name_utf8=name_body,
        containing_comp=composition,
        properties=[],
    )

    root_tdgp_chunk = find_by_list_type(chunks=child_chunks, list_type="tdgp")
    properties = parse_properties(
        chunks_by_match_name=get_chunks_by_match_name(root_tdgp_chunk),
        child_depth=1,
        effect_param_defs=effect_param_defs,
        composition=composition,
    )

    layer.properties = properties
    for child in properties:
        child._parent_property = layer

    synthesize_layer_properties(layer)
    return layer
