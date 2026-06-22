from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..binary.property_chunks import TdmnChunk

if TYPE_CHECKING:
    from ..binary.chunk import Chunk, ListChunk


_SKIP_CHUNK_TYPES = (
    "engv",
    "aRbs",
)


def get_match_name_runs(
    root_chunk: ListChunk,
) -> list[tuple[str, list[Chunk]]]:
    """Group chunks into runs of consecutive same-match-name properties.

    Each run is a `(match_name, chunks)` pair covering one or more
    adjacent properties sharing a match name (e.g. mask atoms, or an
    effect duplicated right after the original). A match name that
    re-occurs after a different one starts a new run, so file order is
    preserved for same-type properties separated by others (unlike
    `get_chunks_by_match_name`, which merges them).
    """
    runs: list[tuple[str, list[Chunk]]] = []
    if root_chunk:
        skip_to_next_tdmn_flag = True
        for chunk in root_chunk.chunks:
            if chunk.chunk_type == "tdmn":
                match_name = cast("TdmnChunk", chunk).value
                if match_name == "ADBE Group End":
                    skip_to_next_tdmn_flag = True
                    continue
                skip_to_next_tdmn_flag = False
                if not runs or runs[-1][0] != match_name:
                    runs.append((match_name, []))
                runs[-1][1].append(chunk)
            elif (
                not skip_to_next_tdmn_flag
            ) and chunk.chunk_type not in _SKIP_CHUNK_TYPES:
                runs[-1][1].append(chunk)
    return runs


def get_chunks_by_match_name(
    root_chunk: ListChunk,
) -> dict[str, list[Chunk]]:
    """Get chunks grouped by their match name.

    Re-occurrences of a match name merge into one entry, losing the
    relative order of same-type properties separated by others; use
    `get_match_name_runs` when property order matters.
    """
    chunks_by_match_name: dict[str, list[Chunk]] = {}
    for match_name, chunks in get_match_name_runs(root_chunk):
        chunks_by_match_name.setdefault(match_name, []).extend(chunks)
    return chunks_by_match_name
