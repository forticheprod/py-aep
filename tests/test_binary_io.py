"""Tests for Phase 1 binary I/O foundation."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from py_aep.binary.bin_utils import (
    is_readable,
    read_bytes,
    read_fmt,
    read_pad,
    write_bytes,
    write_fmt,
    write_pad,
)
from py_aep.binary.chunk import (
    Chunk,
    ListChunk,
    _ReadContext,
    _resolve_cdat_context,
    _resolve_ldat_context,
    _resolve_tdum_context,
    read_aep,
    read_chunks,
    read_header,
    write_aep,
    write_chunk,
)
from py_aep.binary.registry import CHUNK_TYPES, register

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
# Group 2: Chunk tests
# -----------------------------------------------------------------------


class TestChunk:
    def test_read_write_roundtrip(self) -> None:
        original = b"\x01\x02\x03\x04\x05"
        buf = BytesIO(original)
        chunk = Chunk.read(buf, len(original), chunk_type="test")
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == original

    def test_chunk_type_preserved(self) -> None:
        chunk = Chunk(chunk_type="abcd", data=b"\xff")
        assert chunk.chunk_type == "abcd"
        restored = Chunk.frombytes(chunk.tobytes(), chunk_type="abcd")
        assert restored.chunk_type == "abcd"
        assert restored.data == b"\xff"

    def test_empty_body(self) -> None:
        chunk = Chunk(chunk_type="empt", data=b"")
        assert chunk.tobytes() == b""
        out = BytesIO()
        assert chunk.write(out) == 0


# -----------------------------------------------------------------------
# Group 3: ListChunk tests
# -----------------------------------------------------------------------


class TestListChunk:
    def test_list_read_write_roundtrip(self) -> None:
        # Build a LIST with two Chunk children
        child1 = Chunk(chunk_type="ch1\x00", data=b"\x01\x02")
        child2 = Chunk(chunk_type="ch2\x00", data=b"\x03")
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
        assert isinstance(restored.chunks[0], Chunk)
        assert restored.chunks[0].data == b"\x01\x02"
        # ch2 has odd body (1 byte), pad byte was written/read
        assert restored.chunks[1].data == b"\x03"

    def test_list_nested(self) -> None:
        inner = ListChunk(
            list_type="innr",
            chunks=[Chunk(chunk_type="leaf", data=b"\xAA\xBB")],
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
        lst = ListChunk(list_type="btdk", data=raw_data)

        buf = BytesIO()
        write_chunk(buf, lst)

        buf.seek(0)
        ct, lb = read_header(buf)
        ctx = _ReadContext()
        restored = ListChunk.read(buf, lb, ctx=ctx)
        assert restored.list_type == "btdk"
        assert restored.data == raw_data
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
        chunk = Chunk(chunk_type="test", data=b"\x01\x02\x03\x04")
        buf = BytesIO()
        write_chunk(buf, chunk)
        buf.seek(0)
        ct, lb = read_header(buf)
        assert ct == "test"
        assert lb == 4

    def test_write_chunk_pad_odd(self) -> None:
        chunk = Chunk(chunk_type="test", data=b"\x01\x02\x03")
        buf = BytesIO()
        total = write_chunk(buf, chunk)
        # 8 header + 3 body + 1 pad = 12
        assert total == 12
        assert len(buf.getvalue()) == 12
        # Last byte should be pad
        assert buf.getvalue()[-1:] == b"\x00"

    def test_write_chunk_pad_even(self) -> None:
        chunk = Chunk(chunk_type="test", data=b"\x01\x02\x03\x04")
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
        write_chunk(buf, Chunk(chunk_type="aaa\x00", data=b"\x01\x02"))
        write_chunk(buf, Chunk(chunk_type="bbb\x00", data=b"\x03\x04"))
        total_size = buf.tell()

        buf.seek(0)
        ctx = _ReadContext()
        chunks = read_chunks(buf, total_size, ctx=ctx)
        assert len(chunks) == 2

    def test_read_chunks_drift_raises(self) -> None:
        # Create a buffer where size doesn't match actual content
        buf = BytesIO()
        write_chunk(buf, Chunk(chunk_type="aaa\x00", data=b"\x01\x02"))
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
            class ZzzzChunk(Chunk):
                pass

            assert "zzzz" in CHUNK_TYPES
            assert CHUNK_TYPES["zzzz"] is ZzzzChunk
        finally:
            CHUNK_TYPES.clear()
            CHUNK_TYPES.update(saved)

    def test_unregistered_falls_to_chunk(self) -> None:
        cls = CHUNK_TYPES.get("nonexistent", Chunk)
        assert cls is Chunk

    def test_registered_chunk_dispatched(self) -> None:
        saved = dict(CHUNK_TYPES)
        try:

            @register("disp")
            class DispChunk(Chunk):
                pass

            buf = BytesIO()
            write_chunk(buf, Chunk(chunk_type="disp", data=b"\xAA"))

            buf.seek(0)
            ct, lb = read_header(buf)
            cls = CHUNK_TYPES.get(ct, Chunk)
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

    def test_ldat_context_empty_siblings(self) -> None:
        ctx = _ReadContext()
        result = _resolve_ldat_context([], ctx)
        assert result == {}

    def test_tdum_context_phase1_empty(self) -> None:
        ctx = _ReadContext()
        result = _resolve_tdum_context([], ctx)
        assert result == {}

    def test_tdum_context_with_tdb4_sibling(self) -> None:
        from py_aep.binary.property_chunks import Tdb4Chunk

        ctx = _ReadContext()
        tdb4 = Tdb4Chunk(chunk_type="tdb4")
        tdb4.color = True
        tdb4.integer = False
        # siblings[2] is the tdb4
        siblings = [Chunk(), Chunk(), tdb4]
        result = _resolve_tdum_context(siblings, ctx)
        assert result == {"is_color": True, "is_integer": False}

    def test_tdum_context_with_raw_sibling(self) -> None:
        ctx = _ReadContext()
        siblings = [Chunk(), Chunk(), Chunk(chunk_type="tdb4", data=b"\x00")]
        result = _resolve_tdum_context(siblings, ctx)
        assert result == {}


# -----------------------------------------------------------------------
# Group 8: fmt_field + _struct_info tests
# -----------------------------------------------------------------------


class TestFmtField:
    def test_struct_info_returns_none_for_raw_chunk(self) -> None:
        from py_aep.binary.fmt_field import _struct_info

        result = _struct_info(Chunk)
        assert result is None

    def test_struct_info_returns_format_for_u4(self) -> None:
        from py_aep.binary.fmt_field import _struct_info
        from py_aep.binary.scalar_chunks import U4Chunk

        info = _struct_info(U4Chunk)
        assert info is not None
        fmt, data_fields, trailing, encodings, optional_start, endians, items_info = info
        assert fmt == "I"
        assert len(data_fields) == 1
        assert data_fields[0].name == "value"
        assert trailing is not None
        assert trailing.name == "_trailing"
        assert encodings == {}
        assert endians == {}
        assert items_info is None
        assert optional_start == 1  # no optional fields

    def test_struct_info_field_count_validation(self) -> None:
        from attrs import define

        from py_aep.binary.fmt_field import _struct_info, fmt_field

        @define
        class BadChunk(Chunk):
            a: int = fmt_field("I")
            b: int = fmt_field("H")
            c: int = fmt_field("B")
            # "IHB" yields 3 values, 3 fields - OK for now.
            # To test mismatch, we'd need a multi-value format with wrong count.

        info = _struct_info(BadChunk)
        assert info is not None
        fmt, data_fields, _, encodings, optional_start, endians, items_info = info
        assert fmt == "IHB"
        assert len(data_fields) == 3
        assert encodings == {}
        assert endians == {}
        assert items_info is None
        assert optional_start == 3  # all required

    def test_struct_info_encoding_tracked(self) -> None:
        from py_aep.binary.fmt_field import _struct_info
        from py_aep.binary.misc_chunks import PrinChunk

        info = _struct_info(PrinChunk)
        assert info is not None
        _, _, _, encodings, _, _, _ = info
        # PrinChunk has match_name (field index 1) and display_name (index 2)
        assert 1 in encodings
        assert encodings[1] == "ascii"
        assert 2 in encodings
        assert encodings[2] == "ascii"

    def test_encoding_ascii_read_write_roundtrip(self) -> None:
        """PrinChunk reads/writes 48-byte ASCII null-terminated strings."""
        from py_aep.binary.misc_chunks import PrinChunk

        # Build raw 104-byte prin body
        reserved_00 = b"\x00" * 4
        match_name = b"ADBE Advanced 3d" + b"\x00" * 32  # 48 bytes
        display_name = b"Classic 3D" + b"\x00" * 38  # 48 bytes
        reserved_68 = b"\x00" * 3
        end_marker = b"\x01"
        raw = reserved_00 + match_name + display_name + reserved_68 + end_marker

        chunk = PrinChunk.read(BytesIO(raw), len(raw), chunk_type="prin")
        assert chunk.match_name == "ADBE Advanced 3d"
        assert chunk.display_name == "Classic 3D"

        # Round-trip
        buf = BytesIO()
        chunk.write(buf)
        assert buf.getvalue() == raw

    def test_encoding_windows1252_read_write_roundtrip(self) -> None:
        """LdtaChunk reads/writes 32-byte windows-1252 null-terminated layer_name."""
        from py_aep.binary.layer_chunks import LdtaChunk

        # Use a windows-1252 character: e-acute (0xe9)
        name = "caf\xe9"
        chunk = LdtaChunk(chunk_type="ldta", layer_name=name)
        assert chunk.layer_name == name

        buf = BytesIO()
        written = chunk.write(buf)
        assert written == 160  # No matte_layer_id

        # Read back
        buf.seek(0)
        chunk2 = LdtaChunk.read(buf, 160, chunk_type="ldta")
        assert chunk2.layer_name == name

    def test_encoding_truncation_on_write(self) -> None:
        """Encoded strings are truncated to fit the fixed field size."""
        from py_aep.binary.misc_chunks import PrinChunk

        # 48-byte field: overlong strings are truncated to 48 chars
        long_name = "A" * 100
        chunk = PrinChunk(chunk_type="prin", match_name=long_name)

        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        chunk2 = PrinChunk.read(buf, 104, chunk_type="prin")
        assert chunk2.match_name == "A" * 48

    def test_ldta_matte_layer_id_from_trailing(self) -> None:
        """LdtaChunk reads matte_layer_id from optional trailing bytes."""
        from py_aep.binary.layer_chunks import LdtaChunk

        # Build 164-byte ldta (160 fixed + 4 optional matte)
        chunk = LdtaChunk(chunk_type="ldta")
        assert chunk.matte_layer_id is None

        buf = BytesIO()
        chunk.write(buf)
        raw_160 = buf.getvalue()
        assert len(raw_160) == 160

        # Append matte_layer_id = 42
        import struct

        raw_164 = raw_160 + struct.pack(">I", 42)
        chunk2 = LdtaChunk.read(BytesIO(raw_164), 164, chunk_type="ldta")
        assert chunk2.matte_layer_id == 42

        # Round-trip
        buf2 = BytesIO()
        chunk2.write(buf2)
        assert buf2.getvalue() == raw_164

    def test_ldta_matte_layer_id_setter(self) -> None:
        """Setting matte_layer_id to a value causes it to be written."""
        from py_aep.binary.layer_chunks import LdtaChunk

        chunk = LdtaChunk(chunk_type="ldta")
        assert chunk.matte_layer_id is None

        chunk.matte_layer_id = 7
        assert chunk.matte_layer_id == 7

        # Write includes the optional field
        buf = BytesIO()
        written = chunk.write(buf)
        assert written == 164

    def test_ldta_matte_layer_id_zero_roundtrip(self) -> None:
        """matte_layer_id=0 (present) is distinct from None (absent)."""
        import struct

        from py_aep.binary.layer_chunks import LdtaChunk

        # 164 bytes: matte_layer_id is 0 (present, not absent)
        chunk = LdtaChunk(chunk_type="ldta")
        buf = BytesIO()
        chunk.write(buf)
        raw_164 = buf.getvalue() + struct.pack(">I", 0)

        chunk2 = LdtaChunk.read(BytesIO(raw_164), 164, chunk_type="ldta")
        assert chunk2.matte_layer_id == 0  # present, not None

        # Round-trip preserves the field
        buf2 = BytesIO()
        chunk2.write(buf2)
        assert buf2.getvalue() == raw_164


# -----------------------------------------------------------------------
# Group 9: BitField descriptor tests
# -----------------------------------------------------------------------


class TestBitField:
    def test_get_set_bit(self) -> None:
        from py_aep.binary.bitfield import BitField

        class Obj:
            raw: int = 0
            flag = BitField("raw", 3)

        obj = Obj()
        assert obj.flag is False
        obj.flag = True
        assert obj.flag is True
        assert obj.raw == 0x08
        obj.flag = False
        assert obj.flag is False
        assert obj.raw == 0x00

    def test_preserves_other_bits(self) -> None:
        from py_aep.binary.bitfield import BitField

        class Obj:
            raw: int = 0xFF
            bit0 = BitField("raw", 0)
            bit7 = BitField("raw", 7)

        obj = Obj()
        assert obj.bit0 is True
        assert obj.bit7 is True
        obj.bit0 = False
        assert obj.raw == 0xFE
        assert obj.bit7 is True


# -----------------------------------------------------------------------
# Group 10: TdsbChunk tests
# -----------------------------------------------------------------------


class TestTdsbChunk:
    def test_roundtrip(self) -> None:
        from py_aep.binary.property_chunks import TdsbChunk

        raw = b"\x00\x00\x10\x03"
        buf = BytesIO(raw)
        chunk = TdsbChunk.read(buf, 4, chunk_type="tdsb")
        assert isinstance(chunk, TdsbChunk)
        assert chunk.roto_bezier == 0
        assert chunk.locked_ratio is True
        assert chunk.dimensions_separated is True
        assert chunk.enabled is True
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw

    def test_with_trailing(self) -> None:
        from py_aep.binary.property_chunks import TdsbChunk

        raw = b"\x01\x00\x00\x01\xAA\xBB"
        buf = BytesIO(raw)
        chunk = TdsbChunk.read(buf, 6, chunk_type="tdsb")
        assert isinstance(chunk, TdsbChunk)
        assert chunk.roto_bezier == 1
        assert chunk.enabled is True
        assert chunk._trailing == b"\xAA\xBB"
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw

    def test_bitfield_write_through(self) -> None:
        from py_aep.binary.property_chunks import TdsbChunk

        chunk = TdsbChunk(chunk_type="tdsb")
        chunk.enabled = True
        chunk.dimensions_separated = True
        assert chunk._enable_flags == 0x03
        chunk.enabled = False
        assert chunk._enable_flags == 0x02


# -----------------------------------------------------------------------
# Group 11: Tdb4Chunk tests
# -----------------------------------------------------------------------


class TestTdb4Chunk:
    def test_roundtrip_124_bytes(self) -> None:
        import struct

        from py_aep.binary.property_chunks import Tdb4Chunk

        # Build a known 124-byte tdb4 body
        fmt = ">HHBB5sB4s5dBBBB8sB15s32s3sB4s"
        raw = struct.pack(
            fmt,
            0xDB99,  # magic
            3,  # dimensions
            0,  # pad1
            0x09,  # spatial(bit3)=1, static(bit0)=1
            b"\x00" * 5,  # pad2
            0x02,  # can_vary_over_time(bit1)=1
            b"\x00" * 4,  # pad3
            0.0001, 1.777778, 1.0, 1.0, 1.0,  # floats
            0,  # pad4
            0x00,  # no_value=0
            0,  # pad5
            0x05,  # vector(bit3)=0, integer(bit2)=1, color(bit0)=1
            b"\x00" * 8,  # pad6
            1,  # animated
            b"\x00" * 15,  # pad7
            b"\x00" * 32,  # pad8
            b"\x00" * 3,  # pad9
            0x01,  # expression_disabled(bit0)=1
            b"\x00" * 4,  # pad10
        )
        assert len(raw) == 124

        buf = BytesIO(raw)
        chunk = Tdb4Chunk.read(buf, 124, chunk_type="tdb4")
        assert isinstance(chunk, Tdb4Chunk)
        assert chunk.dimensions == 3
        assert chunk.is_spatial is True
        assert chunk.static is True
        assert chunk.can_vary_over_time is True
        assert chunk.integer is True
        assert chunk.color is True
        assert chunk.vector is False
        assert chunk.animated == 1
        assert chunk.expression_disabled is True

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw

    def test_undersize_raises(self) -> None:
        from py_aep.binary.property_chunks import Tdb4Chunk

        buf = BytesIO(b"\x00" * 50)
        with pytest.raises(OSError, match="body too short"):
            Tdb4Chunk.read(buf, 50, chunk_type="tdb4")


# -----------------------------------------------------------------------
# Group 12: CdatChunk tests
# -----------------------------------------------------------------------


class TestCdatChunk:
    def test_roundtrip_be(self) -> None:
        import struct

        from py_aep.binary.property_chunks import CdatChunk

        raw = struct.pack(">3d", 1.0, 2.5, -3.0)
        buf = BytesIO(raw)
        chunk = CdatChunk.read(buf, 24, chunk_type="cdat", is_le=False)
        assert chunk.values == [1.0, 2.5, -3.0]
        assert chunk.is_le is False
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw

    def test_roundtrip_le(self) -> None:
        import struct

        from py_aep.binary.property_chunks import CdatChunk

        raw = struct.pack("<2d", 42.0, -1.5)
        buf = BytesIO(raw)
        chunk = CdatChunk.read(buf, 16, chunk_type="cdat", is_le=True)
        assert chunk.values == [42.0, -1.5]
        assert chunk.is_le is True
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw

    def test_empty_body(self) -> None:
        from py_aep.binary.property_chunks import CdatChunk

        buf = BytesIO(b"")
        chunk = CdatChunk.read(buf, 0, chunk_type="cdat")
        assert chunk.values == []
        out = BytesIO()
        written = chunk.write(out)
        assert written == 0


# -----------------------------------------------------------------------
# Group 13: TdumChunk tests
# -----------------------------------------------------------------------


class TestTdumChunk:
    def test_roundtrip_doubles(self) -> None:
        import struct

        from py_aep.binary.property_chunks import TdumChunk

        raw = struct.pack(">2d", 0.0, 100.0)
        buf = BytesIO(raw)
        chunk = TdumChunk.read(buf, 16, chunk_type="tdum")
        assert chunk.values == [0.0, 100.0]
        assert chunk.is_color is False
        assert chunk.is_integer is False
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw

    def test_roundtrip_color(self) -> None:
        import struct

        from py_aep.binary.property_chunks import TdumChunk

        raw = struct.pack(">4f", 0.0, 0.0, 0.0, 1.0)
        buf = BytesIO(raw)
        chunk = TdumChunk.read(buf, 16, chunk_type="tdum", is_color=True)
        assert len(chunk.values) == 4
        assert chunk.is_color is True
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw

    def test_roundtrip_integer(self) -> None:
        import struct

        from py_aep.binary.property_chunks import TdumChunk

        raw = struct.pack(">I", 255)
        buf = BytesIO(raw)
        chunk = TdumChunk.read(buf, 4, chunk_type="tdum", is_integer=True)
        assert chunk.values == [255.0]
        assert chunk.is_integer is True
        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == raw


# ---------------------------------------------------------------------------
# FipsChunk
# ---------------------------------------------------------------------------


class TestFipsChunk:
    def test_roundtrip(self) -> None:
        from py_aep.binary.misc_chunks import FipsChunk

        chunk = FipsChunk(
            chunk_type="fips",
            channels=1,
            zoom_type=1,
            zoom=0.5,
            exposure=2.0,
            roi_top=10,
            roi_left=20,
            roi_bottom=100,
            roi_right=200,
        )
        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        chunk2 = FipsChunk.read(buf, buf.getbuffer().nbytes, chunk_type="fips")
        assert chunk2.channels == 1
        assert chunk2.zoom_type == 1
        assert chunk2.zoom == 0.5
        assert chunk2.exposure == 2.0
        assert chunk2.roi_top == 10
        assert chunk2.roi_left == 20
        assert chunk2.roi_bottom == 100
        assert chunk2.roi_right == 200

    def test_bitfield_descriptors(self) -> None:
        from py_aep.binary.misc_chunks import FipsChunk

        chunk = FipsChunk(chunk_type="fips")
        chunk.checkerboards = True
        chunk.rulers = True
        chunk.region_of_interest = True
        chunk.grid = True
        assert chunk.checkerboards is True
        assert chunk.rulers is True
        assert chunk.region_of_interest is True
        assert chunk.grid is True

        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        chunk2 = FipsChunk.read(buf, buf.getbuffer().nbytes, chunk_type="fips")
        assert chunk2.checkerboards is True
        assert chunk2.rulers is True
        assert chunk2.region_of_interest is True
        assert chunk2.grid is True

    def test_fast_preview_type(self) -> None:
        from py_aep.binary.misc_chunks import FipsChunk

        chunk = FipsChunk(chunk_type="fips")
        assert chunk.fast_preview_type == 0
        chunk.fast_preview_adaptive = True
        assert chunk.fast_preview_type == 1
        chunk.fast_preview_adaptive = False
        chunk.fast_preview_wireframe = True
        assert chunk.fast_preview_type == 4


# ---------------------------------------------------------------------------
# Fth5Chunk
# ---------------------------------------------------------------------------


class TestFth5Chunk:
    def test_roundtrip(self) -> None:
        from py_aep.binary.misc_chunks import FeatherPoint, Fth5Chunk

        pts = [
            FeatherPoint(seg_loc=1, interp_raw=0, rel_seg_loc=0.5,
                         radius=10.0, corner_angle=45.0, tension=0.5),
            FeatherPoint(seg_loc=2, interp_raw=2, rel_seg_loc=0.75,
                         radius=-5.0, corner_angle=0.0, tension=1.0),
        ]
        chunk = Fth5Chunk(chunk_type="fth5", points=pts)
        buf = BytesIO()
        chunk.write(buf)
        assert buf.tell() == 64  # 2 * 32 bytes
        buf.seek(0)
        chunk2 = Fth5Chunk.read(buf, 64, chunk_type="fth5")
        assert len(chunk2.points) == 2
        assert chunk2.points[0].seg_loc == 1
        assert chunk2.points[0].interp_raw == 0
        assert chunk2.points[0].rel_seg_loc == 0.5
        assert chunk2.points[0].radius == 10.0
        assert chunk2.points[1].seg_loc == 2
        assert chunk2.points[1].interp_raw == 2
        assert chunk2.points[1].radius == -5.0

    def test_empty(self) -> None:
        from py_aep.binary.misc_chunks import Fth5Chunk

        chunk = Fth5Chunk(chunk_type="fth5", points=[])
        buf = BytesIO()
        written = chunk.write(buf)
        assert written == 0


# ---------------------------------------------------------------------------
# RoutChunk
# ---------------------------------------------------------------------------


class TestRoutChunk:
    def test_roundtrip(self) -> None:
        from py_aep.binary.render_chunks import RoutChunk, RoutItem

        items = [RoutItem(flags=0x40), RoutItem(flags=0x00)]
        chunk = RoutChunk(
            chunk_type="Rout",
            header=b"\x00\x00\x00\x02",
            items=items,
        )
        assert chunk.items[0].render is True
        assert chunk.items[1].render is False

        buf = BytesIO()
        chunk.write(buf)
        assert buf.tell() == 12  # 4 header + 2 * 4
        buf.seek(0)
        chunk2 = RoutChunk.read(buf, 12, chunk_type="Rout")
        assert len(chunk2.items) == 2
        assert chunk2.items[0].render is True
        assert chunk2.items[1].render is False

    def test_render_bitfield(self) -> None:
        from py_aep.binary.render_chunks import RoutItem

        item = RoutItem()
        assert item.render is False
        item.render = True
        assert item.render is True
        assert item._flags == 0x40


# ---------------------------------------------------------------------------
# OptiChunk variants
# ---------------------------------------------------------------------------


class TestOptiChunk:
    def test_soli_roundtrip(self) -> None:
        from py_aep.binary.footage_chunks import OptiChunk, SoliOptiChunk

        chunk = SoliOptiChunk(
            chunk_type="opti",
            asset_type_int=9,
            color_r=1.0,
            color_g=0.5,
            color_b=0.0,
            solid_name="Red Solid",
        )
        assert chunk.color == [1.0, 0.5, 0.0]

        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        size = buf.getbuffer().nbytes
        chunk2 = OptiChunk.read(buf, size, chunk_type="opti")
        assert isinstance(chunk2, SoliOptiChunk)
        assert chunk2.asset_type == b"Soli"
        assert chunk2.color_r == 1.0
        assert chunk2.color_g == 0.5
        assert chunk2.color_b == 0.0
        assert chunk2.solid_name == "Red Solid"

    def test_psd_roundtrip(self) -> None:
        import struct

        from py_aep.binary.footage_chunks import OptiChunk, PsdOptiChunk

        data = bytearray(344)
        data[0:4] = b"8BPS"
        struct.pack_into(">H", data, 4, 7)
        struct.pack_into(">H", data, 16, 3)
        data[30] = 4
        struct.pack_into("<H", data, 32, 600)
        struct.pack_into("<H", data, 36, 800)
        data[40] = 8
        data[48] = 5
        struct.pack_into("<iiii", data, 78, 10, 20, 610, 820)

        buf = BytesIO(bytes(data))
        chunk = OptiChunk.read(buf, 344, chunk_type="opti")
        assert isinstance(chunk, PsdOptiChunk)
        assert chunk.psd_layer_index == 3
        assert chunk.psd_canvas_height == 600
        assert chunk.psd_canvas_width == 800
        assert chunk.psd_bit_depth == 8
        assert chunk.psd_layer_top == 10

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == bytes(data)

    def test_placeholder_roundtrip(self) -> None:
        import struct

        from py_aep.binary.footage_chunks import (
            OptiChunk,
            PlaceholderOptiChunk,
        )

        name = "MyPlaceholder"
        name_bytes = name.encode("windows-1252")
        trailing = b"\x00" * 20
        data = (b"\x00" * 4 + struct.pack(">H", 2) + b"\x00" * 4
                + name_bytes + trailing)

        buf = BytesIO(data)
        chunk = OptiChunk.read(buf, len(data), chunk_type="opti")
        assert isinstance(chunk, PlaceholderOptiChunk)
        assert chunk.placeholder_name == "MyPlaceholder"
        assert chunk._trailing == name_bytes + trailing

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_unknown_fallback(self) -> None:
        from py_aep.binary.footage_chunks import OptiChunk

        data = b"UNKN" + b"\x00" * 20
        buf = BytesIO(data)
        chunk = OptiChunk.read(buf, len(data), chunk_type="opti")
        assert type(chunk) is OptiChunk
        assert chunk.data == data


# ---------------------------------------------------------------------------
# RoptChunk variants
# ---------------------------------------------------------------------------


class TestRoptChunk:
    def test_cineon_roundtrip(self) -> None:
        from py_aep.binary.render_chunks import CineonRoptChunk, RoptChunk

        chunk = CineonRoptChunk(
            chunk_type="Ropt",
            ten_bit_black_point=95,
            ten_bit_white_point=685,
            converted_black_point=0.0,
            converted_white_point=1.0,
            current_gamma=1.7,
            highlight_expansion=1,
            logarithmic_conversion=1,
            file_format=0,
            bit_depth=10,
        )
        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        size = buf.getbuffer().nbytes
        chunk2 = RoptChunk.read(buf, size, chunk_type="Ropt")
        assert isinstance(chunk2, CineonRoptChunk)
        assert chunk2.ten_bit_black_point == 95
        assert chunk2.ten_bit_white_point == 685
        assert chunk2.current_gamma == 1.7
        assert chunk2.bit_depth == 10

    def test_jpeg_roundtrip(self) -> None:
        from py_aep.binary.render_chunks import JpegRoptChunk, RoptChunk

        chunk = JpegRoptChunk(
            chunk_type="Ropt", quality=80, format_type=1, scans=3,
        )
        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        chunk2 = RoptChunk.read(buf, buf.getbuffer().nbytes, chunk_type="Ropt")
        assert isinstance(chunk2, JpegRoptChunk)
        assert chunk2.quality == 80
        assert chunk2.format_type == 1

    def test_openexr_roundtrip(self) -> None:
        from py_aep.binary.render_chunks import OpenExrRoptChunk, RoptChunk

        chunk = OpenExrRoptChunk(
            chunk_type="Ropt",
            format_code="oEXR",
            compression=3,
            thirty_two_bit_float=1,
            luminance_chroma=0,
            dwa_compression_level=45.0,
        )
        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        chunk2 = RoptChunk.read(buf, buf.getbuffer().nbytes, chunk_type="Ropt")
        assert isinstance(chunk2, OpenExrRoptChunk)
        assert chunk2.compression == 3
        assert chunk2.thirty_two_bit_float == 1
        assert chunk2.dwa_compression_level == 45.0

    def test_targa_roundtrip(self) -> None:
        from py_aep.binary.render_chunks import RoptChunk, TargaRoptChunk

        chunk = TargaRoptChunk(
            chunk_type="Ropt", bits_per_pixel=32, rle_compression=1,
        )
        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        chunk2 = RoptChunk.read(buf, buf.getbuffer().nbytes, chunk_type="Ropt")
        assert isinstance(chunk2, TargaRoptChunk)
        assert chunk2.bits_per_pixel == 32
        assert chunk2.rle_compression == 1

    def test_png_roundtrip(self) -> None:
        from py_aep.binary.render_chunks import PngRoptChunk, RoptChunk

        chunk = PngRoptChunk(
            chunk_type="Ropt",
            width=1920,
            height=1080,
            bit_depth=8,
            compression=0,
        )
        buf = BytesIO()
        chunk.write(buf)
        buf.seek(0)
        chunk2 = RoptChunk.read(buf, buf.getbuffer().nbytes, chunk_type="Ropt")
        assert isinstance(chunk2, PngRoptChunk)
        assert chunk2.width == 1920
        assert chunk2.height == 1080
        assert chunk2.bit_depth == 8

    def test_unknown_fallback(self) -> None:
        from py_aep.binary.render_chunks import RoptChunk

        data = b"UNKN" + b"\x00" * 20
        buf = BytesIO(data)
        chunk = RoptChunk.read(buf, len(data), chunk_type="Ropt")
        assert type(chunk) is RoptChunk
        assert chunk.data == data


# ---------------------------------------------------------------------------
# PardChunk variants
# ---------------------------------------------------------------------------


class TestPardChunk:
    @staticmethod
    def _build_pard(control_type: int, body: bytes,
                    name: str = "Test") -> bytes:
        """Build a raw pard body with standard 56-byte header + body."""
        import struct

        pad_pre = b"\x00" * 15
        ct = struct.pack(">B", control_type)
        raw_name = name.encode("windows-1252")
        raw_name = raw_name + b"\x00" * (32 - len(raw_name))
        pad_post = b"\x00" * 8
        return pad_pre + ct + raw_name + pad_post + body

    def test_color_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import ColorPardChunk, PardChunk

        body = (struct.pack(">4B", 255, 0, 0, 255)
                + struct.pack(">4B", 128, 128, 128, 255)
                + b"\x00" * 64
                + struct.pack(">4B", 255, 255, 255, 255))
        data = self._build_pard(5, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, ColorPardChunk)
        assert chunk.last_color == [255, 0, 0, 255]
        assert chunk.default_color == [128, 128, 128, 255]
        assert chunk.max_color == [255, 255, 255, 255]
        assert chunk.name == "Test"

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_scalar_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import PardChunk, ScalarPardChunk

        body = (struct.pack(">i", 50)
                + b"\x00" * 72
                + struct.pack(">h", 0)
                + b"\x00" * 2
                + struct.pack(">h", 100))
        data = self._build_pard(2, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, ScalarPardChunk)
        assert chunk.last_value == 50
        assert chunk.min_value == 0
        assert chunk.max_value == 100

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_angle_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import AnglePardChunk, PardChunk

        body = struct.pack(">i", 180)
        data = self._build_pard(3, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, AnglePardChunk)
        assert chunk.last_value == 180

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_boolean_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import BooleanPardChunk, PardChunk

        body = struct.pack(">I", 1) + b"\x01" + b"\x00" * 3
        data = self._build_pard(4, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, BooleanPardChunk)
        assert chunk.last_value == 1
        assert chunk.default == 1

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_enum_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import EnumPardChunk, PardChunk

        body = struct.pack(">Iii", 2, 5, 0)
        data = self._build_pard(7, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, EnumPardChunk)
        assert chunk.last_value == 2
        assert chunk.nb_options == 5
        assert chunk.default == 0

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_slider_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import PardChunk, SliderPardChunk

        body = (struct.pack(">d", 50.0)
                + b"\x00" * 52
                + struct.pack(">f", 100.0))
        data = self._build_pard(10, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, SliderPardChunk)
        assert chunk.last_value == 50.0
        assert chunk.max_value == 100.0

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_twod_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import PardChunk, TwoDPardChunk

        body = struct.pack(">ii", 100, 200)
        data = self._build_pard(6, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, TwoDPardChunk)
        assert chunk.last_value_x_raw == 100
        assert chunk.last_value_y_raw == 200

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_threed_roundtrip(self) -> None:
        import struct

        from py_aep.binary.misc_chunks import PardChunk, ThreeDPardChunk

        body = struct.pack(">ddd", 1.0, 2.0, 3.0)
        data = self._build_pard(18, body)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, ThreeDPardChunk)
        assert chunk.last_value_x_raw == 1.0
        assert chunk.last_value_y_raw == 2.0
        assert chunk.last_value_z_raw == 3.0

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_raw_name_preserved(self) -> None:
        """Garbage bytes after null terminator in name field are preserved."""
        import struct

        from py_aep.binary.misc_chunks import AnglePardChunk, PardChunk

        raw_name = b"Opacity\x00olor" + b"\x00" * 20
        assert len(raw_name) == 32

        pad_pre = b"\x00" * 15
        ct = struct.pack(">B", 3)
        pad_post = b"\x00" * 8
        body_after = struct.pack(">i", 90)
        data = pad_pre + ct + raw_name + pad_post + body_after

        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert isinstance(chunk, AnglePardChunk)
        assert chunk.name == "Opacity"

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_unknown_control_type_fallback(self) -> None:
        from py_aep.binary.misc_chunks import PardChunk

        data = self._build_pard(99, b"\x00" * 10)
        buf = BytesIO(data)
        chunk = PardChunk.read(buf, len(data), chunk_type="pard")
        assert type(chunk) is PardChunk
        assert chunk.data == data


# -----------------------------------------------------------------------
# Group 17: ldat_chunks - Lhd3Chunk
# -----------------------------------------------------------------------


class TestLhd3Chunk:
    def _build_lhd3(
        self,
        count: int,
        item_size: int,
        item_type_raw: int,
        trailing: bytes = b"",
    ) -> bytes:
        import struct

        return (
            b"\x00" * 10
            + struct.pack(">H", count)
            + b"\x00" * 6
            + struct.pack(">H", item_size)
            + b"\x00" * 3
            + struct.pack(">B", item_type_raw)
            + trailing
        )

    def test_roundtrip_basic(self) -> None:
        from py_aep.binary.ldat_chunks import LdatItemType, Lhd3Chunk

        data = self._build_lhd3(5, 48, 4)
        buf = BytesIO(data)
        chunk = Lhd3Chunk.read(buf, len(data), chunk_type="lhd3")
        assert chunk.count == 5
        assert chunk.item_size == 48
        assert chunk.item_type_raw == 4
        assert chunk.item_type == LdatItemType.one_d

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_item_type_dispatch(self) -> None:
        from py_aep.binary.ldat_chunks import LdatItemType, Lhd3Chunk

        cases = [
            (1, 2246, LdatItemType.lrdr),
            (1, 128, LdatItemType.litm),
            (2, 16, LdatItemType.gide),
            (4, 152, LdatItemType.color),
            (4, 128, LdatItemType.three_d),
            (4, 104, LdatItemType.two_d_spatial),
            (4, 88, LdatItemType.two_d),
            (4, 80, LdatItemType.orientation),
            (4, 64, LdatItemType.no_value),
            (4, 48, LdatItemType.one_d),
            (4, 16, LdatItemType.marker),
            (4, 8, LdatItemType.shape),
        ]
        for raw, size, expected in cases:
            data = self._build_lhd3(1, size, raw)
            chunk = Lhd3Chunk.frombytes(data, chunk_type="lhd3")
            assert chunk.item_type == expected, f"({raw}, {size})"

    def test_unknown_fallback(self) -> None:
        from py_aep.binary.ldat_chunks import LdatItemType, Lhd3Chunk

        data = self._build_lhd3(1, 999, 99)
        chunk = Lhd3Chunk.frombytes(data, chunk_type="lhd3")
        assert chunk.item_type == LdatItemType.unknown

    def test_with_trailing(self) -> None:
        from py_aep.binary.ldat_chunks import Lhd3Chunk

        trailing = b"\xab\xcd"
        data = self._build_lhd3(2, 64, 4, trailing=trailing)
        chunk = Lhd3Chunk.frombytes(data, chunk_type="lhd3")
        assert chunk._trailing == trailing
        assert chunk.tobytes() == data


# -----------------------------------------------------------------------
# Group 18: ldat_chunks - ShapePoint / GuideItem
# -----------------------------------------------------------------------


class TestShapePoint:
    def test_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import ShapePoint

        data = struct.pack(">ff", 1.5, -2.5)
        sp = ShapePoint.frombytes(data)
        assert sp.x == pytest.approx(1.5)
        assert sp.y == pytest.approx(-2.5)
        assert sp.tobytes() == data


class TestGuideItem:
    def test_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import GuideItem

        data = struct.pack(">IId", 1, 0, 123.456)
        gi = GuideItem.frombytes(data)
        assert gi.orientation_type == 1
        assert gi.position_type == 0
        assert gi.position == pytest.approx(123.456)
        assert gi.tobytes() == data


# -----------------------------------------------------------------------
# Group 19: ldat_chunks - KfNoValue
# -----------------------------------------------------------------------


class TestKfNoValue:
    def test_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import KfNoValue

        data = struct.pack(
            ">Qddddd", 42, 1.0, 2.0, 33.3, 4.0, 66.6
        )
        kf = KfNoValue.frombytes(data)
        assert kf.in_speed == pytest.approx(2.0)
        assert kf.in_influence == pytest.approx(33.3)
        assert kf.out_speed == pytest.approx(4.0)
        assert kf.out_influence == pytest.approx(66.6)
        assert kf.tobytes() == data


# -----------------------------------------------------------------------
# Group 20: ldat_chunks - KfColor
# -----------------------------------------------------------------------


class TestKfColor:
    def test_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import KfColor

        vals = [0, 0.0, 1.0, 33.3, 2.0, 66.6, 0.5, 0.6, 0.7, 1.0]
        vals += [0.0] * 8
        data = struct.pack(">Qd" + "d" * 16, *vals)
        kf = KfColor.frombytes(data)
        assert kf.in_speed == pytest.approx(1.0)
        assert kf.in_influence == pytest.approx(33.3)
        assert kf.out_speed == pytest.approx(2.0)
        assert kf.out_influence == pytest.approx(66.6)
        assert kf.value == pytest.approx([0.5, 0.6, 0.7, 1.0])
        assert kf.tobytes() == data


# -----------------------------------------------------------------------
# Group 21: ldat_chunks - KfMultiDimensional
# -----------------------------------------------------------------------


class TestKfMultiDimensional:
    def test_1d_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import KfMultiDimensional

        # 5 doubles: value, in_speed, in_influence, out_speed, out_influence
        data = struct.pack(">ddddd", 100.0, 1.0, 33.3, 2.0, 66.6)
        kf = KfMultiDimensional.frombytes(data, num_value=1)
        assert kf.value == pytest.approx([100.0])
        assert kf.in_speed == pytest.approx([1.0])
        assert kf.in_influence == pytest.approx([33.3])
        assert kf.out_speed == pytest.approx([2.0])
        assert kf.out_influence == pytest.approx([66.6])
        assert kf.tobytes() == data

    def test_3d_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import KfMultiDimensional

        # 15 doubles for 3D
        raw = list(range(15))
        data = struct.pack(">" + "d" * 15, *[float(x) for x in raw])
        kf = KfMultiDimensional.frombytes(data, num_value=3)
        assert len(kf.value) == 3
        assert len(kf.in_speed) == 3
        assert kf.tobytes() == data


# -----------------------------------------------------------------------
# Group 22: ldat_chunks - KfPosition
# -----------------------------------------------------------------------


class TestKfPosition:
    def test_2d_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import KfPosition

        # 3B pad + 1B flags + 4B pad + (5 + 3*2) f8 = 8 + 88 = 96 bytes
        flags = 0b00000011  # spatial_auto_bezier + spatial_continuous
        prefix = b"\x00\x00\x00" + struct.pack(">B", flags) + b"\x00" * 4
        # 11 doubles: header, in_speed, in_inf, out_speed, out_inf,
        #   val[0], val[1], in_tang[0], in_tang[1], out_tang[0], out_tang[1]
        doubles = [0.0, 1.0, 33.3, 2.0, 66.6, 10.0, 20.0, 0.1, 0.2, -0.1, -0.2]
        data = prefix + struct.pack(">" + "d" * 11, *doubles)

        kf = KfPosition.frombytes(data, num_value=2)
        assert kf.spatial_auto_bezier
        assert kf.spatial_continuous
        assert kf.in_speed == pytest.approx(1.0)
        assert kf.in_influence == pytest.approx(33.3)
        assert kf.value == pytest.approx([10.0, 20.0])
        assert kf.in_spatial_tangents == pytest.approx([0.1, 0.2])
        assert kf.out_spatial_tangents == pytest.approx([-0.1, -0.2])
        assert kf.tobytes() == data

    def test_3d_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import KfPosition

        prefix = b"\x00" * 8
        # 5 + 3*3 = 14 doubles
        doubles = [float(x) for x in range(14)]
        data = prefix + struct.pack(">" + "d" * 14, *doubles)
        kf = KfPosition.frombytes(data, num_value=3)
        assert len(kf.value) == 3
        assert len(kf.in_spatial_tangents) == 3
        assert len(kf.out_spatial_tangents) == 3
        assert kf.tobytes() == data


# -----------------------------------------------------------------------
# Group 23: ldat_chunks - LdatItem
# -----------------------------------------------------------------------


class TestLdatItem:
    def _build_item(
        self,
        item_type: int,
        time_raw: int = 0,
        in_interp: int = 2,
        out_interp: int = 2,
        label: int = 0,
        flags: int = 0,
        payload: bytes = b"",
    ) -> bytes:
        import struct

        return (
            b"\x00"
            + struct.pack(">h", time_raw)
            + b"\x00"
            + struct.pack(">BBBB", in_interp, out_interp, label, flags)
            + payload
        )

    def test_1d_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import LdatItem, LdatItemType

        # 5 doubles for 1D multidimensional
        payload = struct.pack(">ddddd", 50.0, 1.0, 33.3, 2.0, 66.6)
        data = self._build_item(
            LdatItemType.one_d, time_raw=30, in_interp=2, out_interp=1
        )
        data = data + payload
        # total = 8 header + 40 payload = 48

        item = LdatItem.frombytes(data, item_type=LdatItemType.one_d)
        assert item.time_raw == 30
        assert item.in_interpolation_type == 2
        assert item.out_interpolation_type == 1
        assert item.kf_data.value == pytest.approx([50.0])
        assert item.tobytes() == data

    def test_color_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import LdatItem, LdatItemType

        # 144 bytes for KfColor (18 doubles)
        doubles = [0, 0.0] + [1.0, 33.3, 2.0, 66.6] + [0.5, 0.6, 0.7, 1.0] + [0.0] * 8
        payload = struct.pack(">Qd" + "d" * 16, *doubles)
        data = self._build_item(LdatItemType.color) + payload

        item = LdatItem.frombytes(data, item_type=LdatItemType.color)
        assert item.kf_data.value == pytest.approx([0.5, 0.6, 0.7, 1.0])
        assert item.tobytes() == data

    def test_temporal_flags(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import LdatItem, LdatItemType

        # roving=bit5 (0x20), temporal_auto_bezier=bit4 (0x10)
        flags = 0x30
        payload = struct.pack(">Qddddd", 0, 0.0, 0.0, 0.0, 0.0, 0.0)
        data = self._build_item(LdatItemType.no_value, flags=flags) + payload

        item = LdatItem.frombytes(data, item_type=LdatItemType.no_value)
        assert item.roving
        assert item.temporal_auto_bezier
        assert not item.temporal_continuous
        assert item.tobytes() == data

    def test_marker_raw_bytes(self) -> None:
        from py_aep.binary.ldat_chunks import LdatItem, LdatItemType

        payload = b"\x01\x02\x03\x04\x05\x06\x07\x08"
        data = self._build_item(LdatItemType.marker) + payload
        item = LdatItem.frombytes(data, item_type=LdatItemType.marker)
        assert item.kf_data == payload
        assert item.tobytes() == data


# -----------------------------------------------------------------------
# Group 24: ldat_chunks - LdatChunk
# -----------------------------------------------------------------------


class TestLdatChunk:
    def test_shape_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import (
            LdatChunk,
            LdatItemType,
            ShapePoint,
        )

        items_data = b""
        for i in range(3):
            items_data += struct.pack(">ff", float(i), float(i + 1))
        buf = BytesIO(items_data)
        chunk = LdatChunk.read(
            buf,
            len(items_data),
            chunk_type="ldat",
            item_type=LdatItemType.shape,
            item_size=8,
            count=3,
        )
        assert len(chunk.items) == 3
        assert isinstance(chunk.items[0], ShapePoint)
        assert chunk.items[0].x == pytest.approx(0.0)
        assert chunk.items[2].y == pytest.approx(3.0)

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == items_data

    def test_guide_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import (
            GuideItem,
            LdatChunk,
            LdatItemType,
        )

        items_data = struct.pack(">IId", 1, 0, 50.0) + struct.pack(
            ">IId", 2, 0, 100.0
        )
        buf = BytesIO(items_data)
        chunk = LdatChunk.read(
            buf,
            len(items_data),
            chunk_type="ldat",
            item_type=LdatItemType.gide,
            item_size=16,
            count=2,
        )
        assert len(chunk.items) == 2
        assert isinstance(chunk.items[0], GuideItem)
        assert chunk.items[0].position == pytest.approx(50.0)
        assert chunk.items[1].orientation_type == 2

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == items_data

    def test_1d_keyframe_roundtrip(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import (
            LdatChunk,
            LdatItem,
            LdatItemType,
        )

        # Build one item: 8B header + 40B payload = 48B
        header = (
            b"\x00"
            + struct.pack(">h", 15)
            + b"\x00"
            + struct.pack(">BBBB", 2, 2, 0, 0)
        )
        payload = struct.pack(">ddddd", 100.0, 1.0, 33.3, 2.0, 66.6)
        item_data = header + payload
        assert len(item_data) == 48

        buf = BytesIO(item_data)
        chunk = LdatChunk.read(
            buf,
            48,
            chunk_type="ldat",
            item_type=LdatItemType.one_d,
            item_size=48,
            count=1,
        )
        assert len(chunk.items) == 1
        assert isinstance(chunk.items[0], LdatItem)
        assert chunk.items[0].time_raw == 15
        assert chunk.items[0].kf_data.value == pytest.approx([100.0])

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == item_data

    def test_empty_fallback(self) -> None:
        from py_aep.binary.ldat_chunks import LdatChunk, LdatItemType

        data = b"\xaa\xbb\xcc"
        buf = BytesIO(data)
        chunk = LdatChunk.read(
            buf,
            3,
            chunk_type="ldat",
            item_type=LdatItemType.unknown,
            item_size=0,
            count=0,
        )
        assert chunk.items == []
        assert chunk.data == data

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == data

    def test_spatial_promotion(self) -> None:
        import struct

        from py_aep.binary.ldat_chunks import LdatChunk, LdatItemType

        # Build one 3D spatial item: 8B header + 8B prefix + (5+3*3)*8 = 128B
        header = b"\x00" + struct.pack(">h", 0) + b"\x00" + b"\x02\x02\x00\x00"
        prefix = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        doubles = [float(x) for x in range(14)]
        payload = prefix + struct.pack(">" + "d" * 14, *doubles)
        item_data = header + payload
        assert len(item_data) == 128

        buf = BytesIO(item_data)
        chunk = LdatChunk.read(
            buf,
            128,
            chunk_type="ldat",
            item_type=LdatItemType.three_d,
            item_size=128,
            count=1,
            is_spatial=True,
        )
        assert chunk.item_type == LdatItemType.three_d_spatial
        assert len(chunk.items[0].kf_data.value) == 3

        out = BytesIO()
        chunk.write(out)
        assert out.getvalue() == item_data


# -----------------------------------------------------------------------
# Group 25: ldat context resolver
# -----------------------------------------------------------------------


class TestLdatContextResolver:
    def test_with_lhd3_sibling(self) -> None:
        from py_aep.binary.ldat_chunks import LdatItemType, Lhd3Chunk

        lhd3 = Lhd3Chunk(
            chunk_type="lhd3",
            prefix=b"\x00" * 10,
            count=3,
            gap=b"\x00" * 6,
            item_size=48,
            gap2=b"\x00" * 3,
            item_type_raw=4,
        )
        ctx = _ReadContext()
        result = _resolve_ldat_context([lhd3], ctx)
        assert result["item_type"] == LdatItemType.one_d
        assert result["item_size"] == 48
        assert result["count"] == 3

    def test_spatial_promotion_context(self) -> None:
        from py_aep.binary.ldat_chunks import Lhd3Chunk
        from py_aep.binary.property_chunks import Tdb4Chunk

        lhd3 = Lhd3Chunk(
            chunk_type="lhd3",
            prefix=b"\x00" * 10,
            count=1,
            gap=b"\x00" * 6,
            item_size=128,
            gap2=b"\x00" * 3,
            item_type_raw=4,
        )
        tdb4 = Tdb4Chunk(chunk_type="tdb4")
        tdb4.is_spatial = True
        parent_siblings: list[Chunk] = [Chunk(), Chunk(), tdb4]
        ctx = _ReadContext(
            grandparent_list_type="tdbs",
            parent_siblings=parent_siblings,
        )
        result = _resolve_ldat_context([lhd3], ctx)
        assert result.get("is_spatial") is True

    def test_raw_sibling_fallback(self) -> None:
        ctx = _ReadContext()
        result = _resolve_ldat_context(
            [Chunk(chunk_type="lhd3", data=b"\x00" * 24)], ctx
        )
        assert result == {}
