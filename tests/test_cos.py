"""Tests for COS (Carousel Object Syntax) parser and serializer."""

from __future__ import annotations

import io

import pytest

from py_aep.cos.cos import (
    CosParser,
    IndirectObject,
    IndirectReference,
    Stream,
)
from py_aep.cos.serializer import serialize


class TestCosParserPrimitives:
    """Tests for parsing individual COS value types."""

    def test_parse_integer(self) -> None:
        result = _parse(b"42")
        assert result == 42

    def test_parse_negative_integer(self) -> None:
        result = _parse(b"-7")
        assert result == -7

    def test_parse_positive_sign(self) -> None:
        result = _parse(b"+3")
        assert result == 3

    def test_parse_float(self) -> None:
        result = _parse(b"3.14")
        assert result == pytest.approx(3.14)

    def test_parse_float_no_integer_part(self) -> None:
        result = _parse(b".5")
        assert result == pytest.approx(0.5)

    def test_parse_negative_float(self) -> None:
        result = _parse(b"-2.5")
        assert result == pytest.approx(-2.5)

    def test_parse_true(self) -> None:
        assert _parse(b"true") is True

    def test_parse_false(self) -> None:
        assert _parse(b"false") is False

    def test_parse_null(self) -> None:
        assert _parse(b"null") is None

    def test_parse_string(self) -> None:
        assert _parse(b"(hello)") == "hello"

    def test_parse_string_with_escape(self) -> None:
        assert _parse(b"(line1\\nline2)") == "line1\nline2"

    def test_parse_string_with_parentheses_escape(self) -> None:
        assert _parse(b"(a\\(b\\)c)") == "a(b)c"

    def test_parse_string_with_backslash_escape(self) -> None:
        assert _parse(b"(a\\\\b)") == "a\\b"

    def test_parse_string_with_octal_escape(self) -> None:
        assert _parse(b"(\\101)") == "A"  # octal 101 = 65 = 'A'

    def test_parse_string_with_carriage_return(self) -> None:
        assert _parse(b"(a\\rb)") == "a\rb"

    def test_parse_string_utf8_bom(self) -> None:
        assert _parse(b"(\xef\xbb\xbfhello)") == "hello"

    def test_parse_string_utf16be_bom(self) -> None:
        data = b"(\xfe\xff\x00h\x00i)"
        assert _parse(data) == "hi"

    def test_parse_string_utf16le_bom(self) -> None:
        data = b"(\xff\xfeh\x00i\x00)"
        assert _parse(data) == "hi"

    def test_parse_hex_string(self) -> None:
        result = _parse(b"<48656C6C6F>")
        assert result == b"Hello"

    def test_parse_hex_string_odd_length(self) -> None:
        # Odd-length hex string gets padded with 0
        result = _parse(b"<ABC>")
        assert result == bytes([0xAB, 0xC0])

    def test_parse_hex_string_with_spaces(self) -> None:
        result = _parse(b"<48 65 6C>")
        assert result == b"Hel"

    def test_parse_identifier(self) -> None:
        # Top-level identifier triggers dict-content mode
        result = _parse(b"/Name 42")
        assert result == {"Name": 42}

    def test_parse_identifier_hex_escape(self) -> None:
        result = _parse(b"/Name#20Here 1")
        assert result == {"Name Here": 1}


class TestCosParserComposite:
    """Tests for parsing composite COS structures."""

    def test_parse_dict(self) -> None:
        result = _parse(b"<< /Key1 42 /Key2 (hello) >>")
        assert result == {"Key1": 42, "Key2": "hello"}

    def test_parse_empty_dict(self) -> None:
        result = _parse(b"<< >>")
        assert result == {}

    def test_parse_nested_dict(self) -> None:
        result = _parse(b"<< /outer << /inner 1 >> >>")
        assert result == {"outer": {"inner": 1}}

    def test_parse_array(self) -> None:
        result = _parse(b"[1 2 3]")
        assert result == [1, 2, 3]

    def test_parse_empty_array(self) -> None:
        result = _parse(b"[]")
        assert result == []

    def test_parse_mixed_array(self) -> None:
        result = _parse(b"[1 (two) true null]")
        assert result == [1, "two", True, None]

    def test_parse_nested_array(self) -> None:
        result = _parse(b"[[1 2] [3 4]]")
        assert result == [[1, 2], [3, 4]]

    def test_parse_dict_in_array(self) -> None:
        result = _parse(b"[<< /a 1 >>]")
        assert result == [{"a": 1}]

    def test_parse_bare_values_as_array(self) -> None:
        # Multiple bare number values become a list
        result = _parse(b"1 2 3")
        assert result == [1, 2, 3]


