"""Channel decoding behind the PSD layer-mask crop (`PsdLayer.mask_box`)."""

from __future__ import annotations

import struct
import zlib

from py_aep.resolvers.psd_layers import _channel_flags


def _delta(data: bytes) -> bytes:
    return bytes((b - a) & 0xFF for a, b in zip(b"\x00" + data, data))


def _zip_predicted(rows: list[list[float]], depth: int) -> bytes:
    """Encode rows as Photoshop's zlib-with-prediction channel data: 16-bit
    samples delta-coded per sample, 32-bit ones split into byte planes and
    delta-coded per byte (the layout of the 16 / 32-bit sample assets)."""
    out = b""
    for row in rows:
        if depth == 16:
            values = [int(v) for v in row]
            deltas = [(b - a) & 0xFFFF for a, b in zip([0] + values, values)]
            out += struct.pack(f">{len(row)}H", *deltas)
        else:
            raw = struct.pack(f">{len(row)}f", *row)
            planes = b"".join(raw[k::4] for k in range(4))
            out += _delta(planes)
    return struct.pack(">H", 3) + zlib.compress(out)


class TestChannelFlags:
    def test_raw_8bit(self) -> None:
        chunk = struct.pack(">H", 0) + bytes([0, 7, 0, 255, 0, 0])
        assert _channel_flags(chunk, 3, 2, 8, False) == [
            b"\x00\x01\x00",
            b"\x01\x00\x00",
        ]

    def test_rle_8bit(self) -> None:
        # Row 1: a 3-byte repeat run; row 2: a literal run.
        row_1 = bytes([256 - 2, 9])
        row_2 = bytes([2, 0, 4, 0])
        chunk = struct.pack(">HHH", 1, len(row_1), len(row_2)) + row_1 + row_2
        assert _channel_flags(chunk, 3, 2, 8, False) == [
            b"\x01\x01\x01",
            b"\x00\x01\x00",
        ]

    def test_zip_predicted_16bit(self) -> None:
        rows = [[0, 300, 0, 65535], [256, 0, 0, 1]]
        chunk = _zip_predicted(rows, 16)
        assert _channel_flags(chunk, 4, 2, 16, False) == [
            b"\x00\x01\x00\x01",
            b"\x01\x00\x00\x01",
        ]

    def test_zip_predicted_32bit(self) -> None:
        rows = [[0.0, 0.5, 0.0, 1.0], [2.0, 0.0, 1e-30, 0.0]]
        chunk = _zip_predicted(rows, 32)
        assert _channel_flags(chunk, 4, 2, 32, False) == [
            b"\x00\x01\x00\x01",
            b"\x01\x00\x01\x00",
        ]

    def test_zip_predicted_8bit(self) -> None:
        chunk = struct.pack(">H", 3) + zlib.compress(_delta(bytes([0, 5, 5, 0])))
        assert _channel_flags(chunk, 4, 1, 8, False) == [b"\x00\x01\x01\x00"]
