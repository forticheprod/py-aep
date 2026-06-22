"""Tests for CLI compare module.

These tests verify the aep-compare command line tool functionality,
including leaf-only diff output, multi-file comparison, and context display.
"""

from __future__ import annotations

from pathlib import Path

from py_aep.cli.compare import (
    parse_aep_chunks,
)

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


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
