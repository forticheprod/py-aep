"""MPEG transport-stream footage import versus After Effects' own import of
the same files (samples/models/import/mpegts_import.aep, AE 2026 on Windows)."""

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
FIXTURE = SAMPLES_DIR / "models" / "import" / "mpegts_import.aep"

IMPORTED = [
    "ts_h264_320x180p25_ac3.ts",
    "ts_h264_320x180p25_ac3.m2t",
    "ts_h264_320x180p25_ac3.m2ts",
    "ts_h264_320x180p25_ac3.mts",
    "ts_mpeg2_720x576i25_4x3.ts",
    "ts_h264_720x480p2997_16x9.ts",
    "ts_h264_320x180p2997_sar40x33.ts",
    "ts_h264_1440x1080p25_16x9.ts",
    "ts_h264_320x180p25_cut.ts",
    "ts_mpeg2_320x180p25_cut.ts",
    "ts_aac_only.ts",
    "ts_audio_ac3_2s_aac3s.ts",
    "ts_audio_mp2_2s_aac3s.ts",
    "ts_audio_aac_44k.ts",
    "ts_audio_mp2_mono.ts",
    "ts_audio_lpcm.m2ts",
    "ts_mpeg2_320x180p2997_rateext_div4.ts",
    "ts_mpeg2_704x576_4x3.ts",
    "ts_mpeg2_320x180p25_ac3mono.ts",
    "ts_mpeg2_320x180p25_mp2stereo.ts",
    "ts_mpeg2_320x180p25_mp2mono.ts",
    "ts_hevc_320x180p25.ts",
    "ts_hevc_320x180p2997.ts",
    "ts_hevc_320x180p23976.ts",
    "ts_hevc_320x180p25_sar40x33.ts",
    "ts_hevc_720x576p25_4x3.ts",
    "ts_hevc_720x480p2997_16x9.ts",
    "ts_hevc_1440x1080p25_16x9.ts",
    "ts_hevc_322x182p25.ts",
    "ts_hevc_320x180p25_10bit.ts",
    "ts_hevc_720x576i50_tff.ts",
    "ts_hevc_720x576i25_tff.ts",
    "ts_hevc_320x180p25_aac.ts",
    "ts_hevc_320x180p25_cut.ts",
    "ts_hevc_320x180p25_trail_first.ts",
    "ts_hevc_320x180p25_vuifps50.ts",
    "ts_hevc_320x180p25_novuitiming.ts",
    "ts_hevc_720x576i25_tff_novuitiming.ts",
    "ts_hevc_320x180p25_cut_bla_radl.ts",
    "ts_hevc_320x180p25_slices2.ts",
    "ts_hevc_320x180p12345.ts",
    "ts_hevc_320x180p25_12bit.ts",
    "ts_hevc_320x180p25_444_10bit.ts",
    "ts_hevc_322x182p25_gray.ts",
    "ts_hevc_322x182p25_gray10.ts",
    "ts_hevc_320x180p25_aac44k.ts",
    "ts_hevc_320x180p25.m2ts",
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
    out = tmp_path / "ts.aep"
    project.save(out)
    assert_media_import_matches_ae(parse_project_fresh(out).footages[-1], truth[name])


@pytest.mark.parametrize(
    "name", ["ts_h264_320x180p25_ac3.ts", "ts_h264_320x180p25_ac3.m2ts"]
)
def test_can_import_as_footage_only(name: str) -> None:
    opts = ImportOptions(ASSETS / name)
    assert opts.can_import_as(ImportAsType.FOOTAGE)
    assert not opts.can_import_as(ImportAsType.COMP)
    assert not opts.can_import_as(ImportAsType.COMP_CROPPED_LAYERS)
    assert not opts.can_import_as(ImportAsType.PROJECT)


def test_sequence_import_refused() -> None:
    project = parse_aep(BASE).project
    opts = ImportOptions(ASSETS / "ts_h264_320x180p25_ac3.ts")
    opts.sequence = True
    with pytest.raises(
        ValueError, match="cannot import .ts files as an image sequence"
    ):
        project.import_file(opts)
