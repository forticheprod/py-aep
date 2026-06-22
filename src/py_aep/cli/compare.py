"""
AEP File Comparison Tool.

Compares After Effects project files (.aep) and reports differences
at both the byte level and the structural level:
- Byte-level: chunk path, byte position, hex values, bit position
- Structural: child count mismatches between containers

Modes:
    Compare:  aep-compare file1.aep file2.aep
    Multi:    aep-compare ref.aep v1.aep v2.aep v3.aep

For single-file inspection (tree, dump, list), use `aep-inspect`.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ..binary.chunk import ListChunk, read_aep
from ._chunk_helpers import (
    chunk_label,
    extract_leaf_chunks,
    extract_leaf_chunks_typed,
)

if TYPE_CHECKING:
    from typing import Any, Iterator

    from ..binary.chunk import Chunk

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


# ── Float-tolerant comparison ───────────────────────────────────────────────

#: Default tolerances: floats differing by at most this (relative or
#: absolute) are treated as equal. AE and py_aep encode the same coordinate
#: through different float32/float64 rounding, so tiny deltas are noise.
FLOAT_REL_TOL = 1e-4
FLOAT_ABS_TOL = 1e-3


def _floats_close(a: float, b: float) -> bool:
    return abs(a - b) <= max(FLOAT_ABS_TOL, FLOAT_REL_TOL * max(abs(a), abs(b)))


def _chunk_floats(chunk: Any) -> list[float] | None:
    """Return a chunk's coordinate float fields, or None if it has none.

    Covers the float-bearing leaf chunks whose values AE and py_aep may
    encode with slightly different rounding: `cdat` (doubles), `shph`
    (bounding-box f4), and `ldat` shape-point lists (f4 x/y).
    """
    ct = getattr(chunk, "chunk_type", None)
    if ct == "cdat":
        values = list(chunk.values)
        return values or None
    if ct == "shph":
        return [
            chunk.top_left_x,
            chunk.top_left_y,
            chunk.bottom_right_x,
            chunk.bottom_right_y,
        ]
    if ct == "ldat":
        items = chunk.items
        if items and all(hasattr(i, "x") and hasattr(i, "y") for i in items):
            return [v for i in items for v in (i.x, i.y)]
    return None


def _with_floats(chunk: Any, floats: list[float]) -> Any:
    """Return a copy of `chunk` with its coordinate floats replaced."""
    clone = copy.deepcopy(chunk)
    ct = clone.chunk_type
    if ct == "cdat":
        clone.values = list(floats)
    elif ct == "shph":
        (
            clone.top_left_x,
            clone.top_left_y,
            clone.bottom_right_x,
            clone.bottom_right_y,
        ) = floats
    elif ct == "ldat":
        for idx, item in enumerate(clone.items):
            item.x = floats[2 * idx]
            item.y = floats[2 * idx + 1]
    return clone


_FLOAT_TAG_RE = re.compile(r"<float>([^<]*)</float>")


def _gradient_xml_only_float_diff(s1: Any, s2: Any) -> bool:
    """True when two AE `prop.map` XML strings (gradient color data) differ
    ONLY in their `<float>` values within tolerance.

    Gradient colors/offsets are stored as text floats inside a `Utf8`
    chunk, so the numeric tolerance applied to cdat/shph/ldat cannot reach
    them; AE and py_aep round an 8-bit colour to adjacent float32 values.
    """
    if not isinstance(s1, str) or not isinstance(s2, str):
        return False
    if "<prop.map" not in s1 or "<float>" not in s1:
        return False
    f1 = _FLOAT_TAG_RE.findall(s1)
    f2 = _FLOAT_TAG_RE.findall(s2)
    if len(f1) != len(f2):
        return False
    # Everything except the float values must be byte-identical.
    if _FLOAT_TAG_RE.sub("<float/>", s1) != _FLOAT_TAG_RE.sub("<float/>", s2):
        return False
    for a, b in zip(f1, f2):
        # `<float>` content is normally numeric in AE's prop.map output; an
        # empty/non-numeric tag is not a pure float-precision diff (and must
        # not crash the comparison), so treat it as a real difference.
        try:
            fa, fb = float(a), float(b)
        except ValueError:
            return False
        if not _floats_close(fa, fb):
            return False
    return True


def _only_float_diff(c1: Any, c2: Any) -> bool:
    """True when `c1` and `c2` differ ONLY in float coordinates within
    tolerance (so the byte difference is float-precision noise, not a real
    change). Non-float bytes must still match exactly."""
    ct = getattr(c1, "chunk_type", None)
    if ct != getattr(c2, "chunk_type", None):
        return False
    if ct == "Utf8":
        return _gradient_xml_only_float_diff(
            getattr(c1, "value", None), getattr(c2, "value", None)
        )
    f1 = _chunk_floats(c1)
    if f1 is None:
        return False
    f2 = _chunk_floats(c2)
    if f2 is None or len(f1) != len(f2):
        return False
    if not all(_floats_close(a, b) for a, b in zip(f1, f2)):
        return False
    # Rebuild c1 with c2's float values; equal bytes => only the (in-
    # tolerance) floats differed, everything else is byte-identical.
    rebuilt: bytes = _with_floats(c1, f2).tobytes()
    original: bytes = c2.tobytes()
    return rebuilt == original


def _multi_only_float_diff(
    all_typed: list[dict[str, Any]], present: list[int], path: str
) -> bool:
    """True when `path` differs only in float coordinates across every file
    that contains it (so the multi-file diff is float-precision noise). Files
    byte-identical to the reference do not count as a difference."""
    ref = all_typed[present[0]].get(path)
    if ref is None:
        return False
    ref_bytes = ref.tobytes()
    for i in present[1:]:
        other = all_typed[i].get(path)
        if other is None:
            return False
        if other.tobytes() == ref_bytes:
            continue
        if not _only_float_diff(ref, other):
            return False
    return True


# ── AEP chunk extraction ───────────────────────────────────────────────────

#: Alias for backward compatibility with tests.
parse_aep_chunks = extract_leaf_chunks


# ── Comparison helpers ──────────────────────────────────────────────────────


def _compare_chunk_dicts(
    data1: dict[str, bytes],
    data2: dict[str, bytes],
    typed1: dict[str, Chunk] | None = None,
    typed2: dict[str, Chunk] | None = None,
    exact: bool = False,
) -> tuple[list[ChunkDifference], list[str], list[str], list[str]]:
    """Compare two chunk dictionaries and return differences.

    Args:
        data1: Chunk path to bytes mapping from file 1.
        data2: Chunk path to bytes mapping from file 2.
        typed1: Optional decoded chunks for file 1 (enables float-tolerant
            comparison of coordinate fields).
        typed2: Optional decoded chunks for file 2.
        exact: When `True`, disable float tolerance (byte-exact).

    Returns:
        Tuple of (differences, paths only in data1, paths only in data2,
        paths of the float-precision-only differences suppressed).
    """
    paths1 = set(data1.keys())
    paths2 = set(data2.keys())

    only_in_1 = sorted(paths1 - paths2)
    only_in_2 = sorted(paths2 - paths1)
    common_paths = sorted(paths1 & paths2)

    differences: list[ChunkDifference] = []
    suppressed: list[str] = []
    for path in common_paths:
        bytes1 = data1[path]
        bytes2 = data2[path]
        if bytes1 == bytes2:
            continue
        # Suppress float-precision-only differences (same coordinate, just
        # AE-vs-py_aep float rounding) unless an exact comparison was asked.
        if (
            not exact
            and typed1 is not None
            and typed2 is not None
            and path in typed1
            and path in typed2
            and _only_float_diff(typed1[path], typed2[path])
        ):
            suppressed.append(path)
            continue
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

    return differences, only_in_1, only_in_2, suppressed


# ── Structural comparison ───────────────────────────────────────────────────


@dataclass
class StructuralDifference:
    """A structural mismatch between two chunk trees."""

    path: str
    count1: int
    count2: int
    children1: list[str]
    children2: list[str]


def _compare_structure_recursive(
    c1: Chunk,
    c2: Chunk,
    path: str,
    diffs: list[StructuralDifference],
) -> None:
    """Recursively compare two chunk trees structurally."""
    label1 = chunk_label(c1)
    label2 = chunk_label(c2)
    current = f"{path}/{label1}" if path else label1

    if label1 != label2:
        diffs.append(StructuralDifference(current, -1, -1, [label1], [label2]))
        return

    if isinstance(c1, ListChunk) and isinstance(c2, ListChunk):
        ch1 = [chunk_label(c) for c in c1.chunks]
        ch2 = [chunk_label(c) for c in c2.chunks]
        if ch1 != ch2:
            diffs.append(
                StructuralDifference(
                    current,
                    len(ch1),
                    len(ch2),
                    ch1,
                    ch2,
                )
            )
        for i in range(min(len(c1.chunks), len(c2.chunks))):
            _compare_structure_recursive(
                c1.chunks[i],
                c2.chunks[i],
                current,
                diffs,
            )


def compare_structure(
    file1: Path,
    file2: Path,
) -> list[StructuralDifference]:
    """Compare two AEP files structurally.

    Detects child count mismatches, missing chunks (including empty ones
    invisible to byte-level diffing), and ordering differences.

    Args:
        file1: First AEP file path.
        file2: Second AEP file path.

    Returns:
        List of structural differences.
    """
    with open(file1, "rb") as f:
        rifx1, _ = read_aep(f)
    with open(file2, "rb") as f:
        rifx2, _ = read_aep(f)
    diffs: list[StructuralDifference] = []
    _compare_structure_recursive(rifx1, rifx2, "", diffs)
    return diffs


# ── Multi-file comparison ──────────────────────────────────────────────────


def compare_multi_aep_files(
    files: list[Path],
    exact: bool = False,
) -> tuple[
    list[MultiChunkDifference],
    list[tuple[str, list[int]]],
    list[dict[str, bytes]],
    list[str],
]:
    """Compare multiple AEP files and return per-chunk differences.

    The first file is treated as the reference.

    Args:
        files: List of AEP file paths (first = reference).
        exact: When `True`, disable float tolerance (byte-exact); otherwise
            chunks differing only in float-precision coordinates across all
            present files are suppressed, matching two-file mode.

    Returns:
        Tuple of (chunk differences, missing chunk info, parsed data per file,
        paths of the float-precision-only chunk differences suppressed).
    """
    parsed = [extract_leaf_chunks_typed(f) for f in files]
    all_data = [data for data, _ in parsed]
    all_typed = [typed for _, typed in parsed]
    all_paths: set[str] = set()
    for d in all_data:
        all_paths.update(d.keys())

    differences: list[MultiChunkDifference] = []
    missing_chunks: list[tuple[str, list[int]]] = []
    suppressed: list[str] = []

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
            # Suppress float-precision-only differences (matching two-file mode).
            if not exact and _multi_only_float_diff(all_typed, present, path):
                suppressed.append(path)
                continue
            differences.append(
                MultiChunkDifference(path=path, diffs=chunk_diffs, sizes=sizes)
            )

    return differences, missing_chunks, all_data, suppressed


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
    structural_diffs: list[StructuralDifference] | None = None,
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
        structural_diffs: Structural differences between the two files.
    """
    print(f"\n{'=' * 80}")
    print("Comparing:")
    print(f"  File 1: {file1}")
    print(f"  File 2: {file2}")
    print(f"{'=' * 80}\n")

    has_any = differences or only_in_file1 or only_in_file2 or structural_diffs
    if not has_any:
        print("No differences found!")
        return

    # Print structural differences
    if structural_diffs:
        print(f"\n{'─' * 40}")
        print(f"Structural differences ({len(structural_diffs)}):")
        print(f"{'─' * 40}")
        for sd in structural_diffs:
            if sd.count1 == -1:
                print(
                    f"\n[{sd.path}] type mismatch: {sd.children1[0]} vs {sd.children2[0]}"
                )
            else:
                print(f"\n[{sd.path}] child count: {sd.count1} vs {sd.count2}")
                max_len = max(len(sd.children1), len(sd.children2))
                for i in range(max_len):
                    c1 = sd.children1[i] if i < len(sd.children1) else "<missing>"
                    c2 = sd.children2[i] if i < len(sd.children2) else "<missing>"
                    marker = "  " if c1 == c2 else "!!"
                    print(f"  {marker} [{i:2d}] {c1:20s}  vs  {c2}")

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
    if structural_diffs:
        print(f"  Structural differences: {len(structural_diffs)}")
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
    suppressed: int = 0,
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
        "suppressed_float_diffs": suppressed,
        "summary": {
            "chunks_with_differences": len(differences),
            "total_byte_differences": sum(len(d.byte_diffs) for d in differences),
            "only_in_file1": len(only_in_file1),
            "only_in_file2": len(only_in_file2),
            "suppressed_float_diffs": suppressed,
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


def _report_suppressed(suppressed: int, exact: bool) -> None:
    """Note suppressed float-precision-only diffs so they are never silent."""
    if suppressed and not exact:
        plural = "s" if suppressed != 1 else ""
        print(
            f"Note: suppressed {suppressed} float-precision-only chunk "
            f"difference{plural} (use --exact to show them).",
            file=sys.stderr,
        )


def main() -> int:
    """CLI entry point for aep-compare command."""
    parser = argparse.ArgumentParser(
        prog="aep-compare",
        description="Compare After Effects project files (.aep)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s file1.aep file2.aep
    %(prog)s ref.aep v1.aep v2.aep v3.aep   (multi-file)
    %(prog)s file1.aep file2.aep --context 4
    %(prog)s file1.aep file2.aep --json
    %(prog)s file1.aep file2.aep --filter ldta

For single-file inspection, use aep-inspect.

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
        help="Two or more AEP files to compare",
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
        "--context",
        type=int,
        default=0,
        metavar="N",
        help="Show N surrounding bytes around each difference",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Byte-exact comparison; do not tolerate float-precision "
        "differences in cdat/shph/ldat coordinate fields",
    )

    args = parser.parse_args()
    files: list[Path] = args.files

    # Validate files exist
    for f in files:
        if not f.exists():
            print(f"Error: File not found: {f}", file=sys.stderr)
            return 1

    # ── Comparison mode ────────────────────────────────────────────────

    if len(files) < 2:
        print(
            "Error: Need at least two files for comparison",
            file=sys.stderr,
        )
        return 1

    # ── Multi-file comparison (3+ AEP files) ──────────────────────

    if len(files) > 2:
        multi_diffs, missing, all_data, suppressed = compare_multi_aep_files(
            files, exact=args.exact
        )

        if args.filter:
            pattern = args.filter.lower()
            multi_diffs = [d for d in multi_diffs if pattern in d.path.lower()]
            missing = [(p, idxs) for p, idxs in missing if pattern in p.lower()]
            suppressed = [p for p in suppressed if pattern in p.lower()]

        print_multi_results(
            files,
            multi_diffs,
            missing,
            context=args.context,
            all_data=all_data,
        )
        _report_suppressed(len(suppressed), args.exact)
        return 0 if not multi_diffs and not missing else 1

    # ── Two-file comparison ────────────────────────────────────────────

    file1, file2 = files[0], files[1]

    # Parse once and reuse for both comparison and context
    data1, typed1 = extract_leaf_chunks_typed(file1)
    data2, typed2 = extract_leaf_chunks_typed(file2)
    diffs, only1, only2, suppressed = _compare_chunk_dicts(
        data1, data2, typed1, typed2, exact=args.exact
    )
    struct_diffs = compare_structure(file1, file2)
    ctx1: dict[str, bytes] | None = data1 if args.context > 0 else None
    ctx2: dict[str, bytes] | None = data2 if args.context > 0 else None

    # Apply filter
    if args.filter:
        diffs, only1, only2 = filter_differences(diffs, only1, only2, args.filter)
        pattern = args.filter.lower()
        suppressed = [p for p in suppressed if pattern in p.lower()]

    # Output results
    if args.json:
        output = to_json_output(file1, file2, diffs, only1, only2, len(suppressed))
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
            structural_diffs=struct_diffs,
        )
    _report_suppressed(len(suppressed), args.exact)

    return 0 if not diffs and not only1 and not only2 else 1


if __name__ == "__main__":
    sys.exit(main())
