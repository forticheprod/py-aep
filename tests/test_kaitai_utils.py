"""Tests for kaitai chunk utility functions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from py_aep.kaitai.utils import (
    ChunkNotFoundError,
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    find_by_type,
    find_chunks_after,
    find_chunks_before,
    group_chunks,
    recursive_find,
    split_on_type,
    str_contents,
)


def _chunk(chunk_type: str, list_type: str | None = None) -> MagicMock:
    """Create a mock chunk."""
    c = MagicMock()
    c.chunk_type = chunk_type
    if chunk_type == "LIST":
        c.body.list_type = list_type
        c.body.chunks = []
    return c


class TestFindByType:
    """Tests for find_by_type."""

    def test_finds_first_match(self) -> None:
        a, b = _chunk("cdta"), _chunk("ldta")
        result = find_by_type(chunks=[a, b], chunk_type="cdta")
        assert result is a

    def test_raises_when_not_found(self) -> None:
        with pytest.raises(ChunkNotFoundError):
            find_by_type(chunks=[_chunk("cdta")], chunk_type="xxxx")


class TestFindByListType:
    """Tests for find_by_list_type."""

    def test_finds_list_chunk(self) -> None:
        a = _chunk("LIST", "Fold")
        b = _chunk("LIST", "Layr")
        result = find_by_list_type(chunks=[a, b], list_type="Layr")
        assert result is b

    def test_raises_when_not_found(self) -> None:
        with pytest.raises(ChunkNotFoundError):
            find_by_list_type(chunks=[_chunk("LIST", "Fold")], list_type="Comp")


class TestFilterByType:
    """Tests for filter_by_type."""

    def test_returns_all_matches(self) -> None:
        a, b, c = _chunk("tdmn"), _chunk("LIST", "X"), _chunk("tdmn")
        result = filter_by_type(chunks=[a, b, c], chunk_type="tdmn")
        assert result == [a, c]

    def test_returns_empty_when_no_match(self) -> None:
        result = filter_by_type(chunks=[_chunk("cdta")], chunk_type="xxxx")
        assert result == []


class TestFilterByListType:
    """Tests for filter_by_list_type."""

    def test_returns_all_matching_lists(self) -> None:
        a = _chunk("LIST", "Layr")
        b = _chunk("LIST", "Fold")
        c = _chunk("LIST", "Layr")
        result = filter_by_list_type(chunks=[a, b, c], list_type="Layr")
        assert result == [a, c]

    def test_ignores_non_list_chunks(self) -> None:
        a = _chunk("cdta")
        result = filter_by_list_type(chunks=[a], list_type="Layr")
        assert result == []


class TestFindChunksBefore:
    """Tests for find_chunks_before."""

    def test_finds_run_before_anchor(self) -> None:
        a, b, c, d = _chunk("tdmn"), _chunk("tdmn"), _chunk("LIST", "Als2"), _chunk("cdta")
        result = find_chunks_before(chunks=[a, b, c, d], chunk_type="tdmn", before_type="LIST:Als2")
        assert result == [a, b]

    def test_non_contiguous_stops_at_gap(self) -> None:
        a, b, c, d = _chunk("tdmn"), _chunk("cdta"), _chunk("tdmn"), _chunk("LIST", "Als2")
        result = find_chunks_before(chunks=[a, b, c, d], chunk_type="tdmn", before_type="LIST:Als2")
        assert result == [c]

    def test_empty_when_no_match_before(self) -> None:
        a, b = _chunk("cdta"), _chunk("LIST", "Als2")
        result = find_chunks_before(chunks=[a, b], chunk_type="tdmn", before_type="LIST:Als2")
        assert result == []

    def test_plain_chunk_type_anchor(self) -> None:
        a, b = _chunk("tdmn"), _chunk("opti")
        result = find_chunks_before(chunks=[a, b], chunk_type="tdmn", before_type="opti")
        assert result == [a]

    def test_raises_when_anchor_not_found(self) -> None:
        with pytest.raises(ChunkNotFoundError):
            find_chunks_before(chunks=[_chunk("tdmn")], chunk_type="tdmn", before_type="opti")


class TestFindChunksAfter:
    """Tests for find_chunks_after."""

    def test_finds_run_after_anchor(self) -> None:
        a, b, c = _chunk("opti"), _chunk("tdmn"), _chunk("tdmn")
        result = find_chunks_after(chunks=[a, b, c], chunk_type="tdmn", after_type="opti")
        assert result == [b, c]

    def test_stops_at_different_type(self) -> None:
        a, b, c, d = _chunk("opti"), _chunk("tdmn"), _chunk("cdta"), _chunk("tdmn")
        result = find_chunks_after(chunks=[a, b, c, d], chunk_type="tdmn", after_type="opti")
        assert result == [b]

    def test_empty_when_no_match_after(self) -> None:
        a, b = _chunk("opti"), _chunk("cdta")
        result = find_chunks_after(chunks=[a, b], chunk_type="tdmn", after_type="opti")
        assert result == []

    def test_list_type_anchor(self) -> None:
        a, b = _chunk("LIST", "Als2"), _chunk("tdmn")
        result = find_chunks_after(chunks=[a, b], chunk_type="tdmn", after_type="LIST:Als2")
        assert result == [b]


class TestGroupChunks:
    """Tests for group_chunks."""

    def test_groups_between_markers(self) -> None:
        a, b, c, d, e = _chunk("S"), _chunk("x"), _chunk("E"), _chunk("S"), _chunk("E")
        result = group_chunks(chunks=[a, b, c, d, e], start_type="S", end_type="E")
        assert len(result) == 2
        assert result[0] == [a, b, c]
        assert result[1] == [d, e]

    def test_empty_input(self) -> None:
        result = group_chunks(chunks=[], start_type="S", end_type="E")
        assert result == []

    def test_incomplete_group_ignored(self) -> None:
        a, b = _chunk("S"), _chunk("x")
        result = group_chunks(chunks=[a, b], start_type="S", end_type="E")
        assert result == []

    def test_chunks_outside_groups_ignored(self) -> None:
        a, b, c = _chunk("x"), _chunk("S"), _chunk("E")
        result = group_chunks(chunks=[a, b, c], start_type="S", end_type="E")
        assert len(result) == 1
        assert result[0] == [b, c]


class TestSplitOnType:
    """Tests for split_on_type."""

    def test_splits_on_marker(self) -> None:
        a, b, c, d = _chunk("M"), _chunk("x"), _chunk("M"), _chunk("y")
        result = split_on_type(chunks=[a, b, c, d], chunk_type="M")
        assert len(result) == 2
        assert result[0] == [a, b]
        assert result[1] == [c, d]

    def test_discards_before_first_marker(self) -> None:
        a, b, c = _chunk("x"), _chunk("M"), _chunk("y")
        result = split_on_type(chunks=[a, b, c], chunk_type="M")
        assert len(result) == 1
        assert result[0] == [b, c]

    def test_empty_input(self) -> None:
        result = split_on_type(chunks=[], chunk_type="M")
        assert result == []

    def test_single_marker(self) -> None:
        a = _chunk("M")
        result = split_on_type(chunks=[a], chunk_type="M")
        assert result == [[a]]


class TestStrContents:
    """Tests for str_contents."""

    def test_returns_text_before_null(self) -> None:
        c = _chunk("Utf8")
        c.body.contents = "hello\x00world"
        assert str_contents(c) == "hello"

    def test_no_null(self) -> None:
        c = _chunk("Utf8")
        c.body.contents = "hello"
        assert str_contents(c) == "hello"


class TestRecursiveFind:
    """Tests for recursive_find."""

    def test_finds_in_nested_lists(self) -> None:
        inner = _chunk("cdta")
        outer = _chunk("LIST", "Fold")
        outer.body.chunks = [inner]
        result = recursive_find(chunks=[outer], chunk_type="cdta")
        assert result == [inner]

    def test_finds_list_by_list_type(self) -> None:
        inner = _chunk("LIST", "Layr")
        inner.body.chunks = []
        outer = _chunk("LIST", "Fold")
        outer.body.chunks = [inner]
        result = recursive_find(chunks=[outer], list_type="Layr")
        assert result == [inner]

    def test_raises_when_no_criteria(self) -> None:
        with pytest.raises(ValueError):
            recursive_find(chunks=[], chunk_type=None, list_type=None)

    def test_empty_chunks(self) -> None:
        result = recursive_find(chunks=[], chunk_type="cdta")
        assert result == []
