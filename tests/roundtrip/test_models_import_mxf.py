"""MXF footage import versus After Effects' own import of the same files
(samples/models/import/mxf_import.aep, AE 2026 on Windows)."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, assert_media_import_matches_ae, parse_project_fresh

from py_aep import ImportAsType
from py_aep import parse as parse_aep
from py_aep.models.import_options import ImportOptions
from py_aep.models.items.footage import FootageItem

ASSETS = SAMPLES_DIR / "assets"
BASE = SAMPLES_DIR / "models" / "folder" / "folder.aep"
FIXTURE = SAMPLES_DIR / "models" / "import" / "mxf_import.aep"

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
    assert_media_import_matches_ae(parse_project_fresh(out).footages[-1], truth[name])


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
