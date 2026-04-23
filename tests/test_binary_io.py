"""Tests for Phase 1 binary I/O foundation."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from py_aep.kaitai.bin_utils import (
    is_readable,
    read_bytes,
    read_fmt,
    read_pad,
    write_bytes,
    write_fmt,
    write_pad,
)
from py_aep.kaitai.chunk import (
    ListChunk,
    RawChunk,
    _ReadContext,
    _resolve_cdat_context,
    _resolve_ldat_context,
    _resolve_otda_context,
    _resolve_tdum_context,
    read_aep,
    read_chunks,
    read_header,
    write_aep,
    write_chunk,
)
from py_aep.kaitai.registry import CHUNK_TYPES, register

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


# -----------------------------------------------------------------------
# Group 1: bin_utils unit tests
# -----------------------------------------------------------------------


class TestBinUtils:
    def test_read_write_fmt_roundtrip(self) -> None:
        buf = BytesIO()
        write_fmt(buf, "I H B", 42, 7, 3)
        buf.seek(0)
        result = read_fmt("I H B", buf)
        assert result == (42, 7, 3)

    def test_read_fmt_short_read(self) -> None:
        buf = BytesIO(b"\x00\x00")
        with pytest.raises(OSError, match="Short read"):
            read_fmt("I", buf)

    def test_write_fmt_returns_size(self) -> None:
        buf = BytesIO()
        n = write_fmt(buf, "I", 1)
        assert n == 4

    def test_write_bytes_returns_size(self) -> None:
        buf = BytesIO()
        n = write_bytes(buf, b"hello")
        assert n == 5

    def test_read_bytes_exact(self) -> None:
        buf = BytesIO(b"hello world")
        assert read_bytes(buf, 5) == b"hello"

    def test_read_bytes_short_read(self) -> None:
        buf = BytesIO(b"\x00")
        with pytest.raises(OSError, match="Short read"):
            read_bytes(buf, 10)

    def test_is_readable_true(self) -> None:
        buf = BytesIO(b"\x00\x00\x00\x00")
        assert is_readable(buf, 4) is True

    def test_is_readable_false(self) -> None:
        buf = BytesIO(b"\x00")
        assert is_readable(buf, 4) is False

    def test_is_readable_rewinds(self) -> None:
        buf = BytesIO(b"\x00\x00\x00\x00")
        pos = buf.tell()
        is_readable(buf, 2)
        assert buf.tell() == pos

    def test_write_pad_odd(self) -> None:
        buf = BytesIO()
        n = write_pad(buf, 5)
        assert n == 1
        assert buf.getvalue() == b"\x00"

    def test_write_pad_even(self) -> None:
        buf = BytesIO()
        n = write_pad(buf, 4)
        assert n == 0
        assert buf.getvalue() == b""

    def test_read_pad_odd(self) -> None:
        buf = BytesIO(b"\x00extra")
        read_pad(buf, 5)
        assert buf.tell() == 1

    def test_read_pad_even(self) -> None:
        buf = BytesIO(b"\x00extra")
        read_pad(buf, 4)
        assert buf.tell() == 0

    def test_endian_parameter(self) -> None:
        buf_be = BytesIO()
        write_fmt(buf_be, "H", 0x0102)
        buf_le = BytesIO()
        write_fmt(buf_le, "H", 0x0102, endian="<")
        assert buf_be.getvalue() != buf_le.getvalue()
        assert buf_be.getvalue() == b"\x01\x02"
        assert buf_le.getvalue() == b"\x02\x01"


# -----------------------------------------------------------------------
# Group 2: RawChunk tests
# -----------------------------------------------------------------------


class TestRawChunk:
    def test_raw_read_write_roundtrip(self) -> None:
        original = b"\x01\x02\x03\x04\x05"
        buf = BytesIO(original)
        chunk = RawChunk.read(buf, len(original), chunk_type="test")
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == original

    def test_raw_chunk_type_preserved(self) -> None:
        chunk = RawChunk(chunk_type="abcd", data=b"\xff")
        assert chunk.chunk_type == "abcd"
        restored = RawChunk.frombytes(chunk.tobytes(), chunk_type="abcd")
        assert restored.chunk_type == "abcd"
        assert restored.data == b"\xff"

    def test_raw_empty_body(self) -> None:
        chunk = RawChunk(chunk_type="empt", data=b"")
        assert chunk.tobytes() == b""
        out = BytesIO()
        assert chunk.write(out) == 0


# -----------------------------------------------------------------------
# Group 3: ListChunk tests
# -----------------------------------------------------------------------


class TestListChunk:
    def test_list_read_write_roundtrip(self) -> None:
        # Build a LIST with two RawChunk children
        child1 = RawChunk(chunk_type="ch1\x00", data=b"\x01\x02")
        child2 = RawChunk(chunk_type="ch2\x00", data=b"\x03")
        lst = ListChunk(list_type="test", chunks=[child1, child2])

        buf = BytesIO()
        write_chunk(buf, lst)
        raw = buf.getvalue()

        buf2 = BytesIO(raw)
        ct, lb = read_header(buf2)
        assert ct == "LIST"
        ctx = _ReadContext()
        restored = ListChunk.read(buf2, lb, ctx=ctx)
        assert restored.list_type == "test"
        assert len(restored.chunks) == 2
        assert isinstance(restored.chunks[0], RawChunk)
        assert restored.chunks[0].data == b"\x01\x02"
        # ch2 has odd body (1 byte), pad byte was written/read
        assert restored.chunks[1].data == b"\x03"

    def test_list_nested(self) -> None:
        inner = ListChunk(
            list_type="innr",
            chunks=[RawChunk(chunk_type="leaf", data=b"\xAA\xBB")],
        )
        outer = ListChunk(list_type="outr", chunks=[inner])

        buf = BytesIO()
        write_chunk(buf, outer)

        buf.seek(0)
        ct, lb = read_header(buf)
        ctx = _ReadContext()
        restored = ListChunk.read(buf, lb, ctx=ctx)
        assert restored.list_type == "outr"
        assert len(restored.chunks) == 1
        inner_r = restored.chunks[0]
        assert isinstance(inner_r, ListChunk)
        assert inner_r.list_type == "innr"
        assert len(inner_r.chunks) == 1
        assert inner_r.chunks[0].data == b"\xAA\xBB"

    def test_list_btdk_binary_data(self) -> None:
        raw_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        lst = ListChunk(list_type="btdk", binary_data=raw_data)

        buf = BytesIO()
        write_chunk(buf, lst)

        buf.seek(0)
        ct, lb = read_header(buf)
        ctx = _ReadContext()
        restored = ListChunk.read(buf, lb, ctx=ctx)
        assert restored.list_type == "btdk"
        assert restored.binary_data == raw_data
        assert restored.chunks == []

    def test_list_empty_children(self) -> None:
        lst = ListChunk(list_type="empt")

        buf = BytesIO()
        write_chunk(buf, lst)

        buf.seek(0)
        ct, lb = read_header(buf)
        ctx = _ReadContext()
        restored = ListChunk.read(buf, lb, ctx=ctx)
        assert restored.list_type == "empt"
        assert restored.chunks == []

    def test_list_accessors_correct_type(self) -> None:
        c0 = RawChunk(chunk_type="lhd3", data=b"\x00")
        c1 = RawChunk(chunk_type="ldat", data=b"\x01")
        lst = ListChunk(list_type="list", chunks=[c0, c1])
        assert lst.lhd3 is c0
        assert lst.ldat is c1

        t0 = RawChunk(chunk_type="tdsb", data=b"\x00")
        t1 = RawChunk(chunk_type="tdsn", data=b"\x01")
        t2 = RawChunk(chunk_type="tdb4", data=b"\x02")
        tdbs = ListChunk(list_type="tdbs", chunks=[t0, t1, t2])
        assert tdbs.tdsb is t0
        assert tdbs.tdsn is t1
        assert tdbs.tdb4 is t2

    def test_list_accessors_wrong_type(self) -> None:
        lst = ListChunk(
            list_type="Fold",
            chunks=[RawChunk(chunk_type="xxxx", data=b"")],
        )
        assert lst.lhd3 is None
        assert lst.ldat is None
        assert lst.tdsb is None
        assert lst.tdsn is None
        assert lst.tdb4 is None

    def test_rifx_chunk_type(self) -> None:
        rifx = ListChunk(list_type="Egg!", chunk_type="RIFX")
        assert rifx.chunk_type == "RIFX"


# -----------------------------------------------------------------------
# Group 4: Full AEP file round-trip
# -----------------------------------------------------------------------


ROUNDTRIP_SAMPLES = [
    "versions/ae2018/complete.aep",
    "versions/ae2022/complete.aep",
    "versions/ae2023/complete.aep",
    "versions/ae2024/complete.aep",
    "versions/ae2025/complete.aep",
    "versions/ae2026/complete.aep",
    "models/property/effects.aep",
    "models/property/2_gaussian.aep",
    "models/property/keyframe_spatial.aep",
    "models/property/keyframe_spatial_bezier_3D.aep",
    "models/property/keyframe_1D.aep",
    "models/property/shape_basic.aep",
    "models/property/mask_add.aep",
    "models/essential_graphics/multiple_controllers.aep",
    "models/composition/bgColor_custom.aep",
    "bugs/29.97_fps_time_scale_3.125.aep",
    "bugs/windows-1250_decoding_error.aep",
    "bugs/outputmodule_path.aep",
]


@pytest.mark.parametrize(
    "sample",
    ROUNDTRIP_SAMPLES,
    ids=[s.replace("/", "__") for s in ROUNDTRIP_SAMPLES],
)
def test_read_write_aep_roundtrip(sample: str, tmp_path: Path) -> None:
    aep_path = SAMPLES_DIR / sample
    if not aep_path.exists():
        pytest.skip(f"Sample not found: {aep_path}")
    original = aep_path.read_bytes()

    with open(aep_path, "rb") as fp:
        rifx, xmp = read_aep(fp)

    out = tmp_path / "roundtrip.aep"
    with open(out, "wb") as fp:
        write_aep(fp, rifx, xmp)

    assert out.read_bytes() == original


# -----------------------------------------------------------------------
# Group 5: Header and write_chunk tests
# -----------------------------------------------------------------------


class TestHeaderAndWriteChunk:
    def test_write_chunk_backpatch(self) -> None:
        chunk = RawChunk(chunk_type="test", data=b"\x01\x02\x03\x04")
        buf = BytesIO()
        write_chunk(buf, chunk)
        buf.seek(0)
        ct, lb = read_header(buf)
        assert ct == "test"
        assert lb == 4

    def test_write_chunk_pad_odd(self) -> None:
        chunk = RawChunk(chunk_type="test", data=b"\x01\x02\x03")
        buf = BytesIO()
        total = write_chunk(buf, chunk)
        # 8 header + 3 body + 1 pad = 12
        assert total == 12
        assert len(buf.getvalue()) == 12
        # Last byte should be pad
        assert buf.getvalue()[-1:] == b"\x00"

    def test_write_chunk_pad_even(self) -> None:
        chunk = RawChunk(chunk_type="test", data=b"\x01\x02\x03\x04")
        buf = BytesIO()
        total = write_chunk(buf, chunk)
        # 8 header + 4 body + 0 pad = 12
        assert total == 12
        assert len(buf.getvalue()) == 12

    def test_read_header_values(self) -> None:
        buf = BytesIO()
        write_fmt(buf, "4s I", b"abcd", 42)
        buf.seek(0)
        ct, lb = read_header(buf)
        assert ct == "abcd"
        assert lb == 42

    def test_read_chunks_exact_boundary(self) -> None:
        # Build a buffer with two chunks that exactly fill the size
        buf = BytesIO()
        write_chunk(buf, RawChunk(chunk_type="aaa\x00", data=b"\x01\x02"))
        write_chunk(buf, RawChunk(chunk_type="bbb\x00", data=b"\x03\x04"))
        total_size = buf.tell()

        buf.seek(0)
        ctx = _ReadContext()
        chunks = read_chunks(buf, total_size, ctx=ctx)
        assert len(chunks) == 2

    def test_read_chunks_drift_raises(self) -> None:
        # Create a buffer where size doesn't match actual content
        buf = BytesIO()
        write_chunk(buf, RawChunk(chunk_type="aaa\x00", data=b"\x01\x02"))
        buf.seek(0)
        ctx = _ReadContext()
        # Claim size is larger than actual content
        with pytest.raises(OSError, match="Short read"):
            read_chunks(buf, 100, ctx=ctx)


# -----------------------------------------------------------------------
# Group 6: Registry tests
# -----------------------------------------------------------------------


class TestRegistry:
    def test_register_decorator(self) -> None:
        # Save and restore registry state
        saved = dict(CHUNK_TYPES)
        try:

            @register("zzzz")
            class ZzzzChunk(RawChunk):
                pass

            assert "zzzz" in CHUNK_TYPES
            assert CHUNK_TYPES["zzzz"] is ZzzzChunk
            assert ZzzzChunk.chunk_type == "zzzz"
        finally:
            CHUNK_TYPES.clear()
            CHUNK_TYPES.update(saved)

    def test_unregistered_falls_to_raw(self) -> None:
        cls = CHUNK_TYPES.get("nonexistent", RawChunk)
        assert cls is RawChunk

    def test_registered_chunk_dispatched(self) -> None:
        saved = dict(CHUNK_TYPES)
        try:

            @register("disp")
            class DispChunk(RawChunk):
                pass

            buf = BytesIO()
            write_chunk(buf, RawChunk(chunk_type="disp", data=b"\xAA"))

            buf.seek(0)
            ct, lb = read_header(buf)
            cls = CHUNK_TYPES.get(ct, RawChunk)
            assert cls is DispChunk
        finally:
            CHUNK_TYPES.clear()
            CHUNK_TYPES.update(saved)


# -----------------------------------------------------------------------
# Group 7: Context resolver tests
# -----------------------------------------------------------------------


class TestContextResolvers:
    def test_cdat_context_otst(self) -> None:
        ctx = _ReadContext(
            parent_list_type="tdbs",
            grandparent_list_type="otst",
        )
        result = _resolve_cdat_context([], ctx)
        assert result == {"is_le": True}

    def test_cdat_context_tdbs(self) -> None:
        ctx = _ReadContext(
            parent_list_type="tdbs",
            grandparent_list_type="tdbs",
        )
        result = _resolve_cdat_context([], ctx)
        assert result == {"is_le": False}

    def test_otda_context_always_be(self) -> None:
        ctx = _ReadContext()
        result = _resolve_otda_context([], ctx)
        assert result == {"is_le": False}

    def test_ldat_context_phase1_empty(self) -> None:
        ctx = _ReadContext()
        result = _resolve_ldat_context([], ctx)
        assert result == {}

    def test_tdum_context_phase1_empty(self) -> None:
        ctx = _ReadContext()
        result = _resolve_tdum_context([], ctx)
        assert result == {}
