"""Footage imported into an OCIO-managed project takes the color space After
Effects assigns new files: the config's file rules in order (a rule's color
space recorded as a direct pick), or, for a config without file rules, its
`default` role (recorded as a role pick). Any profile the file embeds stays
recorded as its source profile.

`ocio_input_<config>.aep` are AE 2026 imports of five stills into
`py_aep.new()` projects set to ACES 1.2, ACES 1.3 CG v1.0 and the sergb.ocio
studio config (`EXR` rule -> `scene_linear`, `Default` rule -> `default`).

A replace keeps the space the source had - a rule's pick or one the user
assigned - while a proxy is a new file and gets the rules' pick.
`ocio_replace_sergb.aep` is AE 2026 replacing PNG and EXR footage in a sergb
project (`scripts/jsx/generate_ocio_replace_sample.jsx`): its `py_*` items
were imported by py_aep (`py_pick` then set to `ACEScg yo`), its `ae_*` items
by After Effects.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import new
from py_aep import parse as parse_aep
from py_aep.binary.utils import find_by_list_type
from py_aep.color.ocio import resolve_ocio_config
from py_aep.enums import ColorManagementSystem
from py_aep.models.import_options import ImportOptions

SAMPLES = Path(__file__).parent.parent.parent / "samples"
IMPORT_DIR = SAMPLES / "models" / "import"
SERGB = SAMPLES / "models" / "output_module" / "output_color_space_ocio" / "sergb.ocio"
ASSETS = SAMPLES / "assets"
FILES = {
    "rgb_full.exr": ASSETS / "exr" / "rgb_full.exr",
    "11_progressive.jpg": ASSETS / "11_progressive.jpg",
    "image_with_alpha.png": ASSETS / "image_with_alpha.png",
    "tga_24.tga": ASSETS / "tga_24.tga",
    "8bits.tif": ASSETS / "8bits.tif",
}
CONFIGS = {"aces12": "ACES 1.2", "aces13cg": "ACES 1.3 CG v1.0", "sergb": str(SERGB)}


def _clrs(source: object) -> list[tuple[str, bytes]]:
    """The CLRS record, the embedded profile's bytes left out: py embeds the
    sRGB copy installed on this machine for a TIFF, which can differ from
    After Effects' copy in the advisory rendering-intent byte."""
    clrs = find_by_list_type(chunks=source._pin.chunks, list_type="CLRS")  # type: ignore[attr-defined]
    record = []
    marker = ""
    for chunk in clrs.chunks:
        data = chunk.tobytes()
        if chunk.chunk_type == "Utf8" and marker in ("mcsp", "Mcsp") and data:
            data = b"<embedded>"
        record.append((chunk.chunk_type, data))
        marker = chunk.chunk_type
    return record


@pytest.mark.parametrize("tag", sorted(CONFIGS))
@pytest.mark.parametrize("name", sorted(FILES))
def test_import_records_the_ocio_input_space(tag: str, name: str) -> None:
    config = CONFIGS[tag]
    if resolve_ocio_config(config) is None:
        pytest.skip(f"OCIO config {config!r} is not installed")
    ae = next(
        item
        for item in parse_aep(IMPORT_DIR / f"ocio_input_{tag}.aep").project.footages
        if item.name == name
    )
    project = new().project
    project.color_management_system = ColorManagementSystem.OCIO
    project.ocio_configuration_file = config
    ours = project.import_file(ImportOptions(FILES[name]))
    assert _clrs(ours.main_source) == _clrs(ae.main_source)


PNG = FILES["image_with_alpha.png"]
EXR = FILES["rgb_full.exr"]


@pytest.mark.parametrize(
    ("name", "first", "assigned", "second"),
    [
        ("py_pick", PNG, "ACEScg yo", EXR),
        ("py_dflt", PNG, None, EXR),
        ("ae_png_to_exr", PNG, None, EXR),
        ("ae_exr_to_png", EXR, None, PNG),
    ],
)
def test_replace_keeps_the_ocio_input_space(
    name: str, first: Path, assigned: str | None, second: Path
) -> None:
    if resolve_ocio_config(str(SERGB)) is None:
        pytest.skip("sergb.ocio is not resolvable")
    ae = next(
        item
        for item in parse_aep(IMPORT_DIR / "ocio_replace_sergb.aep").project.footages
        if item.name == name
    )
    project = new().project
    project.color_management_system = ColorManagementSystem.OCIO
    project.ocio_configuration_file = str(SERGB)
    ours = project.import_file(ImportOptions(first))
    if assigned is not None:
        ours.main_source.media_color_space = assigned
    ours.replace(second)
    assert _clrs(ours.main_source) == _clrs(ae.main_source)


def test_proxy_takes_the_rules_pick() -> None:
    if resolve_ocio_config(str(SERGB)) is None:
        pytest.skip("sergb.ocio is not resolvable")
    ae = next(
        item
        for item in parse_aep(IMPORT_DIR / "ocio_replace_sergb.aep").project.footages
        if item.name == "ae_png_proxy_exr"
    )
    project = new().project
    project.color_management_system = ColorManagementSystem.OCIO
    project.ocio_configuration_file = str(SERGB)
    ours = project.import_file(ImportOptions(PNG))
    ours.set_proxy(EXR)
    assert _clrs(ours.proxy_source) == _clrs(ae.proxy_source)
