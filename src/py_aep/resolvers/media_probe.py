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
    """Bits per channel (8, 16, 32). Read for PSD/PSB, DPX/Cineon and HEIF."""
    layer_count: int = 0
    """Number of layers (PSD/PSB only; 0 for a flattened document)."""
    channels: int = 0
    """Channel count from the file header (PSD/PSB only; 3 for RGB, 4 RGBA)."""
    icc_profile: bytes | None = None
    """The ICC color profile the file embeds, for the formats that can carry
    one (PNG, JPEG, TIFF, PSD/PSB). After Effects records it in the footage
    `LIST:CLRS` and shows it as "Embedded"; `None` means the file carries
    none, and AE assigns a profile instead."""


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
    fp.seek(7, 1)  # rest of IHDR (compression/filter/interlace) + its CRC
    has_trns, icc_profile = _png_color_chunks(fp)
    return MediaInfo(
        width=width,
        height=height,
        has_alpha=has_alpha or has_trns,
        icc_profile=icc_profile,
    )


def _png_color_chunks(fp: IO[bytes]) -> tuple[bool, bytes | None]:
    """The `tRNS` presence and `iCCP` profile of a PNG, if any.

    AE reports alpha for a `tRNS`-carrying PNG of colour type 0, 2 and 3 alike:
    the chunk names a transparent colour, or per-palette-entry alpha, for the
    types that have no alpha channel of their own. `fp` must be positioned at
    the first chunk after IHDR. Both chunks precede the image data, so the
    scan stops there.
    """
    has_trns = False
    icc_profile = None
    while True:
        header = fp.read(8)
        if len(header) < 8:
            break
        length, chunk_type = struct.unpack(">I4s", header)
        if chunk_type in (b"IDAT", b"IEND"):
            break
        if chunk_type == b"tRNS":
            has_trns = True
        elif chunk_type == b"iCCP":
            icc_profile = _png_iccp(fp.read(length))
            fp.seek(4, 1)  # CRC
            continue
        fp.seek(length + 4, 1)  # chunk body + CRC
    return has_trns, icc_profile


def _png_iccp(body: bytes) -> bytes | None:
    """The profile in an `iCCP` chunk: a name, NUL, compression method, then
    the deflated profile. An unreadable one counts as absent, the way AE
    treats it."""
    split = body.find(b"\x00")
    if split < 0 or body[split + 1 : split + 2] != b"\x00":  # 0 = deflate
        return None
    try:
        return zlib.decompress(body[split + 2 :])
    except zlib.error:
        return None


# ---------------------------------------------------------------------------
# WAV - RIFF fmt + data (audio only)
# ---------------------------------------------------------------------------


#: `RF64` and `BW64` carry the same WAVE payload as `RIFF` but move the 64-bit
#: sizes into a `ds64` chunk, which lets them exceed 4 GB. AE imports both.
_WAV_RIFF_IDS = (b"RIFF", b"RF64", b"BW64")


def _probe_wav(fp: IO[bytes]) -> MediaInfo:
    riff_id = fp.read(4)
    if riff_id not in _WAV_RIFF_IDS:
        raise ValueError("Not a valid WAV file (missing RIFF)")
    fp.read(4)  # RIFF chunk size (0xFFFFFFFF for RF64; the real one is in ds64)
    if fp.read(4) != b"WAVE":
        raise ValueError("Not a valid WAV file (missing WAVE)")
    fp.seek(0, 2)
    file_size = fp.tell()
    fp.seek(12)
    sample_rate = 0
    byte_rate = 0
    data_size = 0
    ds64_data_size = 0
    while True:
        header = fp.read(8)
        if len(header) < 8:
            break
        chunk_id, chunk_size = struct.unpack("<4sI", header)
        if chunk_id == b"fmt ":
            fmt = fp.read(chunk_size)
            # audio_format(2) channels(2) sample_rate(4) byte_rate(4) ...
            sample_rate, byte_rate = struct.unpack("<II", fmt[4:12])
        elif chunk_id == b"ds64":
            # riffSize(8) dataSize(8) sampleCount(8) tableLength(4) ...
            body = fp.read(chunk_size)
            if len(body) >= 16:
                ds64_data_size = struct.unpack("<Q", body[8:16])[0]
        elif chunk_id == b"data":
            data_size = ds64_data_size or chunk_size
            # A writer streaming to a pipe cannot seek back to patch the size,
            # so it leaves 0xFFFFFFFF behind. Trust the bytes that are actually
            # present instead - AE takes the declared size at face value and
            # reports a 6-hour duration, which is not worth reproducing.
            start = fp.tell()
            if data_size == 0xFFFFFFFF or start + data_size > file_size:
                data_size = file_size - start
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


# Colour channels per TIFF PhotometricInterpretation; a sample beyond them is
# alpha. Modes: 0/1 bilevel+greyscale, 2 RGB, 3 palette, 5 CMYK, 6 YCbCr.
_TIFF_BASE_CHANNELS = {0: 1, 1: 1, 2: 3, 3: 1, 5: 4, 6: 3}

# Struct codes for the IFD value types BigTIFF stores dimensions in.
_BIGTIFF_VALUE_FMT = {3: "H", 4: "I", 16: "Q"}


#: TIFF tag 34675: the embedded ICC profile.
_TIFF_ICC_TAG = 0x8773


