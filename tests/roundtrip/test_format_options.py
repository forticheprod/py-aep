"""Tests for OutputModule.format_options parsing."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from py_aep import parse
from py_aep.enums import (
    AudioCodec,
    CineonFileFormat,
    DnxResolution,
    Hdr10ColorPrimaries,
    JpegFormatType,
    MPEGAudioFormat,
    MPEGMultiplexer,
    MPEGMuxStreamCompatibility,
    MPEGProfile,
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

    @pytest.mark.parametrize("value", [-100, 0x10000, 10**12])
    def test_validate_highlight_expansion_rejects_out_of_u2(self, value: int) -> None:
        # Backed by a u2 field: an unbounded value overflowed `struct` and
        # crashed save() mid-write, leaving a partial .aep (fuzz finding).
        _, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        with pytest.raises(ValueError):
            opts.highlight_expansion = value

    @pytest.mark.parametrize(
        "field", ["converted_black_point", "converted_white_point", "current_gamma"]
    )
    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_validate_float_fields_reject_nonfinite(
        self, field: str, bad: float
    ) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        with pytest.raises(ValueError, match="finite"):
            setattr(opts, field, bad)

    def test_highlight_expansion_valid_roundtrips(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "cineon" / "base.aep")
        assert isinstance(opts, CineonFormatOptions)
        opts.highlight_expansion = 42
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, CineonFormatOptions)
        assert opts2.highlight_expansion == 42


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


class TestMPEGProfile:
    """The H.264 `Profile` dropdown.

    AE encodes `Baseline` by REMOVING the parameter's `<ParamValue>` while
    KEEPING its `<ExporterParam>` element (the `ObjectID` is referenced by
    the PremiereData object graph). Both encodings decode identically, so
    only the element-level assertions below catch a writer that deletes the
    whole element.
    """

    H264 = FORMAT_DIR / "h.264"
    KEY = "ADBEVideoMPEGProfile"

    @classmethod
    def _elements(cls, opts: XmlFormatOptions, key: str) -> list[ET.Element]:
        root = opts._xml_root
        assert root is not None
        out = []
        for elem in root.iter("ExporterParam"):
            ident = elem.find("ParamIdentifier")
            if ident is not None and ident.text == key:
                out.append(elem)
        return out

    @classmethod
    def _child_tags(cls, opts: XmlFormatOptions, key: str) -> list[str]:
        """The param element's child tags - the ObjectID-independent shape.

        `ObjectID` is per-file, so comparing serialized elements across
        samples is meaningless; the child sequence is the invariant.
        """
        elements = cls._elements(opts, key)
        assert len(elements) == 1
        return [child.tag for child in elements[0]]

    @pytest.mark.parametrize(
        ("sample", "expected"),
        [
            ("h264_baseline.aep", MPEGProfile.BASELINE),
            ("h264_high.aep", MPEGProfile.HIGH),
            ("base.aep", MPEGProfile.MAIN),
        ],
    )
    def test_reads(self, sample: str, expected: MPEGProfile) -> None:
        _, opts = _parse_fresh(self.H264 / sample)
        assert isinstance(opts, XmlFormatOptions)
        assert opts.profile is expected

    def test_absent_param_reads_as_baseline(self) -> None:
        _, opts = _parse_fresh(self.H264 / "h264_baseline.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert self.KEY not in opts.params
        assert opts.profile is MPEGProfile.BASELINE

    def test_write_baseline_matches_ae(self, tmp_path: Path) -> None:
        # The bar is parity with AE's OWN output for the same input: the
        # element must survive VALUELESS, exactly as AE's Baseline module
        # has it - not be deleted (which decodes identically).
        #
        # h264_high/h264_baseline are the controlled pair (one AE batch,
        # differing only in the Profile dropdown). `base.aep` is NOT: it was
        # authored separately and carries an extra ParamIsDisabled child.
        project, opts = _parse_fresh(self.H264 / "h264_high.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.profile is MPEGProfile.HIGH
        opts.profile = MPEGProfile.BASELINE
        project.save(tmp_path / "out.aep")

        _, written = _parse_fresh(tmp_path / "out.aep")
        _, ae = _parse_fresh(self.H264 / "h264_baseline.aep")
        assert isinstance(written, XmlFormatOptions)
        assert isinstance(ae, XmlFormatOptions)
        assert written.profile is MPEGProfile.BASELINE
        assert self._child_tags(written, self.KEY) == self._child_tags(ae, self.KEY)
        assert "ParamValue" not in self._child_tags(ae, self.KEY)

    def test_write_baseline_keeps_the_element_and_its_object_id(
        self, tmp_path: Path
    ) -> None:
        project, opts = _parse_fresh(self.H264 / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        before = self._elements(opts, self.KEY)[0].attrib["ObjectID"]
        opts.profile = MPEGProfile.BASELINE
        project.save(tmp_path / "out.aep")
        _, written = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(written, XmlFormatOptions)
        elements = self._elements(written, self.KEY)
        assert len(elements) == 1  # not deleted, not duplicated
        assert elements[0].find("ParamValue") is None
        # The PremiereData object graph references this id.
        assert elements[0].attrib["ObjectID"] == before

    def test_baseline_then_set_restores_value_in_place(self, tmp_path: Path) -> None:
        # Re-setting must restore ParamValue INSIDE the existing element (as
        # its first child, where AE puts it), not append a second element.
        project, opts = _parse_fresh(self.H264 / "h264_baseline.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts.profile = MPEGProfile.MAIN
        project.save(tmp_path / "out.aep")
        _, written = _parse_fresh(tmp_path / "out.aep")
        _, ae_valued = _parse_fresh(self.H264 / "h264_high.aep")
        assert isinstance(written, XmlFormatOptions)
        assert isinstance(ae_valued, XmlFormatOptions)
        assert written.profile is MPEGProfile.MAIN
        assert self._child_tags(written, self.KEY) == self._child_tags(
            ae_valued, self.KEY
        )
        assert self._child_tags(written, self.KEY)[0] == "ParamValue"

    @pytest.mark.parametrize(
        "profile", [MPEGProfile.MAIN, MPEGProfile.HIGH, MPEGProfile.HIGH10]
    )
    def test_roundtrip(self, profile: MPEGProfile, tmp_path: Path) -> None:
        project, opts = _parse_fresh(self.H264 / "h264_baseline.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts.profile = profile
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.profile is profile

    def test_rejects_out_of_enum(self) -> None:
        _, opts = _parse_fresh(self.H264 / "base.aep")
        assert isinstance(opts, XmlFormatOptions)
        with pytest.raises(ValueError):
            opts.profile = 2  # unobserved; deliberately not an enum member


class TestOpenExrHtj2k:
    """AE 2026 added two HTJ2K compression modes beyond the 0-9 block."""

    @pytest.mark.parametrize(
        ("sample", "expected"),
        [
            ("exr_htj2k-256.aep", OpenExrCompression.HTJ2K_256),
            ("exr_htj2k-32.aep", OpenExrCompression.HTJ2K_32),
        ],
    )
    def test_reads(self, sample: str, expected: OpenExrCompression) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "openexr" / sample)
        assert isinstance(opts, OpenExrFormatOptions)
        assert opts.compression is expected

    def test_roundtrip(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "openexr" / "exr_htj2k-256.aep")
        assert isinstance(opts, OpenExrFormatOptions)
        opts.compression = OpenExrCompression.HTJ2K_32
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, OpenExrFormatOptions)
        assert opts2.compression is OpenExrCompression.HTJ2K_32


class TestDnxResolution:
    """The DNxHR/DNxHD `Resolution` preset ids (a contiguous 1001-1019 block).

    Only a few presets are committed as fixtures; the rest of the mapping is
    recorded in [DnxResolution][] from the AE 2026 sample sweep.
    """

    @pytest.mark.parametrize(
        ("sample", "expected"),
        [
            ("720p DNxHD HQX 10-bit.aep", DnxResolution.DNXHD_720P_HQX_10_BIT),
            ("1080p DNxHD LB 8-bit.aep", DnxResolution.DNXHD_1080P_LB_8_BIT),
            ("DNxHR HQ 8-bit.aep", DnxResolution.DNXHR_HQ_8_BIT),
        ],
    )
    def test_reads(self, sample: str, expected: DnxResolution) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "dnx" / sample)
        assert isinstance(opts, XmlFormatOptions)
        assert opts.video_codec == VideoCodec.DNXHR_DNXHD
        assert opts.resolution is expected

    def test_roundtrip(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "dnx" / "DNxHR HQ 8-bit.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts.resolution = DnxResolution.DNXHR_LB_8_BIT
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.resolution is DnxResolution.DNXHR_LB_8_BIT

    def test_rejects_out_of_enum(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "dnx" / "DNxHR HQ 8-bit.aep")
        assert isinstance(opts, XmlFormatOptions)
        with pytest.raises(ValueError):
            opts.resolution = 9999


class TestFormatOptionsBoolValidation:
    """`ChunkField.bool` bakes in `validate_bool`, so a non-bool cannot
    reach the 1-byte chunk field (`= 2` would write a byte AE never
    writes; `= "no"` would only fail later, inside `save()`)."""

    BOOL_FIELDS = [
        ("openexr/base.aep", "luminance_chroma"),
        ("openexr/base.aep", "thirty_two_bit_float"),
        ("targa/base.aep", "rle_compression"),
        ("tiff/base.aep", "lzw_compression"),
        ("tiff/base.aep", "ibm_pc_byte_order"),
        ("cineon/base.aep", "logarithmic_conversion"),
    ]

    @pytest.mark.parametrize(("sample", "field"), BOOL_FIELDS)
    @pytest.mark.parametrize("bad", ["no", 2, 1, 0, None, []])
    def test_rejects_non_bool(self, sample: str, field: str, bad: object) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / sample)
        with pytest.raises(TypeError):
            setattr(opts, field, bad)

    @pytest.mark.parametrize(("sample", "field"), BOOL_FIELDS)
    def test_accepts_bool(self, sample: str, field: str) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / sample)
        setattr(opts, field, True)
        assert getattr(opts, field) is True


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
        # PCM is only offered without a container: switch the
        # multiplexer to None first (as AE's dialog requires).
        opts.mpeg_multiplexer = MPEGMultiplexer.NONE
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


class TestRoundtripXmlParamsDict:
    """`params` mutations must reach the XML, not just the dict.

    `dict.update`/`setdefault` are C-level and skip `__setitem__`, so
    they used to update the dict (and the typed accessors reading it)
    while the saved file kept the old value.
    """

    def test_update_persists(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "mp3" / "mp3_mono_320.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.bitrate == 320
        opts.params.update({"BitRate": "128"})
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.params["BitRate"] == "128"
        assert opts2.bitrate == 128

    def test_update_kwargs_persists(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "mp3" / "mp3_mono_320.aep")
        assert isinstance(opts, XmlFormatOptions)
        opts.params.update(BitRate="192")
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.bitrate == 192

    def test_setdefault_persists_new_key(self, tmp_path: Path) -> None:
        project, opts = _parse_fresh(FORMAT_DIR / "mp3" / "mp3_mono_320.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.params.setdefault("ADBEUnusedParam", "7") == "7"
        project.save(tmp_path / "out.aep")
        _, opts2 = _parse_fresh(tmp_path / "out.aep")
        assert isinstance(opts2, XmlFormatOptions)
        assert opts2.params["ADBEUnusedParam"] == "7"

    def test_setdefault_keeps_existing(self) -> None:
        _, opts = _parse_fresh(FORMAT_DIR / "mp3" / "mp3_mono_320.aep")
        assert isinstance(opts, XmlFormatOptions)
        assert opts.params.setdefault("BitRate", "1") == "320"
        assert opts.bitrate == 320
