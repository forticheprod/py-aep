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
    parse_aep_chunks,
    to_json_output,
)

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


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


class TestLeafOnlyChunks:
    """Tests that only leaf chunks appear in parsed output (no LIST dups)."""

    def test_no_list_paths_in_output(self) -> None:
        """parse_aep_chunks should not include LIST containers as leaves."""
        aep_path = SAMPLES_DIR / "versions" / "ae2025" / "complete.aep"
        chunks = parse_aep_chunks(aep_path)

        for path in chunks:
            # The final segment (after last /) should not be a LIST
            final_segment = path.rsplit("/", 1)[-1]
            base = final_segment.split("[")[0]
            # LIST chunks should only appear as path prefixes, never as
            # the leaf chunk itself (their raw data duplicates children).
            assert not base.startswith("LIST:"), (
                f"LIST chunk found in leaf output: {path}"
            )

    def test_leaf_chunks_have_data(self) -> None:
        """All leaf chunks should have bytes data (may be empty)."""
        aep_path = SAMPLES_DIR / "versions" / "ae2025" / "complete.aep"
        chunks = parse_aep_chunks(aep_path)
        assert len(chunks) > 0
        for path, data in chunks.items():
            assert isinstance(data, bytes), f"Non-bytes data for {path}"


class TestCompareChunkDicts:
    """Tests for _compare_chunk_dicts helper."""

    def test_identical_dicts(self) -> None:
        """Identical dicts produce no differences."""
        data = {"a": b"\x00\x01", "b": b"\x02\x03"}
        diffs, only1, only2 = _compare_chunk_dicts(data, data)
        assert len(diffs) == 0
        assert len(only1) == 0
        assert len(only2) == 0

    def test_missing_paths_detected(self) -> None:
        """Paths in one dict but not the other are reported."""
        data1 = {"a": b"\x00", "b": b"\x01"}
        data2 = {"a": b"\x00", "c": b"\x02"}
        _, only1, only2 = _compare_chunk_dicts(data1, data2)
        assert "b" in only1
        assert "c" in only2


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
