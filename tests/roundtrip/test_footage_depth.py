"""Imported footage caches After Effects' input depth and alpha in `sspc`.

`footage_depth.aep` is AE 2026's own scripted import (Windows) of every asset
under `samples/assets` and `samples/assets/depth`, each item named after its
file, plus the layered-file comps of `_COMP_FILES`
(`scripts/jsx/generate_footage_depth_sample.jsx`). py_aep imports the same
files and must cache the same depth (`sspc` 0x3E), the `01 01` that follows
it, and the same alpha interpretation - AE does not re-read most formats on
open, so a wrong cached depth renders without alpha.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from helpers import parse_project

from py_aep import ImportAsType
from py_aep import parse as parse_aep
from py_aep.models.import_options import ImportOptions
from py_aep.models.sources.file import FileSource

if TYPE_CHECKING:
    from py_aep.models.project import Project

SAMPLES = Path(__file__).parent.parent.parent / "samples"
ASSETS = SAMPLES / "assets"
BASE = SAMPLES / "models" / "folder" / "folder.aep"
FIXTURE = SAMPLES / "models" / "import" / "footage_depth.aep"

_COMP_FILES = [
    "depth/psd_rgb8_bg_layer.psd",
    "depth/psd_rgb16_bg_layer.psd",
    "depth/psd_gray8_layered.psd",
    "layer_bounds.psd",
    "psd_layer_styles.psd",
    "psd_noise_gradient_32bpc.psd",
    "ai.ai",
]


def _ae_sources() -> dict[str, FileSource]:
    """AE's whole-file footage, by file name (layer items carry a `/`)."""
    sources = {}
    for item in parse_project(FIXTURE).footages:
        if "/" not in item.name and isinstance(item.main_source, FileSource):
            sources[item.name] = item.main_source
    return sources


def _ae_layer_sources(file_name: str) -> dict[int, FileSource]:
    """AE's layer-bound footage of `file_name`, by layer index."""
    sources = {}
    for item in parse_project(FIXTURE).footages:
        source = item.main_source
        if (
            item.name.endswith("/" + file_name)
            and isinstance(source, FileSource)
            and source._sspc.layer_index != 0xFFFFFFFF
        ):
            sources[source._sspc.layer_index] = source
    return sources


def _windows_project() -> Project:
    """A fresh project that imports the way AE on Windows (the fixture's) does."""
    return parse_aep(BASE, platform="windows").project


def _asset(name: str) -> Path:
    path = ASSETS / name
    return path if path.exists() else ASSETS / "depth" / name


def _depth_bytes(source: FileSource) -> tuple[bytes, bool]:
    """`sspc` 0x3E-0x44 (depth, `01 01`, 3 zero bytes) and whether the source
    has alpha. (The alpha *mode* AE picks for an RGBA DPX differs between AE
    on macOS and on Windows, so it is not compared here.)"""
    return source._sspc.tobytes()[0x3E:0x45], source.has_alpha


@pytest.mark.parametrize("name", sorted(_ae_sources()))
def test_import_caches_after_effects_depth(name: str) -> None:
    project = _windows_project()
    item = project.import_file(ImportOptions(_asset(name)))
    ae = _ae_sources()[name]
    assert item.main_source._sspc.depth == ae._sspc.depth
    assert _depth_bytes(item.main_source) == _depth_bytes(ae)


@pytest.mark.parametrize("comp_file", _COMP_FILES)
def test_layered_comp_import_caches_after_effects_depth(comp_file: str) -> None:
    project = _windows_project()
    options = ImportOptions(ASSETS / comp_file)
    options.import_as = ImportAsType.COMP
    project.import_file(options)
    file_name = Path(comp_file).name
    ours = {}
    for item in project.footages:
        source = item.main_source
        if (
            isinstance(source, FileSource)
            and Path(source.file).name == file_name
            and source._sspc.layer_index != 0xFFFFFFFF
        ):
            ours[source._sspc.layer_index] = source
    ae = _ae_layer_sources(file_name)
    assert sorted(ours) == sorted(ae)
    for index, source in ours.items():
        assert _depth_bytes(source) == _depth_bytes(ae[index]), index
        # The layer's content box at its own channel count (colour channels,
        # plus one when it has transparency - not for a Background layer).
        assert source._sspc.data_size == ae[index]._sspc.data_size, index


