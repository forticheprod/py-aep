"""Tests for CLI compare module.

These tests verify the aep-compare command line tool functionality,
including leaf-only diff output, multi-file comparison, and context display.
"""

from __future__ import annotations

from pathlib import Path

from py_aep.cli._chunk_helpers import format_hex_dump
from py_aep.cli.compare import (
    ByteDifference,
    ChunkDifference,
    MultiFileDifference,
    _compare_chunk_dicts,
    compare_binary_data,
    filter_differences,
    to_json_output,
)

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


class TestByteDifference:
    """Tests for ByteDifference dataclass."""

    def test_single_bit_difference_detected(self) -> None:
        """Test that single bit differences are detected and position calculated."""
        # Bit 0 differs (0x00 vs 0x01)
        diff = ByteDifference(path="test", offset=0, byte1=0x00, byte2=0x01)
        assert diff.bit_position == 7  # Bit 0 from right = bit 7 from left

    def test_multiple_bit_difference_no_position(self) -> None:
        """Test that multiple bit differences don't have a bit position."""
        # Multiple bits differ (0x00 vs 0xFF)
        diff = ByteDifference(path="test", offset=0, byte1=0x00, byte2=0xFF)
        assert diff.bit_position is None

    def test_format_diff_with_bit_position(self) -> None:
        """Test format_diff output includes bit position when applicable."""
        diff = ByteDifference(path="test", offset=10, byte1=0x80, byte2=0x00)
        formatted = diff.format_diff()
        assert "bit 0" in formatted  # MSB is bit 0
        assert "0x80" in formatted
        assert "0x00" in formatted


class TestMultiFileDifference:
    """Tests for MultiFileDifference dataclass."""

    def test_single_bit_two_distinct_values(self) -> None:
        """Bit position is set when exactly two distinct values differ by 1 bit."""
        diff = MultiFileDifference(
            path="test", offset=0, values=[0x00, 0x80, 0x00, 0x80]
        )
        assert diff.bit_position == 0  # MSB

    def test_multiple_bits_no_position(self) -> None:
        """No bit position when values differ by more than one bit."""
        diff = MultiFileDifference(path="test", offset=0, values=[0x00, 0xFF, 0x00])
        assert diff.bit_position is None

    def test_three_distinct_values_no_position(self) -> None:
        """No bit position when more than two distinct values."""
        diff = MultiFileDifference(path="test", offset=0, values=[0x00, 0x01, 0x02])
        assert diff.bit_position is None


class TestCompareBinaryData:
    """Tests for compare_binary_data function."""

    def test_identical_bytes_no_differences(self) -> None:
        """Test that identical byte sequences produce no differences."""
        data = b"\x00\x01\x02\x03"
        diffs = list(compare_binary_data(data, data, "test"))
        assert len(diffs) == 0

    def test_single_byte_difference(self) -> None:
        """Test detection of a single byte difference."""
        data1 = b"\x00\x01\x02\x03"
        data2 = b"\x00\xff\x02\x03"
        diffs = list(compare_binary_data(data1, data2, "test"))
        assert len(diffs) == 1
        assert diffs[0].offset == 1
        assert diffs[0].byte1 == 0x01
        assert diffs[0].byte2 == 0xFF

    def test_different_lengths_reported(self) -> None:
        """Test that extra bytes in longer sequence are reported."""
        data1 = b"\x00\x01\x02"
        data2 = b"\x00\x01\x02\x03\x04"
        diffs = list(compare_binary_data(data1, data2, "test"))
        assert len(diffs) == 2  # Two extra bytes in data2
        assert diffs[0].offset == 3
        assert diffs[0].byte1 == -1  # Missing in data1
        assert diffs[0].byte2 == 0x03


class TestCompareChunkDicts:
    """Tests for _compare_chunk_dicts helper."""

    def test_identical_dicts(self) -> None:
        """Identical dicts produce no differences."""
        data = {"a": b"\x00\x01", "b": b"\x02\x03"}
        diffs, only1, only2, suppressed = _compare_chunk_dicts(data, data)
        assert len(diffs) == 0
        assert len(only1) == 0
        assert len(only2) == 0
        assert suppressed == []

    def test_missing_paths_detected(self) -> None:
        """Paths in one dict but not the other are reported."""
        data1 = {"a": b"\x00", "b": b"\x01"}
        data2 = {"a": b"\x00", "c": b"\x02"}
        _, only1, only2, _ = _compare_chunk_dicts(data1, data2)
        assert "b" in only1
        assert "c" in only2


