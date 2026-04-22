"""
AEP File Comparison Tool.

Compares After Effects project files (.aep) and reports differences
at the byte level, including:
- The hierarchical chunk path where the difference occurs
- Byte position and hex values
- If only one bit differs, the bit position (7 to 0 from left to right)

Modes:
    Compare:  aep-compare file1.aep file2.aep
    Multi:    aep-compare ref.aep v1.aep v2.aep v3.aep
    List:     aep-compare file.aep --list
    Dump:     aep-compare file.aep --dump "LIST:Fold/ftts"
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ..kaitai import Aep

#: Sentinel used in [ByteDifference][] when one chunk is shorter
#: than the other and a byte position doesn't exist.
MISSING_BYTE = -1


# ── Dataclasses ─────────────────────────────────────────────────────────────


@dataclass
class ByteDifference:
    """Represents a single byte difference between two files."""

    path: str
    offset: int
    byte1: int
    byte2: int
    bit_position: int | None = (
        None  # 7 to 0 from left to right, None if multiple bits differ
    )

    def __post_init__(self) -> None:
        """Calculate bit position if only one bit differs."""
        xor = self.byte1 ^ self.byte2
        if xor != 0 and (xor & (xor - 1)) == 0:  # Check if only one bit is set
            self.bit_position = 7 - (xor.bit_length() - 1)

    def format_diff(self) -> str:
        """Format the difference for display."""
        bit_info = f", bit {self.bit_position}" if self.bit_position is not None else ""
        return (
            f"  Offset {self.offset:4d} (0x{self.offset:04X}): "
            f"0x{self.byte1:02X} ({self.byte1:08b}) vs "
            f"0x{self.byte2:02X} ({self.byte2:08b}){bit_info}"
        )


@dataclass
class ChunkDifference:
    """Represents all differences within a specific chunk/element."""

    path: str
    byte_diffs: list[ByteDifference]
    size1: int
    size2: int

    def has_size_difference(self) -> bool:
        """Check if the chunks have different sizes."""
        return self.size1 != self.size2


@dataclass
class MultiFileDifference:
    """A byte offset where files differ, with values from all files."""

    path: str
    offset: int
    values: list[int]
    """Byte value per file. `-1` if the chunk is missing in that file."""
    bit_position: int | None = None

    def __post_init__(self) -> None:
        """Calculate bit position if exactly two distinct non-missing values
        differ by one bit."""
        distinct = {v for v in self.values if v != MISSING_BYTE}
        if len(distinct) == 2:
            a, b = sorted(distinct)
            xor = a ^ b
            if xor != 0 and (xor & (xor - 1)) == 0:
                self.bit_position = 7 - (xor.bit_length() - 1)


@dataclass
class MultiChunkDifference:
    """All differences within a chunk across multiple files."""

    path: str
    diffs: list[MultiFileDifference]
    sizes: list[int] = field(default_factory=list)
    """Chunk size per file. `0` if missing."""


# ── Binary comparison ───────────────────────────────────────────────────────


def compare_binary_data(
    data1: bytes, data2: bytes, path: str
) -> Iterator[ByteDifference]:
    """Compare two byte sequences and yield differences."""
    min_len = min(len(data1), len(data2))

    # Compare common bytes
    for i in range(min_len):
        if data1[i] != data2[i]:
            yield ByteDifference(path=path, offset=i, byte1=data1[i], byte2=data2[i])

    # Report extra bytes in longer sequence
    if len(data1) > min_len:
        for i in range(min_len, len(data1)):
            yield ByteDifference(
                path=path,
                offset=i,
                byte1=data1[i],
                byte2=MISSING_BYTE,  # byte doesn't exist in file 2
            )
    elif len(data2) > min_len:
        for i in range(min_len, len(data2)):
            yield ByteDifference(
                path=path,
                offset=i,
                byte1=MISSING_BYTE,
                byte2=data2[i],  # byte doesn't exist in file 1
            )


# ── AEP chunk extraction ───────────────────────────────────────────────────


def parse_aep_chunks(file_path: Path) -> dict[str, bytes]:
    """
    Parse an AEP file using Kaitai and extract leaf chunk data with paths.

    Returns a dict mapping chunk paths to their raw binary data.
    Only leaf chunks (non-LIST) are included.
    """
    with Aep.from_file(str(file_path)) as aep:
        aep._read()
        result: dict[str, bytes] = {}
        _extract_chunks_recursive(aep.root.body.chunks, "", result)
        return result


def _get_chunk_identifier(chunk: Any) -> str:
    """Get a descriptive identifier for a chunk."""
    chunk_type = str(chunk.chunk_type)

    # For LIST chunks, include the list_type
    if chunk_type == "LIST" and hasattr(chunk.body, "list_type"):
        return f"LIST:{chunk.body.list_type}"

    return chunk_type


def _build_chunk_path(
    parent_path: str,
    identifier: str,
    counters: dict[str, int],
) -> str:
    """Build a chunk path with duplicate indexing.

    Args:
        parent_path: Parent chunk path prefix.
        identifier: Chunk identifier (e.g. `ldta`, `LIST:Fold`).
        counters: Mutable counter dict tracking duplicates at this level.

    Returns:
        Full chunk path string.
    """
    counter_key = parent_path + "/" + identifier if parent_path else identifier

    if counter_key not in counters:
        counters[counter_key] = 0
    else:
        counters[counter_key] += 1

    if counters[counter_key] > 0:
        return (
            f"{parent_path}/{identifier}[{counters[counter_key]}]"
            if parent_path
            else f"{identifier}[{counters[counter_key]}]"
        )
    return f"{parent_path}/{identifier}" if parent_path else identifier


def _extract_chunks_recursive(
    chunks: list[Any],
    parent_path: str,
    result: dict[str, bytes],
    counters: dict[str, int] | None = None,
) -> None:
    """Recursively extract leaf chunk data with paths.

    Only stores raw data for non-LIST (leaf) chunks.  LIST chunks are
    traversed but their aggregate raw data is **not** stored, so diff
    output only appears at the deepest chunk containing the difference.
    """
    if counters is None:
        counters = {}

    for chunk in chunks:
        identifier = _get_chunk_identifier(chunk)
        current_path = _build_chunk_path(parent_path, identifier, counters)

        # Recurse into LIST chunks without storing their raw data
        if chunk.chunk_type == "LIST":
            if hasattr(chunk.body, "chunks") and chunk.body.chunks:
                child_counters: dict[str, int] = {}
                _extract_chunks_recursive(
                    chunk.body.chunks, current_path, result, child_counters
                )
            # Skip LIST chunks entirely (even empty ones)
        else:
            # Only store raw data for leaf chunks
            try:
                raw_data = chunk._raw_body
                if raw_data:
                    result[current_path] = raw_data
            except (AttributeError, TypeError):
                pass


# ── Comparison helpers ──────────────────────────────────────────────────────


def _compare_chunk_dicts(
    data1: dict[str, bytes], data2: dict[str, bytes]
) -> tuple[list[ChunkDifference], list[str], list[str]]:
    """Compare two chunk dictionaries and return differences.

    Args:
        data1: Chunk path to bytes mapping from file 1.
        data2: Chunk path to bytes mapping from file 2.

    Returns:
        Tuple of (differences, paths only in data1, paths only in data2).
    """
    paths1 = set(data1.keys())
    paths2 = set(data2.keys())

    only_in_1 = sorted(paths1 - paths2)
    only_in_2 = sorted(paths2 - paths1)
    common_paths = sorted(paths1 & paths2)

    differences: list[ChunkDifference] = []
    for path in common_paths:
        bytes1 = data1[path]
        bytes2 = data2[path]
        byte_diffs = list(compare_binary_data(bytes1, bytes2, path))

        if byte_diffs or len(bytes1) != len(bytes2):
            differences.append(
                ChunkDifference(
                    path=path,
                    byte_diffs=byte_diffs,
                    size1=len(bytes1),
                    size2=len(bytes2),
                )
            )

    return differences, only_in_1, only_in_2


# ── List chunks ─────────────────────────────────────────────────────────────


def _walk_chunks_tree(
    chunks: list[Any],
    parent_path: str = "",
    depth: int = 0,
) -> Iterator[tuple[str, str, int, int, bool]]:
    """Walk chunk tree yielding metadata for each node.

    Args:
        chunks: List of Kaitai chunk objects.
        parent_path: Parent chunk path prefix.
        depth: Current nesting depth.

    Yields:
        Tuples of (full_path, identifier, raw_data_size, depth, is_list).
    """
    counters: dict[str, int] = {}

    for chunk in chunks:
        identifier = _get_chunk_identifier(chunk)
        current_path = _build_chunk_path(parent_path, identifier, counters)

        size = 0
        try:
            raw = chunk._raw_body
            if raw:
                size = len(raw)
        except (AttributeError, TypeError):
            pass

        is_list = (
            chunk.chunk_type == "LIST"
            and hasattr(chunk.body, "chunks")
            and chunk.body.chunks is not None
        )
        yield current_path, identifier, size, depth, is_list

        if is_list:
            yield from _walk_chunks_tree(chunk.body.chunks, current_path, depth + 1)


def list_aep_chunks(file_path: Path) -> None:
    """Print a tree of all chunk paths and sizes in an AEP file.

    Args:
        file_path: Path to the AEP file.
    """
    aep = Aep.from_file(str(file_path))
    aep._read()
    print(f"\nChunk tree: {file_path.name}\n")

    for _path, identifier, size, depth, is_list in _walk_chunks_tree(aep.root.body.chunks):
        indent = "  " * depth
        if is_list:
            print(f"{indent}{identifier}/")
        else:
            print(f"{indent}{identifier} ({size}B)")


# ── Dump chunk ──────────────────────────────────────────────────────────────


def _format_hex_dump(data: bytes, bytes_per_line: int = 16) -> str:
    """Format binary data as a hex dump with ASCII representation.

    Args:
        data: Raw bytes to format.
        bytes_per_line: Number of bytes per output line.

    Returns:
        Multi-line hex dump string.
    """
    lines: list[str] = []
    mid = bytes_per_line // 2

    for i in range(0, len(data), bytes_per_line):
        chunk = data[i : i + bytes_per_line]

        # Hex part with midpoint gap
        left_bytes = chunk[:mid]
        right_bytes = chunk[mid:]
        left = " ".join(f"{b:02X}" for b in left_bytes)
        right = " ".join(f"{b:02X}" for b in right_bytes)

        if right:
            hex_str = f"{left}  {right}"
        else:
            hex_str = left

        # Pad to fixed width: "XX XX XX XX XX XX XX XX  XX XX XX XX XX XX XX XX"
        # = (mid*3-1) + 2 + (mid*3-1) when both halves are full
        full_width = (mid * 3 - 1) + 2 + (mid * 3 - 1)
        hex_str = hex_str.ljust(full_width)

        # ASCII part
        ascii_str = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in chunk)

        lines.append(f"{i:04X}: {hex_str}  {ascii_str}")

    return "\n".join(lines)


def dump_aep_chunk(file_path: Path, chunk_path: str) -> None:
    """Hex-dump a specific chunk from an AEP file.

    If the path does not match exactly, a partial (substring) match is
    attempted.  Prints available paths on failure.

    Args:
        file_path: Path to the AEP file.
        chunk_path: Full or partial chunk path (e.g. `LIST:Fold/ftts`).
    """
    chunks = parse_aep_chunks(file_path)

    if chunk_path not in chunks:
        matches = [p for p in sorted(chunks) if chunk_path in p]
        if not matches:
            print(f"Chunk path not found: {chunk_path}", file=sys.stderr)
            print("\nAvailable leaf chunk paths:", file=sys.stderr)
            for p in sorted(chunks):
                print(f"  {p} ({len(chunks[p])}B)", file=sys.stderr)
            return
        if len(matches) == 1:
            chunk_path = matches[0]
        else:
            print(
                f"Ambiguous chunk path '{chunk_path}'. Matches:",
                file=sys.stderr,
            )
            for m in matches:
                print(f"  {m} ({len(chunks[m])}B)", file=sys.stderr)
            return

    data = chunks[chunk_path]
    print(f"\n[{chunk_path}] ({len(data)} bytes)\n")
    print(_format_hex_dump(data))


# ── Multi-file comparison ──────────────────────────────────────────────────


def compare_multi_aep_files(
    files: list[Path],
) -> tuple[
    list[MultiChunkDifference],
    list[tuple[str, list[int]]],
    list[dict[str, bytes]],
]:
    """Compare multiple AEP files and return per-chunk differences.

    The first file is treated as the reference.

    Args:
        files: List of AEP file paths (first = reference).

    Returns:
        Tuple of (chunk differences, missing chunk info, parsed data per file).
    """
    all_data = [parse_aep_chunks(f) for f in files]
    all_paths: set[str] = set()
    for d in all_data:
        all_paths.update(d.keys())

    differences: list[MultiChunkDifference] = []
    missing_chunks: list[tuple[str, list[int]]] = []

    for path in sorted(all_paths):
        present = [i for i, d in enumerate(all_data) if path in d]
        if len(present) < len(files):
            missing_chunks.append((path, present))
            if len(present) < 2:
                continue

        data_list = [all_data[i].get(path, b"") for i in range(len(files))]
        sizes = [len(d) for d in data_list]
        max_len = max(sizes)

        chunk_diffs: list[MultiFileDifference] = []
        for offset in range(max_len):
            values: list[int] = []
            for i in range(len(files)):
                if offset < len(data_list[i]):
                    values.append(data_list[i][offset])
                else:
                    values.append(MISSING_BYTE)

            non_missing = [v for v in values if v != MISSING_BYTE]
            if len(set(non_missing)) > 1:
                chunk_diffs.append(
                    MultiFileDifference(path=path, offset=offset, values=values)
                )

        if chunk_diffs:
            differences.append(
                MultiChunkDifference(path=path, diffs=chunk_diffs, sizes=sizes)
            )

    return differences, missing_chunks, all_data


# ── Output formatting ──────────────────────────────────────────────────────


def _format_context_line(label: str, data: bytes, offset: int, context: int) -> str:
    """Format a context line showing bytes around a diff offset.

    Args:
        label: Label for this line (e.g. `File 1`).
        data: Full chunk data.
        offset: The diff offset to highlight.
        context: Number of bytes before/after to show.

    Returns:
        Formatted context string with the diff byte in brackets.
    """
    start = max(0, offset - context)
    end = min(len(data), offset + context + 1)
    parts: list[str] = []
    for j in range(start, end):
        if j == offset:
            parts.append(f"[{data[j]:02X}]")
        else:
            parts.append(f" {data[j]:02X} ")
    return f"    {label}: " + "".join(parts)


def print_results(
    file1: Path,
    file2: Path,
    differences: list[ChunkDifference],
    only_in_file1: list[str],
    only_in_file2: list[str],
    context: int = 0,
    data1: dict[str, bytes] | None = None,
    data2: dict[str, bytes] | None = None,
) -> None:
    """Print comparison results to stdout.

    Args:
        file1: First file path.
        file2: Second file path.
        differences: Chunk differences.
        only_in_file1: Paths only in file 1.
        only_in_file2: Paths only in file 2.
        context: Number of surrounding bytes to show around diffs.
        data1: Parsed chunk data for file 1 (for context display).
        data2: Parsed chunk data for file 2 (for context display).
    """
    print(f"\n{'=' * 80}")
    print("Comparing:")
    print(f"  File 1: {file1}")
    print(f"  File 2: {file2}")
    print(f"{'=' * 80}\n")

    if not differences and not only_in_file1 and not only_in_file2:
        print("No differences found!")
        return

    # Print chunks only in file1
    if only_in_file1:
        print(f"\n{'─' * 40}")
        print(f"Chunks only in File 1 ({len(only_in_file1)}):")
        print(f"{'─' * 40}")
        for path in only_in_file1:
            print(f"  {path}")

    # Print chunks only in file2
    if only_in_file2:
        print(f"\n{'─' * 40}")
        print(f"Chunks only in File 2 ({len(only_in_file2)}):")
        print(f"{'─' * 40}")
        for path in only_in_file2:
            print(f"  {path}")

    # Print byte differences
    if differences:
        print(f"\n{'─' * 40}")
        print(f"Byte differences ({len(differences)} chunks):")
        print(f"{'─' * 40}")

        for diff in differences:
            print(f"\n[{diff.path}]")
            if diff.has_size_difference():
                print(f"  Size: {diff.size1} bytes vs {diff.size2} bytes")

            for byte_diff in diff.byte_diffs:
                if byte_diff.byte1 == MISSING_BYTE:
                    print(
                        f"  Offset {byte_diff.offset:4d} "
                        f"(0x{byte_diff.offset:04X}): "
                        f"<missing> vs 0x{byte_diff.byte2:02X}"
                    )
                elif byte_diff.byte2 == MISSING_BYTE:
                    print(
                        f"  Offset {byte_diff.offset:4d} "
                        f"(0x{byte_diff.offset:04X}): "
                        f"0x{byte_diff.byte1:02X} vs <missing>"
                    )
                else:
                    print(byte_diff.format_diff())

                # Context display
                if context > 0 and data1 is not None and data2 is not None:
                    d1 = data1.get(diff.path, b"")
                    d2 = data2.get(diff.path, b"")
                    if d1:
                        print(
                            _format_context_line(
                                "File 1", d1, byte_diff.offset, context
                            )
                        )
                    if d2:
                        print(
                            _format_context_line(
                                "File 2", d2, byte_diff.offset, context
                            )
                        )

    # Summary
    total_byte_diffs = sum(len(d.byte_diffs) for d in differences)
    print(f"\n{'=' * 80}")
    print("Summary:")
    print(f"  Chunks with differences: {len(differences)}")
    print(f"  Total byte differences: {total_byte_diffs}")
    print(f"  Chunks only in File 1: {len(only_in_file1)}")
    print(f"  Chunks only in File 2: {len(only_in_file2)}")
    print(f"{'=' * 80}\n")


def print_multi_results(
    files: list[Path],
    differences: list[MultiChunkDifference],
    missing_chunks: list[tuple[str, list[int]]],
    context: int = 0,
    all_data: list[dict[str, bytes]] | None = None,
) -> None:
    """Print multi-file comparison results.

    Args:
        files: List of file paths (first = reference).
        differences: Per-chunk differences.
        missing_chunks: Chunks not present in all files.
        context: Number of surrounding bytes to show.
        all_data: Pre-parsed chunk data per file (for context display).
    """
    # Header
    print(f"\n{'=' * 80}")
    print(f"Comparing {len(files)} files:")
    for i, f in enumerate(files):
        label = "ref" if i == 0 else str(i)
        print(f"  [{label}] {f.name}")
    print(f"{'=' * 80}\n")

    if not differences and not missing_chunks:
        print("No differences found!")
        return

    # Chunks not in all files
    if missing_chunks:
        print(f"{'─' * 40}")
        print(f"Chunks not in all files ({len(missing_chunks)}):")
        print(f"{'─' * 40}")
        for path, present_in in missing_chunks:
            labels = [("ref" if i == 0 else str(i)) for i in present_in]
            print(f"  {path}  (in: {', '.join(labels)})")

    # Byte differences
    if differences:
        print(f"\n{'─' * 40}")
        print(f"Byte differences ({len(differences)} chunks):")
        print(f"{'─' * 40}")

        for chunk_diff in differences:
            print(f"\n[{chunk_diff.path}]")

            unique_sizes = set(chunk_diff.sizes)
            if len(unique_sizes) > 1:
                size_parts = [
                    f"{'ref' if i == 0 else str(i)}={s}"
                    for i, s in enumerate(chunk_diff.sizes)
                ]
                print(f"  Size: {', '.join(size_parts)}")

            for diff in chunk_diff.diffs:
                bit_info = (
                    f", bit {diff.bit_position}"
                    if diff.bit_position is not None
                    else ""
                )
                value_parts: list[str] = []
                for v in diff.values:
                    if v == MISSING_BYTE:
                        value_parts.append("    --    ")
                    else:
                        value_parts.append(f"0x{v:02X} ({v:08b})")
                print(
                    f"  Offset {diff.offset:4d} "
                    f"(0x{diff.offset:04X}): "
                    f"{' | '.join(value_parts)}{bit_info}"
                )

                # Context display
                if context > 0 and all_data:
                    for i in range(len(files)):
                        label = "ref" if i == 0 else f"[{i}]"
                        data = all_data[i].get(chunk_diff.path, b"")
                        if not data:
                            continue
                        print(_format_context_line(label, data, diff.offset, context))

    # Summary
    total_diffs = sum(len(cd.diffs) for cd in differences)
    print(f"\n{'=' * 80}")
    print("Summary:")
    print(f"  Files compared: {len(files)}")
    print(f"  Chunks with differences: {len(differences)}")
    print(f"  Total byte differences: {total_diffs}")
    print(f"  Chunks not in all files: {len(missing_chunks)}")
    print(f"{'=' * 80}\n")


def to_json_output(
    file1: Path,
    file2: Path,
    differences: list[ChunkDifference],
    only_in_file1: list[str],
    only_in_file2: list[str],
) -> dict[str, Any]:
    """Convert comparison results to a JSON-serializable dict."""
    return {
        "file1": str(file1),
        "file2": str(file2),
        "chunks_with_differences": [
            {
                "path": diff.path,
                "size1": diff.size1,
                "size2": diff.size2,
                "byte_differences": [
                    {
                        "offset": bd.offset,
                        "offset_hex": f"0x{bd.offset:04X}",
                        "byte1": bd.byte1 if bd.byte1 != MISSING_BYTE else None,
                        "byte1_hex": f"0x{bd.byte1:02X}"
                        if bd.byte1 != MISSING_BYTE
                        else None,
                        "byte1_binary": f"{bd.byte1:08b}"
                        if bd.byte1 != MISSING_BYTE
                        else None,
                        "byte2": bd.byte2 if bd.byte2 != MISSING_BYTE else None,
                        "byte2_hex": f"0x{bd.byte2:02X}"
                        if bd.byte2 != MISSING_BYTE
                        else None,
                        "byte2_binary": f"{bd.byte2:08b}"
                        if bd.byte2 != MISSING_BYTE
                        else None,
                        "bit_position": bd.bit_position,
                    }
                    for bd in diff.byte_diffs
                ],
            }
            for diff in differences
        ],
        "only_in_file1": only_in_file1,
        "only_in_file2": only_in_file2,
        "summary": {
            "chunks_with_differences": len(differences),
            "total_byte_differences": sum(len(d.byte_diffs) for d in differences),
            "only_in_file1": len(only_in_file1),
            "only_in_file2": len(only_in_file2),
        },
    }


def filter_differences(
    differences: list[ChunkDifference],
    only_in_file1: list[str],
    only_in_file2: list[str],
    filter_pattern: str,
) -> tuple[list[ChunkDifference], list[str], list[str]]:
    """Filter results to only include paths matching the pattern."""
    pattern_lower = filter_pattern.lower()
    filtered_diffs = [d for d in differences if pattern_lower in d.path.lower()]
    filtered_only1 = [p for p in only_in_file1 if pattern_lower in p.lower()]
    filtered_only2 = [p for p in only_in_file2 if pattern_lower in p.lower()]
    return filtered_diffs, filtered_only1, filtered_only2


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    """CLI entry point for aep-compare command."""
    parser = argparse.ArgumentParser(
        prog="aep-compare",
        description=(
            "Compare After Effects project files, list chunks, "
            "or dump specific chunk data"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s file1.aep file2.aep
    %(prog)s ref.aep v1.aep v2.aep v3.aep   (multi-file)
    %(prog)s file.aep --list                  (chunk tree)
    %(prog)s file.aep --dump "LIST:Fold/ftts" (hex dump)
    %(prog)s file1.aep file2.aep --context 4
    %(prog)s file1.aep file2.aep --json
    %(prog)s file1.aep file2.aep --filter ldta

Output shows for each different byte:
    - The chunk path (hierarchy of elements/chunks)
    - Byte offset (decimal and hex)
    - Byte values (hex and binary)
    - Bit position (7-0) if only one bit differs
        """,
    )
    parser.add_argument(
        "files",
        type=Path,
        nargs="+",
        help="AEP files. One file for --list/--dump, two or more for comparison",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help=(
            "Filter results to only show chunks matching "
            "this pattern (case-insensitive)"
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all chunk paths and sizes from a single file",
    )
    parser.add_argument(
        "--dump",
        type=str,
        default=None,
        metavar="PATH",
        help='Hex-dump a specific chunk path (e.g. "LIST:Fold/ftts")',
    )
    parser.add_argument(
        "--context",
        type=int,
        default=0,
        metavar="N",
        help="Show N surrounding bytes around each difference",
    )

    args = parser.parse_args()
    files: list[Path] = args.files

    # Validate files exist
    for f in files:
        if not f.exists():
            print(f"Error: File not found: {f}", file=sys.stderr)
            return 1

    # ── Single-file modes ──────────────────────────────────────────────

    if args.list:
        if len(files) != 1:
            print(
                "Error: --list requires exactly one file",
                file=sys.stderr,
            )
            return 1
        list_aep_chunks(files[0])
        return 0

    if args.dump is not None:
        if len(files) != 1:
            print(
                "Error: --dump requires exactly one file",
                file=sys.stderr,
            )
            return 1
        dump_aep_chunk(files[0], args.dump)
        return 0

    # ── Comparison mode ────────────────────────────────────────────────

    if len(files) < 2:
        print(
            "Error: Need at least two files for comparison",
            file=sys.stderr,
        )
        return 1

    # ── Multi-file comparison (3+ AEP files) ──────────────────────

    if len(files) > 2:
        try:
            multi_diffs, missing, all_data = compare_multi_aep_files(files)
        except Exception as e:
            print(f"Error comparing files: {e}", file=sys.stderr)
            traceback.print_exc()
            return 1

        if args.filter:
            pattern = args.filter.lower()
            multi_diffs = [d for d in multi_diffs if pattern in d.path.lower()]
            missing = [(p, idxs) for p, idxs in missing if pattern in p.lower()]

        print_multi_results(
            files,
            multi_diffs,
            missing,
            context=args.context,
            all_data=all_data,
        )
        return 0 if not multi_diffs and not missing else 1

    # ── Two-file comparison ────────────────────────────────────────────

    file1, file2 = files[0], files[1]

    try:
        # Parse once and reuse for both comparison and context
        data1 = parse_aep_chunks(file1)
        data2 = parse_aep_chunks(file2)
        diffs, only1, only2 = _compare_chunk_dicts(data1, data2)
        ctx1: dict[str, bytes] | None = data1 if args.context > 0 else None
        ctx2: dict[str, bytes] | None = data2 if args.context > 0 else None
    except Exception as e:
        print(f"Error comparing files: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1

    # Apply filter
    if args.filter:
        diffs, only1, only2 = filter_differences(diffs, only1, only2, args.filter)

    # Output results
    if args.json:
        output = to_json_output(file1, file2, diffs, only1, only2)
        print(json.dumps(output, indent=2))
    else:
        print_results(
            file1,
            file2,
            diffs,
            only1,
            only2,
            context=args.context,
            data1=ctx1,
            data2=ctx2,
        )

    return 0 if not diffs and not only1 and not only2 else 1


if __name__ == "__main__":
    sys.exit(main())
