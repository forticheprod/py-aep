"""Imported OpenEXR footage carries After Effects' `oEXR` options header.

`exr_options.aep` is AE 2026's own scripted import (Windows) of every
`samples/assets/exr/*.exr` - tiny uncompressed files that each vary one
property: channels, layers, pixel type, data window - plus
`samples/assets/exr/seq` as a sequence named "seq_inside"
(`scripts/jsx/generate_exr_options_sample.jsx`). `footage_depth.aep` adds the
two repo EXRs, one of them multi-part.

Without the header AE places a data window that differs from the display
window wrongly when it renders, and one larger than the display window
crashed AE's render (AE 2026).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from helpers import parse_project

from py_aep import parse as parse_aep
from py_aep.models.import_options import ImportOptions

SAMPLES = Path(__file__).parent.parent.parent / "samples"
ASSETS = SAMPLES / "assets"
BASE = SAMPLES / "models" / "folder" / "folder.aep"
FIXTURES = (
    SAMPLES / "models" / "import" / "exr_options.aep",
    SAMPLES / "models" / "import" / "footage_depth.aep",
)


def _ae_optis() -> dict[str, bytes]:
    optis = {}
    for fixture in FIXTURES:
        for item in parse_project(fixture).footages:
            if item.name.endswith(".exr") or item.name == "seq_inside":
                optis[item.name] = item.main_source._opti.tobytes()
    return optis


def _import(name: str) -> bytes:
    project = parse_aep(BASE, platform="windows").project
    if name == "seq_inside":
        options = ImportOptions(ASSETS / "exr" / "seq" / "inside.0001.exr")
        options.sequence = True
    else:
        path = ASSETS / "exr" / name
        options = ImportOptions(path if path.exists() else ASSETS / name)
    return project.import_file(options).main_source._opti.tobytes()


@pytest.mark.parametrize("name", sorted(_ae_optis()))
def test_import_writes_after_effects_exr_header(name: str) -> None:
    ae = _ae_optis()[name]
    ours = _import(name)
    assert len(ours) == len(ae) == 9750
    # Magic, length, compression (0x0E), channel count across parts (0x12)
    # and channels + named layers (0x2E).
    assert ours[:0x30] == ae[:0x30]
    # AE's remaining bytes vary from import to import; zeros render the same.
    assert ours[0x30:] == bytes(len(ours) - 0x30)


def test_alpha_is_premultiplied_with_its_flag() -> None:
    """AE interprets an EXR's alpha as premultiplied and sets the sspc flag
    bit that goes with that mode; without it AE resets the footage to
    straight alpha when it opens the project."""
    ae = next(
        item.main_source._sspc
        for item in parse_project(FIXTURES[0]).footages
        if item.name == "rgba_full.exr"
    )
    project = parse_aep(BASE, platform="windows").project
    ours = project.import_file(ImportOptions(ASSETS / "exr" / "rgba_full.exr"))
    sspc = ours.main_source._sspc
    assert (
        (sspc.alpha_mode_raw, sspc._alpha_flags)
        == (
            ae.alpha_mode_raw,
            ae._alpha_flags,
        )
        == (1, 1)
    )


def test_reload_refreshes_the_exr_header(tmp_path: Path) -> None:
    media = tmp_path / "frame.exr"
    shutil.copy(ASSETS / "exr" / "rgb_inside.exr", media)
    project = parse_aep(BASE, platform="windows").project
    item = project.import_file(ImportOptions(media))
    shutil.copy(ASSETS / "exr" / "layered.exr", media)
    item.main_source.reload()
    assert item.main_source._opti.tobytes()[:0x30] == _ae_optis()["layered.exr"][:0x30]
