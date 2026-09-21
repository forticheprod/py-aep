"""Tests for FootageItem model parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import AlphaMode, LinearLightMode
from py_aep import parse as parse_aep
from py_aep.binary.chunk import ListChunk
from py_aep.binary.scalar_chunks import Utf8Chunk
from py_aep.binary.utils import find_by_type
from py_aep.color.icc import (
    ColorProfileNotFoundError,
    default_icc_library,
    icc_profile_id,
)
from py_aep.models.import_options import ImportOptions
from py_aep.models.sources.file import UNDEFINED_FRAME, FileSource
from py_aep.resolvers.media_probe import probe_media

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "footage"
SAMPLES = Path(__file__).parent.parent.parent / "samples" / "models"


def _get_first_footage(aep_path: Path) -> object:
    """Parse an .aep and return the first footage item."""
    project = parse_aep(aep_path).project
    return project.footages[0]


class TestFootageReadOnly:
    """All FootageItem fields backed by source delegation are read-only."""

    def test_width_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "solid_sizes.aep")
        with pytest.raises(AttributeError):
            footage.width = 100  # type: ignore[misc]

    def test_height_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "solid_sizes.aep")
        with pytest.raises(AttributeError):
            footage.height = 100  # type: ignore[misc]

    def test_duration_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "placeholder.aep")
        with pytest.raises(AttributeError):
            footage.duration = 5.0  # type: ignore[misc]

    def test_frame_rate_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "footage_misc.aep")
        with pytest.raises(AttributeError):
            footage.frame_rate = 30.0  # type: ignore[misc]

    def test_frame_duration_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "placeholder.aep")
        with pytest.raises(AttributeError):
            footage.frame_duration = 100  # type: ignore[misc]

    def test_footage_missing_is_read_only(self) -> None:
        footage = _get_first_footage(SAMPLES_DIR / "footage_missing.aep")
        with pytest.raises(AttributeError):
            footage.footage_missing = False  # type: ignore[misc]


class TestSequenceFrameBoundsDerivation:
    """AE leaves `sspc.start_frame`/`end_frame` undefined for some image
    sequences and stores the real numbers only in the `StVc` filenames.
    py_aep derives them on read; it must NOT write them back, or an
    untouched parse/save round trip stops being byte-identical (every
    EXR-sequence footage in a pre-2019 project was affected).
    """

    @staticmethod
    def _sequence_with_stvc(names: list[str]) -> FileSource:
        """A sequence source whose sspc bounds are undefined and whose
        frame numbers live only in an `StVc` list of filenames."""
        source = FileSource._new(
            Path("C:/footage/render/render.0101.exr"),
            source_format="oEXR",
            width=1920,
            height=1080,
            duration=2.0,
            frame_rate=24.0,
            sequence_prefix="render.",
            sequence_ext=".exr",
            start_frame=101,
            end_frame=148,
            frame_padding=4,
        )
        sspc = source._sspc
        sspc.start_frame = UNDEFINED_FRAME
        sspc.end_frame = UNDEFINED_FRAME
        source._pin.chunks.append(
            ListChunk(
                chunk_type="LIST",
                list_type="StVc",
                chunks=[Utf8Chunk(value=name) for name in names],
            )
        )
        # Re-wrap so __init__ runs against the doctored chunks.
        return FileSource(
            _pin=source._pin,
            _sspc=sspc,
            _opti=source._opti,
            _linl=source._linl,
            _clrs=source._clrs,
        )

    def test_bounds_derived_from_stvc_filenames(self) -> None:
        source = self._sequence_with_stvc(
            ["render.0101.exr", "render.0102.exr", "render.0148.exr"]
        )
        assert source._start_frame == 101
        assert source._end_frame == 148

    def test_derivation_does_not_write_the_chunk(self) -> None:
        source = self._sequence_with_stvc(
            ["render.0101.exr", "render.0102.exr", "render.0148.exr"]
        )
        assert source._start_frame == 101
        assert source._end_frame == 148
        # The chunk keeps AE's undefined sentinel, so a save reproduces the
        # original bytes.
        assert source._sspc.start_frame == UNDEFINED_FRAME
        assert source._sspc.end_frame == UNDEFINED_FRAME

    def test_stored_bounds_win_over_derivation(self) -> None:
        source = self._sequence_with_stvc(["render.0101.exr", "render.0148.exr"])
        source._sspc.start_frame = 7
        source._sspc.end_frame = 9
        assert (source._start_frame, source._end_frame) == (7, 9)

    def test_undefined_without_stvc_stays_undefined(self) -> None:
        source = FileSource._new(
            Path("C:/footage/render/render.0101.exr"),
            source_format="oEXR",
            width=1920,
            height=1080,
            duration=2.0,
            frame_rate=24.0,
            sequence_prefix="render.",
            sequence_ext=".exr",
            start_frame=101,
            end_frame=148,
            frame_padding=4,
        )
        source._sspc.start_frame = UNDEFINED_FRAME
        source._sspc.end_frame = UNDEFINED_FRAME
        assert source._start_frame == UNDEFINED_FRAME
        assert source._end_frame == UNDEFINED_FRAME


class TestAlphaModeWrites:
    """Writing `alpha_mode` keeps the `sspc` alpha bytes self-consistent.

    AE pairs the mode byte with bit 0 of the alpha flags and resets the whole
    interpretation to straight alpha when it reads a file where the two
    disagree (AE 2026).
    """

    def _png_source(self) -> FileSource:
        project = parse_aep(SAMPLES / "project" / "emptier.aep").project
        item = project.import_file(
            ImportOptions(SAMPLES.parent / "assets" / "image_with_alpha.png")
        )
        return item.main_source

    @pytest.mark.parametrize(
        ("mode", "raw", "premultiplied"),
        [
            (AlphaMode.STRAIGHT, 0, False),
            (AlphaMode.PREMULTIPLIED, 1, True),
            (AlphaMode.IGNORE, 2, False),
        ],
    )
    def test_mode_byte_and_flag_bit_agree(
        self, mode: AlphaMode, raw: int, premultiplied: bool
    ) -> None:
        source = self._png_source()
        source.alpha_mode = mode
        assert source._sspc.alpha_mode_raw == raw
        assert source._sspc.premultiplied is premultiplied
        assert source.alpha_mode == mode

    def test_rejected_without_an_alpha_channel(self) -> None:
        project = parse_aep(SAMPLES / "project" / "emptier.aep").project
        item = project.import_file(
            ImportOptions(SAMPLES.parent / "assets" / "mov_480.mov")
        )
        source = item.main_source
        assert source.has_alpha is False
        with pytest.raises(ValueError, match="no alpha channel"):
            source.alpha_mode = AlphaMode.PREMULTIPLIED
        # The "no alpha channel" marker survives the rejected write.
        assert source._sspc.alpha_mode_raw == 3
        assert source.has_alpha is False


class TestSourceModifiedStamp:
    """AE stamps the source's last-modified time and re-reads the media when
    it does not match - taking an EXR's size from its data window rather than
    the display window AE's importer recorded."""

    def test_single_file_carries_its_own_mtime(self) -> None:
        project = parse_aep(SAMPLES / "project" / "emptier.aep").project
        path = SAMPLES.parent / "assets" / "new_exr.0002.exr"
        item = project.import_file(ImportOptions(path))
        assert item.main_source._sspc.source_modified == int(path.stat().st_mtime)

    def test_sequence_carries_the_folder_mtime(self) -> None:
        project = parse_aep(SAMPLES / "project" / "emptier.aep").project
        path = SAMPLES.parent / "assets" / "new_exr.0002.exr"
        opts = ImportOptions(path)
        opts.sequence = True
        item = project.import_file(opts)
        assert item.main_source._sspc.source_modified == int(
            path.parent.stat().st_mtime
        )

    def test_unreadable_media_stays_unstamped(self) -> None:
        source = FileSource._new(
            Path("C:/nowhere/render.0001.exr"),
            source_format="oEXR",
            width=64,
            height=64,
            duration=0.0,
            frame_rate=0.0,
        )
        assert source._sspc.source_modified == 0


