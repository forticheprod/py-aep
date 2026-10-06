"""A new footage source's `LIST:CLRS` holds the records of the project's
file version.

`clrs_ae2022.aep` ... `clrs_ae2025.aep` are AE 2022-2025's own scripted
imports, each into an empty `py_aep.new` project of its version, of an
ICC-tagged PNG, an untagged PNG, a TIFF, a JPEG and an Illustrator file (items
named after the keys of `_FILES`); `samples/versions/ae20XX/complete.aep`
hold AE's own solids. AE 2025 (file version 96.9) and later end every CLRS
with the `hdrm` pair; AE 2022-2024 do not (they open a file that has it and
drop it when they save). The `mcsp` pair of an embedded profile is written
by all four.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import parse_project

import py_aep
from py_aep import parse as parse_aep
from py_aep.models.import_options import ImportOptions
from py_aep.models.sources.footage import FootageSource
from py_aep.models.sources.solid import SolidSource

SAMPLES = Path(__file__).parent.parent.parent / "samples"
ASSETS = SAMPLES / "assets"
IMPORT_DIR = SAMPLES / "models" / "import"

#: The version each fixture's release stamps (`samples/versions`).
_VERSIONS = {2022: "22.5x53", 2023: "23.6x62", 2024: "24.6x2", 2025: "25.6x101"}

#: Left out: `ai.ai`, for which AE 2022-2024 also write a `dcui` flag that
#: py_aep does not (they write it back on save).
_FILES = {
    "png_icc": ASSETS / "image_with_alpha.png",
    "png_plain": ASSETS / "depth" / "png_rgb8.png",
    "tif": ASSETS / "8bits.tif",
    "jpg": ASSETS / "11_progressive.jpg",
}


def _shape(source: FootageSource) -> list[str]:
    assert source._clrs is not None
    return [chunk.chunk_type for chunk in source._clrs.chunks]


@pytest.mark.parametrize("year", sorted(_VERSIONS))
@pytest.mark.parametrize("label", sorted(_FILES))
def test_import_writes_the_versions_color_records(
    year: int, label: str, tmp_path: Path
) -> None:
    ae = {
        item.name: item.main_source
        for item in parse_project(IMPORT_DIR / f"clrs_ae{year}.aep").footages
    }
    project = py_aep.new(_VERSIONS[year], platform="windows").project
    item = project.import_file(ImportOptions(_FILES[label]))
    out = tmp_path / "clrs.aep"
    project.save(out)
    ours = parse_aep(out).project.items[item.id].main_source
    assert _shape(ours) == _shape(ae[label])


@pytest.mark.parametrize("year", sorted(_VERSIONS))
def test_new_solid_writes_the_versions_color_records(year: int, tmp_path: Path) -> None:
    ae = next(
        item.main_source
        for item in parse_project(
            SAMPLES / "versions" / f"ae{year}" / "complete.aep"
        ).footages
        if isinstance(item.main_source, SolidSource)
    )
    project = py_aep.new(_VERSIONS[year], platform="windows").project
    comp = project.root_folder.add_comp("Comp", 100, 100, 1.0, 1.0, 25.0)
    solid = comp.add_solid([1.0, 0.0, 0.0]).source
    out = tmp_path / "solid.aep"
    project.save(out)
    ours = parse_aep(out).project.items[solid.id].main_source
    assert _shape(ours) == _shape(ae)


def test_parsed_records_are_kept(tmp_path: Path) -> None:
    # Only a source built for the project is cut to its version: an AE 2022
    # project's own footage round-trips as AE wrote it.
    path = IMPORT_DIR / "clrs_ae2022.aep"
    project = parse_aep(path).project
    out = tmp_path / "same.aep"
    project.save(out)
    assert out.read_bytes() == path.read_bytes()