def test_chosen_background_layer_is_opaque() -> None:
    # A "Choose Layer" import binds the same layer source as a comp import.
    ae = _ae_layer_sources("psd_rgb8_bg_layer.psd")
    project = _windows_project()
    options = ImportOptions(ASSETS / "depth" / "psd_rgb8_bg_layer.psd")
    options.layer_index = 1  # list_layers order is top first: the Background
    item = project.import_file(options)
    source = item.main_source
    assert _depth_bytes(source) == _depth_bytes(ae[source._sspc.layer_index])
    assert source._sspc.data_size == ae[source._sspc.layer_index]._sspc.data_size
    assert source.has_alpha is False


def test_sequence_caches_the_frame_depth() -> None:
    # AE stores a sequence with its frames' depth (media_gap_formats.aep,
    # AE 2026 macOS: the 10-bit DPX sequence is 48 like its frames).
    truth = {
        f.name: f.main_source
        for f in parse_project(
            SAMPLES / "models" / "import" / "media_gap_formats.aep"
        ).footages
    }
    project = _windows_project()
    options = ImportOptions(ASSETS / "dpx_seq.0001.dpx")
    options.sequence = True
    item = project.import_file(options)
    assert _depth_bytes(item.main_source) == _depth_bytes(truth[item.name])
    assert item.main_source._sspc.depth == 48


def test_reload_refreshes_the_depth(tmp_path: Path) -> None:
    media = tmp_path / "frame.png"
    shutil.copy(ASSETS / "depth" / "png_rgb8.png", media)
    project = _windows_project()
    item = project.import_file(ImportOptions(media))
    assert item.main_source._sspc.depth == 24
    shutil.copy(ASSETS / "depth" / "png_rgba16.png", media)
    item.main_source.reload()
    assert item.main_source._sspc.depth == 64
    assert item.main_source.has_alpha is True


@pytest.mark.parametrize("name", sorted(_ae_sources()))
def test_import_sets_after_effects_media_flags(name: str) -> None:
    # Bit 3 of sspc 0x70 and 0x9F: AE sets both for JPEG, BMP/GIF, HEIC,
    # movie, audio and data files, neither for the other formats.
    project = _windows_project()
    ours = project.import_file(ImportOptions(_asset(name))).main_source._sspc.tobytes()
    ae = _ae_sources()[name]._sspc.tobytes()
    assert (ours[0x70], ours[0x9F]) == (ae[0x70], ae[0x9F])


def test_sequence_sets_only_the_first_media_flag() -> None:
    # AE 2026 (macOS) imports a GIF sequence with 0x70 bit 3 set and 0x9F
    # bit 3 clear (imio_sequence.aep).
    truth = parse_project(SAMPLES / "models" / "import" / "imio_sequence.aep")
    ae = next(f.main_source for f in truth.footages if f.main_source._target_is_folder)
    project = parse_aep(BASE, platform="macos").project
    options = ImportOptions(ASSETS / "sequence_001.gif")
    options.sequence = True
    ours = project.import_file(options).main_source._sspc.tobytes()
    assert (ours[0x70], ours[0x9F]) == (0x08, 0x00)
    assert (ours[0x70], ours[0x9F]) == (
        ae._sspc.tobytes()[0x70],
        ae._sspc.tobytes()[0x9F],
    )


@pytest.mark.parametrize("name", sorted(_ae_sources()))
def test_import_caches_after_effects_data_size(name: str) -> None:
    # The file size for most formats; the decoded pixel buffer for TIFF
    # stills and merged PSD footage (w * h * channels * bytes per channel,
    # counting alpha only when the image has it: 2 for gray + alpha).
    project = _windows_project()
    item = project.import_file(ImportOptions(_asset(name)))
    assert item.main_source._sspc.data_size == _ae_sources()[name]._sspc.data_size