def _require_profile(name: str) -> None:
    """Skip unless the named profile is discoverable on this machine.

    An assigned media profile is written by embedding the ICC bytes AE
    itself would embed, discovered from the installed Adobe Color dirs. With
    no ICC store (a CI runner, any machine without AE) the import records no
    profile at all, by design - see `_media_profile_records`.
    """
    try:
        default_icc_library().bytes_for(name)
    except ColorProfileNotFoundError:
        pytest.skip(f"ICC profile {name!r} not installed")


class TestMediaColorProfileRecord:
    """AE records the profile a file embeds, and assigns sRGB when it embeds
    none (AE 2026, measured across PNG, JPEG, TIFF, PSD, EXR, HDR, TGA and
    WAV imports)."""

    def _import(self, name: str) -> FileSource:
        project = parse_aep(SAMPLES / "project" / "emptier.aep").project
        item = project.import_file(ImportOptions(SAMPLES.parent / "assets" / name))
        return item.main_source

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("image_with_alpha.png", "Embedded"),
            ("11_progressive.jpg", "Embedded"),
            ("8bits.tif", "Embedded"),
            ("8bits.psd", "Embedded"),
            ("8bits_compressed.png", "sRGB IEC61966-2.1"),
            ("new_exr.0002.exr", "sRGB IEC61966-2.1"),
            ("hdr.hdr", "sRGB IEC61966-2.1"),
            ("tga_32.tga", "sRGB IEC61966-2.1"),
        ],
    )
    def test_media_color_space(self, filename: str, expected: str) -> None:
        if expected != "Embedded":
            _require_profile(expected)
        assert self._import(filename).media_color_space == expected

    def test_embedded_profile_is_recorded_by_id(self) -> None:
        source = self._import("image_with_alpha.png")
        epid = find_by_type(chunks=source._clrs.chunks, chunk_type="epid")
        blob = probe_media(
            SAMPLES.parent / "assets" / "image_with_alpha.png"
        ).icc_profile
        assert blob is not None
        assert epid.data == icc_profile_id(blob)

    def test_quicktime_records_no_profile(self) -> None:
        """A QuickTime/MP4 names its color space (`empd` + "Rec. 709") from
        data py_aep cannot read yet, so it records none - which is what AE
        writes for an untagged JPEG, and AE fills the name in on open."""
        source = self._import("mov_480.mov")
        clrs = source._clrs
        assert find_by_type(chunks=clrs.chunks, chunk_type="ipws").value == 0
        assert find_by_type(chunks=clrs.chunks, chunk_type="apid").data == b"\xff" * 16
        assert source.media_color_space == "Embedded"

    def test_untagged_jpeg_records_no_profile(self) -> None:
        source = self._import("11_progressive.jpg")
        assert source.media_color_space == "Embedded"

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("gif.gif", "Rec.709 Gamma 2.4"),  # animated
            ("mpeg.mpeg", "Rec.709 Gamma 2.4"),
            ("wmv.wmv", "Rec.709 Gamma 2.4"),
            ("swf.swf", "Rec.709 Gamma 2.4"),
            ("sequence_001.gif", "sRGB IEC61966-2.1"),  # a still of the same format
            ("bmp.bmp", "sRGB IEC61966-2.1"),
        ],
    )
    def test_video_gets_rec709(self, filename: str, expected: str) -> None:
        """AE assigns Rec.709 to the video it decodes itself, and sRGB to a
        still or an image sequence of the same format."""
        _require_profile(expected)
        assert self._import(filename).media_color_space == expected

    def test_tiff_and_psd_embed_the_catalogued_copy(self) -> None:
        """Their importers embed AE's own copy of the profile, not the
        file's bytes - the two differ in the advisory rendering intent."""
        _require_profile("sRGB IEC61966-2.1")
        source = self._import("8bits.tif")
        blob = probe_media(SAMPLES.parent / "assets" / "8bits.tif").icc_profile
        assert blob is not None
        catalogued = default_icc_library().bytes_for("sRGB IEC61966-2.1")
        assert blob != catalogued  # the file's copy differs...
        assert icc_profile_id(blob) == icc_profile_id(catalogued)  # ...but not in id
        epid = find_by_type(chunks=source._clrs.chunks, chunk_type="epid")
        assert epid.data == icc_profile_id(catalogued)

    @pytest.mark.parametrize(
        ("filename", "sequence", "expected"),
        [
            ("11_progressive.jpg", False, LinearLightMode.OFF),
            ("bmp.bmp", False, LinearLightMode.OFF),
            ("gif.gif", False, LinearLightMode.OFF),
            ("mov_480.mov", False, LinearLightMode.OFF),
            ("sequence_001.gif", True, LinearLightMode.ON_FOR_32BPC),
            ("m4a.m4a", False, LinearLightMode.ON_FOR_32BPC),
            ("image_with_alpha.png", False, LinearLightMode.ON_FOR_32BPC),
            ("new_exr.0002.exr", False, LinearLightMode.ON_FOR_32BPC),
        ],
    )
    def test_interpret_as_linear_light_default(
        self, filename: str, sequence: bool, expected: LinearLightMode
    ) -> None:
        """AE turns it off for the formats it decodes through its media
        importers - but not for an audio-only movie or an image sequence."""
        project = parse_aep(SAMPLES / "project" / "emptier.aep").project
        opts = ImportOptions(SAMPLES.parent / "assets" / filename)
        if sequence:
            opts.sequence = True
        item = project.import_file(opts)
        assert item.main_source.interpret_as_linear_light == expected


