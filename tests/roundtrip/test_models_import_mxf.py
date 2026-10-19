"""MXF footage import versus After Effects' own import of the same files
(samples/models/import/mxf_import.aep, AE 2026 on Windows)."""

from __future__ import annotations

from pathlib import Path

import pytest
from attrs import fields
from helpers import parse_project_fresh

from py_aep import ImportAsType
from py_aep import parse as parse_aep
from py_aep.binary.chunk import Chunk, ListChunk
from py_aep.binary.utils import find_by_list_type, find_by_type
from py_aep.models.import_options import ImportOptions
from py_aep.models.items.footage import FootageItem

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"
BASE = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "folder" / "folder.aep"
)
FIXTURE = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "import"
    / "mxf_import.aep"
)

IMPORTED = [
    "mxf_dnxhr_320x180p25.mxf",
    "mxf_dnxhr_2997_df_tc.mxf",
    "mxf_mpeg2_pal_4x3_tff.mxf",
    "mxf_h264_ntsc_16x9.mxf",
    "mxf_dv_pal_16x9.mxf",
    "mxf_prores422_320x180.mxf",
    "mxf_mpeg2_1440x1080_16x9.mxf",
    "mxf_opatom_pcm_1ch.mxf",
    "mxf_opatom_h264_320x180.mxf",
]

# The source's modification stamp depends on the checkout; the codec bytes
# of the generic opti (offsets 38-41) are the importer's, which AE re-derives
# from the file on open (zero in py_aep, as for every other movie format).
_SKIPPED_SSPC_FIELDS = {"chunk_type", "data", "synthetic", "_source_stamp"}


def _pin_list(item: FootageItem, list_type: str) -> ListChunk:
    pin = find_by_list_type(chunks=item._item_list.chunks, list_type="Pin ")
    return find_by_list_type(chunks=pin.chunks, list_type=list_type)


def _leaf(container: ListChunk, chunk_type: str) -> Chunk:
    return find_by_type(chunks=container.chunks, chunk_type=chunk_type)


@pytest.fixture(scope="module")
def truth() -> dict[str, FootageItem]:
    project = parse_aep(FIXTURE).project
    return {item.name: item for item in project.footages}


@pytest.mark.parametrize("name", IMPORTED)
def test_import_matches_ae_fixture(
    name: str, truth: dict[str, FootageItem], tmp_path: Path
) -> None:
    project = parse_aep(BASE).project
    item = project.import_file(ImportOptions(ASSETS / name))
    assert item.name == name
    out = tmp_path / "mxf.aep"
    project.save(out)
    item = parse_project_fresh(out).footages[-1]  # type: ignore[index]
    ae = truth[name]

    mine, theirs = item.main_source._sspc, ae.main_source._sspc
    for f in fields(type(mine)):
        if f.name in _SKIPPED_SSPC_FIELDS:
            continue
        assert getattr(mine, f.name) == getattr(theirs, f.name), f.name

    opti, ae_opti = item.main_source._opti.data, ae.main_source._opti.data
    assert len(opti) == len(ae_opti) == 58
    assert opti[:38] == ae_opti[:38]
    assert opti[42:] == ae_opti[42:]

    # The start timecode and its drop-frame flag.
    mnfo, ae_mnfo = _pin_list(item, "mnfo"), _pin_list(ae, "mnfo")
    assert _leaf(mnfo, "strt").tobytes() == _leaf(ae_mnfo, "strt").tobytes()
    assert _leaf(mnfo, "drop").tobytes() == _leaf(ae_mnfo, "drop").tobytes()

    assert item.width == ae.width and item.height == ae.height
    assert item.duration == pytest.approx(ae.duration)
    assert item.frame_rate == pytest.approx(ae.frame_rate)
    assert item.pixel_aspect == pytest.approx(ae.pixel_aspect)
    assert item.has_audio == ae.has_audio
    assert (
        item.main_source.field_separation_type == ae.main_source.field_separation_type
    )


def test_refused_coding_raises_and_leaves_project_unchanged() -> None:
    project = parse_aep(BASE).project
    count = len(project.items)
    with pytest.raises(ValueError, match="cannot decode the MXF picture coding"):
        project.import_file(ImportOptions(ASSETS / "mxf_ffv1_320x180.mxf"))
    assert len(project.items) == count


def test_can_import_as_footage_only() -> None:
    opts = ImportOptions(ASSETS / "mxf_dnxhr_320x180p25.mxf")
    assert opts.can_import_as(ImportAsType.FOOTAGE)
    assert not opts.can_import_as(ImportAsType.COMP)
    assert not opts.can_import_as(ImportAsType.COMP_CROPPED_LAYERS)
    assert not opts.can_import_as(ImportAsType.PROJECT)


def test_sequence_import_refused() -> None:
    project = parse_aep(BASE).project
    opts = ImportOptions(ASSETS / "mxf_dnxhr_320x180p25.mxf")
    opts.sequence = True
    with pytest.raises(
        ValueError, match="cannot import .mxf files as an image sequence"
    ):
        project.import_file(opts)
