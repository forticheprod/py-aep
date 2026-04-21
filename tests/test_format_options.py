"""Tests for OutputModule.format_options parsing."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import parse_project

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

FORMAT_DIR = Path(__file__).parent.parent / "samples" / "models" / "format_options"
CINEON_DIR = FORMAT_DIR / "cineon"
AVI_DIR = FORMAT_DIR / "avi"


def _cineon_opts(name: str) -> CineonFormatOptions:
    """Parse a Cineon sample and return its CineonFormatOptions."""
    project = parse_project(CINEON_DIR / f"{name}.aep")
    opts = project.render_queue.items[0].output_modules[0].format_options
    assert isinstance(opts, CineonFormatOptions)
    return opts


def _avi_opts(name: str) -> XmlFormatOptions:
    """Parse an AVI sample and return its XmlFormatOptions."""
    project = parse_project(AVI_DIR / f"{name}.aep")
    opts = project.render_queue.items[0].output_modules[0].format_options
    assert isinstance(opts, XmlFormatOptions)
    return opts


class TestCineonFormatOptions:
    """Tests for Cineon/DPX format options parsed from Ropt chunks."""

    def test_base_defaults(self) -> None:
        """Base Cineon sample has expected default values."""
        opts = _cineon_opts("base")
        assert opts.ten_bit_black_point == 0
        assert opts.ten_bit_white_point == 1023
        assert opts.converted_black_point == 0.0
        assert opts.converted_white_point == 1.0
        assert opts.current_gamma == 1.0
        assert opts.highlight_expansion == 0
        assert opts.logarithmic_conversion is False
        assert opts.file_format == CineonFileFormat.DPX
        assert opts.bit_depth == 10

    # --- 10-bit black point ---

    def test_10_bit_black_point_1(self) -> None:
        opts = _cineon_opts("10_bit_black_point_1")
        assert opts.ten_bit_black_point == 1

    def test_10_bit_black_point_1023(self) -> None:
        opts = _cineon_opts("10_bit_black_point_1023")
        assert opts.ten_bit_black_point == 1023

    # --- 10-bit white point ---

    def test_10_bit_white_point_0(self) -> None:
        opts = _cineon_opts("10_bit_white_point_0")
        assert opts.ten_bit_white_point == 0

    def test_10_bit_white_point_1021(self) -> None:
        opts = _cineon_opts("10_bit_white_point_1021")
        assert opts.ten_bit_white_point == 1021

    # --- converted black point ---

    def test_converted_black_point_1(self) -> None:
        opts = _cineon_opts("converted_black_point_1")
        assert opts.converted_black_point == pytest.approx(1.0 / 255.0)

    def test_converted_black_point_2(self) -> None:
        opts = _cineon_opts("converted_black_point_2")
        assert opts.converted_black_point == pytest.approx(2.0 / 255.0)

    def test_converted_black_point_255(self) -> None:
        opts = _cineon_opts("converted_black_point_255")
        assert opts.converted_black_point == pytest.approx(1.0)

    # --- converted white point ---

    def test_converted_white_point_0(self) -> None:
        opts = _cineon_opts("converted_white_point_0")
        assert opts.converted_white_point == pytest.approx(0.0)

    def test_converted_white_point_253(self) -> None:
        opts = _cineon_opts("converted_white_point_253")
        assert opts.converted_white_point == pytest.approx(253.0 / 255.0)

    def test_converted_white_point_32767(self) -> None:
        opts = _cineon_opts("converted_white_point_32767")
        assert opts.converted_white_point == pytest.approx(32767.0 / 32768.0)

    def test_converted_white_point_0_987(self) -> None:
        opts = _cineon_opts("converted_white_point_0.987")
        assert opts.converted_white_point == pytest.approx(0.987)

    # --- current gamma ---

    def test_current_gamma_0_01(self) -> None:
        opts = _cineon_opts("current_gamma_0.01")
        assert opts.current_gamma == pytest.approx(0.01)

    def test_current_gamma_1_1(self) -> None:
        opts = _cineon_opts("current_gamma_1.1")
        assert opts.current_gamma == pytest.approx(1.1)

    def test_current_gamma_5(self) -> None:
        opts = _cineon_opts("current_gamma_5")
        assert opts.current_gamma == pytest.approx(5.0)

    # --- logarithmic conversion ---

    def test_logarithmic_conversion_on(self) -> None:
        # Note: filename has typo "logarighmic"
        opts = _cineon_opts("logarighmic_conversion_on")
        assert opts.logarithmic_conversion is True

    def test_logarithmic_conversion_off(self) -> None:
        opts = _cineon_opts("logarighmic_conversion_off")
        assert opts.logarithmic_conversion is False

    # --- file format and bit depth ---

    def test_file_format_dpx_8(self) -> None:
        opts = _cineon_opts("file_format_dpx_8")
        assert opts.file_format == CineonFileFormat.DPX
        assert opts.bit_depth == 8

    def test_file_format_dpx_10(self) -> None:
        opts = _cineon_opts("file_format_dpx_10")
        assert opts.file_format == CineonFileFormat.DPX
        assert opts.bit_depth == 10

    def test_file_format_dpx_12(self) -> None:
        opts = _cineon_opts("file_format_dpx_12")
        assert opts.file_format == CineonFileFormat.DPX
        assert opts.bit_depth == 12

    def test_file_format_dpx_16(self) -> None:
        opts = _cineon_opts("file_format_dpx_16")
        assert opts.file_format == CineonFileFormat.DPX
        assert opts.bit_depth == 16

    def test_file_format_fido(self) -> None:
        """FIDO/Cineon 4.5 format."""
        opts = _cineon_opts("file_format_fido")
        assert opts.file_format == CineonFileFormat.FIDO_CINEON

    # --- highlight expansion ---

    def test_highlight_expansion_0(self) -> None:
        opts = _cineon_opts("highlight_expansion_0")
        assert opts.highlight_expansion == 0

    def test_highlight_expansion_1(self) -> None:
        opts = _cineon_opts("highlight_expansion_1")
        assert opts.highlight_expansion == 1

    def test_highlight_expansion_150(self) -> None:
        opts = _cineon_opts("highlight_expansion_150")
        assert opts.highlight_expansion == 150


class TestAviFormatOptions:
    """Tests for AVI format options parsed from Ropt chunks (now XmlFormatOptions)."""

    def test_base_defaults(self) -> None:
        """AVI base sample has expected default values."""
        opts = _avi_opts("base")
        assert opts.format_code == ".AVI"
        assert opts.video_codec == VideoCodec.NONE
        assert opts.audio_codec == AudioCodec.UNCOMPRESSED
        assert opts.frame_rate == 24.0
        assert "ADBEVideoCodec" in opts.params
        assert "ADBEVideoQuality" in opts.params
        assert "ADBEVideoWidth" in opts.params
        assert "ADBEVideoHeight" in opts.params

    # --- video codecs ---

    def test_video_codec_dv_24p_advanced(self) -> None:
        """DV 24p Advanced codec maps to VideoCodec.DV_24P."""
        opts = _avi_opts("video_codec_dv_24p_advanced")
        assert opts.video_codec == VideoCodec.DV_24P

    def test_video_codec_dv_ntsc(self) -> None:
        """DV NTSC codec maps to VideoCodec.DV_NTSC."""
        opts = _avi_opts("video_codec_dv_ntsc")
        assert opts.video_codec == VideoCodec.DV_NTSC

    def test_video_codec_dv_pal(self) -> None:
        """DV PAL codec maps to VideoCodec.DV_PAL."""
        opts = _avi_opts("video_codec_dv_pal")
        assert opts.video_codec == VideoCodec.DV_PAL

    def test_video_codec_intel_iyuv(self) -> None:
        """Intel IYUV codec maps to VideoCodec.INTEL_IYUV."""
        opts = _avi_opts("video_codec_intel_iyuv_codec")
        assert opts.video_codec == VideoCodec.INTEL_IYUV

    def test_video_codec_uyvy_422(self) -> None:
        """Uncompressed UYVY 422 8bit maps to VideoCodec.UYVY."""
        opts = _avi_opts("video_codec_uncompressed_uyvy_422_8bit")
        assert opts.video_codec == VideoCodec.UYVY

    def test_video_codec_v210(self) -> None:
        """V210 10-bit YUV maps to VideoCodec.V210."""
        opts = _avi_opts("video_codec_v210_10-bit_yuv")
        assert opts.video_codec == VideoCodec.V210

    # --- audio interleave ---

    def test_audio_interleave_none(self) -> None:
        """Audio interleave 'None' has no ADBEAudioInterleave param."""
        opts = _avi_opts("audio_interleave_none")
        assert opts.params.get("ADBEAudioInterleave") is None

    def test_audio_interleave_1_frame(self) -> None:
        opts = _avi_opts("audio_interleave_1_frame")
        assert opts.params["ADBEAudioInterleave"] == "1"

    def test_audio_interleave_half_second(self) -> None:
        opts = _avi_opts("audio_interleave_half_second")
        assert opts.params["ADBEAudioInterleave"] == "2"

    def test_audio_interleave_1_second(self) -> None:
        opts = _avi_opts("audio_interleave_1_second")
        assert opts.params["ADBEAudioInterleave"] == "3"

    def test_audio_interleave_2_seconds(self) -> None:
        opts = _avi_opts("audio_interleave2_seconds")
        assert opts.params["ADBEAudioInterleave"] == "4"


class TestFormatOptionsNone:
    """Test that formats without Ropt parsing return None."""

    def test_no_ropt_returns_none(self) -> None:
        """A format that doesn't have Ropt (or uses unsupported format)
        should return None for format_options."""
        samples_dir = Path(__file__).parent.parent / "samples" / "models"
        rq_base = samples_dir / "renderqueue" / "base.aep"
        project = parse_project(rq_base)
        om = project.render_queue.items[0].output_modules[0]
        assert om.format_options is None or isinstance(
            om.format_options,
            (
                CineonFormatOptions,
                JpegFormatOptions,
                OpenExrFormatOptions,
                PngFormatOptions,
                TargaFormatOptions,
                TiffFormatOptions,
                XmlFormatOptions,
            ),
        )


def _format_opts(fmt_dir: str, name: str = "base") -> XmlFormatOptions:
    """Parse a sample from the given format dir and return XmlFormatOptions."""
    project = parse_project(FORMAT_DIR / fmt_dir / f"{name}.aep")
    opts = project.render_queue.items[0].output_modules[0].format_options
    assert isinstance(opts, XmlFormatOptions)
    return opts


class TestH264FormatOptions:
    """Tests for H.264 format options (XML-based)."""

    def test_base_defaults(self) -> None:
        """Base H.264 sample has expected default values."""
        opts = _format_opts("h.264")
        assert opts.format_code == "H264"
        assert opts.video_codec == VideoCodec.AVC1
        assert opts.audio_codec == AudioCodec.AAC
        assert opts.frame_rate == 24.0
        assert len(opts.params) > 0
        assert opts.mpeg_audio_format == MPEGAudioFormat.AAC
        assert opts.mpeg_multiplexer == MPEGMultiplexer.MP4
        assert opts.mpeg_mux_stream_compatibility == MPEGMuxStreamCompatibility.STD

    def test_audio_format_mpeg(self) -> None:
        """MPEG audio format sample has MPEG format and layer I."""
        project = parse_project(FORMAT_DIR / "h.264" / "audio_format_mpeg.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, XmlFormatOptions)
        assert opts.mpeg_audio_format == MPEGAudioFormat.MPEG
        assert opts.params["ADBEMPEGAudioLayer"] == "1"

    def test_mpeg_audio_layer_ii(self) -> None:
        project = parse_project(FORMAT_DIR / "h.264" / "audio_format_mpeg_layer_II.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, XmlFormatOptions)
        assert opts.params["ADBEMPEGAudioLayer"] == "2"

    def test_mpeg_audio_format_pcm(self) -> None:
        """PCM audio format sample."""
        opts = _format_opts("h.264", "audio_format_pcm")
        assert opts.mpeg_audio_format == MPEGAudioFormat.PCM

    def test_multiplexer_3gpp(self) -> None:
        opts = _format_opts("h.264", "multiplexer_3gpp")
        assert opts.mpeg_multiplexer == MPEGMultiplexer.THREEGPP

    def test_multiplexer_none(self) -> None:
        opts = _format_opts("h.264", "multiplexer_none")
        assert opts.mpeg_multiplexer == MPEGMultiplexer.NONE

    def test_audio_codec_aac_plus_v1(self) -> None:
        opts = _format_opts("h.264", "audio_codec_aac+_version_1")
        assert opts.audio_codec == AudioCodec.AAC_PLUS_V1

    def test_audio_codec_aac_plus_v2(self) -> None:
        opts = _format_opts("h.264", "audio_codec_aac+_version_2")
        assert opts.audio_codec == AudioCodec.AAC_PLUS_V2

    def test_stream_compat_ipod(self) -> None:
        opts = _format_opts("h.264", "stream_compat_ipod")
        assert opts.mpeg_mux_stream_compatibility == MPEGMuxStreamCompatibility.IPOD

    def test_stream_compat_psp(self) -> None:
        opts = _format_opts("h.264", "stream_compat_psp")
        assert opts.mpeg_mux_stream_compatibility == MPEGMuxStreamCompatibility.PSP


class TestMp3FormatOptions:
    """Tests for MP3 format options (XML-based)."""

    def test_base_defaults(self) -> None:
        """MP3 base sample has expected default values."""
        opts = _format_opts("mp3")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.format_code == "Mp3 "
        assert opts.video_codec is None
        assert opts.frame_rate is None
        assert opts.audio_codec == AudioCodec.UNCOMPRESSED
        assert len(opts.params) > 0


class TestQuickTimeFormatOptions:
    """Tests for QuickTime format options (XML-based)."""

    def test_base_defaults(self) -> None:
        """QuickTime base sample has expected default values."""
        opts = _format_opts("quicktime")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.format_code == "MooV"
        assert opts.video_codec == VideoCodec.ANIMATION
        assert opts.frame_rate == 24.0
        assert opts.audio_codec is None
        assert opts.mpeg_audio_format is None
        assert opts.mpeg_multiplexer == MPEGMultiplexer.MP4
        assert opts.mpeg_mux_stream_compatibility == MPEGMuxStreamCompatibility.STD
        assert len(opts.params) > 0

    def test_video_codec_apple_prores_422(self) -> None:
        opts = _format_opts("quicktime", "apple_prores_422")
        assert opts.video_codec == VideoCodec.APPLE_PRORES_422

    def test_video_codec_apple_prores_422_hq(self) -> None:
        opts = _format_opts("quicktime", "apple_prores_422_hq")
        assert opts.video_codec == VideoCodec.APPLE_PRORES_422_HQ

    def test_video_codec_apple_prores_422_lt(self) -> None:
        opts = _format_opts("quicktime", "apple_prores_422_lt")
        assert opts.video_codec == VideoCodec.APPLE_PRORES_422_LT

    def test_video_codec_apple_prores_422_proxy(self) -> None:
        opts = _format_opts("quicktime", "apple_prores_422_proxy")
        assert opts.video_codec == VideoCodec.APPLE_PRORES_422_PROXY

    def test_video_codec_apple_prores_4444(self) -> None:
        opts = _format_opts("quicktime", "apple_prores_4444")
        assert opts.video_codec == VideoCodec.APPLE_PRORES_4444

    def test_video_codec_apple_prores_4444_xq(self) -> None:
        opts = _format_opts("quicktime", "apple_prores_4444_xq")
        assert opts.video_codec == VideoCodec.APPLE_PRORES_4444_XQ

    def test_video_codec_dnxhr_dnxhd(self) -> None:
        opts = _format_opts("quicktime", "dnxhr_dnxhd")
        assert opts.video_codec == VideoCodec.DNXHR_DNXHD

    def test_video_codec_dv25_ntsc(self) -> None:
        opts = _format_opts("quicktime", "dv25_ntsc")
        assert opts.video_codec == VideoCodec.DV25_NTSC

    def test_video_codec_dv25_ntsc_24p(self) -> None:
        opts = _format_opts("quicktime", "dv25_ntsc_24p")
        assert opts.video_codec == VideoCodec.DV25_NTSC_24P

    def test_video_codec_dv25_pal(self) -> None:
        opts = _format_opts("quicktime", "dv25_pal")
        assert opts.video_codec == VideoCodec.DV25_PAL

    def test_video_codec_dv50_ntsc(self) -> None:
        opts = _format_opts("quicktime", "dv50_ntsc")
        assert opts.video_codec == VideoCodec.DV50_NTSC

    def test_video_codec_dv50_pal(self) -> None:
        opts = _format_opts("quicktime", "dv50_pal")
        assert opts.video_codec == VideoCodec.DV50_PAL

    def test_video_codec_dvcpro_hd_1080i50(self) -> None:
        opts = _format_opts("quicktime", "dvcpro_hd_1080i50")
        assert opts.video_codec == VideoCodec.DVCPRO_HD_1080I50

    def test_video_codec_dvcpro_hd_1080i60(self) -> None:
        opts = _format_opts("quicktime", "dvcpro_hd_1080i60")
        assert opts.video_codec == VideoCodec.DVCPRO_HD_1080I60

    def test_video_codec_dvcpro_hd_1080p25(self) -> None:
        opts = _format_opts("quicktime", "dvcpro_hd_1080p25")
        assert opts.video_codec == VideoCodec.DVCPRO_HD_1080P25

    def test_video_codec_dvcpro_hd_1080p30(self) -> None:
        opts = _format_opts("quicktime", "dvcpro_hd_1080p30")
        assert opts.video_codec == VideoCodec.DVCPRO_HD_1080P30

    def test_video_codec_dvcpro_hd_720p50(self) -> None:
        opts = _format_opts("quicktime", "dvcpro_hd_720p50")
        assert opts.video_codec == VideoCodec.DVCPRO_HD_720P50

    def test_video_codec_dvcpro_hd_720p60(self) -> None:
        opts = _format_opts("quicktime", "dvcpro_hd_720p60")
        assert opts.video_codec == VideoCodec.DVCPRO_HD_720P60

    def test_video_codec_gopro_cineform(self) -> None:
        opts = _format_opts("quicktime", "gopro_cineform")
        assert opts.video_codec == VideoCodec.GOPRO_CINEFORM

    def test_video_codec_h264(self) -> None:
        opts = _format_opts("quicktime", "h.264")
        assert opts.video_codec == VideoCodec.AVC1

    def test_video_codec_none_uncompressed_rgb(self) -> None:
        opts = _format_opts("quicktime", "none_uncompressed_rgb_8-bit")
        assert opts.video_codec == VideoCodec.UNCOMPRESSED_RGB_8_BIT

    def test_video_codec_uncompressed_yuv_10_bit(self) -> None:
        opts = _format_opts("quicktime", "uncompressed_yuv_10_bit_422")
        assert opts.video_codec == VideoCodec.UNCOMPRESSED_YUV_10_BIT_422

    def test_video_codec_uncompressed_yuv_8_bit(self) -> None:
        opts = _format_opts("quicktime", "uncompressed_yuv_8_bit_422")
        assert opts.video_codec == VideoCodec.UNCOMPRESSED_YUV_8_BIT_422


class TestWavFormatOptions:
    """Tests for WAV format options (XML-based)."""

    def test_base_defaults(self) -> None:
        """WAV base sample has expected default values."""
        opts = _format_opts("wav")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.format_code == "wao_"
        assert opts.video_codec is None
        assert opts.frame_rate is None
        assert opts.audio_codec == AudioCodec.UNCOMPRESSED
        assert len(opts.params) > 0

    def test_audio_codec_ima_adpcm(self) -> None:
        opts = _format_opts("wav", "audio_codec_ima_adpcm")
        assert opts.audio_codec == AudioCodec.IMA_ADPCM

    def test_audio_codec_microsoft_adpcm(self) -> None:
        opts = _format_opts("wav", "audio_codec_microsoft_adpcm")
        assert opts.audio_codec == AudioCodec.MICROSOFT_ADPCM

    def test_audio_codec_ccitt_a_law(self) -> None:
        opts = _format_opts("wav", "audio_codec_ccitt_a-law")
        assert opts.audio_codec == AudioCodec.CCITT_A_LAW

    def test_audio_codec_ccitt_u_law(self) -> None:
        opts = _format_opts("wav", "audio_codec_ccitt_u-law")
        assert opts.audio_codec == AudioCodec.CCITT_U_LAW

    def test_audio_codec_gsm_6_10(self) -> None:
        opts = _format_opts("wav", "audio_codec_gsm_6.10")
        assert opts.audio_codec == AudioCodec.GSM_6_10


class TestJpegFormatOptions:
    """Tests for JPEG format options."""

    def _opts(self, stem: str) -> JpegFormatOptions:
        project = parse_project(FORMAT_DIR / "jpeg" / f"{stem}.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, JpegFormatOptions)
        return opts

    def test_base_defaults(self) -> None:
        opts = self._opts("base")
        assert opts.quality == 5
        assert opts.scans == 3

    def test_quality_0(self) -> None:
        assert self._opts("quality_0").quality == 0

    def test_quality_10(self) -> None:
        assert self._opts("quality_10").quality == 10

    def test_baseline_standard(self) -> None:
        assert (
            self._opts("baseline_standard").format_type
            == JpegFormatType.BASELINE_STANDARD
        )

    def test_baseline_optimized(self) -> None:
        assert (
            self._opts("baseline_optimized").format_type
            == JpegFormatType.BASELINE_OPTIMIZED
        )

    def test_progressive_3(self) -> None:
        opts = self._opts("progressive_3")
        assert opts.format_type == JpegFormatType.PROGRESSIVE
        assert opts.scans == 3

    def test_scans_4(self) -> None:
        assert self._opts("progressive_4").scans == 4

    def test_scans_5(self) -> None:
        assert self._opts("progressive_5").scans == 5

    def test_scans_non_progressive(self) -> None:
        assert self._opts("baseline_standard").scans == 3


class TestOpenExrFormatOptions:
    """Tests for OpenEXR format options."""

    def test_base_defaults(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "base.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.ZIP
        assert opts.luminance_chroma is False
        assert opts.thirty_two_bit_float is False
        assert opts.dwa_compression_level is None

    def test_compression_none(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_none.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.NONE

    def test_compression_rle(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_rle.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.RLE

    def test_compression_zip16(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_zip16.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.ZIP16

    def test_compression_piz(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_piz.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.PIZ

    def test_compression_pxr24(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_pxr24.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.PXR24

    def test_compression_b44(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_b44.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.B44

    def test_compression_b44a(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_b44a.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.B44A

    def test_compression_dwaa(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_dwaa_45.0.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.DWAA
        assert opts.dwa_compression_level == 45.0

    def test_compression_dwab(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_dwab_200.0.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression == OpenExrCompression.DWAB
        assert opts.dwa_compression_level == 200.0

    def test_luminance_chroma_on(self) -> None:
        project = parse_project(
            FORMAT_DIR / "openexr" / "compression_zip_luminance_chroma.aep"
        )
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.luminance_chroma is True

    def test_32_bit_float_on(self) -> None:
        project = parse_project(
            FORMAT_DIR / "openexr" / "compression_zip_32_bit_float.aep"
        )
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.thirty_two_bit_float is True

    def test_dwa_compression_level_dwaa_custom(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_dwaa_1.0.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.dwa_compression_level == 1.0

    def test_dwa_compression_level_dwaa_large(self) -> None:
        project = parse_project(
            FORMAT_DIR / "openexr" / "compression_dwaa_10000000000.0.aep"
        )
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.dwa_compression_level == 10000000000.0

    def test_dwa_compression_level_dwab(self) -> None:
        project = parse_project(FORMAT_DIR / "openexr" / "compression_dwab_200.0.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.dwa_compression_level == 200.0


class TestPngFormatOptions:
    """Tests for PNG format options (typed binary)."""

    def test_base_defaults(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "base.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.width == 1920
        assert opts.height == 1080
        assert opts.bit_depth == 16
        assert opts.include_hdr10_metadata is False
        assert opts.luminance_min is None
        assert opts.luminance_max is None
        assert opts.content_light_max is None
        assert opts.content_light_average is None

    def test_compression_none(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "compression_none.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.compression == PngCompression.NONE

    def test_compression_interlaced(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "compression_interlaced.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.compression == PngCompression.INTERLACED

    def test_include_hdr10_metadata_on(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "include_hdr10_metadata_on.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.include_hdr10_metadata is True
        assert opts.color_primaries == Hdr10ColorPrimaries.P3_D65

    def test_color_primaries_rec709(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "color_primaries_rec709.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.color_primaries == Hdr10ColorPrimaries.REC709

    def test_color_primaries_rec2020(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "color_primaries_rec2020.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.color_primaries == Hdr10ColorPrimaries.REC2020

    def test_color_primaries_p3d65(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "color_primaries_p3d65.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.color_primaries == Hdr10ColorPrimaries.P3_D65

    def test_luminance_min_zero(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "luminance_min_0.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.luminance_min == 0.0

    def test_luminance_max_set(self) -> None:
        project = parse_project(FORMAT_DIR / "png" / "luminance_max_1.797693e+308.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.luminance_max == 1.7976931348623157e308

    def test_content_light_max_set(self) -> None:
        project = parse_project(
            FORMAT_DIR / "png" / "content_light_levels_maximum_1.797693e+308.aep"
        )
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.content_light_max == 1.7976931348623157e308

    def test_content_light_average_set(self) -> None:
        project = parse_project(
            FORMAT_DIR / "png" / "content_light_levels_average_1.797693e+308.aep"
        )
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, PngFormatOptions)
        assert opts.content_light_average == 1.7976931348623157e308


class TestTargaFormatOptions:
    """Tests for Targa format options (binary)."""

    def test_base_defaults(self) -> None:
        project = parse_project(FORMAT_DIR / "targa" / "base.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, TargaFormatOptions)
        assert opts.bits_per_pixel == 32
        assert opts.rle_compression is False

    def test_24_bits_per_pixel(self) -> None:
        project = parse_project(FORMAT_DIR / "targa" / "24_bits_per_pixel.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, TargaFormatOptions)
        assert opts.bits_per_pixel == 24

    def test_32_bits_per_pixel(self) -> None:
        project = parse_project(FORMAT_DIR / "targa" / "32_bits_per_pixel.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, TargaFormatOptions)
        assert opts.bits_per_pixel == 32

    def test_rle_compression_on(self) -> None:
        project = parse_project(FORMAT_DIR / "targa" / "rle_compression_on.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, TargaFormatOptions)
        assert opts.rle_compression is True
        assert opts.bits_per_pixel == 24


class TestTiffFormatOptions:
    """Tests for TIFF format options."""

    def test_base_defaults(self) -> None:
        project = parse_project(FORMAT_DIR / "tiff" / "base.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, TiffFormatOptions)
        assert opts.lzw_compression is False
        assert opts.ibm_pc_byte_order is False

    def test_lzw_compression_on(self) -> None:
        project = parse_project(FORMAT_DIR / "tiff" / "lze_compression_on.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, TiffFormatOptions)
        assert opts.lzw_compression is True
        assert opts.ibm_pc_byte_order is False

    def test_ibm_pc_byte_order_on(self) -> None:
        project = parse_project(FORMAT_DIR / "tiff" / "ibm_pc_byte_order_on.aep")
        opts = project.render_queue.items[0].output_modules[0].format_options
        assert isinstance(opts, TiffFormatOptions)
        assert opts.ibm_pc_byte_order is True
        assert opts.lzw_compression is False


# ---------------------------------------------------------------------------
# Roundtrip tests (parse -> modify -> save -> re-parse -> assert)
# ---------------------------------------------------------------------------


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