class TestWritableInterpretation:
    """`pixel_aspect` and `conform_frame_rate` write what AE writes."""

    def _import(self, name: str, sequence: bool = False) -> object:
        project = parse_aep(SAMPLES / "project" / "emptier.aep").project
        opts = ImportOptions(SAMPLES.parent / "assets" / name)
        if sequence:
            opts.sequence = True
        return project.import_file(opts)

    def test_pixel_aspect_is_writable(self) -> None:
        item = self._import("image_with_alpha.png")
        item.pixel_aspect = 1.5
        assert item.pixel_aspect == 1.5
        assert item.main_source._sspc.pixel_aspect_dividend == 3
        assert item.main_source._sspc.pixel_aspect_divisor == 2

    @pytest.mark.parametrize("value", [0.0, -1.0, 0.001, 1000.0])
    def test_pixel_aspect_bounds(self, value: float) -> None:
        """AE accepts 0.01 to 100."""
        item = self._import("image_with_alpha.png")
        with pytest.raises(ValueError):
            item.pixel_aspect = value

    def test_conform_rate_on_a_movie_uses_the_conform_slot(self) -> None:
        item = self._import("mov_480.mov")
        item.main_source.conform_frame_rate = 25.0
        assert item.main_source._sspc.conform_frame_rate == 25.0
        assert item.main_source._sspc.native_frame_rate == 30.0
        assert item.main_source.conform_frame_rate == 25.0

    def test_conform_rate_on_a_sequence_uses_the_native_slot(self) -> None:
        """A sequence has no rate of its own: AE keeps the assumed one as the
        native rate, leaves the conform slot at 0, and rescales the stored
        duration over the new rate."""
        item = self._import("new_exr.0002.exr", sequence=True)
        sspc = item.main_source._sspc
        assert (sspc.native_frame_rate, sspc.duration) == (30.0, pytest.approx(2 / 30))
        item.main_source.conform_frame_rate = 25.0
        assert sspc.conform_frame_rate == 0.0
        assert sspc.native_frame_rate == 25.0
        assert sspc.duration == pytest.approx(2 / 25)
        assert item.main_source.conform_frame_rate == 25.0
        assert item.frame_rate == 25.0

    def test_zero_conform_rate_is_ignored_on_a_sequence(self) -> None:
        item = self._import("new_exr.0002.exr", sequence=True)
        item.main_source.conform_frame_rate = 25.0
        item.main_source.conform_frame_rate = 0.0
        assert item.main_source.conform_frame_rate == 25.0

    def test_zero_conform_rate_clears_it_on_a_movie(self) -> None:
        item = self._import("mov_480.mov")
        item.main_source.conform_frame_rate = 25.0
        item.main_source.conform_frame_rate = 0.0
        assert item.main_source.conform_frame_rate == 0.0
        assert item.frame_rate == 30.0
