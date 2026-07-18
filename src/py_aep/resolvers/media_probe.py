"""Read footage metadata from media-file headers.

After Effects caches footage metadata (dimensions, duration, frame rate, alpha,
audio) in the `.aep` `sspc` chunk and does NOT re-read the media on open. So a
newly created `FileSource` must carry correct values; this module extracts them
from the source file's header. Parsers are added per format.

This reads external media files (not `.aep` chunks), so `struct` is used here.
"""

from __future__ import annotations

import io
import json
import lzma
import math
import re
import struct
import zlib
from datetime import datetime
from fractions import Fraction
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
    channels: int = 0
    """Channel count from the file header (PSD/PSB only; 3 for RGB, 4 RGBA)."""


def probe_media(file: Path, data: bytes | None = None) -> MediaInfo:
    """Read footage metadata from a media file's header.

    Args:
        file: Path to the source media file (drives the format dispatch).
        data: The file's bytes, if the caller already read them; probed
            in memory instead of re-reading `file`.

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
    if data is not None:
        return parser(io.BytesIO(data))
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
    if struct.unpack(en + "H", fp.read(2))[0] != 42:
        return MediaInfo()  # BigTIFF (magic 43) or not a classic TIFF
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
    dib_size = struct.unpack("<I", fp.read(4))[0]
    if dib_size == 12:
        # Legacy OS/2 BITMAPCOREHEADER stores width/height as u2.
        width, height = struct.unpack("<HH", fp.read(4))
    else:
        # BITMAPINFOHEADER (or later): width u4, height s4 (negative = top-down).
        width = struct.unpack("<I", fp.read(4))[0]
        height = abs(struct.unpack("<i", fp.read(4))[0])
    # AE allocates an alpha channel for BMP regardless of bit depth.
    return MediaInfo(width=width, height=height, has_alpha=True)


# ---------------------------------------------------------------------------
# GIF - logical screen descriptor (still image; AE treats GIF as alpha)
# ---------------------------------------------------------------------------


def _probe_gif(fp: IO[bytes]) -> MediaInfo:
    sig = fp.read(6)
    if sig[:3] != b"GIF" or sig[3:] not in (b"87a", b"89a"):
        raise ValueError("Not a valid GIF file (bad signature)")
    width, height = struct.unpack("<HH", fp.read(4))
    return MediaInfo(width=width, height=height, has_alpha=True)


# ---------------------------------------------------------------------------
# PSD / PSB - file header (still image)
# ---------------------------------------------------------------------------


# Additional-layer-info keys whose length field is 8 bytes (not 4) in PSB.
# `luni`/`lyid`/`lsct` and the adjustment keys are not among them.
PSB_8BYTE_KEYS = frozenset(
    {
        b"LMsk",
        b"Lr16",
        b"Lr32",
        b"Layr",
        b"Mt16",
        b"Mt32",
        b"Mtrn",
        b"Alph",
        b"FMsk",
        b"lnk2",
        b"FEid",
        b"FXid",
        b"PxSD",
        b"cinf",
    }
)

# Global additional-info blocks that hold the layer records when the classic
# Layer Info block is empty: 16/32-bit documents use Lr16/Lr32, and some
# writers use Layr.
_LAYER_RECORD_KEYS = (b"Lr16", b"Lr32", b"Layr")


def psd_layer_record_count(fp: IO[bytes], is_psb: bool) -> tuple[int, int]:
    """Walk a PSD/PSB stream to its layer records.

    `fp` must be positioned right after the 26-byte header. Skips the Color
    Mode Data and Image Resources sections and steps into the Layer and Mask
    Information section's nested Layer Info block. 16/32-bit documents keep
    that block empty and store the records inside a global `Lr16`/`Lr32`
    additional-info block instead; the walk continues there.

    Returns:
        `(record_count, remaining)` - the layer record count (`0` for a
        flattened document: an empty or truncated Layer-and-Mask or Layer
        Info section, and no `Lr16`/`Lr32`/`Layr` block) and the record
        bytes left after the count. On a non-zero count, `fp` is positioned
        at the first layer record.

    Shared by `_probe_psd` and `resolvers.psd_layers.read_psd_layers` so the
    two agree on which files count as flattened.
    """
    # Color Mode Data and Image Resources sections (4-byte lengths in both).
    fp.seek(struct.unpack(">I", fp.read(4))[0], 1)
    fp.seek(struct.unpack(">I", fp.read(4))[0], 1)
    # The section length and the nested layer-info length are 8 bytes in PSB,
    # 4 in PSD. The signed record count follows; a negative value flags
    # merged-transparency in the first alpha channel.
    len_fmt = ">Q" if is_psb else ">I"
    len_size = 8 if is_psb else 4
    raw = fp.read(len_size)
    if len(raw) < len_size or struct.unpack(len_fmt, raw)[0] == 0:
        return 0, 0
    section_end = fp.tell() + struct.unpack(len_fmt, raw)[0]
    layer_info_len = struct.unpack(len_fmt, fp.read(len_size))[0]
    if layer_info_len:
        return abs(struct.unpack(">h", fp.read(2))[0]), layer_info_len - 2
    # Empty Layer Info: walk the global additional-info blocks that follow
    # the Global Layer Mask Info for the record container block.
    glm_raw = fp.read(4)
    if len(glm_raw) < 4:
        return 0, 0
    fp.seek(struct.unpack(">I", glm_raw)[0], 1)
    while fp.tell() + 12 <= section_end:
        if fp.read(4) not in (b"8BIM", b"8B64"):
            break
        key = fp.read(4)
        if is_psb and key in PSB_8BYTE_KEYS:
            block_len = struct.unpack(">Q", fp.read(8))[0]
        else:
            block_len = struct.unpack(">I", fp.read(4))[0]
        if key in _LAYER_RECORD_KEYS:
            count_raw = fp.read(2)
            if len(count_raw) < 2:
                return 0, 0
            return abs(struct.unpack(">h", count_raw)[0]), block_len - 2
        # Global blocks are padded to a multiple of 4.
        fp.seek(block_len + (-block_len % 4), 1)
    return 0, 0


# Color-channel count per PSD color mode. A channel beyond the mode's
# color-channel count is alpha: 4 channels mean alpha for RGB but are all
# color for CMYK.
# Modes: 0 Bitmap, 1 Grayscale, 2 Indexed, 3 RGB, 4 CMYK, 8 Duotone, 9 Lab.
_PSD_BASE_CHANNELS = {0: 1, 1: 1, 2: 1, 3: 3, 4: 4, 8: 1, 9: 3}


def iter_image_resources(fp: IO[bytes]) -> Iterator[tuple[int, bytes]]:
    """Yield `(resource_id, body)` for each PSD image resource, in file order.

    `fp` must be positioned right after the 26-byte header (the walker skips
    the color-mode-data section itself); the position is NOT restored. A
    truncated or malformed section ends the iteration silently - callers keep
    their defaults for resources that never arrive.
    """
    try:
        fp.seek(struct.unpack(">I", fp.read(4))[0], 1)  # color mode data
        section = fp.read(struct.unpack(">I", fp.read(4))[0])
    except struct.error:
        return
    pos = 0
    while pos + 10 <= len(section):
        if section[pos : pos + 4] != b"8BIM":
            break
        resource_id = struct.unpack(">H", section[pos + 4 : pos + 6])[0]
        name_len = section[pos + 6]
        pos += 6 + ((name_len + 2) & ~1)
        if pos + 4 > len(section):
            break
        size = struct.unpack(">I", section[pos : pos + 4])[0]
        yield resource_id, section[pos + 4 : pos + 4 + size]
        pos += 4 + size + (size & 1)


def _psd_pixel_aspect(fp: IO[bytes]) -> float:
    """The document pixel aspect from image resource 1064 (1.0 when absent).

    `fp` must be positioned right after the 26-byte header; the position is
    restored before returning. Photoshop stores the ratio as a truncated
    decimal (a user-typed 4/3 becomes 1.333); AE snaps it to the simple
    fraction when it imports (sspc 4/3, psd_layer_styles_single fixture),
    so the ratio is re-rationalized the same way here.
    """
    start = fp.tell()
    ratio = 1.0
    for resource_id, body in iter_image_resources(fp):
        if resource_id == 1064 and len(body) >= 12:
            # u4 version + f8 ratio (x/y of a pixel).
            ratio = struct.unpack(">d", body[4:12])[0]
            break
    fp.seek(start)
    # A corrupt resource can decode to NaN/inf, which Fraction() rejects.
    if ratio <= 0 or not math.isfinite(ratio):
        return 1.0
    return float(Fraction(ratio).limit_denominator(100))


def _probe_psd(fp: IO[bytes]) -> MediaInfo:
    if fp.read(4) != b"8BPS":
        raise ValueError("Not a valid PSD/PSB file (bad signature)")
    version = struct.unpack(">H", fp.read(2))[0]  # 1=PSD, 2=PSB
    fp.read(6)  # reserved
    channels = struct.unpack(">H", fp.read(2))[0]
    height, width = struct.unpack(">II", fp.read(8))
    bit_depth = struct.unpack(">H", fp.read(2))[0]
    color_mode = struct.unpack(">H", fp.read(2))[0]
    pixel_aspect = _psd_pixel_aspect(fp)
    layer_count, _ = psd_layer_record_count(fp, version == 2)
    # AE composites a layered PSD to RGBA (alpha from layer transparency),
    # but treats a flattened document as opaque unless it carries an alpha
    # channel (flattened_rgb_comp.aep: AE writes alpha_mode 3 = no alpha).
    base_channels = _PSD_BASE_CHANNELS.get(color_mode, 3)
    return MediaInfo(
        width=width,
        height=height,
        has_alpha=layer_count > 0 or channels > base_channels,
        bit_depth=bit_depth,
        layer_count=layer_count,
        channels=channels,
        pixel_aspect=pixel_aspect,
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
    movie_ts = 0
    audio_elst_dur = 0.0

    for a2, b2, e2 in _atoms(data, 0, len(data)):
        if a2 == b"mvhd":
            v = data[b2]
            ts = _u(data, b2 + (20 if v == 1 else 12), 4)
            movie_ts = ts
            dur = _u(data, b2 + 24, 8) if v == 1 else _u(data, b2 + 16, 4)
            duration = dur / ts if ts else 0.0
        elif a2 == b"trak":
            handler = b""
            tw = th = 0
            mts = mdur = sample_delta = 0
            elst_seg_dur = 0
            elst_sentinel = 0xFFFFFFFF
            depth = 0
            track_pa = 0.0
            for a3, b3, e3 in _atoms(data, b2, e2):
                if a3 == b"tkhd":
                    tw = _u(data, e3 - 8, 4) >> 16
                    th = _u(data, e3 - 4, 4) >> 16
                elif a3 == b"edts":
                    for ae, be, ee in _atoms(data, b3, e3):
                        if ae == b"elst" and ee - be >= 16:
                            # Entries follow version/flags(4) + entry_count(4);
                            # segment_duration is u32 (v0) or u64 (v1) in the
                            # movie timescale; the all-ones value is an empty edit.
                            ev = data[be]
                            elst_seg_dur = _u(data, be + 8, 8 if ev == 1 else 4)
                            elst_sentinel = (1 << (64 if ev == 1 else 32)) - 1
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
                                        depth, track_pa = _parse_stsd(data, b6, e6)
                                    elif a6 == b"stts" and e6 - b6 >= 16:
                                        sample_delta = _u(data, b6 + 12, 4)
            if handler == b"vide":
                width, height = tw, th
                # depth and pixel aspect are only meaningful for a visual
                # sample entry (reading them from an audio stsd gives garbage).
                if depth == 32:
                    has_alpha = True
                if track_pa:
                    pixel_aspect = track_pa
                if mts and sample_delta:
                    frame_rate = round(mts / sample_delta, 3)
                if mts and mdur:  # AE uses the video track's duration
                    duration = mdur / mts
            elif handler == b"soun":
                has_audio = True
                # An audio track's media timescale is its sample rate.
                audio_sample_rate = float(mts)
                # AAC encoder pre-roll makes the mdhd/mvhd duration about one
                # edit-list media_time too long; the elst segment_duration (in
                # the movie timescale) is the playable length AE reports.
                if elst_seg_dur not in (0, elst_sentinel) and movie_ts:
                    audio_elst_dur = elst_seg_dur / movie_ts
    # For audio-only media (no video track sets width), prefer the edit-list
    # duration over the raw mdhd/mvhd duration.
    if width == 0 and audio_elst_dur:
        duration = audio_elst_dur
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


# ---------------------------------------------------------------------------
# FBX - 3D scene (AE renders at fixed defaults; dims are not in the file)
# ---------------------------------------------------------------------------

_FBX_MAGIC = b"Kaydara FBX Binary  \x00\x1a\x00"


def _probe_fbx(fp: IO[bytes]) -> MediaInfo:
    if fp.read(len(_FBX_MAGIC)) != _FBX_MAGIC:
        raise ValueError("Not a binary FBX file (bad magic)")
    # AE imports an FBX as a 1920x1080, 30 fps, 30 s 3D scene regardless of the
    # scene's authored render settings, and re-reads the geometry on open.
    return MediaInfo(
        width=1920, height=1080, duration=30.0, frame_rate=30.0, has_alpha=True
    )


# ---------------------------------------------------------------------------
# Data footage (txt/csv/json) - AE imports as a 0x0 data item
# ---------------------------------------------------------------------------


def _probe_data(fp: IO[bytes]) -> MediaInfo:
    """Text/CSV/JSON data footage: no dimensions, duration, or audio."""
    return MediaInfo()


# ---------------------------------------------------------------------------
# mgjson - After Effects motion-graphics data stream (duration from samples)
# ---------------------------------------------------------------------------


def _parse_mgjson_time(t: str) -> datetime | None:
    """Parse an mgjson ISO-8601 sample time, tolerating fractional-second
    precision and timezone offsets that Python 3.7's strict
    `datetime.fromisoformat` rejects.

    Returns a naive `datetime` (any timezone offset is dropped - all samples
    in a stream share one offset, so the inter-sample span is unaffected) or
    `None` if the value cannot be parsed.
    """
    s = t.strip()
    # Drop a trailing 'Z' or numeric UTC offset (+HH:MM / +HHMM); the span
    # between samples is offset-independent.
    s = re.sub(r"(Z|[+-]\d{2}:?\d{2})$", "", s)
    # Clamp over-long fractional seconds to 6 digits (strptime %f accepts 1-6).
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _probe_mgjson(fp: IO[bytes]) -> MediaInfo:
    doc = json.load(fp)
    times = []
    for stream in doc.get("dataDynamicSamples", []):
        for sample in stream.get("samples", []):
            t = sample.get("time")
            if t:
                parsed = _parse_mgjson_time(t)
                if parsed is not None:
                    times.append(parsed)
    if not times:
        return MediaInfo(frame_rate=30.0)
    span = (max(times) - min(times)).total_seconds()
    # AE imports mgjson at a fixed 30 fps and reports the span plus one frame.
    return MediaInfo(duration=span + 1.0 / 30.0, frame_rate=30.0)


# ---------------------------------------------------------------------------
# MP3 - MPEG audio frame header (audio only)
# ---------------------------------------------------------------------------

_MP3_SR = {
    3: (44100, 48000, 32000),
    2: (22050, 24000, 16000),
    0: (11025, 12000, 8000),
}
_MP3_BR_M1_L3 = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0)
_MP3_BR_M2_L3 = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0)


def _skip_id3v2(raw: bytes) -> int:
    """Byte offset of the audio data after a leading ID3v2 tag (0 if absent).

    The tag length is a 28-bit syncsafe integer in header bytes 6-9.
    """
    if raw[:3] == b"ID3" and len(raw) >= 10:
        s = raw[6:10]
        return 10 + (
            (s[0] & 0x7F) << 21
            | (s[1] & 0x7F) << 14
            | (s[2] & 0x7F) << 7
            | (s[3] & 0x7F)
        )
    return 0


def _probe_mp3(fp: IO[bytes]) -> MediaInfo:
    # The duration math needs only the file size, the first frame header and
    # the fixed-offset Xing/Info tag - never the audio payload, so read a
    # bounded window instead of the whole file.
    audio_start = _skip_id3v2(fp.read(10))
    fp.seek(0, 2)
    file_size = fp.tell()
    fp.seek(audio_start)
    # Frame header (4) + max side info (32) + Xing tag header (12).
    raw = fp.read(48)
    if len(raw) < 4:
        return MediaInfo(has_audio=True)
    h = struct.unpack_from(">I", raw, 0)[0]
    if (h >> 21) & 0x7FF != 0x7FF:  # 11-bit frame sync
        return MediaInfo(has_audio=True)
    mpeg_ver = (h >> 19) & 0x3  # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
    bitrate_i = (h >> 12) & 0xF
    sr_i = (h >> 10) & 0x3
    padding = (h >> 9) & 0x1
    mono = ((h >> 6) & 0x3) == 3
    sr = _MP3_SR.get(mpeg_ver, (0, 0, 0))[sr_i] if sr_i < 3 else 0
    # `.mp3` is MPEG Audio Layer III by definition, so the Layer III bitrate
    # tables apply; the frame-size coefficient is samples-per-frame/8
    # (1152/8=144 for MPEG-1, 576/8=72 for MPEG-2/2.5).
    bitrate = (_MP3_BR_M1_L3 if mpeg_ver == 3 else _MP3_BR_M2_L3)[bitrate_i] * 1000
    spf = 1152 if mpeg_ver == 3 else 576
    # A Xing/Info header (VBR) carries the exact frame count; else assume CBR.
    side = (17 if mono else 32) if mpeg_ver == 3 else (9 if mono else 17)
    duration = 0.0
    tag_at = 4 + side
    if raw[tag_at : tag_at + 4] in (b"Xing", b"Info"):
        flags = struct.unpack_from(">I", raw, tag_at + 4)[0]
        if flags & 0x1 and sr:
            frames = struct.unpack_from(">I", raw, tag_at + 8)[0]
            duration = frames * spf / sr
    elif bitrate and sr:
        # bitrate >= 32 kbps and sr >= 8 kHz, so frame_size is always > 0.
        frame_size = spf // 8 * bitrate // sr + padding
        duration = (file_size - audio_start) // frame_size * spf / sr
    return MediaInfo(duration=duration, has_audio=True, audio_sample_rate=float(sr))


# ---------------------------------------------------------------------------
# AAC - ADTS frame stream (audio only)
# ---------------------------------------------------------------------------

# ADTS sampling-frequency index -> Hz (indices 13-15 are reserved/explicit).
_AAC_SR = (
    96000,
    88200,
    64000,
    48000,
    44100,
    32000,
    24000,
    22050,
    16000,
    12000,
    11025,
    8000,
    7350,
)


def _adts_frame_len(raw: bytes, pos: int) -> int:
    """13-bit ADTS frame length: low 2 bits of byte 3, all of byte 4, high 3
    bits of byte 5."""
    return (raw[pos + 3] & 0x03) << 11 | raw[pos + 4] << 3 | raw[pos + 5] >> 5


def _is_adts_header(raw: bytes, pos: int, n: int) -> bool:
    """Whether `pos` begins a plausible ADTS frame header.

    Beyond the 12-bit sync word this checks the layer bits (always 0 for ADTS)
    and the sampling-frequency index (< 13), and that the frame length is at
    least a full header - enough to reject a coincidental `0xFF 0xFx` byte pair
    in non-ADTS data.
    """
    return (
        pos + 7 <= n
        and raw[pos] == 0xFF
        and raw[pos + 1] & 0xF0 == 0xF0
        and (raw[pos + 1] >> 1) & 0x3 == 0
        and (raw[pos + 2] >> 2) & 0xF < 13
        and _adts_frame_len(raw, pos) >= 7
    )


def _probe_aac(fp: IO[bytes]) -> MediaInfo:
    """AAC in a raw ADTS stream (audio only).

    Each ADTS frame carries 1024 samples per raw-data-block; the duration is
    the summed sample count divided by the sampling rate. After Effects
    decodes the file via Windows Media Foundation and may report a slightly
    different duration (decoder priming), but it re-derives the value from
    the located file on open, so the header estimate never affects playback.
    """
    audio_start = _skip_id3v2(fp.read(10))
    fp.seek(0, 2)
    file_size = fp.tell()
    fp.seek(audio_start)
    # Locate the first real ADTS frame: a valid header whose successor also
    # syncs (or which ends the file). Requiring the next frame guards against
    # locking onto a coincidental sync word in leading non-ADTS bytes. A
    # 64 KiB window holds several max-size (8191-byte) frames, so only a
    # pathological amount of leading garbage escapes it.
    window = fp.read(65536)
    n = len(window)
    pos = 0
    while pos + 7 <= n:
        if _is_adts_header(window, pos, n):
            nxt = pos + _adts_frame_len(window, pos)
            if audio_start + nxt >= file_size or _is_adts_header(window, nxt, n):
                break
        pos += 1
    else:
        return MediaInfo(has_audio=True)
    sr_i = (window[pos + 2] >> 2) & 0xF
    sr = _AAC_SR[sr_i] if sr_i < len(_AAC_SR) else 0
    # Walk the stream header-to-header, seeking over the audio payloads so
    # the file is never loaded whole.
    total_samples = 0
    fp.seek(audio_start + pos)
    while True:
        hdr = fp.read(7)
        if len(hdr) < 7 or hdr[0] != 0xFF or hdr[1] & 0xF0 != 0xF0:
            break
        frame_len = _adts_frame_len(hdr, 0)
        if frame_len < 7:  # shorter than the header: corrupt, stop scanning
            break
        total_samples += 1024 * ((hdr[6] & 0x03) + 1)
        fp.seek(frame_len - 7, 1)
    duration = total_samples / sr if sr else 0.0
    return MediaInfo(duration=duration, has_audio=True, audio_sample_rate=float(sr))


# ---------------------------------------------------------------------------
# SWF - file header (AE rasterizes the movie to video)
# ---------------------------------------------------------------------------


def _probe_swf(fp: IO[bytes]) -> MediaInfo:
    sig = fp.read(3)
    fp.read(5)  # version (1 byte) + file length (LE u32)
    if sig == b"FWS":
        body = fp.read(21)
    elif sig == b"CWS":
        body = zlib.decompress(fp.read())[:21]
    elif sig == b"ZWS":
        fp.read(4)  # uncompressed length precedes the LZMA stream
        stream = fp.read()
        # A SWF LZMA body is 5 props bytes then the raw stream, with no 8-byte
        # uncompressed-size field; splice one in (unknown = all ones) so the
        # FORMAT_ALONE decoder accepts it.
        body = lzma.decompress(
            stream[:5] + b"\xff" * 8 + stream[5:], format=lzma.FORMAT_ALONE
        )[:21]
    else:
        raise ValueError("Not a valid SWF file (bad signature)")
    # Frame size is a bit-packed RECT (twips): nbits in the top 5 bits, then
    # four nbits-wide fields (xmin, xmax, ymin, ymax). The stage is non-negative.
    nbits = body[0] >> 3
    rect_bytes = (5 + 4 * nbits + 7) // 8
    bits = "".join(format(b, "08b") for b in body[:rect_bytes])
    vals = []
    pos = 5
    for _ in range(4):
        vals.append(int(bits[pos : pos + nbits], 2))
        pos += nbits
    width = (vals[1] - vals[0]) // 20
    height = (vals[3] - vals[2]) // 20
    fr_raw = struct.unpack_from("<H", body, rect_bytes)[0]
    frame_rate = fr_raw / 256.0  # 8.8 fixed-point
    frame_count = struct.unpack_from("<H", body, rect_bytes + 2)[0]
    duration = frame_count / frame_rate if frame_rate else 0.0
    return MediaInfo(
        width=width,
        height=height,
        duration=duration,
        frame_rate=frame_rate,
        has_alpha=True,
    )


# ---------------------------------------------------------------------------
# MPEG-1/2 program stream - sequence header + picture-start-code count
# ---------------------------------------------------------------------------

_MPEG_FR = {
    1: 24000 / 1001,
    2: 24.0,
    3: 25.0,
    4: 30000 / 1001,
    5: 30.0,
    6: 50.0,
    7: 60000 / 1001,
    8: 60.0,
}


def _probe_mpeg(fp: IO[bytes]) -> MediaInfo:
    data = fp.read()
    seq = data.find(b"\x00\x00\x01\xb3")
    if seq < 0:
        raise ValueError("Not a valid MPEG file (no sequence header)")
    val = struct.unpack_from(">I", data, seq + 4)[0]
    width = (val >> 20) & 0xFFF
    height = (val >> 8) & 0xFFF
    fps = _MPEG_FR.get(val & 0xF, 0.0)
    # Program streams carry no global duration and the SCR timeline stops short
    # of the final frames, so count picture start codes. This reads the whole
    # file, which is acceptable for the sizes py_aep handles.
    frames = data.count(b"\x00\x00\x01\x00")
    duration = frames / fps if fps else 0.0
    has_audio = any(data.find(bytes((0, 0, 1, sid))) >= 0 for sid in range(0xC0, 0xE0))
    return MediaInfo(
        width=width,
        height=height,
        duration=duration,
        frame_rate=fps,
        has_audio=has_audio,
    )


# ---------------------------------------------------------------------------
# Radiance HDR (RGBE) - text header with a resolution line (still image)
# ---------------------------------------------------------------------------


def _probe_hdr(fp: IO[bytes]) -> MediaInfo:
    if not fp.readline().startswith(b"#?"):
        raise ValueError("Not a Radiance HDR file (missing '#?' identifier)")
    while True:
        line = fp.readline()
        if not line:
            raise ValueError("Unexpected EOF in Radiance HDR header")
        if line.strip() == b"":  # blank line separates header from resolution
            break
    # Resolution line is two axis specifiers, e.g. "-Y 426 +X 640"; the X
    # specifier gives width and the Y specifier gives height. Radiance allows
    # either order (and either sign), so key off the axis letter, not position.
    parts = fp.readline().split()
    if len(parts) < 4:
        raise ValueError("Cannot parse HDR resolution line")
    dims = {parts[0][-1:]: int(parts[1]), parts[2][-1:]: int(parts[3])}
    if b"X" not in dims or b"Y" not in dims:
        raise ValueError("Cannot parse HDR resolution line (missing X or Y axis)")
    return MediaInfo(width=dims[b"X"], height=dims[b"Y"])


# ---------------------------------------------------------------------------
# AI / EPS / PDF - vector page dimensions (still image, TEXT source format)
# ---------------------------------------------------------------------------

_MEDIABOX_RE = re.compile(
    rb"/MediaBox\s*\[\s*([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s+([\d.+-]+)\s*\]"
)


def _probe_pdf(fp: IO[bytes]) -> MediaInfo:
    m = _MEDIABOX_RE.search(fp.read())
    if m is None:
        return MediaInfo(has_alpha=True)
    x0, y0, x1, y1 = (float(g) for g in m.groups())
    return MediaInfo(width=round(x1 - x0), height=round(y1 - y0), has_alpha=True)


def _probe_eps(fp: IO[bytes]) -> MediaInfo:
    width = height = 0
    hires = False
    for raw in fp:
        line = raw.strip()
        if line.startswith(b"%%HiResBoundingBox:"):
            nums = line.split(b":", 1)[1].split()
            if len(nums) >= 4:
                llx, lly, urx, ury = (float(n) for n in nums[:4])
                width, height = round(urx - llx), round(ury - lly)
                hires = True
        elif not hires and line.startswith(b"%%BoundingBox:"):
            rest = line.split(b":", 1)[1].strip()
            if rest != b"(atend)":
                nums = rest.split()
                if len(nums) >= 4:
                    llx, lly, urx, ury = (float(n) for n in nums[:4])
                    width, height = round(urx - llx), round(ury - lly)
        elif line.startswith(b"%%EndComments"):
            break
    return MediaInfo(width=width, height=height, has_alpha=True)


def _probe_text(fp: IO[bytes]) -> MediaInfo:
    """AI/EPS/PDF dimensions: PDF uses /MediaBox, EPS/PostScript %%BoundingBox."""
    sig = fp.read(4)
    fp.seek(0)
    if sig == b"%PDF":
        return _probe_pdf(fp)
    return _probe_eps(fp)


# ---------------------------------------------------------------------------
# WMV / ASF - header objects (dims exact; duration/fps are decoder-derived)
# ---------------------------------------------------------------------------

_ASF_HEADER = bytes.fromhex("3026B2758E66CF11A6D900AA0062CE6C")
_ASF_FILE_PROPS = bytes.fromhex("A1DCAB8C47A9CF118EE400C00C205365")
_ASF_STREAM_PROPS = bytes.fromhex("9107DCB7B7A9CF118EE600C00C205365")
_ASF_VIDEO_PREFIX = bytes.fromhex("C0EF19BC")  # first 4 LE bytes of the video GUID


def _probe_wmv(fp: IO[bytes]) -> MediaInfo:
    if fp.read(16) != _ASF_HEADER:
        raise ValueError("Not a valid ASF/WMV file (bad header GUID)")
    header_size = struct.unpack("<Q", fp.read(8))[0]
    fp.read(6)  # object count (u32) + 2 reserved bytes
    body = fp.read(max(0, header_size - 30))
    width = height = 0
    duration = 0.0
    pos = 0
    while pos + 24 <= len(body):
        guid = body[pos : pos + 16]
        size = struct.unpack_from("<Q", body, pos + 16)[0]
        if size < 24 or pos + size > len(body):
            break
        payload = body[pos + 24 : pos + size]
        if guid == _ASF_FILE_PROPS and len(payload) >= 64:
            # Send Duration (100ns, +48) is the content length excluding the
            # preroll; it is the closest header value to AE's decoded duration.
            # Fall back to Play Duration (+40, includes preroll) minus preroll
            # (ms, +56) when Send Duration is absent. Neither is exact: AE
            # decodes the video to get the true frame-accurate duration/fps,
            # which the ASF header does not store.
            send_duration = struct.unpack_from("<Q", payload, 48)[0]
            if send_duration:
                duration = send_duration / 1e7
            else:
                play_duration = struct.unpack_from("<Q", payload, 40)[0]
                preroll = struct.unpack_from("<Q", payload, 56)[0]
                duration = max(0.0, play_duration / 1e7 - preroll / 1e3)
        elif guid == _ASF_STREAM_PROPS and len(payload) >= 62:
            # Video stream: type-specific data at +54 begins with enc_width/height.
            if payload[:4] == _ASF_VIDEO_PREFIX:
                width = struct.unpack_from("<I", payload, 54)[0]
                height = struct.unpack_from("<I", payload, 58)[0]
        pos += size
    # ASF carries no frame rate (AE derives it from the decoder); leave 0.
    return MediaInfo(width=width, height=height, duration=duration)


_PARSERS: dict[str, Callable[[IO[bytes]], MediaInfo]] = {
    ".png": _probe_png,
    ".mov": _probe_mov,
    ".m4v": _probe_mov,
    ".m4a": _probe_mov,
    ".fbx": _probe_fbx,
    ".txt": _probe_data,
    ".csv": _probe_data,
    ".json": _probe_data,
    ".mgjson": _probe_mgjson,
    ".mp3": _probe_mp3,
    ".aac": _probe_aac,
    ".swf": _probe_swf,
    ".mpeg": _probe_mpeg,
    ".mpg": _probe_mpeg,
    ".hdr": _probe_hdr,
    ".ai": _probe_text,
    ".eps": _probe_text,
    ".pdf": _probe_text,
    ".wmv": _probe_wmv,
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