class TestFloatTolerance:
    """Tests for float-precision-tolerant chunk comparison."""

    _GRAD_XML = (
        "<?xml version='1.0'?>\n<prop.map version='4'>\n"
        "<float>{a}</float>\n<float>0.5</float>\n</prop.map>\n"
    )

    def test_cdat_within_tolerance_suppressed(self) -> None:
        from py_aep.binary.property_chunks import CdatChunk
        from py_aep.cli.compare import _only_float_diff

        c1 = CdatChunk(values=[535.0, 228.0, 0.0])
        c2 = CdatChunk(values=[535.00001, 228.0, 0.0])
        assert _only_float_diff(c1, c2) is True

    def test_gradient_xml_color_ulp_suppressed(self) -> None:
        # Gradient colors live as text floats in a Utf8 chunk; a 1-ULP
        # color difference (AE vs py float32 rounding) must be tolerated.
        from py_aep.binary.scalar_chunks import Utf8Chunk
        from py_aep.cli.compare import _only_float_diff

        c1 = Utf8Chunk(value=self._GRAD_XML.format(a="0.44705886"))
        c2 = Utf8Chunk(value=self._GRAD_XML.format(a="0.44705883"))
        assert _only_float_diff(c1, c2) is True

    def test_gradient_xml_real_color_change_reported(self) -> None:
        from py_aep.binary.scalar_chunks import Utf8Chunk
        from py_aep.cli.compare import _only_float_diff

        c1 = Utf8Chunk(value=self._GRAD_XML.format(a="0.44705886"))
        c2 = Utf8Chunk(value=self._GRAD_XML.format(a="0.80000001"))
        assert _only_float_diff(c1, c2) is False

    def test_gradient_xml_empty_float_tag_not_crash(self) -> None:
        # An empty <float></float> element must not crash float() parsing; it
        # is not a pure float-precision diff, so it is reported (False).
        from py_aep.cli.compare import _gradient_xml_only_float_diff

        xml = "<prop.map><array><float>0.5</float><float></float></array></prop.map>"
        assert _gradient_xml_only_float_diff(xml, xml) is False

    def test_non_gradient_utf8_not_tolerated(self) -> None:
        # A plain Utf8 (e.g. a layer name) is not gradient XML; only exact
        # equality applies (no float parsing).
        from py_aep.binary.scalar_chunks import Utf8Chunk
        from py_aep.cli.compare import _only_float_diff

        assert (
            _only_float_diff(Utf8Chunk(value="Layer 1"), Utf8Chunk(value="Layer 2"))
            is False
        )

    def test_cdat_beyond_tolerance_reported(self) -> None:
        from py_aep.binary.property_chunks import CdatChunk
        from py_aep.cli.compare import _only_float_diff

        c1 = CdatChunk(values=[535.0, 228.0, 0.0])
        c2 = CdatChunk(values=[600.0, 228.0, 0.0])
        assert _only_float_diff(c1, c2) is False

    def test_shph_within_tolerance_suppressed(self) -> None:
        from py_aep.binary.misc_chunks import ShphChunk
        from py_aep.cli.compare import _only_float_diff

        c1 = ShphChunk(top_left_x=-29.75, top_left_y=-32.5)
        c2 = ShphChunk(top_left_x=-29.7500012, top_left_y=-32.5)
        assert _only_float_diff(c1, c2) is True

    def test_nonfloat_bytes_still_reported(self) -> None:
        # Same floats but a different open/closed flag must NOT be suppressed.
        from py_aep.binary.misc_chunks import ShphChunk
        from py_aep.cli.compare import _only_float_diff

        c1 = ShphChunk(top_left_x=1.0, bottom_right_x=2.0)
        c2 = ShphChunk(top_left_x=1.0, bottom_right_x=2.0)
        c2.open = True
        assert _only_float_diff(c1, c2) is False

    def test_dict_compare_suppresses_float_noise(self) -> None:
        from py_aep.binary.property_chunks import CdatChunk
        from py_aep.cli.compare import _compare_chunk_dicts

        c1 = CdatChunk(values=[1.0, 2.0])
        c2 = CdatChunk(values=[1.00001, 2.0])
        data1 = {"x": c1.tobytes()}
        data2 = {"x": c2.tobytes()}
        typed1 = {"x": c1}
        typed2 = {"x": c2}
        diffs, _, _, suppressed = _compare_chunk_dicts(data1, data2, typed1, typed2)
        assert diffs == []
        assert suppressed == ["x"]  # the float-only diff is reported, not silent
        # --exact disables tolerance.
        diffs_exact, _, _, suppressed_exact = _compare_chunk_dicts(
            data1, data2, typed1, typed2, exact=True
        )
        assert len(diffs_exact) == 1
        assert suppressed_exact == []

    def test_multi_float_only_suppressed(self) -> None:
        # Multi-file: a chunk differing only in float coords across all files
        # is float-noise (a byte-identical file does not count as a diff).
        from py_aep.binary.property_chunks import CdatChunk
        from py_aep.cli.compare import _multi_only_float_diff

        ref = CdatChunk(values=[1.0, 2.0])
        close = CdatChunk(values=[1.00001, 2.0])
        same = CdatChunk(values=[1.0, 2.0])
        all_typed = [{"x": ref}, {"x": close}, {"x": same}]
        assert _multi_only_float_diff(all_typed, [0, 1, 2], "x") is True

    def test_multi_real_diff_not_suppressed(self) -> None:
        from py_aep.binary.property_chunks import CdatChunk
        from py_aep.cli.compare import _multi_only_float_diff

        ref = CdatChunk(values=[1.0, 2.0])
        far = CdatChunk(values=[9.0, 2.0])  # beyond tolerance
        all_typed = [{"x": ref}, {"x": far}]
        assert _multi_only_float_diff(all_typed, [0, 1], "x") is False


