"""Parser for Essential Graphics panel data (LIST:CIF3 chunks)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.scalar_chunks import U4Chunk, Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..models.descriptors import _suppress_materialization
from ..models.essential_graphics import EssentialGraphicsController

if TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk


def _parse_controller(cctl_chunk: ListChunk) -> EssentialGraphicsController:
    """Parse a single LIST:CCtl chunk into a controller.

    Args:
        cctl_chunk: A LIST:CCtl chunk.
    """
    cps2 = find_by_list_type(chunks=cctl_chunk.chunks, list_type="CpS2")
    name_utf8 = cast(
        "Utf8Chunk", filter_by_type(chunks=cps2.chunks, chunk_type="Utf8")[0]
    )

    ctyp = cast("U4Chunk", find_by_type(chunks=cctl_chunk.chunks, chunk_type="CTyp"))

    uuid_chunks = filter_by_type(chunks=cctl_chunk.chunks, chunk_type="Utf8")
    uuid = cast("Utf8Chunk", uuid_chunks[0]).value if uuid_chunks else ""

    return EssentialGraphicsController(
        _name_utf8=name_utf8,
        _ctyp=ctyp,
        uuid=uuid,
    )


@_suppress_materialization()
def parse_essential_graphics(
    child_chunks: list[Chunk],
) -> tuple[Utf8Chunk, list[EssentialGraphicsController]] | None:
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
    template_name_utf8 = cast(
        "Utf8Chunk",
        filter_by_type(
            chunks=cps2.chunks,
            chunk_type="Utf8",
        )[0],
    )

    cctl_chunks = filter_by_list_type(chunks=cif3_chunks, list_type="CCtl")
    controllers = [_parse_controller(cctl) for cctl in cctl_chunks]

    return (template_name_utf8, controllers)
