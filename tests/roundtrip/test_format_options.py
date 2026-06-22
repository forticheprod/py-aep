"""Tests for OutputModule.format_options parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse
from py_aep.enums import (
    AudioCodec,
    CineonFileFormat,
    Hdr10ColorPrimaries,
    JpegFormatType,
    MPEGAudioFormat,
    MPEGMultiplexer,
    MPEGMuxStreamCompatibility,
    OpenExrCompression,
    PngCompression,
    VideoCodec,
)
from py_aep.models.renderqueue.format_options import (
    CineonFormatOptions,
    JpegFormatOptions,
    OpenExrFormatOptions,
    PngFormatOptions,
    TargaFormatOptions,
    TiffFormatOptions,
    XmlFormatOptions,
)

FORMAT_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "format_options"
)
CINEON_DIR = FORMAT_DIR / "cineon"
AVI_DIR = FORMAT_DIR / "avi"


def _parse_fresh(path: Path) -> tuple:
    """Parse without caching and return (project, format_options)."""
    project = parse(path).project
    opts = project.render_queue.items[0].output_modules[0].format_options
    return project, opts


class TestRoundtripTargaFormatOptions:
    """Roundtrip tests for TargaFormatOptions."""

    def test_modify_bits_per_pixel(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "targa" / "base.aep")
        assert isinstance(opts, TargaFormatOptions)
        assert opts.bits_per_pixel == 32
        opts.bits_per_pixel = 24
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, TargaFormatOptions)
        assert opts2.bits_per_pixel == 24

    def test_modify_rle_compression(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "targa" / "base.aep")
        assert isinstance(opts, TargaFormatOptions)
        assert opts.rle_compression is False
        opts.rle_compression = True
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, TargaFormatOptions)
        assert opts2.rle_compression is True

    def test_validate_bits_per_pixel(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "targa" / "base.aep")
        assert isinstance(opts, TargaFormatOptions)
        with pytest.raises(ValueError):
            opts.bits_per_pixel = 16


class TestRoundtripTiffFormatOptions:
    """Roundtrip tests for TiffFormatOptions."""

    def test_modify_lzw_compression(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "tiff" / "base.aep")
        assert isinstance(opts, TiffFormatOptions)
        assert opts.lzw_compression is False
        opts.lzw_compression = True
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, TiffFormatOptions)
        assert opts2.lzw_compression is True

    def test_modify_ibm_pc_byte_order(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "tiff" / "base.aep")
        assert isinstance(opts, TiffFormatOptions)
        assert opts.ibm_pc_byte_order is False
        opts.ibm_pc_byte_order = True
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, TiffFormatOptions)
        assert opts2.ibm_pc_byte_order is True


class TestRoundtripJpegFormatOptions:
    """Roundtrip tests for JpegFormatOptions."""

    def test_modify_quality(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "jpeg" / "base.aep")
        assert isinstance(opts, JpegFormatOptions)
        opts.quality = 10
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, JpegFormatOptions)
        assert opts2.quality == 10

    def test_modify_format_type(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "jpeg" / "base.aep")
        assert isinstance(opts, JpegFormatOptions)
        opts.format_type = JpegFormatType.PROGRESSIVE
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, JpegFormatOptions)
        assert opts2.format_type == JpegFormatType.PROGRESSIVE

    def test_modify_scans(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "jpeg" / "progressive_3.aep")
        assert isinstance(opts, JpegFormatOptions)
        assert opts.scans == 3
        opts.scans = 5
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, JpegFormatOptions)
        assert opts2.scans == 5

    def test_validate_quality_too_high(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "jpeg" / "base.aep")
        assert isinstance(opts, JpegFormatOptions)
        with pytest.raises(ValueError):
            opts.quality = 11

    def test_validate_scans_invalid(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "jpeg" / "progressive_3.aep")
        assert isinstance(opts, JpegFormatOptions)
        with pytest.raises(ValueError):
            opts.scans = 2


class TestRoundtripCineonFormatOptions:
    """Roundtrip tests for CineonFormatOptions."""

    def test_modify_ten_bit_black_point(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        opts.ten_bit_black_point = 100
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, CineonFormatOptions)
        assert opts2.ten_bit_black_point == 100

    def test_modify_logarithmic_conversion(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        assert opts.logarithmic_conversion is False
        opts.logarithmic_conversion = True
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, CineonFormatOptions)
        assert opts2.logarithmic_conversion is True

    def test_modify_file_format(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        opts.file_format = CineonFileFormat.FIDO_CINEON
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, CineonFormatOptions)
        assert opts2.file_format == CineonFileFormat.FIDO_CINEON

    def test_modify_bit_depth(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        opts.bit_depth = 8
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, CineonFormatOptions)
        assert opts2.bit_depth == 8

    def test_validate_bit_depth_rejects_invalid(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        with pytest.raises(ValueError):
            opts.bit_depth = 9

    def test_validate_ten_bit_black_point_rejects_negative(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        with pytest.raises(ValueError):
            opts.ten_bit_black_point = -1

    def test_validate_ten_bit_black_point_rejects_too_high(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        with pytest.raises(ValueError):
            opts.ten_bit_black_point = 1024


class TestRoundtripOpenExrFormatOptions:
    """Roundtrip tests for OpenExrFormatOptions."""

    def test_modify_compression(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "openexr" / "base.aep")
        assert isinstance(opts, OpenExrFormatOptions)
        opts.compression = OpenExrCompression.RLE
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, OpenExrFormatOptions)
        assert opts2.compression == OpenExrCompression.RLE

    def test_modify_luminance_chroma(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "openexr" / "base.aep")
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.luminance_chroma is False
        opts.luminance_chroma = True
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, OpenExrFormatOptions)
        assert opts2.luminance_chroma is True

    def test_modify_thirty_two_bit_float(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "openexr" / "base.aep")
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.thirty_two_bit_float is False
        opts.thirty_two_bit_float = True
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, OpenExrFormatOptions)
        assert opts2.thirty_two_bit_float is True

    def test_modify_dwa_compression_level(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(
            FORMAT_DIR / "openexr" / "compression_dwaa_45.0.aep"
        )
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.dwa_compression_level == 45.0
        opts.dwa_compression_level = 100.0
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, OpenExrFormatOptions)
        assert opts2.dwa_compression_level == 100.0


class TestRoundtripPngFormatOptions:
    """Roundtrip tests for PngFormatOptions binary fields."""

    def test_modify_bit_depth(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "png" / "base.aep")
        assert isinstance(opts, PngFormatOptions)
        assert opts.bit_depth == 16
        opts.bit_depth = 8
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.bit_depth == 8

    def test_modify_compression(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "png" / "compression_none.aep")
        assert isinstance(opts, PngFormatOptions)
        assert opts.compression == PngCompression.NONE
        opts.compression = PngCompression.INTERLACED
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.compression == PngCompression.INTERLACED

    def test_width_read_only(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "png" / "base.aep")
        assert isinstance(opts, PngFormatOptions)
        with pytest.raises(AttributeError):
            opts.width = 3840

    def test_height_read_only(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "png" / "base.aep")
        assert isinstance(opts, PngFormatOptions)
        with pytest.raises(AttributeError):
            opts.height = 2160

    def test_bit_depth_rejects_invalid(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "png" / "base.aep")
        assert isinstance(opts, PngFormatOptions)
        with pytest.raises(ValueError, match="must be one of"):
            opts.bit_depth = 24

    def test_bit_depth_accepts_valid(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "png" / "base.aep")
        assert isinstance(opts, PngFormatOptions)
        for depth in (8, 16, 32):
            opts.bit_depth = depth
            assert opts.bit_depth == depth


class TestRoundtripPngHdr10:
    """Roundtrip tests for PngFormatOptions HDR10 metadata fields."""

    def test_modify_include_hdr10_metadata(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(
            FORMAT_DIR / "png" / "include_hdr10_metadata_on.aep"
        )
        assert isinstance(opts, PngFormatOptions)
        assert opts.include_hdr10_metadata is True
        opts.include_hdr10_metadata = False
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.include_hdr10_metadata is False

    def test_modify_color_primaries(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(
            FORMAT_DIR / "png" / "include_hdr10_metadata_on.aep"
        )
        assert isinstance(opts, PngFormatOptions)
        opts.color_primaries = Hdr10ColorPrimaries.REC709
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.color_primaries == Hdr10ColorPrimaries.REC709

    def test_modify_luminance_min(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(
            FORMAT_DIR / "png" / "include_hdr10_metadata_on.aep"
        )
        assert isinstance(opts, PngFormatOptions)
        opts.luminance_min = 0.1
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.luminance_min == 0.1

    def test_modify_luminance_max(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(
            FORMAT_DIR / "png" / "include_hdr10_metadata_on.aep"
        )
        assert isinstance(opts, PngFormatOptions)
        opts.luminance_max = 1000.0
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.luminance_max == 1000.0

    def test_modify_content_light_max(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(
            FORMAT_DIR / "png" / "include_hdr10_metadata_on.aep"
        )
        assert isinstance(opts, PngFormatOptions)
        opts.content_light_max = 500.0
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.content_light_max == 500.0

    def test_modify_content_light_average(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(
            FORMAT_DIR / "png" / "include_hdr10_metadata_on.aep"
        )
        assert isinstance(opts, PngFormatOptions)
        opts.content_light_average = 250.0
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.content_light_average == 250.0

    def test_clear_luminance_min(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "png" / "luminance_min_0.aep")
        assert isinstance(opts, PngFormatOptions)
        assert opts.luminance_min is not None
        opts.luminance_min = None
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, PngFormatOptions)
        assert opts2.luminance_min is None


class TestRoundtripXmlFormatOptions:
    """Roundtrip tests for XmlFormatOptions."""

    def test_modify_video_codec(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "avi" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.video_codec == VideoCodec.NONE
        opts.video_codec = VideoCodec.DV_NTSC
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.video_codec == VideoCodec.DV_NTSC

    def test_modify_audio_codec(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.audio_codec == AudioCodec.AAC
        opts.audio_codec = AudioCodec.AAC_PLUS_V1
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.audio_codec == AudioCodec.AAC_PLUS_V1

    def test_modify_frame_rate(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.frame_rate == 24.0
        opts.frame_rate = 30.0
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.frame_rate == 30.0

    def test_modify_mpeg_multiplexer(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.mpeg_multiplexer == MPEGMultiplexer.MP4
        opts.mpeg_multiplexer = MPEGMultiplexer.THREEGPP
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.mpeg_multiplexer == MPEGMultiplexer.THREEGPP

    def test_modify_mpeg_audio_format(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.mpeg_audio_format == MPEGAudioFormat.AAC
        opts.mpeg_audio_format = MPEGAudioFormat.PCM
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.mpeg_audio_format == MPEGAudioFormat.PCM

    def test_modify_mpeg_mux_stream_compatibility(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.mpeg_mux_stream_compatibility == MPEGMuxStreamCompatibility.STD
        opts.mpeg_mux_stream_compatibility = MPEGMuxStreamCompatibility.IPOD
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.mpeg_mux_stream_compatibility == MPEGMuxStreamCompatibility.IPOD

    def test_format_code_read_only(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "avi" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        with pytest.raises(AttributeError):
            opts.format_code = "H264"  # type: ignore[misc]

    def test_set_none_is_noop(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "avi" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        original = opts.video_codec
        opts.video_codec = None
        assert opts.video_codec == original

    def test_settings_view_format_code_read_only(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "h.264" / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        with pytest.raises(AttributeError):
            opts.settings["Format Code"] = "MooV"
