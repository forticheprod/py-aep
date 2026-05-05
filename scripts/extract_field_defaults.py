#!/usr/bin/env python3
"""Extract field value statistics from AEP files for default analysis.

Parses AEP files, walks all chunks recursively, and for each
(ChunkClass, field_name) pair reports observed values, mode, current
default, and whether the default should change.

Usage::

    python scripts/extract_field_defaults.py samples/versions/ae2025/complete.aep
    python scripts/extract_field_defaults.py samples/versions/ae2025/complete.aep samples/unused/debug/*.aep
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path
from typing import Any

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from attrs import NOTHING

# Force all chunk registrations
import py_aep.binary.composition_chunks  # noqa: F401
import py_aep.binary.footage_chunks  # noqa: F401
import py_aep.binary.item_chunks  # noqa: F401
import py_aep.binary.layer_chunks  # noqa: F401
import py_aep.binary.ldat_chunks  # noqa: F401
import py_aep.binary.misc_chunks  # noqa: F401
import py_aep.binary.property_chunks  # noqa: F401
import py_aep.binary.render_chunks  # noqa: F401
import py_aep.binary.scalar_chunks  # noqa: F401
from py_aep.binary.bitfield import BitField
from py_aep.binary.chunk import read_aep
from py_aep.binary.fmt_field import FmtItem, _struct_info


def walk_chunks(chunk: Any) -> Any:
    """Yield every chunk in the tree."""
    yield chunk
    if hasattr(chunk, "chunks") and isinstance(chunk.chunks, list):
        for child in chunk.chunks:
            yield from walk_chunks(child)


def get_bitfields(cls: type) -> dict[str, list[tuple[str, BitField]]]:
    """Map raw-byte field names to their BitField descriptors."""
    mapping: dict[str, list[tuple[str, BitField]]] = {}
    for klass in cls.__mro__:
        for name, val in vars(klass).items():
            if isinstance(val, BitField):
                mapping.setdefault(val.byte_field, []).append((name, val))
    return mapping


def get_default(fld: Any) -> Any:
    """Extract the current default from an attrs field."""
    d = fld.default
    if hasattr(d, "factory"):
        return f"Factory({d.factory.__name__})"
    if d is NOTHING:
        return "<NOTHING>"
    return d


def fmt_char(fld: Any) -> str:
    """Get the struct format character from field metadata."""
    return fld.metadata.get("fmt", "?")


def display_val(val: Any) -> str:
    """Format a value for display."""
    if isinstance(val, bytes):
        if len(val) <= 8:
            return val.hex()
        return val[:8].hex() + f"...({len(val)}B)"
    if isinstance(val, float):
        return f"{val:.6g}"
    return repr(val)


def collect_from_object(
    obj: Any,
    stats: dict[str, dict[str, list[Any]]],
    bf_stats: dict[str, dict[tuple[str, str], collections.Counter]],
) -> None:
    """Collect fmt_field values from a single chunk or FmtItem."""
    cls = type(obj)
    info = _struct_info(cls)
    if info is None:
        return
    _, data_fields, _, _, _, _, items_info, _ = info
    bf_map = get_bitfields(cls)
    cls_name = cls.__name__

    for fld in data_fields:
        val = getattr(obj, fld.name)
        stats[cls_name][fld.name].append(val)

        if fld.name in bf_map:
            raw = val if isinstance(val, int) else 0
            for bit_name, bf in bf_map[fld.name]:
                bf_stats[cls_name][(fld.name, bit_name)][bool(raw & bf.mask)] += 1

    # Recurse into items_field lists
    if items_info is not None:
        items_name, item_cls, item_size = items_info
        items_list = getattr(obj, items_name, [])
        for item in items_list:
            if isinstance(item, FmtItem):
                collect_from_object(item, stats, bf_stats)


def collect(
    aep_paths: list[Path],
) -> tuple[
    dict[str, dict[str, list[Any]]],
    dict[str, dict[tuple[str, str], collections.Counter]],
]:
    """Collect all field values from all chunks in all files."""
    stats: dict[str, dict[str, list[Any]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    bf_stats: dict[str, dict[tuple[str, str], collections.Counter]] = (
        collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    )

    for path in aep_paths:
        print(f"Parsing {path.name} ...", file=sys.stderr)
        with open(path, "rb") as f:
            rifx, _ = read_aep(f)
        for chunk in walk_chunks(rifx):
            collect_from_object(chunk, stats, bf_stats)

    return stats, bf_stats


def get_field_meta(cls_name: str, field_name: str) -> tuple[str, Any]:
    """Look up format char and current default for a class+field."""
    # Find the class
    for mod in [
        py_aep.binary.scalar_chunks,
        py_aep.binary.property_chunks,
        py_aep.binary.item_chunks,
        py_aep.binary.composition_chunks,
        py_aep.binary.layer_chunks,
        py_aep.binary.ldat_chunks,
        py_aep.binary.footage_chunks,
        py_aep.binary.misc_chunks,
        py_aep.binary.render_chunks,
    ]:
        cls = getattr(mod, cls_name, None)
        if cls is not None:
            break
    else:
        return "?", "<unknown>"

    info = _struct_info(cls)
    if info is None:
        return "?", "<unknown>"
    _, data_fields, _, _, _, _, _, _ = info
    for fld in data_fields:
        if fld.name == field_name:
            return fmt_char(fld), get_default(fld)
    return "?", "<unknown>"


def classify(
    mode_val: Any, current_default: Any, unique_count: int, total: int
) -> str:
    """Classify whether the default needs changing."""
    # Type mismatch: bytes field with int default
    if isinstance(mode_val, bytes) and isinstance(current_default, int):
        return "TYPE_MISMATCH"
    # Check if mode matches default
    if mode_val == current_default:
        return "OK"
    if unique_count == 1:
        return "CONSTANT"
    if unique_count <= 5:
        return "FEW_VALUES"
    return "VARIES"


def report(
    stats: dict[str, dict[str, list[Any]]],
    bf_stats: dict[str, dict[tuple[str, str], collections.Counter]],
) -> None:
    """Print the analysis report."""
    for cls_name in sorted(stats):
        fields = stats[cls_name]
        first_field = next(iter(fields.values()))
        n_instances = len(first_field)
        n_fields = len(fields)
        print(f"\n{'=' * 72}")
        print(f"  {cls_name} ({n_fields} fields, {n_instances} instances)")
        print(f"{'=' * 72}")

        for field_name, values in fields.items():
            fc, cur_default = get_field_meta(cls_name, field_name)

            # Compute unique set (capped for display)
            counter: collections.Counter[Any] = collections.Counter()
            for v in values:
                key = v.hex() if isinstance(v, bytes) else v
                counter[key] += 1
            mode_key, mode_count = counter.most_common(1)[0]
            unique_count = len(counter)

            # Get raw mode value for classification
            mode_raw = values[0]  # fallback
            for v in values:
                k = v.hex() if isinstance(v, bytes) else v
                if k == mode_key:
                    mode_raw = v
                    break

            status = classify(mode_raw, cur_default, unique_count, len(values))

            # Format unique values for display
            if unique_count <= 8:
                unique_str = "{" + ", ".join(display_val(v) if not isinstance(v, str) else v for v in sorted(counter.keys(), key=str)) + "}"
            else:
                unique_str = f"({unique_count} unique)"

            cur_def_str = display_val(cur_default)
            mode_str = display_val(mode_raw) if not isinstance(mode_key, str) else mode_key

            marker = ""
            if status != "OK":
                marker = f" *** {status}"

            print(
                f"  {field_name:30s} {fc:5s} | n={len(values):5d} "
                f"| {unique_str:30s} | mode={mode_str:20s} "
                f"| default={cur_def_str:20s} | {status}{marker}"
            )

            # BitField breakdown
            for (raw_field, bit_name), bit_counter in bf_stats[cls_name].items():
                if raw_field == field_name:
                    print(f"    bit {bit_name}: {dict(bit_counter)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract field value statistics from AEP files."
    )
    parser.add_argument("files", nargs="+", type=Path, help="AEP files to analyze")
    args = parser.parse_args()

    for f in args.files:
        if not f.exists():
            print(f"ERROR: {f} does not exist", file=sys.stderr)
            sys.exit(1)

    s, bs = collect(args.files)
    report(s, bs)


if __name__ == "__main__":
    main()