def _probe_bigtiff(fp: IO[bytes], en: str) -> MediaInfo:
    """Probe a BigTIFF (magic 43): 8-byte offsets and 20-byte IFD entries.

    AE reads BigTIFF, so returning 0x0 would write an unusable footage item.
    Unlike AE's classic-TIFF path, which always reports an alpha channel, the
    BigTIFF path honours SamplesPerPixel: a 3-sample RGB BigTIFF imports opaque
    and a 4-sample one imports with alpha.
    """
    if struct.unpack(en + "H", fp.read(2))[0] != 8:
        raise ValueError("Unsupported BigTIFF offset size (expected 8)")
    fp.read(2)  # reserved, always 0
    fp.seek(struct.unpack(en + "Q", fp.read(8))[0])
    width = height = samples = 0
    photometric = 2
    icc_span: tuple[int, int] | None = None
    for _ in range(struct.unpack(en + "Q", fp.read(8))[0]):
        entry = fp.read(20)
        if len(entry) < 20:
            break
        tag, typ = struct.unpack(en + "HH", entry[:4])
        if tag == _TIFF_ICC_TAG:
            length = struct.unpack_from(en + "Q", entry, 4)[0]
            if length > 8:  # values this long are stored by offset
                icc_span = (struct.unpack_from(en + "Q", entry, 12)[0], length)
            continue
        fmt = _BIGTIFF_VALUE_FMT.get(typ)
        if fmt is None:
            continue
        # A value of 8 bytes or fewer is stored inline in the value field.
        val = struct.unpack_from(en + fmt, entry, 12)[0]
        if tag == 0x0100:
            width = val
        elif tag == 0x0101:
            height = val
        elif tag == 0x0106:
            photometric = val
        elif tag == 0x0115:
            samples = val
    icc_profile = None
    if icc_span is not None:
        fp.seek(icc_span[0])
        icc_profile = fp.read(icc_span[1])
    base = _TIFF_BASE_CHANNELS.get(photometric, 3)
    return MediaInfo(
        width=width,
        height=height,
        has_alpha=samples > base,
        icc_profile=icc_profile,
    )


def _probe_tiff(fp: IO[bytes]) -> MediaInfo:
    bo = fp.read(2)
    if bo not in (b"II", b"MM"):
        raise ValueError(f"Not a valid TIFF file (bad byte order {bo!r})")
    en = "<" if bo == b"II" else ">"
    version = struct.unpack(en + "H", fp.read(2))[0]
    if version == 43:
        return _probe_bigtiff(fp, en)
    if version != 42:
        raise ValueError(f"Not a valid TIFF file (bad magic {version})")
    ifd_offset = struct.unpack(en + "I", fp.read(4))[0]
    fp.seek(ifd_offset)
    count = struct.unpack(en + "H", fp.read(2))[0]
    width = height = 0
    icc_span: tuple[int, int] | None = None
    for _ in range(count):
        entry = fp.read(12)
        tag, typ = struct.unpack(en + "HH", entry[:4])
        length = struct.unpack(en + "I", entry[4:8])[0]
        val = (
            struct.unpack(en + "H", entry[8:10])[0]
            if typ == 3
            else struct.unpack(en + "I", entry[8:12])[0]
        )
        if tag == 0x0100:
            width = val
        elif tag == 0x0101:
            height = val
        elif tag == _TIFF_ICC_TAG and length > 4:
            icc_span = (val, length)  # values this long are stored by offset
    icc_profile = None
    if icc_span is not None:
        fp.seek(icc_span[0])
        icc_profile = fp.read(icc_span[1])
    # AE allocates an alpha channel for TIFF regardless of SamplesPerPixel.
    return MediaInfo(
        width=width, height=height, has_alpha=True, icc_profile=icc_profile
    )


# ---------------------------------------------------------------------------
# JPEG - SOF marker (still image, never alpha)
# ---------------------------------------------------------------------------


def _probe_jpeg(fp: IO[bytes]) -> MediaInfo:
    fp.read(2)  # SOI
    width = height = 0
    # An ICC profile too large for one segment is split over numbered APP2
    # chunks that have to be concatenated in order.
    icc_chunks: dict[int, bytes] = {}
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
        if m == 0xDA:  # start of scan: no metadata past here
            break
        # SOF0..SOF15 carry the frame size, except DHT(C4)/JPG(C8)/DAC(CC).
        if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
            fp.read(3)  # length(2) + precision(1)
            height, width = struct.unpack(">HH", fp.read(4))
            continue
        length = struct.unpack(">H", fp.read(2))[0]
        if m == 0xE2:  # APP2, where an ICC profile lives
            body = fp.read(length - 2)
            if body.startswith(b"ICC_PROFILE\x00"):
                icc_chunks[body[12]] = body[14:]
            continue
        fp.seek(length - 2, 1)
    icc_profile = b"".join(icc_chunks[key] for key in sorted(icc_chunks)) or None
    return MediaInfo(
        width=width, height=height, has_alpha=False, icc_profile=icc_profile
    )


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


def _skip_gif_sub_blocks(fp: IO[bytes]) -> None:
    """Seek past a chain of GIF data sub-blocks, up to its 0-length terminator."""
    while True:
        size = fp.read(1)
        if not size or size == b"\x00":
            return
        fp.seek(size[0], 1)


def _gif_frame_timing(fp: IO[bytes]) -> tuple[int, int]:
    """Return `(image count, summed delay in hundredths of a second)`.

    `fp` must be positioned after the logical screen descriptor and any global
    colour table. AE plays an animated GIF at the rate the Graphic Control
    Extension delays imply, so they decide both duration and frame rate.
    """
    frames = delay = 0
    while True:
        block = fp.read(1)
        if not block or block == b"\x3b":  # trailer
            return frames, delay
        if block == b"\x21":  # extension
            if fp.read(1) == b"\xf9":  # graphic control
                size = fp.read(1)
                if not size:
                    return frames, delay
                body = fp.read(size[0])
                if len(body) >= 3:
                    delay += struct.unpack_from("<H", body, 1)[0]
            _skip_gif_sub_blocks(fp)
        elif block == b"\x2c":  # image descriptor
            frames += 1
            fp.seek(8, 1)  # left, top, width, height
            packed = fp.read(1)
            if not packed:
                return frames, delay
            if packed[0] & 0x80:  # local colour table
                fp.seek(3 * (1 << ((packed[0] & 0x07) + 1)), 1)
            fp.read(1)  # LZW minimum code size
            _skip_gif_sub_blocks(fp)
        else:  # not a block introducer: the stream is not walkable
            return frames, delay