class TestFormatHexDump:
    """Tests for _format_hex_dump helper."""

    def test_small_data(self) -> None:
        """Hex dump of a few bytes formats correctly."""
        data = b"\x00\x01\x02\x03"
        result = format_hex_dump(data)
        assert "0000:" in result
        assert "00 01 02 03" in result

    def test_ascii_representation(self) -> None:
        """ASCII column shows printable chars and dots for non-printable."""
        data = b"Hello\x00World"
        result = format_hex_dump(data)
        assert "Hello.World" in result

    def test_multi_line(self) -> None:
        """Data longer than 16 bytes produces multiple lines."""
        data = bytes(range(32))
        result = format_hex_dump(data)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("0000:")
        assert lines[1].startswith("0010:")


class TestFilterDifferences:
    """Tests for filter_differences function."""

    def test_filter_matches_pattern(self) -> None:
        """Test that filter correctly matches patterns."""
        diff1 = ChunkDifference(
            path="LIST:Layr/ldta", byte_diffs=[], size1=10, size2=10
        )
        diff2 = ChunkDifference(
            path="LIST:Comp/cdta", byte_diffs=[], size1=10, size2=10
        )
        differences = [diff1, diff2]

        filtered, _, _ = filter_differences(differences, [], [], "ldta")
        assert len(filtered) == 1
        assert filtered[0].path == "LIST:Layr/ldta"

    def test_filter_case_insensitive(self) -> None:
        """Test that filter is case-insensitive."""
        diff = ChunkDifference(path="LIST:Layr/LDTA", byte_diffs=[], size1=10, size2=10)
        filtered, _, _ = filter_differences([diff], [], [], "ldta")
        assert len(filtered) == 1


class TestToJsonOutput:
    """Tests for to_json_output function."""

    def test_json_output_structure(self) -> None:
        """Test that JSON output has expected structure."""
        diff = ChunkDifference(
            path="test/path",
            byte_diffs=[ByteDifference(path="test", offset=0, byte1=0x00, byte2=0x01)],
            size1=10,
            size2=10,
        )
        output = to_json_output(
            Path("file1.aep"),
            Path("file2.aep"),
            [diff],
            ["only1"],
            ["only2"],
        )
        assert "file1" in output
        assert "file2" in output
        assert "chunks_with_differences" in output
        assert "only_in_file1" in output
        assert "only_in_file2" in output
        assert "summary" in output
        assert output["summary"]["chunks_with_differences"] == 1
        assert output["summary"]["total_byte_differences"] == 1
