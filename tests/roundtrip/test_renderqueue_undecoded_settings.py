"""A render queue whose settings items py_aep cannot decode parses as empty.

A project saved by AE 13.5 stores the per-item render settings in a layout
other than the 2246-byte item every AE 15 to 26 sample writes, so its items
read as raw `LdatItem`s (issue #260). The rest of the project must still
parse, and the raw items must round-trip.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse
from py_aep.binary.chunk import read_aep, write_aep
from py_aep.binary.utils import find_by_list_type, find_by_type

SAMPLE = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "renderqueue"
    / "frame_rate.aep"
)


def _with_undecoded_settings(tmp_path: Path) -> Path:
    """`frame_rate.aep` with its render-settings header claiming an item
    size py_aep has no layout for, so the items read back as raw bytes."""
    with open(SAMPLE, "rb") as fp:
        rifx, xmp = read_aep(fp)
    lrdr = find_by_list_type(chunks=rifx.chunks, list_type="LRdr")
    settings = find_by_list_type(chunks=lrdr.chunks, list_type="list")
    find_by_type(chunks=settings.chunks, chunk_type="lhd3").item_size = 2182
    out = tmp_path / "undecoded_settings.aep"
    with open(out, "wb") as fp:
        write_aep(fp, rifx, xmp)
    return out


def test_parses_with_an_empty_queue_and_warns(tmp_path: Path) -> None:
    path = _with_undecoded_settings(tmp_path)
    with pytest.warns(UserWarning, match="2182 bytes"):
        project = parse(path).project
    assert project.render_queue.items == []
    assert [comp.name for comp in project.compositions]


def test_the_raw_items_round_trip(tmp_path: Path) -> None:
    path = _with_undecoded_settings(tmp_path)
    with pytest.warns(UserWarning):
        project = parse(path).project
    out = tmp_path / "resaved.aep"
    project.save(out)
    assert out.read_bytes() == path.read_bytes()
