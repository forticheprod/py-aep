"""Read footage metadata from media-file headers.

After Effects caches footage metadata (dimensions, duration, frame rate, alpha,
audio) in the `.aep` `sspc` chunk and does NOT re-read the media on open. So a
newly created `FileSource` must carry correct values; this module extracts them
from the source file's header. Parsers are added per format.

This reads external media files (not `.aep` chunks), so `struct` is used here.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import IO, TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from typing import Callable, Iterator


class MediaInfo(NamedTuple):
    """Footage metadata read from a media-file header."""

    width: int = 0
    height: int = 0
    duration: float = 0.0
    """Raw media duration in seconds (0 for a still image)."""
    frame_rate: float = 0.0
    """Native frame rate in fps (0 for stills and audio-only media)."""
    has_alpha: bool = False
    has_audio: bool = False
    audio_sample_rate: float = 0.0
    pixel_aspect: float = 1.0
    bit_depth: int = 8
    """Bits per channel (8, 16, 32). Currently read only for PSD/PSB."""
    layer_count: int = 0
    """Number of layers (PSD/PSB only; 0 for a flattened document)."""


def probe_media(file: Path) -> MediaInfo:
    """Read footage metadata from a media file's header.

    Args:
        file: Path to the source media file.

    Raises:
        NotImplementedError: If header probing is not implemented for the
            file's extension.
    """
    suffix = file.suffix.lower()
    parser = _PARSERS.get(suffix)
    if parser is None:
        raise NotImplementedError(
            f"Media-header probing is not implemented for {suffix!r}. "
            f"Supported: {', '.join(sorted(_PARSERS))}."
        )
    with file.open("rb") as fp:
        return parser(fp)


# ---------------------------------------------------------------------------
# PNG - IHDR (still image)
# ---------------------------------------------------------------------------

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _probe_png(fp: IO[bytes]) -> MediaInfo:
    sig = fp.read(8)
    if sig != _PNG_SIGNATURE:
        raise ValueError("Not a valid PNG file (bad signature)")
    # First chunk must be IHDR: length(4) "IHDR"(4) width(4) height(4) bitdepth(1) colortype(1)
    fp.read(4)  # IHDR length
    if fp.read(4) != b"IHDR":
        raise ValueError("PNG missing IHDR chunk")
    width, height = struct.unpack(">II", fp.read(8))
    fp.read(1)  # bit depth
    color_type = fp.read(1)[0]
    # color_type bit 2 (value 4) means an alpha channel (types 4 and 6).
    has_alpha = bool(color_type & 4)
    return MediaInfo(width=width, height=height, has_alpha=has_alpha)


# ---------------------------------------------------------------------------
# WAV - RIFF fmt + data (audio only)
# ---------------------------------------------------------------------------


def _probe_wav(fp: IO[bytes]) -> MediaInfo:
    if fp.read(4) != b"RIFF":
        raise ValueError("Not a valid WAV file (missing RIFF)")
    fp.read(4)  # RIFF chunk size
    if fp.read(4) != b"WAVE":
        raise ValueError("Not a valid WAV file (missing WAVE)")
    sample_rate = 0
    byte_rate = 0
    data_size = 0
    while True:
        header = fp.read(8)
        if len(header) < 8:
            break
        chunk_id, chunk_size = struct.unpack("<4sI", header)
        if chunk_id == b"fmt ":
            fmt = fp.read(chunk_size)
            # audio_format(2) channels(2) sample_rate(4) byte_rate(4) ...
            sample_rate, byte_rate = struct.unpack("<II", fmt[4:12])
        elif chunk_id == b"data":
            data_size = chunk_size
            break
        else:
            fp.seek(chunk_size + (chunk_size & 1), 1)  # chunks are word-aligned
    duration = data_size / byte_rate if byte_rate else 0.0
    return MediaInfo(
        duration=duration,
        has_audio=True,
        audio_sample_rate=float(sample_rate),
    )


# ---------------------------------------------------------------------------
# AIFF / AIFC - IFF COMM chunk (audio only)
# ---------------------------------------------------------------------------


def _read_extended(b: bytes) -> float:
    """Decode an 80-bit IEEE-754 extended float (big-endian, AIFF sampleRate)."""
    exp = (b[0] << 8 | b[1]) & 0x7FFF
    mant = int.from_bytes(b[2:10], "big")
    if exp == 0 and mant == 0:
        return 0.0
    sign = -1.0 if b[0] & 0x80 else 1.0
    # The 64-bit mantissa carries an explicit integer bit (bit 63).
    return sign * mant * 2.0 ** (exp - 16383 - 63)


def _probe_aiff(fp: IO[bytes]) -> MediaInfo:
    if fp.read(4) != b"FORM":
        raise ValueError("Not a valid AIFF/AIFC file (missing FORM)")
    fp.read(4)  # FORM chunk size
    form_type = fp.read(4)
    if form_type not in (b"AIFF", b"AIFC"):
        raise ValueError("Not a valid AIFF/AIFC file (bad form type)")
    while True:
        header = fp.read(8)
        if len(header) < 8:
            break
        chunk_id, chunk_size = struct.unpack(">4sI", header)
        if chunk_id == b"COMM":
            body = fp.read(chunk_size)
            # numChannels(2) numSampleFrames(4) sampleSize(2) sampleRate(10)
            num_frames = struct.unpack(">I", body[2:6])[0]
            sample_rate = _read_extended(body[8:18])
            duration = num_frames / sample_rate if sample_rate else 0.0
            return MediaInfo(
                duration=duration,
                has_audio=True,
                audio_sample_rate=sample_rate,
            )
        # AIFF chunks are word-aligned (an odd size has a trailing pad byte).
        fp.seek(chunk_size + (chunk_size & 1), 1)
    return MediaInfo(has_audio=True)


# ---------------------------------------------------------------------------
# EXR - header attributes (still image; sequences handled by the caller)
# ---------------------------------------------------------------------------

_EXR_MAGIC = b"\x76\x2f\x31\x01"


def _read_cstr(fp: IO[bytes]) -> bytes:
    out = bytearray()
    while True:
        b = fp.read(1)
        if b in (b"", b"\x00"):
            return bytes(out)
        out += b


def _probe_exr(fp: IO[bytes]) -> MediaInfo:
    if fp.read(4) != _EXR_MAGIC:
        raise ValueError("Not a valid EXR file (bad magic)")
    fp.read(4)  # version + flags
    width = height = 0
    has_alpha = False
    pixel_aspect = 1.0
    frame_rate = 0.0
    while True:
        name = _read_cstr(fp)
        if not name:  # empty name terminates the header
            break
        _read_cstr(fp)  # attribute type
        size = struct.unpack("<I", fp.read(4))[0]
        value = fp.read(size)
        # AE sizes EXR footage by the displayWindow (canvas), not the
        # dataWindow (actual pixel-data extent, which may be cropped/oversized).
        if name == b"displayWindow":
            x_min, y_min, x_max, y_max = struct.unpack("<iiii", value)
            width = x_max - x_min + 1
            height = y_max - y_min + 1
        elif name == b"channels":
            has_alpha = _exr_channels_have_alpha(value)
        elif name == b"pixelAspectRatio":
            pixel_aspect = struct.unpack("<f", value)[0]
        elif name == b"framesPerSecond":
            num, den = struct.unpack("<ii", value)
            frame_rate = num / den if den else 0.0
    return MediaInfo(
        width=width,
        height=height,
        has_alpha=has_alpha,
        pixel_aspect=pixel_aspect,
        frame_rate=frame_rate,
    )


def _exr_channels_have_alpha(value: bytes) -> bool:
    """A chlist is a sequence of null-terminated channel names, each followed
    by 16 bytes of channel data, terminated by an empty name."""
    pos = 0
    while pos < len(value):
        end = value.find(b"\x00", pos)
        if end <= pos:  # empty name -> end of list
            break
        name = value[pos:end]
        if name in (b"A", b"a"):
            return True
        pos = end + 1 + 16  # skip name terminator + 16-byte channel descriptor
    return False


# ---------------------------------------------------------------------------
# TIFF - IFD tags (still image)
# ---------------------------------------------------------------------------


def _probe_tiff(fp: IO[bytes]) -> MediaInfo:
    bo = fp.read(2)
    en = "<" if bo == b"II" else ">"
    fp.read(2)  # 42 magic
    ifd_offset = struct.unpack(en + "I", fp.read(4))[0]
    fp.seek(ifd_offset)
    count = struct.unpack(en + "H", fp.read(2))[0]
    width = height = 0
    for _ in range(count):
        entry = fp.read(12)
        tag, typ = struct.unpack(en + "HH", entry[:4])
        val = (
            struct.unpack(en + "H", entry[8:10])[0]
            if typ == 3
            else struct.unpack(en + "I", entry[8:12])[0]
        )
        if tag == 0x0100:
            width = val
        elif tag == 0x0101:
            height = val
    # AE allocates an alpha channel for TIFF regardless of SamplesPerPixel.
    return MediaInfo(width=width, height=height, has_alpha=True)


# ---------------------------------------------------------------------------
# JPEG - SOF marker (still image, never alpha)
# ---------------------------------------------------------------------------


def _probe_jpeg(fp: IO[bytes]) -> MediaInfo:
    fp.read(2)  # SOI
    while True:
        b = fp.read(1)
        if not b:
            break
        if b != b"\xff":
            continue
        marker = fp.read(1)
        while marker == b"\xff":  # skip fill bytes
            marker = fp.read(1)
        m = marker[0]
        # SOF0..SOF15 carry the frame size, except DHT(C4)/JPG(C8)/DAC(CC).
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            fp.read(3)  # length(2) + precision(1)
            height, width = struct.unpack(">HH", fp.read(4))
            return MediaInfo(width=width, height=height, has_alpha=False)
        length = struct.unpack(">H", fp.read(2))[0]
        fp.seek(length - 2, 1)
    return MediaInfo(has_alpha=False)


# ---------------------------------------------------------------------------
# TGA - 18-byte header (still image)
# ---------------------------------------------------------------------------


def _probe_tga(fp: IO[bytes]) -> MediaInfo:
    header = fp.read(18)
    width, height = struct.unpack("<HH", header[12:16])
    depth = header[16]
    # AE treats only 32-bit TGA as having alpha (16-bit's single attribute
    # bit and 24-bit are reported as no-alpha).
    return MediaInfo(width=width, height=height, has_alpha=depth == 32)


# ---------------------------------------------------------------------------
# BMP - DIB header (still image)
# ---------------------------------------------------------------------------


def _probe_bmp(fp: IO[bytes]) -> MediaInfo:
    fp.read(14)  # BITMAPFILEHEADER
    fp.read(4)  # DIB header size
    width = struct.unpack("<i", fp.read(4))[0]
    height = struct.unpack("<i", fp.read(4))[0]
    # AE allocates an alpha channel for BMP regardless of bit depth.
    return MediaInfo(width=abs(width), height=abs(height), has_alpha=True)


# ---------------------------------------------------------------------------
# GIF - logical screen descriptor (still image; AE treats GIF as alpha)
# ---------------------------------------------------------------------------


def _probe_gif(fp: IO[bytes]) -> MediaInfo:
    fp.read(6)  # GIF87a / GIF89a
    width, height = struct.unpack("<HH", fp.read(4))
    return MediaInfo(width=width, height=height, has_alpha=True)


# ---------------------------------------------------------------------------
# PSD / PSB - file header (still image)
# ---------------------------------------------------------------------------


def _probe_psd(fp: IO[bytes]) -> MediaInfo:
    if fp.read(4) != b"8BPS":
        raise ValueError("Not a valid PSD/PSB file (bad signature)")
    version = struct.unpack(">H", fp.read(2))[0]  # 1=PSD, 2=PSB
    fp.read(6)  # reserved
    fp.read(2)  # channel count (ignored; AE composites the merge to RGBA)
    height, width = struct.unpack(">II", fp.read(8))
    bit_depth = struct.unpack(">H", fp.read(2))[0]
    fp.read(2)  # color mode
    # Skip the Color Mode Data and Image Resources sections (length-prefixed).
    fp.seek(struct.unpack(">I", fp.read(4))[0], 1)
    fp.seek(struct.unpack(">I", fp.read(4))[0], 1)
    # Layer and Mask Information: section length and the nested layer-info
    # length are 8 bytes in PSB, 4 in PSD. The signed layer count follows;
    # a negative value flags merged-transparency in the first alpha channel.
    len_fmt = ">Q" if version == 2 else ">I"
    len_size = 8 if version == 2 else 4
    layer_count = 0
    if struct.unpack(len_fmt, fp.read(len_size))[0] > 0:
        if struct.unpack(len_fmt, fp.read(len_size))[0] > 0:
            layer_count = abs(struct.unpack(">h", fp.read(2))[0])
    # AE composites a PSD to RGBA, so the merged footage always has alpha.
    return MediaInfo(
        width=width,
        height=height,
        has_alpha=True,
        bit_depth=bit_depth,
        layer_count=layer_count,
    )


# ---------------------------------------------------------------------------
# MOV / QuickTime - atom tree (video and/or audio)
# ---------------------------------------------------------------------------


def _atoms(data: bytes, start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
    """Yield (type, body_start, atom_end) for each atom in [start, end)."""
    pos = start
    while pos + 8 <= end:
        size = int.from_bytes(data[pos : pos + 4], "big")
        atype = data[pos + 4 : pos + 8]
        body = pos + 8
        if size == 1:  # 64-bit extended size
            size = int.from_bytes(data[pos + 8 : pos + 16], "big")
            body = pos + 16
        elif size == 0:  # extends to end
            size = end - pos
        if size < 8 or pos + size > end:
            return
        yield atype, body, pos + size
        pos += size


def _u(data: bytes, off: int, n: int) -> int:
    return int.from_bytes(data[off : off + n], "big")


def _read_moov(fp: IO[bytes]) -> bytes:
    """Return the body of the top-level `moov` atom, or `b""` if absent.

    Walks top-level atom headers and seeks past their bodies so the bulk
    of the file (`mdat`, often gigabytes) is never read into memory.
    """
    fp.seek(0, 2)
    file_end = fp.tell()
    fp.seek(0)
    pos = 0
    while pos + 8 <= file_end:
        header = fp.read(8)
        if len(header) < 8:
            return b""
        size = int.from_bytes(header[:4], "big")
        atype = header[4:8]
        body = pos + 8
        if size == 1:  # 64-bit extended size
            size = int.from_bytes(fp.read(8), "big")
            body = pos + 16
        elif size == 0:  # extends to end
            size = file_end - pos
        if size < 8 or pos + size > file_end:
            return b""
        if atype == b"moov":
            return fp.read(pos + size - body)
        pos += size
        fp.seek(pos)
    return b""


def _probe_mov(fp: IO[bytes]) -> MediaInfo:
    data = _read_moov(fp)
    width = height = 0
    duration = frame_rate = 0.0
    pixel_aspect = 1.0
    audio_sample_rate = 0.0
    has_audio = has_alpha = False

    for a2, b2, e2 in _atoms(data, 0, len(data)):
        if a2 == b"mvhd":
            v = data[b2]
            ts = _u(data, b2 + (20 if v == 1 else 12), 4)
            dur = _u(data, b2 + 24, 8) if v == 1 else _u(data, b2 + 16, 4)
            duration = dur / ts if ts else 0.0
        elif a2 == b"trak":
            handler = b""
            tw = th = 0
            mts = mdur = sample_delta = 0
            for a3, b3, e3 in _atoms(data, b2, e2):
                if a3 == b"tkhd":
                    tw = _u(data, e3 - 8, 4) >> 16
                    th = _u(data, e3 - 4, 4) >> 16
                elif a3 == b"mdia":
                    for a4, b4, e4 in _atoms(data, b3, e3):
                        if a4 == b"mdhd":
                            v = data[b4]
                            mts = _u(data, b4 + (20 if v == 1 else 12), 4)
                            mdur = (
                                _u(data, b4 + 24, 8) if v == 1 else _u(data, b4 + 16, 4)
                            )
                        elif a4 == b"hdlr":
                            handler = data[b4 + 8 : b4 + 12]
                        elif a4 == b"minf":
                            for a5, b5, e5 in _atoms(data, b4, e4):
                                if a5 != b"stbl":
                                    continue
                                for a6, b6, e6 in _atoms(data, b5, e5):
                                    if a6 == b"stsd":
                                        d, pa = _parse_stsd(data, b6, e6)
                                        if d == 32:
                                            has_alpha = True
                                        if pa:
                                            pixel_aspect = pa
                                    elif a6 == b"stts" and e6 - b6 >= 16:
                                        sample_delta = _u(data, b6 + 12, 4)
            if handler == b"vide":
                width, height = tw, th
                if mts and sample_delta:
                    frame_rate = round(mts / sample_delta, 3)
                if mts and mdur:  # AE uses the video track's duration
                    duration = mdur / mts
            elif handler == b"soun":
                has_audio = True
                # An audio track's media timescale is its sample rate.
                audio_sample_rate = float(mts)
    return MediaInfo(
        width=width,
        height=height,
        duration=duration,
        frame_rate=frame_rate,
        has_alpha=has_alpha,
        has_audio=has_audio,
        audio_sample_rate=audio_sample_rate,
        pixel_aspect=pixel_aspect,
    )


def _parse_stsd(data: bytes, body: int, end: int) -> tuple[int, float]:
    """Return (depth, pixel_aspect) from a video sample description."""
    entry = body + 8  # skip version/flags(4) + entry_count(4)
    if entry + 16 > end:
        return 0, 0.0
    entry_size = _u(data, entry, 4)
    depth = _u(data, entry + 82, 2) if entry + 84 <= end else 0
    pixel_aspect = 0.0
    # pasp extension atom lives after the 86-byte base video sample entry.
    for atype, b, _e in _atoms(data, entry + 86, min(entry + entry_size, end)):
        if atype == b"pasp":
            h_spacing = _u(data, b, 4)
            v_spacing = _u(data, b + 4, 4)
            if v_spacing:
                pixel_aspect = round(h_spacing / v_spacing, 5)
    return depth, pixel_aspect


_PARSERS: dict[str, Callable[[IO[bytes]], MediaInfo]] = {
    ".png": _probe_png,
    ".mov": _probe_mov,
    ".m4v": _probe_mov,
    ".aiff": _probe_aiff,
    ".wav": _probe_wav,
    ".exr": _probe_exr,
    ".tif": _probe_tiff,
    ".tiff": _probe_tiff,
    ".jpg": _probe_jpeg,
    ".jpeg": _probe_jpeg,
    ".tga": _probe_tga,
    ".bmp": _probe_bmp,
    ".gif": _probe_gif,
    ".psd": _probe_psd,
    ".psb": _probe_psd,
}
