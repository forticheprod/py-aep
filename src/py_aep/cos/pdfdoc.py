"""PDFDocEncoding - the default character set of a PDF text string.

A PDF text string that does not open with a UTF-16 byte-order mark is
encoded in PDFDocEncoding (PDF 32000-1:2008, Annex D.2), which is Latin-1
with the C0/C1 control ranges replaced by typographic characters. Probed
against After Effects 2026, which decodes `.ai` layer names this way:
`0x80` imports as U+2022 BULLET (not the Windows-1252 euro sign), `0x18`
as U+02D8 BREVE, `0xA0` as U+20AC EURO, and the code points the table
leaves undefined (`0x7F`, `0x9F`, `0xAD`) as U+FFFD.

The overrides are written as code points rather than character literals
so the table cannot be mangled by an editor or formatter.
"""

from __future__ import annotations

from .cos import CosString

_UNDEFINED = 0xFFFD

# byte -> unicode code point, for every byte Latin-1 does not already cover.
_OVERRIDES = {
    0x18: 0x02D8,  # breve
    0x19: 0x02C7,  # caron
    0x1A: 0x02C6,  # circumflex
    0x1B: 0x02D9,  # dotaccent
    0x1C: 0x02DD,  # hungarumlaut
    0x1D: 0x02DB,  # ogonek
    0x1E: 0x02DA,  # ring
    0x1F: 0x02DC,  # tilde
    0x7F: _UNDEFINED,
    0x80: 0x2022,  # bullet
    0x81: 0x2020,  # dagger
    0x82: 0x2021,  # daggerdbl
    0x83: 0x2026,  # ellipsis
    0x84: 0x2014,  # emdash
    0x85: 0x2013,  # endash
    0x86: 0x0192,  # florin
    0x87: 0x2044,  # fraction
    0x88: 0x2039,  # guilsinglleft
    0x89: 0x203A,  # guilsinglright
    0x8A: 0x2212,  # minus
    0x8B: 0x2030,  # perthousand
    0x8C: 0x201E,  # quotedblbase
    0x8D: 0x201C,  # quotedblleft
    0x8E: 0x201D,  # quotedblright
    0x8F: 0x2018,  # quoteleft
    0x90: 0x2019,  # quoteright
    0x91: 0x201A,  # quotesinglbase
    0x92: 0x2122,  # trademark
    0x93: 0xFB01,  # fi ligature
    0x94: 0xFB02,  # fl ligature
    0x95: 0x0141,  # Lslash
    0x96: 0x0152,  # OE
    0x97: 0x0160,  # Scaron
    0x98: 0x0178,  # Ydieresis
    0x99: 0x017D,  # Zcaron
    0x9A: 0x0131,  # dotlessi
    0x9B: 0x0142,  # lslash
    0x9C: 0x0153,  # oe
    0x9D: 0x0161,  # scaron
    0x9E: 0x017E,  # zcaron
    0x9F: _UNDEFINED,
    0xA0: 0x20AC,  # Euro
    0xAD: _UNDEFINED,
}


def decode_pdf_text_string(raw: bytes | str) -> str:
    """Decode a PDF text string.

    A BOM-prefixed literal (UTF-16 either way, or UTF-8) is decoded by the
    COS lexer already and passes through. Everything else is
    PDFDocEncoding, and reaches this function one of two ways: as raw
    bytes the lexer could not decode at all, or - when the bytes happen to
    form valid UTF-8 - as a `CosString` the lexer decoded speculatively
    but kept the original bytes on, as `cos_raw`.

    Probed on AE 2026, which imports `.ai` / `.pdf` layer names strictly
    this way: `(caf\\xc3\\xa9)` with no BOM becomes `caf` + U+00C3 U+00A9,
    NOT the UTF-8 reading `café`.

    Args:
        raw: The string object read from the PDF.
    """
    if isinstance(raw, bytes):
        return _from_bytes(raw)
    if isinstance(raw, CosString) and raw.cos_raw is not None:
        return _from_bytes(raw.cos_raw)
    return raw


def _from_bytes(raw: bytes) -> str:
    # Latin-1 maps every byte to the same code point, and `str.translate`
    # leaves the ones absent from the table alone - which is exactly the
    # passthrough the other 215 bytes need.
    return raw.decode("latin-1").translate(_OVERRIDES)
