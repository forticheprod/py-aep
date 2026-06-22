"""Tests for media-file probing and file-source creation via import_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.resolvers.media_probe import probe_media

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"
BASE = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "folder" / "folder.aep"
)
IMPORT_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "import"


class TestMediaProbe:
    """Media-header probing matches the values AE reads on import."""

    @pytest.mark.parametrize(
        "name,width,height,has_alpha",
        [
            ("image_with_alpha.png", 640, 346, True),
            ("8bits_compressed.png", 25, 26, True),
            ("8bits.tif", 25, 26, True),
            ("8bits_transparency.tif", 25, 26, True),
            ("11_progressive.jpg", 25, 26, False),
            ("tga_16.tga", 25, 26, False),
            ("tga_24.tga", 25, 26, False),
            ("tga_32.tga", 25, 26, True),
            ("bmp.bmp", 25, 26, True),
            ("sequence_001.gif", 146, 93, True),
            ("8bits.psd", 25, 26, True),
            ("8bits.psb", 25, 26, True),
        ],
    )
    def test_still_image(
        self, name: str, width: int, height: int, has_alpha: bool
    ) -> None:
        info = probe_media(ASSETS / name)
        assert info.width == width
        assert info.height == height
        assert info.has_alpha is has_alpha
        assert info.duration == 0.0

    @pytest.mark.parametrize(
        "name,width,height,has_alpha",
        [
            ("new_exr.0002.exr", 2356, 1002, False),
            ("old_exr.00004.exr", 2356, 1002, True),
        ],
    )
    def test_exr(self, name: str, width: int, height: int, has_alpha: bool) -> None:
        info = probe_media(ASSETS / name)
        assert (info.width, info.height) == (width, height)
        assert info.has_alpha is has_alpha

    @pytest.mark.parametrize("name", ["8bits.psd", "8bits.psb"])
    def test_psd_metadata(self, name: str) -> None:
        info = probe_media(ASSETS / name)
        assert (info.width, info.height) == (25, 26)
        assert info.bit_depth == 8
        assert info.layer_count == 2

    def test_wav(self) -> None:
        info = probe_media(ASSETS / "wav.wav")
        assert info.width == 0 and info.height == 0
        assert info.has_audio is True
        assert info.audio_sample_rate == 44100.0
        assert info.duration == pytest.approx(5.9431746, abs=1e-4)

    @pytest.mark.parametrize(
        "name,width,height,fps,has_audio,has_alpha,pixel_aspect",
        [
            ("mov_480.mov", 480, 270, 30.0, True, False, 1.0),
            ("mov_23_976.mov", 480, 270, 23.976, True, False, 1.0),
            ("mov_23_976_no_audio.mov", 480, 270, 23.976, False, False, 1.0),
            ("mov_alpha_small.mov", 320, 240, 25.0, False, True, 1.33333),
        ],
    )
    def test_mov(
        self,
        name: str,
        width: int,
        height: int,
        fps: float,
        has_audio: bool,
        has_alpha: bool,
        pixel_aspect: float,
    ) -> None:
        info = probe_media(ASSETS / name)
        assert (info.width, info.height) == (width, height)
        assert info.frame_rate == pytest.approx(fps, abs=1e-3)
        assert info.has_audio is has_audio
        assert info.has_alpha is has_alpha
        assert info.pixel_aspect == pytest.approx(pixel_aspect, abs=1e-4)

    def test_m4v(self) -> None:
        # MP4 video shares the QuickTime atom tree, so _probe_mov parses it.
        info = probe_media(ASSETS / "m4v.m4v")
        assert (info.width, info.height) == (640, 360)
        assert info.frame_rate == pytest.approx(29.97, abs=1e-3)
        assert info.has_audio is False
        assert info.duration == pytest.approx(13.3467, abs=1e-3)

    def test_aiff(self) -> None:
        info = probe_media(ASSETS / "click.aiff")
        assert info.width == 0 and info.height == 0
        assert info.has_audio is True
        assert info.audio_sample_rate == 44100.0
        assert info.duration == pytest.approx(0.1274376, abs=1e-5)

    def test_unsupported_format_raises(self) -> None:
        # .c4d import is deferred (no media probe), so probing must raise.
        with pytest.raises(NotImplementedError):
            probe_media(ASSETS / "c4d.c4d")

    def test_every_importable_format_has_probe(self) -> None:
        # Every extension import_file accepts must have a media probe;
        # otherwise import dies mid-probe with NotImplementedError instead
        # of the early ValueError for unsupported formats.
        from py_aep.data.file_formats import _FILE_FORMATS
        from py_aep.resolvers.media_probe import _PARSERS

        importable = {
            ext for ext, fmt in _FILE_FORMATS.items() if fmt.opti != "unsupported"
        }
        assert importable <= set(_PARSERS)


class TestProbeFormatVariants:
    """Spec-derived edge cases not covered by the samples/assets/ files."""

    def test_gif_bad_signature_raises(self) -> None:
        from io import BytesIO

        from py_aep.resolvers.media_probe import _probe_gif

        with pytest.raises(ValueError, match="GIF"):
            _probe_gif(BytesIO(b"NOTGIFdata"))

    def test_bmp_os2_core_header(self) -> None:
        """Legacy OS/2 BITMAPCOREHEADER (size 12) stores dims as u2."""
        import struct
        from io import BytesIO

        from py_aep.resolvers.media_probe import _probe_bmp

        data = (
            b"BM"
            + b"\x00" * 12  # rest of the 14-byte BITMAPFILEHEADER
            + struct.pack("<I", 12)  # BITMAPCOREHEADER size
            + struct.pack("<HH", 100, 50)  # width, height (u2)
            + struct.pack("<HH", 1, 24)  # planes, bpp
        )
        info = _probe_bmp(BytesIO(data))
        assert (info.width, info.height) == (100, 50)
        assert info.has_alpha is True

    def test_tiff_bigtiff_returns_unknown(self) -> None:
        """BigTIFF (magic 43) is not a classic TIFF; probe returns no dims."""
        import struct
        from io import BytesIO

        from py_aep.resolvers.media_probe import _probe_tiff

        data = b"II" + struct.pack("<H", 43) + struct.pack("<H", 8) + b"\x00" * 16
        info = _probe_tiff(BytesIO(data))
        assert (info.width, info.height) == (0, 0)

    def test_mp3_mpeg2_cbr_duration(self) -> None:
        """MPEG-2/2.5 Layer III CBR frames are 72*bitrate/sr, not 144."""
        from io import BytesIO

        from py_aep.resolvers.media_probe import _probe_mp3

        # MPEG-2 (version bits 10) Layer III, no CRC, bitrate index 8
        # (64 kbps), sample-rate index 0 (22050 Hz), stereo.
        header = b"\xff\xf3\x80\x00"
        frame_size = 72 * 64000 // 22050  # 208 (the 144 bug computes ~2x this)
        raw = header + b"\x00" * (100 * frame_size - len(header))
        info = _probe_mp3(BytesIO(raw))
        # 100 frames * 576 samples / 22050 Hz; the 144 coefficient halved this.
        assert info.duration == pytest.approx(100 * 576 / 22050, abs=1e-3)
        assert info.audio_sample_rate == 22050.0

    def test_hdr_x_major_resolution_line(self) -> None:
        """An X-major Radiance resolution line must not transpose dims."""
        from io import BytesIO

        from py_aep.resolvers.media_probe import _probe_hdr

        # "+X 640 -Y 426" (X-major) must still yield width=640, height=426.
        data = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n+X 640 -Y 426\n"
        info = _probe_hdr(BytesIO(data))
        assert (info.width, info.height) == (640, 426)

    def test_hdr_malformed_resolution_line_raises_valueerror(self) -> None:
        """A resolution line missing an axis must raise ValueError, not KeyError."""
        from io import BytesIO

        from py_aep.resolvers.media_probe import _probe_hdr

        # No Y axis ("+X 640 +X 480") - must not leak a bare KeyError.
        data = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n+X 640 +X 480\n"
        with pytest.raises(ValueError):
            _probe_hdr(BytesIO(data))

    def test_mgjson_tolerant_timestamps(self) -> None:
        """Sample times with sub-second precision / offsets that Python 3.7's
        strict fromisoformat rejects must parse, not crash the probe."""
        import json
        from io import BytesIO

        from py_aep.resolvers.media_probe import _probe_mgjson

        doc = {
            "dataDynamicSamples": [
                {
                    "samples": [
                        {"time": "2020-01-01T00:00:00.1234567Z"},
                        {"time": "2020-01-01T00:00:05.0000000+00:00"},
                    ]
                }
            ]
        }
        info = _probe_mgjson(BytesIO(json.dumps(doc).encode("utf-8")))
        # Both samples parse (5.0s - 0.123s span + one 30fps frame); if either
        # timestamp had failed to parse the span would collapse to ~0.03s.
        assert info.duration is not None
        assert 4.8 < info.duration < 5.0


class TestTiffOpti:
    """The reverse-engineered TIFF opti header."""

    def test_build_tiff_opti_data(self) -> None:
        import struct

        from py_aep.binary.footage_chunks import build_tiff_opti_data

        data = build_tiff_opti_data(25, 26)
        assert len(data) == 602
        assert data[:4] == b"TIF "
        assert struct.unpack_from("<I", data, 32)[0] == 26  # height
        assert struct.unpack_from("<I", data, 36)[0] == 25  # width


class TestPsdOpti:
    """The reverse-engineered merged-PSD opti header."""

    def test_build_psd_opti_data(self) -> None:
        import struct

        from py_aep.binary.footage_chunks import build_psd_opti_data

        data = build_psd_opti_data(25, 26, bit_depth=8, layer_count=2)
        assert len(data) == 602
        assert data[:4] == b"8BPS"
        assert data[0x12:0x16] == b"SPB8"  # reversed code
        assert data[0x1E] == 4  # channels (always RGBA)
        assert struct.unpack_from("<I", data, 0x20)[0] == 26  # height
        assert struct.unpack_from("<I", data, 0x24)[0] == 25  # width
        assert struct.unpack_from("<H", data, 0x28)[0] == 8  # bit depth
        assert data[0x30] == 2  # layer count

    def test_flattened_psd_stores_one_layer(self) -> None:
        from py_aep.binary.footage_chunks import build_psd_opti_data

        # A flattened PSD (0 layers) is stored as 1, matching AE.
        data = build_psd_opti_data(1000, 1000, bit_depth=16, layer_count=0)
        assert data[0x30] == 1

    def test_layer_name_truncates_on_utf8_boundary(self) -> None:
        """A >255-byte layer name is cut on a char boundary, not mid-sequence."""
        from py_aep.binary.footage_chunks import build_psd_layer_opti_data

        # 4-byte chars: 255 is not a multiple of 4, so a naive [:255] slice
        # would split the 64th char (252 full bytes + 3 partial).
        name = "\U0001f600" * 120
        data = build_psd_layer_opti_data(100, 100, 8, 2, 0, 1, name, (0, 0, 100, 100))
        raw = data[0x158:]
        decoded = raw[: raw.index(0)].decode("utf-8")  # must not raise
        assert decoded == "\U0001f600" * (255 // 4)


class TestGapOptiBuilders:
    """opti builders for the newly supported HDR and TEXT (AI/EPS/PDF) formats."""

    def test_build_rhdr_opti_data(self) -> None:
        from py_aep.binary.footage_chunks import build_rhdr_opti_data

        data = build_rhdr_opti_data()
        assert len(data) == 30
        assert data[:4] == b"RHDR"

    def test_build_text_opti_data(self) -> None:
        import struct

        from py_aep.binary.footage_chunks import build_text_opti_data

        data = build_text_opti_data(612, 792)
        assert len(data) == 596
        assert data[:4] == b"TEXT"
        assert struct.unpack_from(">H", data, 24)[0] == 612  # width
        assert struct.unpack_from(">H", data, 28)[0] == 792  # height
        assert data[40:44] == b"\xff\xff\xff\xff"
