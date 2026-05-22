"""
AEP File Inspection Tool.

Inspect After Effects project files (.aep) structure:
- Item summary with children types and counts
- Full chunk tree visualization
- Detailed item children inspection
- Chunk path listing with sizes
- Hex dump of specific chunks

Modes:
    Default:  aep-inspect file.aep              (item summary)
    Tree:     aep-inspect file.aep --tree        (full chunk tree)
    Item:     aep-inspect file.aep --item 6      (inspect Item[6])
    List:     aep-inspect file.aep --list        (chunk paths + sizes)
    Dump:     aep-inspect file.aep --dump "path" (hex dump)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ..binary.chunk import ListChunk, read_aep
from ..binary.utils import filter_by_list_type
from ._chunk_helpers import (
    chunk_label,
    extract_leaf_chunks,
    format_hex_dump,
    walk_chunks,
)

if TYPE_CHECKING:
    from ..binary.chunk import Chunk


# ── Tree display ────────────────────────────────────────────────────────────


def _chunk_detail(chunk: Chunk) -> str:
    """Return size or value detail for a leaf chunk."""
    val = getattr(chunk, "value", None)
    if val is not None:
        v = repr(val)
        if len(v) > 60:
            v = v[:57] + "..."
        return f"value={v}"
    data = getattr(chunk, "data", None)
    if data is not None:
        return f"{len(data)}B"
    return ""


def print_tree(
    chunk: Chunk,
    depth: int = 0,
    max_depth: int = -1,
) -> None:
    """Print a chunk tree with types and sizes.

    Args:
        chunk: Root chunk to print.
        depth: Current depth (for indentation).
        max_depth: Maximum depth to recurse (-1 for unlimited).
    """
    if max_depth >= 0 and depth > max_depth:
        return
    label = chunk_label(chunk)
    if isinstance(chunk, ListChunk):
        n = len(chunk.chunks)
        print(f"{'  ' * depth}{label} ({n} children)")
        for c in chunk.chunks:
            print_tree(c, depth + 1, max_depth)
    else:
        detail = _chunk_detail(chunk)
        print(f"{'  ' * depth}{label} ({detail})")


# ── Item inspection ─────────────────────────────────────────────────────────


def _inspect_item(path: Path, index: int) -> int:
    """Show detailed children of a specific Item by 0-based index.

    Args:
        path: Path to the `.aep` file.
        index: 0-based item index within `LIST:Fold`.

    Returns:
        Exit code (0 on success, 1 on error).
    """
    with open(path, "rb") as fp:
        rifx, _ = read_aep(fp)

    fold = None
    for c in rifx.chunks:
        if isinstance(c, ListChunk) and c.list_type == "Fold":
            fold = c
            break
    if fold is None:
        print("ERROR: No LIST:Fold found", file=sys.stderr)
        return 1

    items = filter_by_list_type(chunks=fold.chunks, list_type="Item")
    if index >= len(items):
        print(
            f"ERROR: Item[{index}] out of range (only {len(items)} items)",
            file=sys.stderr,
        )
        return 1

    item = items[index]
    print(f"=== {path.name} Item[{index}] ({len(item.chunks)} children) ===")
    for i, c in enumerate(item.chunks):
        label = chunk_label(c)
        if isinstance(c, ListChunk):
            print(f"  [{i:2d}] {label} ({len(c.chunks)} children)")
            for j, cc in enumerate(c.chunks):
                cl = chunk_label(cc)
                if isinstance(cc, ListChunk):
                    print(f"    [{j:2d}] {cl} ({len(cc.chunks)} children)")
                else:
                    detail = _chunk_detail(cc)
                    print(f"    [{j:2d}] {cl} ({detail})")
        else:
            detail = _chunk_detail(c)
            print(f"  [{i:2d}] {label} ({detail})")
    return 0


# ── Item summary ────────────────────────────────────────────────────────────


def _item_summary(path: Path) -> int:
    """Show item summary with children types for each item in Fold.

    Args:
        path: Path to the `.aep` file.

    Returns:
        Exit code.
    """
    with open(path, "rb") as fp:
        rifx, _ = read_aep(fp)

    fold = None
    for c in rifx.chunks:
        if isinstance(c, ListChunk) and c.list_type == "Fold":
            fold = c
            break
    if fold is None:
        print("No LIST:Fold found", file=sys.stderr)
        return 1

    items = filter_by_list_type(chunks=fold.chunks, list_type="Item")
    print(f"{path.name}: {len(items)} items in Fold")
    for i, item in enumerate(items):
        children = [chunk_label(c) for c in item.chunks]
        print(f"  Item[{i}]: {len(children)} children - {', '.join(children)}")
    return 0


# ── Chunk listing ───────────────────────────────────────────────────────────


def _list_chunks(path: Path) -> int:
    """Print a tree of all chunk paths and sizes in an AEP file.

    Args:
        path: Path to the `.aep` file.

    Returns:
        Exit code.
    """
    with open(path, "rb") as fp:
        rifx, _xmp = read_aep(fp)

    print(f"\nChunk tree: {path.name}\n")
    for _path, identifier, size, depth, is_list in walk_chunks(rifx.chunks):
        indent = "  " * depth
        if is_list:
            print(f"{indent}{identifier}/")
        else:
            print(f"{indent}{identifier} ({size}B)")
    return 0


# ── Hex dump ────────────────────────────────────────────────────────────────


def _dump_chunk(path: Path, chunk_path: str) -> int:
    """Hex-dump a specific chunk from an AEP file.

    If the path does not match exactly, a partial (substring) match is
    attempted. Prints available paths on failure.

    Args:
        path: Path to the `.aep` file.
        chunk_path: Full or partial chunk path (e.g. `LIST:Fold/ftts`).

    Returns:
        Exit code.
    """
    chunks = extract_leaf_chunks(path)

    if chunk_path not in chunks:
        matches = [p for p in sorted(chunks) if chunk_path in p]
        if not matches:
            print(f"Chunk path not found: {chunk_path}", file=sys.stderr)
            print("\nAvailable leaf chunk paths:", file=sys.stderr)
            for p in sorted(chunks):
                print(f"  {p} ({len(chunks[p])}B)", file=sys.stderr)
            return 1
        if len(matches) == 1:
            chunk_path = matches[0]
        else:
            print(
                f"Ambiguous chunk path '{chunk_path}'. Matches:",
                file=sys.stderr,
            )
            for m in matches:
                print(f"  {m} ({len(chunks[m])}B)", file=sys.stderr)
            return 1

    data = chunks[chunk_path]
    print(f"\n[{chunk_path}] ({len(data)} bytes)\n")
    print(format_hex_dump(data))
    return 0


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    """CLI entry point for aep-inspect command."""
    parser = argparse.ArgumentParser(
        prog="aep-inspect",
        description="Inspect After Effects project file (.aep) structure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s file.aep                        (item summary)
    %(prog)s file.aep --tree                 (full chunk tree)
    %(prog)s file.aep --tree --depth 3       (limited depth)
    %(prog)s file.aep --item 6               (inspect Item[6])
    %(prog)s file.aep --list                 (chunk paths + sizes)
    %(prog)s file.aep --dump "LIST:Fold/ftts"(hex dump)
        """,
    )
    parser.add_argument("file", type=Path, help="AEP file to inspect")
    parser.add_argument(
        "--tree",
        action="store_true",
        help="Print full chunk tree",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=-1,
        metavar="N",
        help="Max tree depth (-1 for unlimited, use with --tree)",
    )
    parser.add_argument(
        "--item",
        type=int,
        default=None,
        metavar="N",
        help="Inspect Item[N] (0-based) in LIST:Fold",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all chunk paths and sizes",
    )
    parser.add_argument(
        "--dump",
        type=str,
        default=None,
        metavar="PATH",
        help='Hex-dump a specific chunk (e.g. "LIST:Fold/ftts")',
    )

    args = parser.parse_args()
    path: Path = args.file

    if not path.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        return 1

    if args.tree:
        with open(path, "rb") as fp:
            rifx, _ = read_aep(fp)
        print_tree(rifx, max_depth=args.depth)
        return 0

    if args.item is not None:
        return _inspect_item(path, args.item)

    if args.list:
        return _list_chunks(path)

    if args.dump is not None:
        return _dump_chunk(path, args.dump)

    # Default: item summary
    return _item_summary(path)


if __name__ == "__main__":
    sys.exit(main())
