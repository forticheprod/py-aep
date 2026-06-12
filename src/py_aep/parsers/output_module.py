from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.render_chunks import RouuChunk
from ..binary.scalar_chunks import Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..models.descriptors import _suppress_materialization
from ..models.renderqueue.output_module import OutputModule
from ..models.renderqueue.render_queue_item import RenderQueueItem
from .format_options import parse_format_options

if TYPE_CHECKING:
    from ..binary.chunk import Chunk
    from ..binary.render_chunks import OutputModuleSettingsItem


@_suppress_materialization()
def parse_output_module(
    chunks: list[Chunk],
    om_ldat_data: OutputModuleSettingsItem,
    render_queue_item: RenderQueueItem,
) -> OutputModule:
    """
    Parse an output module from its chunk group.

    Each output module consists of:
    - Roou: Output options (binary data)
    - Ropt: Render options (binary data)
    - hdrm: HDR metadata (optional)
    - Utf8: HDR10 / color metadata JSON (optional, only when hdrm present)
    - LIST Als2: Output file path info (only once an output file is set;
      a freshly added module has none)
      - alas: JSON with fullpath and target_is_folder
    - Utf8: Template/format name (e.g., "H.264 - Match Render Settings - 15 Mbps")
    - Utf8: File name template (e.g., "[compName].[fileextension]" or "output.mp4")

    The format name and file-name template are always the last two top-level
    `Utf8` chunks (the optional HDR-metadata `Utf8` precedes them, and the
    `alas` lives inside the `Als2` LIST), so they are located by position
    rather than relative to `Als2` - which may be absent.

    Args:
        chunks: List of chunks belonging to this output module.
        om_ldat_data: Parsed OutputModuleSettingsItem from LdatItem.
        render_queue_item: The parent render queue item.

    Returns:
        OutputModule with parsed attributes.
    """
    roou_chunk = cast("RouuChunk", find_by_type(chunks=chunks, chunk_type="Roou"))

    # The alas (output file path) is present only once a file is set.
    try:
        als2_chunk = find_by_list_type(chunks=chunks, list_type="Als2")
        alas_utf8: Utf8Chunk | None = cast(
            "Utf8Chunk", find_by_type(chunks=als2_chunk.chunks, chunk_type="alas")
        )
    except ChunkNotFoundError:
        alas_utf8 = None

    # Format name + file-name template are the last two top-level Utf8 chunks.
    om_utf8 = cast("list[Utf8Chunk]", filter_by_type(chunks=chunks, chunk_type="Utf8"))
    if len(om_utf8) >= 2:
        name_utf8: Utf8Chunk | None = om_utf8[-2]
        file_name_utf8: Utf8Chunk | None = om_utf8[-1]
    else:
        name_utf8 = None
        file_name_utf8 = None

    format_options = parse_format_options(chunks)

    return OutputModule(
        _om_ldat=om_ldat_data,
        _roou=roou_chunk,
        _alas_utf8=alas_utf8,
        _file_name_utf8=file_name_utf8,
        _name_utf8=name_utf8,
        _render_settings_ldat=render_queue_item._ldat,
        parent=render_queue_item,
        format_options=format_options,
    )
