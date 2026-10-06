"""Stdlib decoders for the render matrix: AE's TIFF and AIFF render output.

After Effects' "TIFF Sequence with Alpha" template writes uncompressed 8-bit
RGBA strips (premultiplied); the "AIFF 48kHz" template writes 16-bit PCM.
No third-party imaging library is needed.
"""

from __future__ import annotations

import struct
from pathlib import Path

_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 16: 8}
_CODES = {1: "B", 3: "H", 4: "I", 7: "B", 16: "Q"}


def _tags(data: bytes) -> tuple[str, dict[int, list[int]]]:
    e = "<" if data[:2] == b"II" else ">"
    (ifd,) = struct.unpack(e + "I", data[4:8])
    (n,) = struct.unpack(e + "H", data[ifd : ifd + 2])
    out: dict[int, list[int]] = {}
    for i in range(n):
        entry = ifd + 2 + 12 * i
        tag, typ, cnt = struct.unpack(e + "HHI", data[entry : entry + 8])
        if typ not in _CODES:
            continue
        size = _SIZES[typ] * cnt
        off = entry + 8
        if size > 4:
            (off,) = struct.unpack(e + "I", data[off : off + 4])
        out[tag] = list(struct.unpack(e + _CODES[typ] * cnt, data[off : off + size]))
    return e, out


def _lzw(data: bytes) -> bytes:
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    pos, width, prev = 0, 9, None
    while pos + width <= len(data) * 8:
        code = 0
        for _ in range(width):
            code = (code << 1) | ((data[pos >> 3] >> (7 - (pos & 7))) & 1)
            pos += 1
        if code == 256:
            table, width, prev = table[:258], 9, None
            continue
        if code == 257:
            break
        if prev is None:
            entry = table[code]
        elif code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        else:
            entry = prev + prev[:1]
            table.append(entry)
        out += entry
        prev = entry
        if len(table) + 1 >= (1 << width) and width < 12:
            width += 1
    return bytes(out)


def tiff_pixels(path: Path) -> tuple[int, int, bytes]:
    """`(width, height, RGBA bytes)` of an 8-bit RGBA TIFF."""
    data = path.read_bytes()
    _, t = _tags(data)
    width, height = t[256][0], t[257][0]
    compression = t.get(259, [1])[0]
    raw = bytearray()
    for off, cnt in zip(t[273], t[279]):
        strip = data[off : off + cnt]
        raw += _lzw(strip) if compression == 5 else strip
    return width, height, bytes(raw)


def aiff_samples(path: Path) -> bytes:
    """The raw sample bytes of an AIFF file's `SSND` chunk."""
    data = path.read_bytes()
    pos = 12
    while pos + 8 <= len(data):
        tag = data[pos : pos + 4]
        (size,) = struct.unpack(">I", data[pos + 4 : pos + 8])
        if tag == b"SSND":
            return data[pos + 16 : pos + 8 + size]
        pos += 8 + size + (size & 1)
    return b""
