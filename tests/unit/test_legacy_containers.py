"""Tests for name containers as older projects write them (AE CC 12.0).

Newer projects wrap a `tdsn`, `fnam`, `pdnm` or `RCom` string in a `Utf8`
child; older ones write the NUL-terminated string itself, in a buffer of
its own size (a `tdsn` of a lone zero byte, a 48-byte `fnam`).
"""

from __future__ import annotations

import struct
from io import BytesIO

from py_aep.binary.chunk import ContainerChunk, read_chunks, write_chunk
from py_aep.binary.item_chunks import NhedChunk
from py_aep.binary.property_chunks import TDSN_SENTINEL, TdsnChunk
from py_aep.binary.scalar_chunks import Utf8Chunk
from py_aep.parsers.project import _nnhd_from_nhed


def _chunk(chunk_type: str, body: bytes) -> bytes:
    pad = b"\x00" if len(body) & 1 else b""
    return chunk_type.encode("ASCII") + struct.pack(">I", len(body)) + body + pad


def _read(data: bytes) -> list:
    return read_chunks(BytesIO(data), len(data))


def _write(chunks: list) -> bytes:
    out = BytesIO()
    for chunk in chunks:
        write_chunk(out, chunk)
    return out.getvalue()


def test_a_one_byte_tdsn_does_not_swallow_the_next_chunk() -> None:
    data = _chunk("tdsn", b"\x00") + _chunk("tdmn", b"ADBE Transform Group".ljust(40, b"\x00"))
    chunks = _read(data)
    assert [c.chunk_type for c in chunks] == ["tdsn", "tdmn"]
    tdsn = chunks[0]
    assert isinstance(tdsn, TdsnChunk)
    # An empty legacy name is an unnamed property.
    assert tdsn.utf8.value == TDSN_SENTINEL
    assert tdsn.utf8.synthetic
    assert _write(chunks) == data


def test_a_legacy_fnam_reads_its_string() -> None:
    body = b"Color Control\x00ol\x00\x00" + bytes(range(1, 32))
    body = body[:48]
    data = _chunk("fnam", body)
    (fnam,) = _read(data)
    assert isinstance(fnam, ContainerChunk)
    (utf8,) = fnam.chunks
    assert isinstance(utf8, Utf8Chunk)
    assert utf8.value == "Color Control"
    # Written back byte for byte, stale bytes included.
    assert _write([fnam]) == data


def test_a_renamed_legacy_fnam_keeps_its_buffer() -> None:
    body = b"Color Control".ljust(48, b"\x00")
    (fnam,) = _read(_chunk("fnam", body))
    fnam.chunks[0].value = "Text Color"
    written = _write([fnam])
    assert written == _chunk("fnam", b"Text Color".ljust(48, b"\x00"))


def test_a_modern_fnam_is_unchanged() -> None:
    utf8 = _chunk("Utf8", b"Glow")
    data = _chunk("fnam", utf8)
    (fnam,) = _read(data)
    (child,) = fnam.chunks
    assert child.value == "Glow"
    assert not child.synthetic
    assert fnam.data == b""
    assert _write([fnam]) == data


def test_nnhd_stands_in_from_nhed() -> None:
    nhed = NhedChunk()
    nhed.bits_per_channel = 1
    nhed.frames_count_type = 1
    nhed.timecode_default_base = 25
    nnhd = _nnhd_from_nhed(nhed)
    assert nnhd.synthetic
    assert (nnhd.bits_per_channel, nnhd.frames_count_type, nnhd.timecode_default_base) == (1, 1, 25)
