"""Orientation, shape, text document, and gradient property parsers."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, cast

from ..binary.ldat_chunks import LdatChunk
from ..binary.misc_chunks import Fth5Chunk, ShphChunk
from ..binary.property_chunks import CdatChunk, OtdaChunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..cos import CosParser
from ..enums import PropertyValueType
from ..models.properties.parallel import ORIENTATION_KIND
from ..models.properties.shape import FeatherPoint, Shape
from .gradient import parse_gradient_xml
from .property_value import (
    parse_property,
)
from .text import parse_btdk_cos

if TYPE_CHECKING:
    from ..binary.chunk import ListChunk
    from ..binary.property_chunks import TdmnChunk
    from ..binary.scalar_chunks import Utf8Chunk
    from ..models.items.composition import CompItem
    from ..models.properties.property import Property


logger = logging.getLogger(__name__)


def parse_orientation(
    otst_chunk: ListChunk,
    match_name: str,
    property_depth: int,
    composition: CompItem,
    tdmn: TdmnChunk,
) -> Property:
    """
    Parse an orientation property.

    Args:
        otst_chunk: The OTST chunk to parse.
        match_name: A special name for the property used to build unique
            naming paths. The match name is not displayed, but you can refer
            to it in scripts. Every property has a unique match-name
            identifier. Match names are stable from version to version
            regardless of the display name (the name attribute value) or any
            changes to the application. Unlike the display name, it is not
            localized.
        property_depth: The nesting depth of this property (0 = layer level).
        composition: The parent composition.
    """
    tdbs_chunk = find_by_list_type(chunks=otst_chunk.chunks, list_type="tdbs")
    prop = parse_property(
        tdbs_chunk=tdbs_chunk,
        match_name=match_name,
        composition=composition,
        property_depth=property_depth,
        tdmn=tdmn,
    )
    prop._wrapper = otst_chunk
    ORIENTATION_KIND.apply_model_metadata(prop)

    # cdat is parameterized with is_le; .value returns the correctly-
    # endian doubles regardless of context.
    try:
        cdat = cast(
            "CdatChunk", find_by_type(chunks=tdbs_chunk.chunks, chunk_type="cdat")
        )
        values = list(cdat.values)
        while len(values) < 3:
            values.append(0.0)
        prop._cache_value(values[:3])
    except ChunkNotFoundError:
        prop._cache_value(None)

    # Animated orientation keyframes store their 3-component values in
    # otky > otda chunks (one otda per keyframe), a sibling of tdbs inside
    # otst.  The standard _parse_keyframes() reads from tdbs which only has 1D
    # orientation data, so we override each keyframe's value with the full 3D
    # otda data.
    try:
        otky_chunk = find_by_list_type(chunks=otst_chunk.chunks, list_type="otky")
        prop._kf_value_container = otky_chunk
        otda_chunks = cast(
            "list[OtdaChunk]",
            filter_by_type(chunks=otky_chunk.chunks, chunk_type="otda"),
        )
        for idx, kf in enumerate(prop.keyframes):
            if idx < len(otda_chunks):
                kf._cache_value(list(otda_chunks[idx].values))
    except ChunkNotFoundError:
        pass

    return prop


def _parse_shape_shap(
    shap_chunk: ListChunk,
    composition: CompItem,
    is_mask_shape: bool,
) -> Shape:
    """Parse a single shape path from a `shap` LIST chunk.

    Each `shap` LIST contains:
    - `shph` chunk: shape header with closed flag and bounding box
    - `list` LIST:  contains `lhd3` (point count/size) and `ldat`
      (raw normalized bezier points)

    Points in `ldat` are stored as `(x, y)` pairs,
    normalized to the `[0, 1]` range of the bounding box.  Every three
    consecutive points form a cycle:
    `vertex, out_tangent, in_tangent_of_next_vertex`.

    Mask shapes use a normalized `[0, 1]` bounding box, so the
    resulting coordinates must be scaled by the composition size to get
    pixel values.  Shape-layer paths already have a pixel bounding box.

    Args:
        shap_chunk: A `shap` LIST chunk.
        composition: The parent composition, used for denormalizing
            mask shapes.
        is_mask_shape: Whether this shape belongs to a mask property.

    Returns:
        A [Shape][] with absolute coordinates and tangent offsets.
    """
    shph_chunk = cast(
        "ShphChunk", find_by_type(chunks=shap_chunk.chunks, chunk_type="shph")
    )
    list_chunk = find_by_list_type(chunks=shap_chunk.chunks, list_type="list")

    # An empty path (no vertices) carries only the lhd3 header, no ldat;
    # treat it as zero points so the value is an empty Shape, not None.
    try:
        ldat = cast(
            "LdatChunk", find_by_type(chunks=list_chunk.chunks, chunk_type="ldat")
        )
        points = ldat.items
    except ChunkNotFoundError:
        points = []

    # Extract variable-width mask feather data from fth5 chunk (if present).
    try:
        fth5 = cast(
            "Fth5Chunk", find_by_type(chunks=shap_chunk.chunks, chunk_type="fth5")
        )
        feather_points = [FeatherPoint(_fp=pt) for pt in fth5.points]
    except ChunkNotFoundError:
        feather_points = []

    return Shape._from_binary(
        _shph=shph_chunk,
        _points=points,
        _is_mask=is_mask_shape,
        _composition=composition if is_mask_shape else None,
        feather_points=feather_points,
    )


def parse_shape(
    oms_chunk: ListChunk,
    match_name: str,
    property_depth: int,
    composition: CompItem,
    tdmn: TdmnChunk,
) -> Property:
    """Parse a shape/mask-path property from an `om-s` LIST chunk.

    An `om-s` LIST contains:
    - `tdbs` LIST: standard property metadata (timing, keyframes, etc.)
    - `omks` LIST: shape keyframe values (one `shap` per keyframe,
      or one `shap` for static shapes)

    Args:
        oms_chunk: The `om-s` LIST chunk to parse.
        match_name: The property match name.
        property_depth: Nesting depth of this property.
        composition: The parent composition.

    Returns:
        A [Property][] with `property_value_type` set to
        [SHAPE][py_aep.enums.PropertyValueType.SHAPE] and `value`
        set to a [Shape][].
    """
    tdbs_chunk = find_by_list_type(chunks=oms_chunk.chunks, list_type="tdbs")
    prop = parse_property(
        tdbs_chunk=tdbs_chunk,
        match_name=match_name,
        composition=composition,
        property_depth=property_depth,
        tdmn=tdmn,
    )

    prop._wrapper = oms_chunk
    prop._property_value_type = PropertyValueType.SHAPE
    # Shape properties always carry a value (from omks), even though
    # tdb4 may report no_value=True (a static shape's cdat is the empty
    # 4-byte form).
    prop.__dict__["_no_value"] = False

    # Collect shape values from omks > shap LISTs
    try:
        omks_chunk = find_by_list_type(chunks=oms_chunk.chunks, list_type="omks")
        prop._kf_value_container = omks_chunk
        shape_values: list[Shape] = []
        is_mask = match_name == "ADBE Mask Shape"
        for shap_chunk in filter_by_list_type(
            chunks=omks_chunk.chunks, list_type="shap"
        ):
            shape_values.append(_parse_shape_shap(shap_chunk, composition, is_mask))
    except ChunkNotFoundError:
        logger.debug("Could not parse omks shape data for %s", match_name)
        return prop

    # Assign static value (first shape).  Set an empty Shape as default
    # so that is_modified detects any real mask path as modified.
    prop.default_value = Shape(closed=False)
    if shape_values:
        prop._cache_value(shape_values[0])

    for idx, kf in enumerate(prop.keyframes):
        if idx < len(shape_values):
            kf._cache_value(shape_values[idx])

    return prop


def parse_text_document(
    btds_chunk: ListChunk,
    match_name: str,
    property_depth: int,
    composition: CompItem,
    tdmn: TdmnChunk,
) -> Property:
    """
    Parse a text document property.

    Args:
        btds_chunk: The BTDS chunk to parse.
        match_name: A special name for the property used to build unique
            naming paths. The match name is not displayed, but you can refer
            to it in scripts. Every property has a unique match-name
            identifier. Match names are stable from version to version
            regardless of the display name (the name attribute value) or any
            changes to the application. Unlike the display name, it is not
            localized.
        property_depth: The nesting depth of this property (0 = layer level).
        composition: The parent composition.
    """
    tdbs_chunk = find_by_list_type(chunks=btds_chunk.chunks, list_type="tdbs")
    prop = parse_property(
        tdbs_chunk=tdbs_chunk,
        match_name=match_name,
        composition=composition,
        property_depth=property_depth,
        tdmn=tdmn,
    )
    prop._wrapper = btds_chunk
    prop._property_value_type = PropertyValueType.TEXT_DOCUMENT

    try:
        btdk_chunk = find_by_list_type(
            chunks=btds_chunk.chunks,
            list_type="btdk",
        )
        # btdk is a ListChunk with list_type="btdk"; raw data stored in .data
        parser = CosParser(
            io.BytesIO(btdk_chunk.data),
            len(btdk_chunk.data),
        )
        cos_data = parser.parse()
    except (ChunkNotFoundError, OverflowError, SyntaxError, ValueError):
        logger.debug("Failed to parse btdk COS binary for %s", match_name)
        return prop

    if not isinstance(cos_data, dict):
        logger.debug("Unexpected btdk COS structure for %s", match_name)
        return prop

    text_documents, _fonts = parse_btdk_cos(cos_data, btdk_chunk)
    # Wire each document to the project head so version-gated attributes
    # (e.g. the box-text setters) can resolve the AE major version, and to
    # the AE preferences, which hold the Character/Paragraph panel defaults
    # the reset methods restore.
    project_head = composition._project._head
    project_preferences = composition._project._preferences
    for doc in text_documents:
        doc._head = project_head
        doc._preferences = project_preferences
    if text_documents:
        if prop.keyframes:
            for kf, doc in zip(prop.keyframes, text_documents):
                kf._cache_value(doc)
        else:
            prop._cache_value(text_documents[0])

    return prop


def parse_gradient(
    gcst_chunk: ListChunk,
    match_name: str,
    property_depth: int,
    composition: CompItem,
    tdmn: TdmnChunk,
) -> Property:
    """Parse a gradient color property from a GCst chunk.

    The GCst chunk contains:
    - LIST:tdbs with base property metadata
    - LIST:GCky with Utf8 chunks containing gradient XML per keyframe

    Args:
        gcst_chunk: The GCst LIST chunk to parse.
        match_name: The match name identifier for this property.
        property_depth: The nesting depth of this property.
        composition: The parent composition.
        tdmn: The tdmn chunk for this property.
    """
    tdbs_chunk = find_by_list_type(chunks=gcst_chunk.chunks, list_type="tdbs")
    prop = parse_property(
        tdbs_chunk=tdbs_chunk,
        match_name=match_name,
        composition=composition,
        property_depth=property_depth,
        tdmn=tdmn,
    )

    prop._wrapper = gcst_chunk
    try:
        gcky_chunk = find_by_list_type(
            chunks=gcst_chunk.chunks,
            list_type="GCky",
        )
    except ChunkNotFoundError:
        return prop

    prop._kf_value_container = gcky_chunk
    utf8_chunks = cast(
        "list[Utf8Chunk]",
        filter_by_type(chunks=gcky_chunk.chunks, chunk_type="Utf8"),
    )
    gradient_values = []
    for utf8 in utf8_chunks:
        gdata = parse_gradient_xml(utf8)
        if gdata is not None:
            gradient_values.append(gdata)

    if gradient_values:
        if prop.keyframes:
            for kf, gdata in zip(prop.keyframes, gradient_values):
                kf._cache_value(gdata)
        else:
            prop._cache_value(gradient_values[0])

    return prop
