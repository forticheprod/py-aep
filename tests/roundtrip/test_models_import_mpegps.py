"""MPEG-1 system / MPEG-2 program stream footage import versus After Effects'
own import of the same files (samples/models/import/mpegps_import.aep, AE
2026 on Windows)."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, assert_media_import_matches_ae, parse_project_fresh

from py_aep import parse as parse_aep
from py_aep.models.import_options import ImportOptions
from py_aep.models.items.footage import FootageItem

ASSETS = SAMPLES_DIR / "assets"
BASE = SAMPLES_DIR / "models" / "folder" / "folder.aep"
FIXTURE = SAMPLES_DIR / "models" / "import" / "mpegps_import.aep"

IMPORTED = [
    "mpg_720x576_4x3.mpg",
    "mpg_704x576_4x3.mpg",
    "mpg_1440x1080_16x9.mpg",
    "mpg_320x180p23976.mpg",
    "mpg_320x180p25_cut.mpg",
    "mpg_320x180p25_mp2_44k.mpg",
    "mpg_320x180p2997_rateext_x2.mpg",
    "mpg_ps2_720x576_4x3.mpg",
    "mpg_ps2_704x576_4x3.mpg",
    "mpg_ps2_320x180p25_cut.mpg",
    "mpg_ps2_320x180p25_ac3.mpg",
    "mpg_ps2_320x180p25_mp2stereo.mpg",
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
    out = tmp_path / "ps.aep"
    project.save(out)
    assert_media_import_matches_ae(parse_project_fresh(out).footages[-1], truth[name])


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("mpg_320x180p25_cut_e.mpg", "sequence header"),
        ("mpg_320x180p2997_rateext_div4_post.mpg", "divides the rate"),
    ],
)
def test_refused_streams_leave_the_project_unchanged(name: str, message: str) -> None:
    project = parse_aep(BASE).project
    count = len(project.items)
    with pytest.raises(ValueError, match=message):
        project.import_file(ImportOptions(ASSETS / name))
    assert len(project.items) == count
