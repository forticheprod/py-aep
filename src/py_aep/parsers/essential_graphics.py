"""Parser for Essential Graphics panel data (LIST:CIF3 chunks)."""

from __future__ import annotations

import typing

from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..models.essential_graphics import EssentialGraphicsController

if typing.TYPE_CHECKING:
    from ..binary.chunk import Chunk


def _parse_controller(cctl_chunk: Chunk) -> EssentialGraphicsController:
    """Parse a single LIST:CCtl chunk into a controller.

    Args:
        cctl_chunk: A LIST:CCtl chunk.
    """
    chunks = cctl_chunk.chunks

    cps2 = find_by_list_type(chunks=chunks, list_type="CpS2")
    name_utf8 = filter_by_type(chunks=cps2.chunks, chunk_type="Utf8")[0]

    ctyp = find_by_type(chunks=chunks, chunk_type="CTyp")

    return EssentialGraphicsController(
        _name_utf8=name_utf8,
        _ctyp=ctyp,
    )


def parse_essential_graphics(
    child_chunks: list[Chunk],
) -> tuple[Chunk, list[EssentialGraphicsController]] | None:
    """Parse the Essential Graphics panel from a composition's child chunks.

    Reads the `LIST:CIF3` chunk (the most complete EG definition version)
    and extracts the template name and controllers.

    Args:
        child_chunks: The child chunks of a composition LIST:Item chunk.

    Returns:
        A tuple of (template_name_utf8_chunk, controllers) if a CIF3 chunk
        is found, otherwise `None`.
    """
    try:
        cif3 = find_by_list_type(chunks=child_chunks, list_type="CIF3")
    except ChunkNotFoundError:
        return None

    cif3_chunks = cif3.chunks

    # Template name from the first LIST:CpS2
    cps2 = find_by_list_type(chunks=cif3_chunks, list_type="CpS2")
    template_name_utf8 = filter_by_type(chunks=cps2.chunks, chunk_type="Utf8")[0]

    # Parse controllers from LIST:CCtl entries
    cctl_chunks = filter_by_list_type(chunks=cif3_chunks, list_type="CCtl")
    controllers = [_parse_controller(cctl) for cctl in cctl_chunks]

    return (template_name_utf8, controllers)