def test_data_size_above_32_bits_round_trips(tmp_path: Path) -> None:
    project = _windows_project()
    item = project.import_file(ImportOptions(ASSETS / "depth" / "png_rgb8.png"))
    item.main_source._sspc.data_size = 5 << 30
    out = tmp_path / "big.aep"
    project.save(out)
    reread = parse_aep(out).project.items[item.id]
    assert reread.main_source._sspc.data_size == 5 << 30


def test_hq_field_separation_keeps_the_container_media_bit(tmp_path: Path) -> None:
    # AE sets bit 3 of sspc 0x9F on container media; the HQ flag is bit 0.
    project = parse_aep(FIXTURE).project
    item = next(f for f in project.footages if f.name == "mov_480.mov")
    assert item.main_source._sspc.tobytes()[0x9F] == 0x08
    item.main_source.high_quality_field_separation = True
    out = tmp_path / "hq.aep"
    project.save(out)
    reread = parse_aep(out).project.items[item.id].main_source
    assert reread.high_quality_field_separation is True
    assert reread._sspc.tobytes()[0x9F] == 0x09


def test_movie_pixel_aspect_is_the_exact_pasp_ratio() -> None:
    # mov_alpha_small.mov declares pasp 4:3; AE stores the ratio 4/3.
    project = _windows_project()
    item = project.import_file(ImportOptions(ASSETS / "mov_alpha_small.mov"))
    sspc = item.main_source._sspc
    ae = _ae_sources()["mov_alpha_small.mov"]._sspc
    assert (sspc.pixel_aspect_dividend, sspc.pixel_aspect_divisor) == (4, 3)
    assert (ae.pixel_aspect_dividend, ae.pixel_aspect_divisor) == (4, 3)


#: Formats whose `opti` header AE fills from the file: the Photoshop-family
#: still importer (PSD/PSB and TIFF) and the Illustrator/PDF/EPS one.
_HEADER_FORMATS = ("8BPS", "TIF ", "TEXT")


def _header_names(*formats: str) -> list[str]:
    return sorted(
        name
        for name, source in _ae_sources().items()
        if source._sspc.source_format_type in formats
    )


@pytest.mark.parametrize("name", _header_names(*_HEADER_FORMATS))
def test_import_writes_after_effects_opti_header(name: str, tmp_path: Path) -> None:
    # The whole opti body, read back from disk: the channel count (colour
    # channels plus alpha), bit depth, colour mode and layer count of a
    # PSD/TIFF; the document layer count, page count and page size of an
    # Illustrator/PDF document (an EPS keeps the bare body).
    project = _windows_project()
    item = project.import_file(ImportOptions(_asset(name)))
    out = tmp_path / "opti.aep"
    project.save(out)
    ours = parse_aep(out).project.items[item.id].main_source
    assert ours._opti.tobytes() == _ae_sources()[name]._opti.tobytes()


@pytest.mark.parametrize("name", _header_names("TEXT"))
def test_document_footage_writes_after_effects_kind_bytes(
    name: str, tmp_path: Path
) -> None:
    # sspc 0xC8-0xC9: AE 2026 writes 00 02 for an Illustrator/PDF/EPS file
    # imported whole, like any other file footage (00 00 is for the layers
    # of an Illustrator composition import).
    project = _windows_project()
    item = project.import_file(ImportOptions(_asset(name)))
    out = tmp_path / "kind.aep"
    project.save(out)
    ours = parse_aep(out).project.items[item.id].main_source
    assert ours._sspc._reserved_c8 == _ae_sources()[name]._sspc._reserved_c8
    assert ours._sspc._reserved_c8 == b"\x00\x02"