class TestCosParserIndirect:
    """Tests for indirect object / reference parsing."""

    def test_parse_indirect_object(self) -> None:
        result = _parse(b"1 0 obj 42 endobj")
        assert isinstance(result, IndirectObject)
        assert result.object_number == 1
        assert result.generation_number == 0
        assert result.data == 42

    def test_parse_indirect_reference(self) -> None:
        result = _parse(b"<< /Ref 5 0 R >>")
        assert result == {"Ref": IndirectReference(5, 0)}


class TestCosParserStream:
    """Tests for stream parsing."""

    def test_parse_stream(self) -> None:
        data = b"<< /Length 5 >>\nstream\nhelloendstream"
        f = io.BytesIO(data)
        parser = CosParser(f, max_pos=len(data))
        result = parser.parse()
        assert isinstance(result, Stream)
        assert result.dictionary == {"Length": 5}
        assert result.data == b"hello"


class TestCosParserComments:
    """Tests for comment handling."""

    def test_comment_skipped(self) -> None:
        result = _parse(b"% this is a comment\n42")
        assert result == 42

    def test_inline_comment(self) -> None:
        result = _parse(b"[1 % mid-array comment\n2]")
        assert result == [1, 2]


class TestCosParserErrors:
    """Tests for parser error handling."""

    def test_unterminated_string(self) -> None:
        with pytest.raises(SyntaxError):
            _parse(b"(unterminated")

    def test_unterminated_hex_string(self) -> None:
        with pytest.raises(SyntaxError):
            _parse(b"<48656C6C6F")

    def test_unknown_keyword(self) -> None:
        with pytest.raises(SyntaxError):
            _parse(b"badkeyword")

    def test_unexpected_token(self) -> None:
        with pytest.raises(SyntaxError):
            _parse(b"<< 42 >>")  # dict expects /identifier first

    def test_invalid_escape_sequence(self) -> None:
        with pytest.raises(SyntaxError):
            _parse(b"(\\z)")


class TestCosParserMaxPos:
    """Tests for max_pos limit."""

    def test_max_pos_truncates(self) -> None:
        f = io.BytesIO(b"42 99")
        parser = CosParser(f, max_pos=2)
        result = parser.parse()
        assert result == 42

    def test_max_pos_none_reads_all(self) -> None:
        f = io.BytesIO(b"[1 2]")
        parser = CosParser(f, max_pos=5)
        result = parser.parse()
        assert result == [1, 2]


class TestCosParserSaveRestore:
    """Tests for save_state / restore_state."""

    def test_save_restore_rewinds(self) -> None:
        f = io.BytesIO(b"42 99")
        parser = CosParser(f)
        parser.lex()
        state = parser.save_state()
        parser.lex()
        assert parser.lookahead.value == 99
        parser.restore_state(state)
        assert parser.lookahead.value == 42


class TestCosSerializer:
    """Tests for COS serializer roundtrip."""

    def test_roundtrip_dict(self) -> None:
        original = b"/Key1 42 /Key2 (hello)"
        parsed = _parse(original)
        serialized = serialize(parsed)
        reparsed = _parse(serialized)
        assert reparsed == parsed

    def test_roundtrip_array(self) -> None:
        original = b"[1 2.5 (text) true null]"
        parsed = _parse(original)
        serialized = serialize(parsed)
        reparsed = _parse(serialized)
        assert reparsed == parsed

    def test_roundtrip_nested(self) -> None:
        original = b"<< /a << /b [1 2] >> /c (str) >>"
        parsed = _parse(original)
        serialized = serialize(parsed)
        reparsed = _parse(serialized)
        assert reparsed == parsed

    def test_serialize_none(self) -> None:
        assert b"null" in serialize(None)

    def test_serialize_bool(self) -> None:
        assert b"true" in serialize(True)
        assert b"false" in serialize(False)

    def test_serialize_int(self) -> None:
        assert b"42" in serialize(42)

    def test_serialize_float(self) -> None:
        result = serialize(3.14)
        assert b"3.14" in result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _parse(data: bytes) -> object:
    """Parse COS data from bytes."""
    f = io.BytesIO(data)
    parser = CosParser(f, max_pos=len(data))
    return parser.parse()
