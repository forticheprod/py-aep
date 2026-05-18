from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.property_chunks import TdmnChunk

if TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk


def get_chunks_by_match_name(
    root_chunk: ListChunk,
) -> dict[str, list[Chunk]]:
    """Get chunks grouped by their match name."""
    SKIP_CHUNK_TYPES = (
        "engv",
        "aRbs",
    )
    chunks_by_match_name: dict[str, list[Chunk]] = {}
    if root_chunk:
        skip_to_next_tdmn_flag = True
        match_name = ""
        for chunk in root_chunk.chunks:
            if chunk.chunk_type == "tdmn":
                match_name = cast("TdmnChunk", chunk).value
                if match_name == "ADBE Group End":
                    skip_to_next_tdmn_flag = True
                else:
                    skip_to_next_tdmn_flag = False
                    chunks_by_match_name.setdefault(match_name, []).append(
                        chunk
                    )
            elif (
                not skip_to_next_tdmn_flag
            ) and chunk.chunk_type not in SKIP_CHUNK_TYPES:
                chunks_by_match_name.setdefault(match_name, []).append(chunk)
    return chunks_by_match_name
