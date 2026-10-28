"""Parser for Essential Graphics panel data (LIST:CIF3 chunks)."""

from __future__ import annotations

import json
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
from ..models.essential_graphics import EssentialGraphicsController, SourcePropertyRef

if TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk

# AE stores 0xFFFFFFFF in a CPrp path node's `index` to mean "match by name".
_BY_NAME_INDEX = 0xFFFFFFFF


def _parse_source_property_path(raw: str) -> list[SourcePropertyRef]:
    """Parse a controller's `CPrp` path JSON into root-to-leaf refs.

    The JSON maps stringified positions (`"0"`, `"1"`, ...) to
    `{"index", "matchName"}` nodes describing the path from the layer root to
    the source property the controller exposes.
    """
    nodes = json.loads(raw)
    path: list[SourcePropertyRef] = []
    for key in sorted(nodes, key=int):
        node = nodes[key]
        index = node.get("index")
        path.append(
            SourcePropertyRef(
                match_name=node.get("matchName", ""),
                prop_index=None if index == _BY_NAME_INDEX else index,
            )
        )
    return path


def _name_utf8(chunks: list[Chunk]) -> Utf8Chunk:
    """The name `Utf8` of a CIF container or controller: the first text of
    its `LIST:CpS2`, or of its `LIST:CapS` caption when the project predates
    `CpS2` (file format 92.7, AE 15.1; AE 13.8-15.0 wrote `CapS` alone).
    AE 2026 reads the name from `CapS` in such files and resaves both lists
    with that text.
    """
    for list_type in ("CpS2", "CapS"):
        try:
            names = find_by_list_type(chunks=chunks, list_type=list_type)
        except ChunkNotFoundError:
            continue
        return cast(
            "Utf8Chunk", filter_by_type(chunks=names.chunks, chunk_type="Utf8")[0]
        )
    raise ChunkNotFoundError("Missing LIST/CpS2 and LIST/CapS chunks")


def _parse_controller(cctl_chunk: ListChunk) -> EssentialGraphicsController:
    """Parse a single LIST:CCtl chunk into a controller.

    Args:
        cctl_chunk: A LIST:CCtl chunk.
    """
    name_utf8 = _name_utf8(cctl_chunk.chunks)

    ctyp = cast("U4Chunk", find_by_type(chunks=cctl_chunk.chunks, chunk_type="CTyp"))

    uuid_chunks = filter_by_type(chunks=cctl_chunk.chunks, chunk_type="Utf8")
    uuid = cast("Utf8Chunk", uuid_chunks[0]).value if uuid_chunks else ""

    # The controlled-property path is the nested LIST:CPrp's Utf8 (JSON), a
    # different CPrp from the override-side OvG2/CPrp. Absent for some
    # controllers -> empty path.
    source_property_path: list[SourcePropertyRef] = []
    source_comp_id: int | None = None
    source_layer_id: int | None = None
    try:
        cprp = find_by_list_type(chunks=cctl_chunk.chunks, list_type="CPrp")
    except ChunkNotFoundError:
        cprp = None
    if cprp is not None:
        path_utf8 = filter_by_type(chunks=cprp.chunks, chunk_type="Utf8")
        if path_utf8:
            source_property_path = _parse_source_property_path(
                cast("Utf8Chunk", path_utf8[0]).value
            )
        # CCId / CLId identify the source comp + layer that own the
        # controlled property (the layer is matched by its `layer_id`).
        ccid = filter_by_type(chunks=cprp.chunks, chunk_type="CCId")
        if ccid:
            source_comp_id = cast("U4Chunk", ccid[0]).value
        clid = filter_by_type(chunks=cprp.chunks, chunk_type="CLId")
        if clid:
            source_layer_id = cast("U4Chunk", clid[0]).value

    return EssentialGraphicsController(
        _name_utf8=name_utf8,
        _ctyp=ctyp,
        uuid=uuid,
        source_property_path=source_property_path,
        source_comp_id=source_comp_id,
        source_layer_id=source_layer_id,
    )


@_suppress_materialization()
def parse_essential_graphics(
    child_chunks: list[Chunk],
) -> tuple[Utf8Chunk, list[EssentialGraphicsController]] | None:
    """Parse the Essential Graphics panel from a composition's child chunks.

    Reads the Essential Graphics container and extracts the template name and
    controllers. `CIF3` is the current, authoritative version (AE 2022+);
    `CIF2`/`CIFO` are same-structure legacy versions that can be STALE
    snapshots holding fewer (or zero) controllers than `CIF3` in the same
    file. The `CIF3 -> CIF2 -> CIFO` order is therefore necessary - prefer
    `CIF3` when present, and fall back to the legacy versions only so a
    pre-CIF3 file still yields its template name and controllers rather than
    silently parsing as no Essential Graphics.

    Args:
        child_chunks: The child chunks of a composition LIST:Item chunk.

    Returns:
        A tuple of (template_name_utf8_chunk, controllers) if an Essential
        Graphics container is found, otherwise `None`.
    """
    cif = None
    for list_type in ("CIF3", "CIF2", "CIFO"):
        try:
            cif = find_by_list_type(chunks=child_chunks, list_type=list_type)
            break
        except ChunkNotFoundError:
            continue
    if cif is None:
        return None

    cif_chunks = cif.chunks

    template_name_utf8 = _name_utf8(cif_chunks)

    cctl_chunks = filter_by_list_type(chunks=cif_chunks, list_type="CCtl")
    controllers = [_parse_controller(cctl) for cctl in cctl_chunks]

    return (template_name_utf8, controllers)
