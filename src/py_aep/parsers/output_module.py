from __future__ import annotations

from ..kaitai import Aep
from ..kaitai.utils import (
    ChunkNotFoundError,
    find_by_list_type,
    find_by_type,
    find_chunks_after,
)
from ..models.renderqueue.output_module import OutputModule
from ..models.renderqueue.render_queue_item import RenderQueueItem
from .format_options import parse_format_options


def parse_output_module(
    chunks: list[Aep.Chunk],
    om_ldat_data: Aep.OutputModuleSettingsLdatBody,
    render_queue_item: RenderQueueItem,
) -> OutputModule:
    """
    Parse an output module from its chunk group.

    Each output module consists of:
    - Roou: Output options (binary data)
    - Ropt: Render options (binary data)
    - hdrm: HDR metadata (optional)
    - Utf8: HDR10 / color metadata JSON (optional, only when hdrm present)
    - LIST Als2: Output file path info
      - alas: JSON with fullpath and target_is_folder
    - Utf8: Template/format name (e.g., "H.264 - Match Render Settings - 15 Mbps")
    - Utf8: File name template (e.g., "[compName].[fileextension]" or "output.mp4")

    The Utf8 chunks after Als2 are always name + file template. Files without
    hdrm have only 2 Utf8 chunks total.

    Args:
        chunks: List of chunks belonging to this output module.
        om_ldat_data: Parsed OutputModuleSettingsLdatBody from LdatItem.
        render_queue_item: The parent render queue item.

    Returns:
        OutputModule with parsed attributes.
    """
    roou_chunk = find_by_type(chunks=chunks, chunk_type="Roou")

    # Get the alas chunk body for write-through
    # Utf8 chunks after the Als2 LIST: [0] = format/template name, [1] = file
    # name template. Files without hdrm (pre-2024) have no Utf8 before Als2.
    try:
        als2_chunk = find_by_list_type(chunks=chunks, list_type="Als2")
        alas_utf8 = find_by_type(chunks=als2_chunk.body.chunks, chunk_type="alas").body
        post_als2_utf8 = find_chunks_after(chunks, "Utf8", "LIST:Als2")
        name_utf8 = post_als2_utf8[0].body
        file_name_utf8 = post_als2_utf8[1].body
    except ChunkNotFoundError:
        alas_utf8 = None
        name_utf8 = None
        file_name_utf8 = None

    format_options = parse_format_options(chunks)

    return OutputModule(
        _om_ldat=om_ldat_data,
        _roou=roou_chunk.body,
        _alas_utf8=alas_utf8,
        _file_name_utf8=file_name_utf8,
        _name_utf8=name_utf8,
        _render_settings_ldat=render_queue_item._ldat,
        parent=render_queue_item,
        format_options=format_options,
    )
