"""PDFDocEncoding decoding of PDF text strings.

Expected characters are AE 2026's own, read back from the layer names it
gives a hand-built `.ai` whose OCG names carry these bytes. They are
written as code points so the test does not depend on its own encoding.
"""

from __future__ import annotations

import io

import pytest

from py_aep.cos import CosParser, decode_pdf_text_string

_REPLACEMENT = chr(0xFFFD)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Latin-1 range: unchanged (the reported German layer names).
        (b"L\xf6sung", "L" + chr(0xF6) + "sung"),
        (b"Gl\xe4nzen", "Gl" + chr(0xE4) + "nzen"),
        (b"100% K\xf6rper Stroke", "100% K" + chr(0xF6) + "rper Stroke"),
        # C1 range: typographic characters, NOT Windows-1252. 0x80 is a
        # bullet here, where cp1252 would give a euro sign.
        (b"\x80", chr(0x2022)),
        (b"\x92", chr(0x2122)),
        (b"\x96", chr(0x0152)),
        # C0 range 0x18-0x1F: accents.
        (b"\x18", chr(0x02D8)),
        (b"\x1f", chr(0x02DC)),
        # 0xA0 is the euro sign, where Latin-1 has a non-breaking space.
        (b"\xa0", chr(0x20AC)),
        # Undefined code points.
        (b"\x7f", _REPLACEMENT),
        (b"\x9f", _REPLACEMENT),
        (b"\xad", _REPLACEMENT),
        # ASCII passes through.
        (b"Layer 1", "Layer 1"),
        (b"", ""),
    ],
)
def test_decodes_like_after_effects(raw: bytes, expected: str) -> None:
    assert decode_pdf_text_string(raw) == expected


def test_already_decoded_strings_pass_through() -> None:
    # The COS lexer decodes a BOM-prefixed UTF-16 string itself.
    already = chr(0xDC) + "n" + chr(0xEF) + "code"
    assert decode_pdf_text_string(already) == already


@pytest.mark.parametrize(
    ("literal", "expected"),
    [
        # Invalid UTF-8: the lexer gives up and hands over raw bytes.
        (b"a_\xf6", "a_" + chr(0xF6)),
        (b"b_\x80", "b_" + chr(0x2022)),
        # Valid UTF-8 AND meaningful PDFDocEncoding. With no BOM the PDF
        # spec says PDFDocEncoding, and so does AE: these four are the
        # exact layer names AE 2026 imported this file's OCGs as, where
        # the UTF-8 reading would give U+00E9 / U+00A0 / U+20AC / U+00C0.
        (b"c_\xc3\xa9", "c_" + chr(0x00C3) + chr(0x00A9)),
        (b"d_\xc2\xa0", "d_" + chr(0x00C2) + chr(0x20AC)),
        (b"e_\xe2\x82\xac", "e_" + chr(0x00E2) + chr(0x2021) + chr(0x00AC)),
        (b"f_\xc3\x80", "f_" + chr(0x00C3) + chr(0x2022)),
        # A BOM means what it says, and is left alone.
        (b"\xfe\xff\x00g\x00_\x00o\x00k", "g_ok"),
        (b"\xef\xbb\xbfh_\xc3\xa9", "h_" + chr(0x00E9)),
        (b"Layer 1", "Layer 1"),
    ],
)
def test_decodes_lexer_output_like_after_effects(literal: bytes, expected: str) -> None:
    """The whole path: a COS string literal as it sits in the file.

    Feeding raw bytes straight in cannot catch a regression here - the
    lexer decodes anything that is valid UTF-8 before this function ever
    sees it, so only a literal exercises the case that matters.
    """
    token = CosParser(io.BytesIO(literal + b")")).lex_string()
    assert decode_pdf_text_string(token.value) == expected