@pytest.mark.parametrize("layer_index", [0, 1])
def test_chosen_layer_records_the_document_channels_and_mode(
    layer_index: int, tmp_path: Path
) -> None:
    # Every opti of a document carries the document's channel count and
    # colour mode, a layer's too: 2 channels (gray + alpha) and mode 1
    # (grayscale) for psd_gray8_layered.psd, whose layers AE imported as a
    # composition in the fixture; the layer's own channel count at 0x5E is
    # gray + transparency = 2. A chosen layer's opti is the one AE writes
    # for that layer in a composition import.
    ae = _ae_layer_sources("psd_gray8_layered.psd")
    project = _windows_project()
    options = ImportOptions(ASSETS / "depth" / "psd_gray8_layered.psd")
    options.layer_index = layer_index
    item = project.import_file(options)
    out = tmp_path / "layer.aep"
    project.save(out)
    source = parse_aep(out).project.items[item.id].main_source
    ours = source._opti.tobytes()
    assert (ours[0x1E], ours[0x2A], ours[0x30], ours[0x5E]) == (2, 1, 2, 2)
    assert ours == ae[source._sspc.layer_index]._opti.tobytes()


@pytest.mark.parametrize(
    ("file_name", "layer_index", "channels"),
    [
        # Background layer: RGB, no transparency.
        ("psd_rgb8_bg_layer.psd", 1, 3),
        ("psd_rgb16_bg_layer.psd", 1, 3),
        # The layer above it: RGB + transparency.
        ("psd_rgb8_bg_layer.psd", 0, 4),
    ],
)
def test_chosen_layer_records_its_own_channels(
    file_name: str, layer_index: int, channels: int
) -> None:
    # opti 0x5E: the document's colour channels plus one when the layer
    # has transparency (the document channel count at 0x1E stays 3).
    ae = _ae_layer_sources(file_name)
    project = _windows_project()
    options = ImportOptions(ASSETS / "depth" / file_name)
    options.layer_index = layer_index
    source = project.import_file(options).main_source
    ours = source._opti.tobytes()
    theirs = ae[source._sspc.layer_index]._opti.tobytes()
    assert (ours[0x1E], ours[0x5E]) == (3, channels)
    assert (ours[0x1E], ours[0x5E]) == (theirs[0x1E], theirs[0x5E])


#: AE 2026's scripted import (Windows) of the hand-written colour-mode files
#: in `samples/assets/depth`: flattened PSDs with an alpha channel, bitmap,
#: indexed and Lab PSDs, and Lab, CMYK + alpha, WhiteIsZero and
#: two-extra-sample TIFFs. Items are named after their files.
MODES_FIXTURE = SAMPLES / "models" / "import" / "photoshop_modes.aep"


def _mode_sources() -> dict[str, FileSource]:
    sources = {}
    for item in parse_project(MODES_FIXTURE).footages:
        if isinstance(item.main_source, FileSource):
            sources[item.name] = item.main_source
    return sources


@pytest.mark.parametrize("name", sorted(_mode_sources()))
def test_color_mode_import_matches_after_effects(name: str, tmp_path: Path) -> None:
    # The opti header (channels: a flattened PSD's alpha channel is not
    # counted; colour mode: Lab = 9, a TIFF's CIELab too; layers: a TIFF's
    # alpha sample counts as one), the cached depth (bitmap 0, indexed 8)
    # and data size, read back from disk.
    project = _windows_project()
    item = project.import_file(ImportOptions(ASSETS / "depth" / name))
    out = tmp_path / "modes.aep"
    project.save(out)
    ours = parse_aep(out).project.items[item.id].main_source
    ae = _mode_sources()[name]
    assert ours._opti.tobytes() == ae._opti.tobytes()
    assert _depth_bytes(ours) == _depth_bytes(ae)
    assert ours._sspc.data_size == ae._sspc.data_size


def test_audio_and_data_files_have_no_depth() -> None:
    sources = _ae_sources()
    for name in ("wav.wav", "mp3.mp3", "csv.csv", "mp4_av1_with_audio.mp4"):
        assert sources[name]._sspc.depth == 0, name
        assert sources[name]._sspc.tobytes()[0x40:0x42] == b"\x01\x01", name
