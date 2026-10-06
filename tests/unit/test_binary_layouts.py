"""Field layouts of chunks whose widths, byte order or signs After Effects
fixes (decoded values; the bytes round-trip unchanged)."""

from __future__ import annotations

import struct
from io import BytesIO

from py_aep.binary.chunk import Chunk
from py_aep.binary.composition_chunks import CsctChunk
from py_aep.binary.layer_chunks import LdtaChunk
from py_aep.binary.project_chunks import WsnsChunk
from py_aep.binary.property_chunks import Tdb4Chunk, TdsbChunk
from py_aep.binary.registry import CHUNK_TYPES


def _read(chunk_type: str, body: bytes) -> Chunk:
    cls = CHUNK_TYPES[chunk_type]
    chunk = cls.read(BytesIO(body), len(body), chunk_type=chunk_type)
    out = BytesIO()
    chunk.write(out)
    assert out.getvalue() == body
    return chunk


class TestLittleEndianAtoms:
    """`CsCt`, `sfid` and `mrid` are little-endian inside the big-endian file
    (`sfid` holds the Solids folder's item id, `mrid` the Media Replacement
    Comps folder's)."""

    def test_csct(self) -> None:
        chunk = _read("CsCt", b"\x02\x00\x00\x00")
        assert isinstance(chunk, CsctChunk)
        assert chunk.value == 2
        assert CsctChunk().tobytes() == b"\x01\x00\x00\x00"

    def test_sfid_and_mrid(self) -> None:
        assert _read("sfid", b"\x0d\x00\x00\x00").value == 13  # type: ignore[attr-defined]
        assert _read("mrid", b"\x1d\x00\x00\x00").value == 29  # type: ignore[attr-defined]


class TestSignedCounters:
    """`CcCt`, `CprC`, `parn`, `fipc`, `fivc` and `wsns` are signed."""

    def test_four_byte(self) -> None:
        for tag in ("CcCt", "CprC", "parn"):
            assert _read(tag, b"\xff\xff\xff\xff").value == -1  # type: ignore[attr-defined]

    def test_two_byte(self) -> None:
        for tag in ("fipc", "fivc"):
            assert _read(tag, b"\xff\xfe").value == -2  # type: ignore[attr-defined]
        chunk = _read("wsns", b"\x00\x0e")
        assert isinstance(chunk, WsnsChunk)
        assert chunk.value == 14


class TestLdtaDoubles:
    """ldta 0x70 and 0x78 are doubles (0.0 in every sample), 0x8C-0x9F three
    words and a double."""

    def test_layout(self) -> None:
        body = bytearray(LdtaChunk().tobytes())
        struct.pack_into(">dd", body, 0x70, 1.5, -2.25)
        struct.pack_into(">IIId", body, 0x8C, 1, 0x01000000, 1, 36.0)
        chunk = _read("ldta", bytes(body))
        assert isinstance(chunk, LdtaChunk)
        assert chunk._reserved_70 == 1.5
        assert chunk._reserved_78 == -2.25
        assert (chunk._reserved_8c, chunk._reserved_90, chunk._reserved_94) == (
            1,
            0x01000000,
            1,
        )
        assert chunk._reserved_98 == 36.0


class TestTdb4Layout:
    """tdb4 0x48 is one word (a time in units or 0x80000000 in the
    samples), 0x4C/0x4D bytes, and 0x54-0x73 four doubles."""

    def test_layout(self) -> None:
        body = bytearray(Tdb4Chunk().tobytes())
        struct.pack_into(">I", body, 0x48, 0x0000A800)
        body[0x4C], body[0x4D] = 3, 1
        struct.pack_into(">dddd", body, 0x54, 0.0, 0.16666666667, 0.0, 0.5)
        chunk = _read("tdb4", bytes(body))
        assert isinstance(chunk, Tdb4Chunk)
        assert chunk._reserved_48 == 0xA800
        assert (chunk._reserved_4c, chunk._reserved_4d) == (3, 1)
        assert chunk._reserved_5c == 0.16666666667
        assert chunk._reserved_6c == 0.5


class TestTdsbRatioLink:
    """Lock-byte bit 5 (bit 13 of the flags word) is set when a Scale or
    Mask Feather's dimensions are unlinked; bit 4 is never saved."""

    def test_unlinked(self) -> None:
        chunk = _read("tdsb", b"\x00\x00\x20\x01")
        assert isinstance(chunk, TdsbChunk)
        assert chunk.ratio_unlinked is True

    def test_linked(self) -> None:
        chunk = _read("tdsb", b"\x00\x00\x00\x01")
        assert isinstance(chunk, TdsbChunk)
        assert chunk.ratio_unlinked is False