def _probe_gif(fp: IO[bytes]) -> MediaInfo:
    sig = fp.read(6)
    if sig[:3] != b"GIF" or sig[3:] not in (b"87a", b"89a"):
        raise ValueError("Not a valid GIF file (bad signature)")
    width, height = struct.unpack("<HH", fp.read(4))
    packed = fp.read(1)[0]
    fp.read(2)  # background colour index + pixel aspect ratio
    if packed & 0x80:  # global colour table
        fp.seek(3 * (1 << ((packed & 0x07) + 1)), 1)
    frames, delay = _gif_frame_timing(fp)
    if frames < 2:
        return MediaInfo(width=width, height=height, has_alpha=True)  # a still
    if delay == 0:
        # Nothing in the file says how fast an all-zero-delay GIF should run.
        # AE stretches it to roughly two seconds, giving every frame the same
        # floor(200 / frames) hundredths - measured at 3, 5, 7, 9 and 14
        # frames. (ffmpeg instead substitutes a flat 10 hundredths.)
        delay = frames * max(1, 200 // frames)
    duration = delay / 100.0
    return MediaInfo(
        width=width,
        height=height,
        duration=duration,
        frame_rate=round(frames / duration, 3),
        has_alpha=True,
    )


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


def _psd_image_resources(fp: IO[bytes]) -> tuple[float, bytes | None]:
    """The document pixel aspect (resource 1064, 1.0 when absent) and the
    embedded ICC profile (resource 1039, `None` when absent).

    `fp` must be positioned right after the 26-byte header; the position is
    restored before returning. Photoshop stores the ratio as a truncated
    decimal (a user-typed 4/3 becomes 1.333); AE snaps it to the simple
    fraction when it imports (sspc 4/3, psd_layer_styles_single fixture),
    so the ratio is re-rationalized the same way here.
    """
    start = fp.tell()
    ratio = 1.0
    icc_profile = None
    for resource_id, body in iter_image_resources(fp):
        if resource_id == 1064 and len(body) >= 12:
            # u4 version + f8 ratio (x/y of a pixel).
            ratio = struct.unpack(">d", body[4:12])[0]
        elif resource_id == 1039:
            icc_profile = body
    fp.seek(start)
    # A corrupt resource can decode to NaN/inf, which Fraction() rejects.
    if ratio <= 0 or not math.isfinite(ratio):
        return 1.0, icc_profile
    return float(Fraction(ratio).limit_denominator(100)), icc_profile


def _probe_psd(fp: IO[bytes]) -> MediaInfo:
    if fp.read(4) != b"8BPS":
        raise ValueError("Not a valid PSD/PSB file (bad signature)")
    version = struct.unpack(">H", fp.read(2))[0]  # 1=PSD, 2=PSB
    fp.read(6)  # reserved
    channels = struct.unpack(">H", fp.read(2))[0]
    height, width = struct.unpack(">II", fp.read(8))
    bit_depth = struct.unpack(">H", fp.read(2))[0]
    color_mode = struct.unpack(">H", fp.read(2))[0]
    pixel_aspect, icc_profile = _psd_image_resources(fp)
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
        icc_profile=icc_profile,
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


def _s(data: bytes, off: int, n: int) -> int:
    return int.from_bytes(data[off : off + n], "big", signed=True)


def _top_level_atoms(fp: IO[bytes], wanted: bytes) -> Iterator[bytes]:
    """Yield the body of each top-level atom of type `wanted`.

    Other bodies are seeked over, so the bulk of the file (`mdat`, often
    gigabytes) is never read into memory.
    """
    fp.seek(0, 2)
    file_end = fp.tell()
    fp.seek(0)
    pos = 0
    while pos + 8 <= file_end:
        header = fp.read(8)
        if len(header) < 8:
            return
        size = int.from_bytes(header[:4], "big")
        atype = header[4:8]
        body = pos + 8
        if size == 1:  # 64-bit extended size
            size = int.from_bytes(fp.read(8), "big")
            body = pos + 16
        elif size == 0:  # extends to end
            size = file_end - pos
        if size < 8 or pos + size > file_end:
            return
        if atype == wanted:
            yield fp.read(pos + size - body)
        pos += size
        fp.seek(pos)


def _read_moov(fp: IO[bytes]) -> bytes:
    """Return the body of the top-level `moov` atom, or `b""` if absent."""
    return next(_top_level_atoms(fp, b"moov"), b"")


def _tkhd_axes_swapped(data: bytes, end: int) -> bool:
    """Whether the `tkhd` display matrix turns the track a quarter turn.

    AE honours the matrix: a 640x360 track carrying a 90-degree rotation
    imports as 360x640. The 3x3 matrix sits immediately before the 16.16
    width/height pair, so it ends 8 bytes before the atom does (which holds
    for both `tkhd` versions). Only the a/b/c/d terms decide whether x maps
    onto y; a half turn leaves them on the diagonal and needs no swap.
    """
    matrix = end - 44
    if matrix < 0:
        return False
    a, b = _s(data, matrix, 4), _s(data, matrix + 4, 4)
    c, d = _s(data, matrix + 12, 4), _s(data, matrix + 16, 4)
    return abs(b) > abs(a) and abs(c) > abs(d)


def _stts_totals(data: bytes, body: int, end: int) -> tuple[int, int]:
    """Return `(sample_count, total_ticks)` summed over every `stts` run.

    AE follows these sums rather than the `mdhd` duration - a rotated fixture
    whose `mdhd` claimed one frame too many imported at the `stts` length.
    Reading only the first run also reports the wrong rate for variable frame
    rate media, where the runs alternate.
    """
    samples = ticks = 0
    for i in range(_u(data, body + 4, 4)):
        off = body + 8 + 8 * i
        if off + 8 > end:
            break
        count = _u(data, off, 4)
        samples += count
        ticks += count * _u(data, off + 4, 4)
    return samples, ticks


#: `tfhd` / `trun` flag bits naming the fields that are actually present.
_TFHD_BASE_OFFSET = 0x000001
_TFHD_SAMPLE_DESC = 0x000002
_TFHD_DEFAULT_DURATION = 0x000008
_TRUN_DATA_OFFSET = 0x000001
_TRUN_FIRST_SAMPLE_FLAGS = 0x000004
#: Per-sample `trun` fields, in the order they are stored.
_TRUN_SAMPLE_FIELDS = (0x000100, 0x000200, 0x000400, 0x000800)


def _fragment_totals(fp: IO[bytes], track_id: int) -> tuple[int, int]:
    """Return `(sample_count, total_ticks)` from one track's movie fragments.

    A fragmented file (an `empty_moov` stream) carries no `stts`; each sample's
    duration lives in its `traf`, either as the `tfhd` default or per sample in
    the `trun`. AE reads these, so a fragmented `.mp4` that py_aep reported as
    0 s / 0 fps imports in AE with its real duration and rate.
    """
    samples = ticks = 0
    for moof in _top_level_atoms(fp, b"moof"):
        for a1, b1, e1 in _atoms(moof, 0, len(moof)):
            if a1 != b"traf":
                continue
            default_duration = 0
            traf_track = -1
            for a2, b2, e2 in _atoms(moof, b1, e1):
                if a2 == b"tfhd":
                    flags = _u(moof, b2 + 1, 3)
                    traf_track = _u(moof, b2 + 4, 4)
                    off = b2 + 8
                    if flags & _TFHD_BASE_OFFSET:
                        off += 8
                    if flags & _TFHD_SAMPLE_DESC:
                        off += 4
                    if flags & _TFHD_DEFAULT_DURATION and off + 4 <= e2:
                        default_duration = _u(moof, off, 4)
                elif a2 == b"trun" and traf_track == track_id:
                    flags = _u(moof, b2 + 1, 3)
                    count = _u(moof, b2 + 4, 4)
                    samples += count
                    off = b2 + 8
                    if flags & _TRUN_DATA_OFFSET:
                        off += 4
                    if flags & _TRUN_FIRST_SAMPLE_FLAGS:
                        off += 4
                    row = 4 * sum(1 for f in _TRUN_SAMPLE_FIELDS if flags & f)
                    if flags & _TRUN_SAMPLE_FIELDS[0]:
                        for i in range(count):
                            if off + row * i + 4 > e2:
                                break
                            ticks += _u(moof, off + row * i, 4)
                    else:
                        ticks += count * default_duration
    return samples, ticks


def _probe_mov(fp: IO[bytes], undecodable: frozenset[bytes] = frozenset()) -> MediaInfo:
    """Probe a QuickTime-family container (`.mov`, `.m4v`, `.m4a`, `.mp4`).

    Args:
        fp: The open media file.
        undecodable: Video sample-entry codes whose track AE's importer
            cannot decode, so it must be reported as absent (see
            `_MP4_UNDECODABLE_CODECS`).
    """
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
            track_id = 0
            swap_axes = False
            mts = mdur = 0
            samples = ticks = 0
            elst_seg_dur = 0
            elst_sentinel = 0xFFFFFFFF
            entry = _VideoSampleEntry()
            for a3, b3, e3 in _atoms(data, b2, e2):
                if a3 == b"tkhd":
                    v = data[b3]
                    track_id = _u(data, b3 + (20 if v == 1 else 12), 4)
                    tw = _u(data, e3 - 8, 4) >> 16
                    th = _u(data, e3 - 4, 4) >> 16
                    swap_axes = _tkhd_axes_swapped(data, e3)
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
                                        entry = _parse_stsd(data, b6, e6)
                                    elif a6 == b"stts" and e6 - b6 >= 16:
                                        samples, ticks = _stts_totals(data, b6, e6)
            if handler == b"vide" and entry.codec not in undecodable:
                # AE sizes footage by the stsd coded dimensions, not tkhd:
                # tkhd holds the *display* size (coded width x pixel aspect),
                # so trusting it counts an anamorphic file's aspect twice.
                width = entry.width or tw
                height = entry.height or th
                if swap_axes:
                    width, height = height, width
                # depth and pixel aspect are only meaningful for a visual
                # sample entry (reading them from an audio stsd gives garbage).
                if entry.depth == 32:
                    has_alpha = True
                if entry.pixel_aspect:
                    # A quarter turn maps x onto y, so the sample aspect
                    # turns with the axes.
                    pixel_aspect = (
                        round(1 / entry.pixel_aspect, 5)
                        if swap_axes
                        else entry.pixel_aspect
                    )
                if not samples:  # fragmented: the durations live in the moofs
                    samples, ticks = _fragment_totals(fp, track_id)
                if mts and ticks:
                    frame_rate = round(mts * samples / ticks, 3)
                    duration = ticks / mts  # AE uses the video track's duration
                elif mts and mdur:
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


class _VideoSampleEntry(NamedTuple):
    """The fields a video `stsd` sample entry contributes to `MediaInfo`."""

    codec: bytes = b""
    width: int = 0
    height: int = 0
    depth: int = 0
    pixel_aspect: float = 0.0


def _parse_stsd(data: bytes, body: int, end: int) -> _VideoSampleEntry:
    """Decode the first sample description as a video sample entry."""
    entry = body + 8  # skip version/flags(4) + entry_count(4)
    if entry + 16 > end:
        return _VideoSampleEntry()
    entry_size = _u(data, entry, 4)
    codec = data[entry + 4 : entry + 8]
    # The visual sample entry is 86 bytes: a 16-byte base, then 16 bytes of
    # version/vendor/quality, then the coded width/height pair at +32.
    width = _u(data, entry + 32, 2) if entry + 36 <= end else 0
    height = _u(data, entry + 34, 2) if entry + 36 <= end else 0
    depth = _u(data, entry + 82, 2) if entry + 84 <= end else 0
    pixel_aspect = 0.0
    # pasp extension atom lives after the 86-byte base video sample entry.
    for atype, b, _e in _atoms(data, entry + 86, min(entry + entry_size, end)):
        if atype == b"pasp":
            h_spacing = _u(data, b, 4)
            v_spacing = _u(data, b + 4, 4)
            if v_spacing:
                pixel_aspect = round(h_spacing / v_spacing, 5)
    return _VideoSampleEntry(codec, width, height, depth, pixel_aspect)


#: Video sample-entry codes AE 2026's Media Core `.mp4` importer cannot
#: decode. AE drops such a track and imports whatever is left, so an `.aep`
#: that claims the real video track instead makes AE report the footage
#: MISSING on open - the track must be reported as absent. Codecs are listed
#: only once verified, since under-claiming a codec AE *can* decode breaks
#: the footage too (AE warns and renders nothing).
_MP4_UNDECODABLE_CODECS = frozenset({b"vp09", b"av01"})


def _probe_mp4(fp: IO[bytes]) -> MediaInfo:
    """Probe an `.mp4`.

    MP4 shares the QuickTime atom tree, but AE routes `.mp4` through its
    Media Core importer, which decodes fewer video codecs than the
    QuickTime importer used for `.mov`/`.m4v`.

    Raises:
        ValueError: If the file has no track AE can decode. AE refuses such a
            file outright ("The source compression type is not supported"),
            so there is no import for py-aep to reproduce.

    Whether AE refuses depends on what survives dropping the undecodable
    video, not on which codec it was. All four cells were measured in AE
    2026; the two kept fixtures cover one codec and one outcome each:

    | video | audio | AE 2026            | fixture                   |
    |-------|-------|--------------------|---------------------------|
    | av01  | AAC   | imports audio only | `mp4_av1_with_audio.mp4`  |
    | vp09  | none  | refused            | `mp4_vp9_no_audio.mp4`    |
    | vp09  | AAC   | imports audio only | (measured, file not kept) |
    | av01  | none  | refused            | (measured, file not kept) |
    """
    info = _probe_mov(fp, undecodable=_MP4_UNDECODABLE_CODECS)
    if info.width or info.has_audio:
        return info
    # Nothing survived. Re-probe ungated to tell an undecodable codec (AE
    # refuses the file) from a file whose atom tree we simply could not read,
    # so the error names the right problem.
    if _probe_mov(fp).width == 0:
        raise ValueError(
            "Could not read a video or audio track from this .mp4 (no "
            "readable moov atom)."
        )
    raise ValueError(
        "After Effects cannot import this .mp4: it has no video track in "
        "a codec AE decodes, and no audio track either. AE refuses the "
        'file with "The source compression type is not supported".'
    )


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

    The tag length is a 28-bit syncsafe integer in header bytes 6-9, and it
    covers neither the 10-byte header nor the optional 10-byte ID3v2.4 footer
    that flag bit 4 announces.
    """
    if raw[:3] == b"ID3" and len(raw) >= 10:
        s = raw[6:10]
        size = (
            (s[0] & 0x7F) << 21
            | (s[1] & 0x7F) << 14
            | (s[2] & 0x7F) << 7
            | (s[3] & 0x7F)
        )
        return 10 + size + (10 if raw[5] & 0x10 else 0)
    return 0


def _mp3_frame_size(header: int) -> int:
    """Length in bytes of the Layer III frame `header` describes (0 if bogus).

    The frame-size coefficient is samples-per-frame/8 (1152/8=144 for MPEG-1,
    576/8=72 for MPEG-2/2.5).
    """
    version = (header >> 19) & 0x3  # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
    layer = (header >> 17) & 0x3  # 1 = Layer III
    bitrate_i = (header >> 12) & 0xF
    sr_i = (header >> 10) & 0x3
    if version == 1 or layer != 1 or bitrate_i in (0, 0xF) or sr_i == 3:
        return 0
    bitrate = (_MP3_BR_M1_L3 if version == 3 else _MP3_BR_M2_L3)[bitrate_i] * 1000
    spf = 1152 if version == 3 else 576
    return spf // 8 * bitrate // _MP3_SR[version][sr_i] + ((header >> 9) & 0x1)


def _find_mp3_frame(window: bytes) -> int:
    """Offset of the first MPEG audio frame in `window`, or -1 if none syncs.

    A well-formed file starts its audio exactly where the tag ended, so offset
    0 is taken on its own. Past that the search needs corroboration: a
    candidate counts only when the frame its own length points at also syncs,
    which rejects a stray 0xFF pair inside tag or junk bytes. Scanning at all
    is what keeps a footer-bearing or sloppily tagged file - where the audio
    does not begin at the tag boundary - from reporting a zero duration.
    """
    n = len(window)
    if (
        n >= 4
        and window[0] == 0xFF
        and window[1] & 0xE0 == 0xE0
        and _mp3_frame_size(struct.unpack_from(">I", window, 0)[0])
    ):
        return 0
    pos = 1
    while pos + 4 <= n:
        if window[pos] == 0xFF and window[pos + 1] & 0xE0 == 0xE0:
            size = _mp3_frame_size(struct.unpack_from(">I", window, pos)[0])
            nxt = pos + size
            if size and (
                nxt + 2 > n  # this frame runs to the end of the window
                or (window[nxt] == 0xFF and window[nxt + 1] & 0xE0 == 0xE0)
            ):
                return pos
        pos += 1
    return -1


def _probe_mp3(fp: IO[bytes]) -> MediaInfo:
    # The duration math needs only the file size, the first frame header and
    # the fixed-offset Xing/Info tag - never the audio payload, so read a
    # bounded window instead of the whole file.
    audio_start = _skip_id3v2(fp.read(10))
    fp.seek(0, 2)
    file_size = fp.tell()
    fp.seek(audio_start)
    # A 64 KiB window holds several max-size frames, so only a pathological
    # amount of leading garbage escapes the search.
    window = fp.read(65536)
    offset = _find_mp3_frame(window)
    if offset < 0:
        return MediaInfo(has_audio=True)
    audio_start += offset
    # Frame header (4) + max side info (32) + a Xing or VBRI tag; VBRI's frame
    # count is the furthest field, ending 54 bytes into the frame.
    raw = window[offset : offset + 64]
    h = struct.unpack_from(">I", raw, 0)[0]
    mpeg_ver = (h >> 19) & 0x3  # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
    sr_i = (h >> 10) & 0x3
    mono = ((h >> 6) & 0x3) == 3
    sr = _MP3_SR.get(mpeg_ver, (0, 0, 0))[sr_i] if sr_i < 3 else 0
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
    elif raw[36:40] == b"VBRI" and sr and len(raw) >= 54:
        # Fraunhofer's VBR tag sits at a fixed offset (frame start + 4 + 32)
        # rather than after the side info: tag(4) version(2) delay(2)
        # quality(2) bytes(4) frames(4). AE ignores it and falls back to a
        # bitrate estimate that is wrong for a variable-rate file (4.91 s for
        # an 8.05 s fixture), so this reports the true length instead.
        if struct.unpack_from(">H", raw, 40)[0] == 1:  # tag version
            frames = struct.unpack_from(">I", raw, 50)[0]
            duration = frames * spf / sr
    elif sr:
        # _find_mp3_frame already rejected the reserved bitrate/rate codes, so
        # the frame size here is always > 0.
        frame_size = _mp3_frame_size(h)
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


#: AE's pixel aspect for the D1/DV frame sizes, keyed by
#: `(width, height, aspect_ratio_information)`. AE applies its own named
#: presets here instead of the arithmetic the sequence header implies:
#: 720x480 flagged 16:9 imports as D1/DV NTSC Widescreen (40/33 = 1.2121),
#: not the (16/9)/(720/480) = 1.1852 the frame size alone would give. Every
#: other frame size measured square. Values verified against AE 2026.
_MPEG_D1_PIXEL_ASPECT = {
    (720, 480, 2): 10 / 11,
    (720, 480, 3): 40 / 33,
    (720, 576, 2): 128 / 117,
    (720, 576, 3): 512 / 351,
}


def _pes_payload_start(data: bytes, pos: int, end: int) -> int:
    """Offset of a PES packet's payload, skipping its variable-length header."""
    p = pos + 6
    if p < end and data[p] & 0xC0 == 0x80:  # MPEG-2 PES: flags(2) + header len
        return min(p + 3 + (data[p + 2] if p + 3 <= end else 0), end)
    while p < end and data[p] == 0xFF:  # MPEG-1 PES: stuffing bytes
        p += 1
    if p + 1 < end and data[p] & 0xC0 == 0x40:  # STD buffer scale/size
        p += 2
    if p < end:
        if data[p] & 0xF0 == 0x20:  # PTS only
            p += 5
        elif data[p] & 0xF0 == 0x30:  # PTS + DTS
            p += 10
        elif data[p] == 0x0F:  # neither
            p += 1
    return min(p, end)


def _mpeg_video_es(data: bytes) -> tuple[bytes, bool]:
    """Return `(video elementary stream, has_audio)` from a program stream.

    The elementary stream has to be reassembled before its picture start codes
    can be counted: a start code routinely straddles a PES packet boundary, so
    scanning the muxed file both misses real pictures and matches the zero
    padding that precedes a pack or PES header. Counting the raw file was off
    by one in both directions on the measured fixtures.
    """
    out = bytearray()
    has_audio = False
    pos, n = 0, len(data)
    while pos + 4 <= n:
        if data[pos : pos + 3] != b"\x00\x00\x01":
            pos += 1
            continue
        stream_id = data[pos + 3]
        if stream_id == 0xBA:  # pack header
            if pos + 5 > n:
                break
            if data[pos + 4] & 0xC0 == 0x40:  # MPEG-2: 14 bytes + stuffing
                if pos + 14 > n:
                    break
                pos += 14 + (data[pos + 13] & 0x07)
            else:  # MPEG-1: a flat 12 bytes
                pos += 12
            continue
        if stream_id == 0xB9:  # program end
            break
        if pos + 6 > n:
            break
        length = int.from_bytes(data[pos + 4 : pos + 6], "big")
        end = min(pos + 6 + length, n) if length else n
        if 0xC0 <= stream_id <= 0xDF or stream_id == 0xBD:
            has_audio = True
        elif 0xE0 <= stream_id <= 0xEF:
            out += data[_pes_payload_start(data, pos, end) : end]
        pos = end
    return bytes(out), has_audio


def _probe_mpeg(fp: IO[bytes]) -> MediaInfo:
    # Program streams carry no global duration and the SCR timeline stops short
    # of the final frames, so the frames have to be counted. This reads the
    # whole file, which is acceptable for the sizes py_aep handles.
    video, has_audio = _mpeg_video_es(fp.read())
    seq = video.find(b"\x00\x00\x01\xb3")
    if seq < 0:
        raise ValueError("Not a valid MPEG file (no sequence header)")
    val = struct.unpack_from(">I", video, seq + 4)[0]
    width = (val >> 20) & 0xFFF
    height = (val >> 8) & 0xFFF
    fps = _MPEG_FR.get(val & 0xF, 0.0)
    frames = video.count(b"\x00\x00\x01\x00")
    duration = frames / fps if fps else 0.0
    pixel_aspect = _MPEG_D1_PIXEL_ASPECT.get((width, height, (val >> 4) & 0xF), 1.0)
    return MediaInfo(
        width=width,
        height=height,
        duration=duration,
        frame_rate=fps,
        has_audio=has_audio,
        pixel_aspect=pixel_aspect,
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
# Canon CRW (CIFF) - Camera Raw still
# ---------------------------------------------------------------------------

_CIFF_IMAGE_INFO = 0x1810


def _probe_crw(fp: IO[bytes]) -> MediaInfo:
    data = fp.read()
    order = {b"II": "<", b"MM": ">"}.get(data[:2])
    if order is None or data[6:14] != b"HEAPCCDR":
        raise ValueError("Not a Canon CRW file (missing CIFF heap header)")
    (header_length,) = struct.unpack(order + "I", data[2:6])
    info = _ciff_record(data, order, header_length, len(data), _CIFF_IMAGE_INFO)
    if info is None:
        raise ValueError("CRW file has no ImageInfo record")
    # Camera Raw develops the image at the ImageInfo size, turned by its
    # rotation (AE 2026 reports a CRW marked 90 or 270 degrees upright).
    width, height, _pixel_aspect, rotation = struct.unpack(order + "IIfi", info[:16])
    if rotation % 180 == 90:
        width, height = height, width
    return MediaInfo(width=width, height=height)


def _ciff_record(
    data: bytes, order: str, start: int, end: int, wanted: int
) -> bytes | None:
    """The body of the first `wanted` record in the CIFF heap `[start, end)`."""
    (table,) = struct.unpack(order + "I", data[end - 4 : end])
    table += start
    (count,) = struct.unpack(order + "H", data[table : table + 2])
    for i in range(count):
        entry = table + 2 + i * 10
        tag, size, offset = struct.unpack(order + "HII", data[entry : entry + 10])
        if tag & 0xC000:  # value stored in the entry itself: not a heap
            continue
        body = start + offset
        if tag & 0x3800 in (0x2800, 0x3000):  # a sub-heap
            found = _ciff_record(data, order, body, body + size, wanted)
            if found is not None:
                return found
        elif tag & 0x3FFF == wanted:
            return data[body : body + size]
    return None


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
_ASF_HEADER_EXTENSION = bytes.fromhex("B503BF5F2EA9CF118EE300C00C205365")
_ASF_EXT_STREAM_PROPS = bytes.fromhex("CBA5E61472C632438399A96952065B5A")
_ASF_METADATA = bytes.fromhex("EACBF8C5AF5B77488467AA8C44FA4CCA")
_ASF_VIDEO_PREFIX = bytes.fromhex("C0EF19BC")  # first 4 LE bytes of the video GUID
_ASF_AUDIO_PREFIX = bytes.fromhex("409E69F8")  # first 4 LE bytes of the audio GUID


def _asf_objects(body: bytes, start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
    """Yield `(guid, payload_start, payload_end)` for each ASF header object.

    Descends into the Header Extension Object, which AE reads: the stream's
    frame rate and pixel aspect live in objects nested inside it, invisible to
    a walk that only steps over the top-level objects. Its nested objects begin
    46 bytes in - object GUID(16) + size(8) + a reserved GUID(16) + a reserved
    u2 + the extension data size u4.
    """
    pos = start
    while pos + 24 <= end:
        guid = body[pos : pos + 16]
        size = struct.unpack_from("<Q", body, pos + 16)[0]
        if size < 24 or pos + size > end:
            return
        yield guid, pos + 24, pos + size
        if guid == _ASF_HEADER_EXTENSION:
            yield from _asf_objects(body, pos + 46, pos + size)
        pos += size


#: Metadata Object value types that carry an integer, and their struct codes.
#: BOOL is 16-bit here (only the Extended Content Description Object widens
#: it to 32), so 2 and 5 share a code.
_ASF_INT_TYPES = {2: "<H", 3: "<I", 4: "<Q", 5: "<H"}


def _asf_metadata(body: bytes, start: int, end: int) -> dict[tuple[int, str], int]:
    """Decode the Metadata Object's integer records, keyed by `(stream, name)`.

    This is where AE finds a WMV's pixel aspect (`AspectRatioX`/`AspectRatioY`)
    and its frame count (`NumberOfFrames`).
    """
    out: dict[tuple[int, str], int] = {}
    if start + 2 > end:
        return out
    pos = start + 2
    for _ in range(struct.unpack_from("<H", body, start)[0]):
        if pos + 12 > end:
            break
        _lang, stream, name_len, value_type = struct.unpack_from("<4H", body, pos)
        value_len = struct.unpack_from("<I", body, pos + 8)[0]
        name_at = pos + 12
        value_at = name_at + name_len
        if value_at + value_len > end:
            break
        fmt = _ASF_INT_TYPES.get(value_type)
        if fmt is not None and value_len >= struct.calcsize(fmt):
            name = body[name_at:value_at].decode("utf-16-le", "replace").rstrip("\x00")
            out[stream, name] = struct.unpack_from(fmt, body, value_at)[0]
        pos = value_at + value_len
    return out


def _probe_wmv(fp: IO[bytes]) -> MediaInfo:
    if fp.read(16) != _ASF_HEADER:
        raise ValueError("Not a valid ASF/WMV file (bad header GUID)")
    header_size = struct.unpack("<Q", fp.read(8))[0]
    fp.read(6)  # object count (u32) + 2 reserved bytes
    body = fp.read(max(0, header_size - 30))
    width = height = 0
    send_duration = play_duration = preroll = 0.0
    frame_rate = 0.0
    audio_sample_rate = 0.0
    has_audio = False
    video_stream = -1
    metadata: dict[tuple[int, str], int] = {}
    avg_frame_time: dict[int, int] = {}

    for guid, start, end in _asf_objects(body, 0, len(body)):
        size = end - start
        if guid == _ASF_FILE_PROPS and size >= 64:
            play_duration = struct.unpack_from("<Q", body, start + 40)[0] / 1e7
            send_duration = struct.unpack_from("<Q", body, start + 48)[0] / 1e7
            preroll = struct.unpack_from("<Q", body, start + 56)[0] / 1e3
        elif guid == _ASF_STREAM_PROPS and size >= 62:
            stream = struct.unpack_from("<H", body, start + 48)[0] & 0x7F
            if body[start : start + 4] == _ASF_VIDEO_PREFIX:
                video_stream = stream
                # Type-specific data at +54 begins with enc_width/height.
                width = struct.unpack_from("<I", body, start + 54)[0]
                height = struct.unpack_from("<I", body, start + 58)[0]
            elif body[start : start + 4] == _ASF_AUDIO_PREFIX:
                has_audio = True
                # Type-specific data at +54 is a WAVEFORMATEX; its
                # nSamplesPerSec follows wFormatTag(2) and nChannels(2).
                audio_sample_rate = float(struct.unpack_from("<I", body, start + 58)[0])
        elif guid == _ASF_EXT_STREAM_PROPS and size >= 64:
            stream = struct.unpack_from("<H", body, start + 48)[0]
            avg_frame_time[stream] = struct.unpack_from("<Q", body, start + 52)[0]
        elif guid == _ASF_METADATA:
            metadata = _asf_metadata(body, start, end)

    # Average Time Per Frame (100 ns units) is authoritative for AE: a 25 fps
    # file whose header claims 29.97 imports at 29.97. Without it, invert AE's
    # own duration rule below against the Metadata Object's frame count.
    avg = avg_frame_time.get(video_stream, 0)
    frames = metadata.get((video_stream, "NumberOfFrames"), 0)
    if avg:
        frame_rate = round(1e7 / avg, 3)
    elif frames > 1 and send_duration:
        frame_rate = round((frames - 1) / send_duration, 3)

    aspect_x = metadata.get((video_stream, "AspectRatioX"), 0)
    aspect_y = metadata.get((video_stream, "AspectRatioY"), 0)
    pixel_aspect = round(aspect_x / aspect_y, 5) if aspect_x and aspect_y else 1.0

    # AE reports the Send Duration rounded out to a whole frame, plus one:
    # a 1.96 s / 25 fps stream imports as 50 frames = 2.0 s, and the same
    # stream relabelled 29.97 fps imports as 60 frames = 2.002002 s.
    if frame_rate and send_duration:
        duration = (round(send_duration * frame_rate) + 1) / frame_rate
    elif send_duration:
        duration = send_duration
    else:
        duration = max(0.0, play_duration - preroll)
    return MediaInfo(
        width=width,
        height=height,
        duration=duration,
        frame_rate=frame_rate,
        has_audio=has_audio,
        audio_sample_rate=audio_sample_rate,
        pixel_aspect=pixel_aspect,
    )


def _probe_dpx_cineon(fp: IO[bytes]) -> MediaInfo:
    """Probe a DPX (SMPTE 268M) or Cineon (SMPTE V4.5) file header.

    Handles both byte orders for each format: DPX big-endian (`SDPX`) and
    little-endian (`XPDS`), Cineon big-endian (``0x802A5FD7``) and
    little-endian (``0xD75F2A80``).

    Args:
        fp: Readable binary stream positioned at the start of the file.

    Returns:
        A `MediaInfo` with width, height, bit_depth, and has_alpha filled in.
        Duration is 0 (still frame); pixel_aspect defaults to 1.0.

    Raises:
        ValueError: If the file is too short or has an unrecognised magic number.
    """
    header = fp.read(1408)  # 768-byte file info + 640-byte image info
    if len(header) < 1024:
        raise ValueError("Not a valid DPX/Cineon file (header too short)")

    magic = header[:4]

    # --- DPX (SMPTE 268M) ---
    if magic in (b"SDPX", b"XPDS"):
        endian = ">" if magic == b"SDPX" else "<"
        n_elem = struct.unpack(endian + "H", header[770:772])[0]
        width, height = struct.unpack(endian + "II", header[772:780])
        has_alpha = False
        bit_depth = 8
        for i in range(min(n_elem, 8)):
            offset = 780 + i * 72
            if offset + 24 > len(header):
                break
            desc, _, _, bits = struct.unpack("BBBB", header[offset + 20 : offset + 24])
            if i == 0:
                bit_depth = bits
            # Descriptor 4 = alpha-only, 51 = RGBA, 52 = ABGR.
            if desc in (4, 51, 52):
                has_alpha = True
        return MediaInfo(
            width=width, height=height, bit_depth=bit_depth, has_alpha=has_alpha
        )

    # --- Cineon (SMPTE V4.5) ---
    if magic in (b"\x80\x2a\x5f\xd7", b"\xd7\x5f\x2a\x80"):
        endian = ">" if magic == b"\x80\x2a\x5f\xd7" else "<"
        # Byte 192 = orientation (u1), byte 193 = number_of_elements (u1).
        n_elem = header[193]
        has_alpha = n_elem > 3
        bit_depth = 8
        width, height = 0, 0
        for i in range(min(n_elem, 8)):
            offset = 196 + i * 28
            if offset + 12 > len(header):
                break
            _, _, bits, _ = struct.unpack("BBBB", header[offset : offset + 4])
            w, h = struct.unpack(endian + "II", header[offset + 4 : offset + 12])
            if i == 0:
                bit_depth = bits
                width, height = w, h
        return MediaInfo(
            width=width, height=height, bit_depth=bit_depth, has_alpha=has_alpha
        )

    raise ValueError("Not a valid DPX/Cineon file (bad magic number)")


def _probe_heif(fp: IO[bytes]) -> MediaInfo:
    """Probe a HEIF/HEIC (ISO/IEC 23008-12) still image.

    Walks the ISOBMFF box tree (`meta` -> `iprp` -> `ipco`) for `ispe`
    (dimensions), `pixi` (bit depth) and an `auxC` alpha item. Accepts any
    `ftyp` whose major or compatible brands include `heic`, `heix`, `mif1`
    or `heif`.

    Raises:
        ValueError: If the file is too short, has no HEIF brand, or no `ispe`.
    """
    data = fp.read()
    if len(data) < 12:
        raise ValueError("Not a valid HEIF file (too short)")

    ftyp_size = _u(data, 0, 4)
    if data[4:8] != b"ftyp" or ftyp_size < 16 or ftyp_size > len(data):
        raise ValueError("Not a valid HEIF file (missing ftyp box)")
    heif_brands = {b"heic", b"heix", b"mif1", b"heif"}
    major = data[8:12]
    compat = {data[i : i + 4] for i in range(16, ftyp_size, 4)}
    if major not in heif_brands and not (compat & heif_brands):
        raise ValueError("Not a valid HEIF file (no HEIF brand in ftyp)")

    width = height = 0
    bit_depth = 8
    has_alpha = False
    for a1, b1, e1 in _atoms(data, 0, len(data)):
        if a1 != b"meta":
            continue
        # meta is a full box: version(1) + flags(3) precede its children.
        for a2, b2, e2 in _atoms(data, b1 + 4, e1):
            if a2 != b"iprp":
                continue
            for a3, b3, e3 in _atoms(data, b2, e2):
                if a3 != b"ipco":
                    continue
                for a4, b4, e4 in _atoms(data, b3, e3):
                    if a4 == b"ispe" and width == 0:
                        # ispe is a full box: version(4) + width(4) + height(4).
                        width = _u(data, b4 + 4, 4)
                        height = _u(data, b4 + 8, 4)
                    elif a4 == b"pixi" and bit_depth == 8:
                        nc = data[b4 + 4] if b4 + 5 <= e4 else 0
                        if nc and b4 + 5 + nc <= e4:
                            bit_depth = data[b4 + 5]
                    elif a4 == b"auxC":
                        # Null-terminated URN after version+flags; the alpha
                        # plane's is urn:mpeg:hevc:2015:auxid:1.
                        urn = data[b4 + 4 : e4].split(b"\x00", 1)[0]
                        if b"auxid" in urn:
                            has_alpha = True
    if width == 0:
        raise ValueError("Not a valid HEIF file (no ispe box found)")
    return MediaInfo(
        width=width, height=height, bit_depth=bit_depth, has_alpha=has_alpha
    )


_PARSERS: dict[str, Callable[[IO[bytes]], MediaInfo]] = {
    ".png": _probe_png,
    ".mov": _probe_mov,
    ".m4v": _probe_mov,
    ".mp4": _probe_mp4,
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
    ".crw": _probe_crw,
    ".ai": _probe_text,
    ".eps": _probe_text,
    ".pdf": _probe_text,
    ".wmv": _probe_wmv,
    ".aiff": _probe_aiff,
    ".aif": _probe_aiff,
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
    ".dpx": _probe_dpx_cineon,
    ".cin": _probe_dpx_cineon,
    ".heic": _probe_heif,
    ".heif": _probe_heif,
}
