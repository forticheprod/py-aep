"""Footage chunk types: sspc (source settings), opti (asset info).

SspcChunk uses `fmt_field()` for all fixed-layout fields with `BitField`
descriptors for alpha flags.
OptiChunk uses variant subclass dispatch: SoliOptiChunk (fmt_field),
PsdOptiChunk (custom read/write for LE fields), PlaceholderOptiChunk.
"""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from attrs import define

from .bin_utils import read_bytes, to_dividend_divisor, truncate_utf8
from .bitfield import BitField
from .chunk import Chunk
from .fmt_field import (
    ascii_field,
    bool_field,
    bytes_field,
    f4_field,
    f8_field,
    s4_field,
    str_field,
    u1_field,
    u2_field,
    u4_field,
)
from .registry import register

if TYPE_CHECKING:
    from typing import IO, Any

# ---------------------------------------------------------------------------
# sspc - source footage settings (184+ bytes)
# ---------------------------------------------------------------------------


@register("sspc")
@define
class SspcChunk(Chunk):
    """Source footage settings chunk.

    Contains dimensions, timing, alpha/field settings, pixel ratio,
    audio sample rate, and sequence info. A variable-length trailing
    section is preserved for round-trip fidelity.
    """

    chunk_type: str = "sspc"

    # -- Reserved (bytes 0-21) ---------------------------------------------
    _reserved_00: bytes = bytes_field(22, repr=False)

    # -- Source format (bytes 22-31) ---------------------------------------
    source_format_type: str = ascii_field(4)
    """4-char code: 'png!', '8BPS', 'MOoV', 'Soli', etc."""

    _reserved_1a: bytes = bytes_field(6, repr=False)

    # -- Dimensions / duration (bytes 32-45) -------------------------------
    width: int = u2_field()
    _reserved_22: bytes = bytes_field(2, repr=False)
    height: int = u2_field()
    duration_dividend: int = u4_field(default=1)
    duration_divisor: int = u4_field(default=1)

    # -- Frame rate (bytes 46-68) ------------------------------------------
    _reserved_2e: bytes = bytes_field(6, repr=False)
    _time_base: int = u2_field(default=600)
    _reserved_36: bytes = bytes_field(2, repr=False)
    native_frame_rate_integer: int = u4_field()
    native_frame_rate_fractional: int = u2_field()
    _reserved_3e: bytes = bytes_field(7, repr=False)

    # -- Alpha flags (byte 69) ---------------------------------------------
    _alpha_flags: int = u1_field(repr=False)
    """Byte 69: bit 1 = invert_alpha, bit 0 = premultiplied."""

    # -- Premul color / alpha mode (bytes 70-73) ---------------------------
    premul_color_r: int = u1_field()
    premul_color_g: int = u1_field()
    premul_color_b: int = u1_field()
    alpha_mode_raw: int = u1_field()
    """Alpha interpretation mode. 3 = no alpha channel."""

    # -- Field separation (bytes 74-87) ------------------------------------
    _reserved_4a: bytes = bytes_field(9, repr=False)
    field_separation_type_raw: int = u1_field()
    """0 = OFF, 1 = enabled (check field_order for upper/lower)."""

    _reserved_54: bytes = bytes_field(3, repr=False)
    field_order: int = u1_field()

    # -- Reserved / footage state (bytes 88-128) ---------------------------
    _reserved_58: bytes = bytes_field(17, repr=False)
    _is_synthetic_a: int = u1_field(default=1, repr=False)
    _reserved_6b: bytes = bytes_field(3, repr=False)
    _is_synthetic_b: int = u1_field(default=1, repr=False)
    _reserved_6f: bytes = bytes_field(5, repr=False)
    footage_missing_at_save: bool = bool_field()
    """0 = found, 1 = missing or placeholder."""

    _reserved_74: bytes = bytes_field(9, repr=False)
    _depth_flag: int = u1_field(default=0x0C, repr=False)

    # -- Loop / pixel ratio (bytes 126-146) --------------------------------
    loop: int = u4_field(default=1)
    """Loop count (1 = no loop, 2+ = loop count). Stored as a 4-byte
    big-endian field (AE writes e.g. 1000 as 00 00 03 e8); a u1 here read
    only the low byte and overflowed on save for counts > 255."""

    _reserved_82: bytes = bytes_field(4, repr=False)
    _is_synthetic_c: int = u1_field(default=1, repr=False)
    _reserved_87: bytes = bytes_field(1, repr=False)
    pixel_aspect_dividend: int = u4_field(default=1)
    pixel_aspect_divisor: int = u4_field(default=1)
    _reserved_90: bytes = bytes_field(3, repr=False)

    # -- Pulldown / conform (bytes 147-158) --------------------------------
    _remove_pulldown_value: int = u1_field(repr=False)

    conform_frame_rate_integer: int = u2_field()
    """0 = no conforming."""

    conform_frame_rate_fractional: int = u2_field()
    display_frame_rate_integer: int = u2_field()
    display_frame_rate_fractional: int = u2_field()
    _reserved_9c: bytes = bytes_field(3, repr=False)
    high_quality_field_separation: int = u1_field()

    # -- Audio / sequence (bytes 160-183) ----------------------------------
    audio_sample_rate: float = f8_field()
    """Sample rate in Hz (0.0 = no audio)."""

    _reserved_a8: bytes = bytes_field(4, repr=False)
    start_frame: int = u4_field()
    end_frame: int = u4_field()
    frame_padding: int = u4_field()
    """Zero-padded digit count for image sequences (0 for non-sequences)."""

    # -- Extended settings (bytes 184-221) ---------------------------------
    _reserved_b8: bytes = bytes_field(4, repr=False)
    work_area_start: int = u4_field(default=0xFFFFFFFF)
    work_area_end: int = u4_field(default=0xFFFFFFFF)
    _reserved_c4: bytes = bytes_field(3, repr=False)
    full_frame: bool = bool_field()
    """Byte 0xC7: `True` when the footage spans its full source frame,
    `False` for a layer cropped to its content box (`COMP_CROPPED_LAYERS`).
    Written only for file footage; solids/placeholders leave it `False`."""

    _reserved_c8: bytes = bytes_field(2, repr=False)
    _reserved_ca: bytes = bytes_field(10, repr=False)
    _reserved_d4: bytes = bytes_field(10, default=b"\x01" + b"\x00" * 9, repr=False)

    # -- BitField descriptors (not attrs fields) ---------------------------
    invert_alpha = BitField("_alpha_flags", 1)
    premultiplied = BitField("_alpha_flags", 0)

    # -- Computed properties -----------------------------------------------

    @property
    def native_frame_rate(self) -> float:
        """Native frame rate (integer + fractional/65536)."""
        return (
            self.native_frame_rate_integer + self.native_frame_rate_fractional / 65536.0
        )

    @native_frame_rate.setter
    def native_frame_rate(self, value: float) -> None:
        self.native_frame_rate_integer = int(value)
        self.native_frame_rate_fractional = round((value - int(value)) * 65536)
        self._update_display_frame_rate()

    @property
    def conform_frame_rate(self) -> float:
        """Conform frame rate (integer + fractional/65536). 0 = no conform."""
        return (
            self.conform_frame_rate_integer
            + self.conform_frame_rate_fractional / 65536.0
        )

    @conform_frame_rate.setter
    def conform_frame_rate(self, value: float) -> None:
        self.conform_frame_rate_integer = int(value)
        self.conform_frame_rate_fractional = round((value - int(value)) * 65536)
        self._update_display_frame_rate()

    @property
    def duration(self) -> float:
        """Duration in seconds (dividend / divisor)."""
        if self.duration_divisor == 0:
            return 0.0
        return self.duration_dividend / self.duration_divisor

    @duration.setter
    def duration(self, value: float) -> None:
        self.duration_dividend, self.duration_divisor = to_dividend_divisor(value)

    @property
    def pixel_aspect(self) -> float:
        """Pixel aspect ratio (dividend / divisor)."""
        if self.pixel_aspect_divisor == 0:
            return 1.0
        return self.pixel_aspect_dividend / self.pixel_aspect_divisor

    @pixel_aspect.setter
    def pixel_aspect(self, value: float) -> None:
        self.pixel_aspect_dividend, self.pixel_aspect_divisor = to_dividend_divisor(
            value
        )

    @property
    def premul_color(self) -> list[float]:
        """Premultiply color as [R, G, B] in 0.0-1.0 range."""
        return [
            self.premul_color_r / 255,
            self.premul_color_g / 255,
            self.premul_color_b / 255,
        ]

    @premul_color.setter
    def premul_color(self, value: list[float]) -> None:
        self.premul_color_r = round(value[0] * 255)
        self.premul_color_g = round(value[1] * 255)
        self.premul_color_b = round(value[2] * 255)

    @property
    def field_separation_type(self) -> int:
        """Field separation type (0=off, 1=upper_first, 2=lower_first)."""
        if self.field_separation_type_raw == 0:
            return 0
        return self.field_order + 1

    @field_separation_type.setter
    def field_separation_type(self, value: int) -> None:
        if value == 0:
            self.field_separation_type_raw = 0
            self.field_order = 0
        else:
            self.field_separation_type_raw = 1
            self.field_order = value - 1

    @property
    def has_alpha(self) -> bool:
        """Whether the footage has an alpha component."""
        return self.alpha_mode_raw != 3

    @property
    def remove_pulldown(self) -> int:
        """0 = OFF, 1-10 = pulldown phase."""
        return self._remove_pulldown_value

    @remove_pulldown.setter
    def remove_pulldown(self, value: int) -> None:
        self._remove_pulldown_value = value
        self._update_display_frame_rate()

    @property
    def display_frame_rate(self) -> float:
        """Effective frame rate as displayed."""
        conform = self.conform_frame_rate
        base = conform if conform != 0 else self.native_frame_rate
        return base * (0.8 if self._remove_pulldown_value != 0 else 1.0)

    @display_frame_rate.setter
    def display_frame_rate(self, value: float) -> None:
        self.display_frame_rate_integer = int(value)
        self.display_frame_rate_fractional = round((value - int(value)) * 65536)

    def _update_display_frame_rate(self) -> None:
        """Recompute and store display_frame_rate from current settings."""
        conform = self.conform_frame_rate
        base = conform if conform != 0 else self.native_frame_rate
        self.display_frame_rate = base * (
            0.8 if self._remove_pulldown_value != 0 else 1.0
        )


# ---------------------------------------------------------------------------
# opti - footage asset info (variant dispatch by asset_type)
# ---------------------------------------------------------------------------


def build_generic_opti_data(source_format: str) -> bytes:
    """Build the 58-byte generic `opti` asset-info body for a file source.

    AE accepts an empty `opti` for single still images (it re-reads the
    located file), but requires this header to recognize non-TIFF/PSD
    image sequences and audio/video. The layout is the format 4-char code,
    a version word, the chunk length, the reversed code, and importer
    markers - matching what AE writes for WAV/MOV/etc.

    Note: TIFF sequences use `build_tiff_opti_data` instead (AE 2026
    measured); PSD sequences use an empty opti via `PsdOptiChunk`.
    """
    code = source_format.encode("ascii")[:4].ljust(4, b" ")
    return (
        code
        + b"\x00\x05"
        + b"\x00\x00\x00\x3a"  # 58 = total length
        + b"\x00" * 20
        + code[::-1]
        + b"\xff\xff\xff\xff"
        + b"\x00\x00\x00\x00"  # codec fourcc (unknown / not needed)
        + b"\x01\x00\x00\x00"
        + b"\x01"
        + b"\x00" * 11
    )


def _build_still_opti(
    code: bytes, width: int, height: int, bit_depth: int, tail: bytes
) -> bytes:
    """Build the 602-byte still-importer `opti` body shared by TIFF and PSD.

    Reverse-engineered from AE 2026. `code` is the 4-char format code (also
    embedded reversed mid-header); `tail` is the format-specific trailing
    field. The channel count is always 4 (AE composites the merge to RGBA).
    """
    return (
        code
        + b"\x01\x09"
        + struct.pack(">I", 602)  # total length (big-endian)
        + b"\x00\x00\x01\x01"
        + b"\xff\xff\xff\xff"
        + code[::-1]
        + b"\x01\x00\x00\x00"
        + b"\x00\x00\x00\x00"
        + b"\x04\x00"
        + struct.pack("<I", height)
        + struct.pack("<I", width)
        + struct.pack("<H", bit_depth)
        + b"\x03\x00"
        + b"\x00\x00\x00\x00"
        + tail
    ).ljust(602, b"\x00")


def build_tiff_opti_data(width: int, height: int, bit_depth: int = 8) -> bytes:
    """Build the 602-byte TIFF `opti` asset-info body.

    Unlike PNG/EXR, AE does not re-read a TIFF from the located file, so it
    needs this header for both stills and image sequences (an empty or generic
    header crashes AE in both cases - AE 2026 measured). The header is
    identical for 3- and 4-channel TIFFs.
    """
    return _build_still_opti(b"TIF ", width, height, bit_depth, b"\x02\x00")


def build_psd_opti_data(
    width: int, height: int, bit_depth: int = 8, layer_count: int = 1
) -> bytes:
    """Build the 602-byte merged-PSD/PSB `opti` asset-info body.

    AE 2026 measured: AE itself writes an empty opti for PSD imports (both
    stills and sequences), but it also accepts the 602-byte header produced
    here on re-open without error. This function is used by `PsdOptiChunk`
    via `write()` and for the `file_attributes` round-trip; it stores layer
    metadata (index, dimensions, bit depth, layer count) that AE exposes in
    its "Interpret Footage" dialog. Uses the same still-importer template as
    `build_tiff_opti_data` but with the `8BPS`/`SPB8` codes and the layer
    count in the trailing field.

    Args:
        width: Full PSD canvas width in pixels.
        height: Full PSD canvas height in pixels.
        bit_depth: Bits per channel (8, 16, or 32).
        layer_count: Number of layers in the PSD. A flattened document (0
            layers) is stored as 1, matching AE.
    """
    tail = struct.pack("<B", min(max(layer_count, 1), 255))
    return _build_still_opti(b"8BPS", width, height, bit_depth, tail)


def build_psd_flattened_opti_data(
    width: int, height: int, bit_depth: int, channels: int
) -> bytes:
    """Build the 602-byte `8BPS` `opti` for a FLATTENED PSD/PSB imported as a
    one-layer composition.

    AE writes a full opti (not the empty one it uses for footage) for this
    merged-still comp layer. It differs from the merged `build_psd_opti_data`
    in three bytes (AE 2026 byte-verified against a real flattened RGB PSD):

    - 0x0A: 1 (a merged/flattened-reference flag; per-layer optis leave 0).
    - 0x1E: the file's real channel count (3 for RGB, 4 for RGBA), not the
      composited-to-4 value the still template hard-codes.
    - 0x30: the true layer count, 0 (the merged builder clamps this to 1).
    """
    buf = bytearray(build_psd_opti_data(width, height, bit_depth))
    buf[0x0A] = 0x01
    buf[0x1E] = channels
    buf[0x30] = 0x00
    return bytes(buf)


def build_psd_layer_opti_data(
    canvas_width: int,
    canvas_height: int,
    bit_depth: int,
    layer_count: int,
    layer_index: int,
    layer_id: int,
    layer_name: str,
    bounds: tuple[int, int, int, int],
) -> bytes:
    """Build the 602-byte `8BPS` `opti` for one layer of a layered PSD import.

    When After Effects imports a layered Photoshop file as a composition, it
    creates one footage item per layer, each referencing the same file with its
    source layer selected. The selection is stored in this opti, identically for
    a whole-canvas (`COMP`) or cropped (`COMP_CROPPED_LAYERS`) import - the crop
    only changes the footage `sspc` dimensions and the comp-layer transform, not
    this opti. It extends the merged `build_psd_opti_data` (which sets a
    `0xFFFFFFFF` sentinel at 0x0E and an empty trailing name) with:

    - 0x0E: the 0-based layer index (BE u32), clearing the merged sentinel.
    - 0x4E/0x52/0x56/0x5A: the layer's content bounding box top/left/bottom/right
      (LE s32), i.e. the layer record's rectangle - NOT the canvas.
    - 0x5E: channel count - 4 (RGBA) for a layer with pixel content, 0 for an
      empty content box (e.g. an adjustment layer).
    - 0x154: the Photoshop layer id (`lyid`, LE u32).
    - 0x158: the layer name, NUL-terminated UTF-8.

    The `psd_canvas_*` fields keep the full document size. Byte-verified against
    AE 2026's `COMP`/`COMP_CROPPED_LAYERS` import of `8bits.psd`/`.psb` and a
    margined 3-layer PSD.

    Args:
        canvas_width: Full document width in pixels.
        canvas_height: Full document height in pixels.
        bit_depth: Bits per channel.
        layer_count: Total layers in the document.
        layer_index: 0-based document index of this layer (bottom first).
        layer_id: Photoshop layer id (`lyid`).
        layer_name: Layer name.
        bounds: The layer's content box as `(left, top, right, bottom)`.
    """
    left, top, right, bottom = bounds
    buf = bytearray(
        build_psd_opti_data(canvas_width, canvas_height, bit_depth, layer_count)
    )
    struct.pack_into(">I", buf, 0x0E, layer_index)
    struct.pack_into("<i", buf, 0x4E, top)
    struct.pack_into("<i", buf, 0x52, left)
    struct.pack_into("<i", buf, 0x56, bottom)
    struct.pack_into("<i", buf, 0x5A, right)
    # Channel count: 4 (RGBA) for a layer with pixel content, 0 for an empty
    # content box (e.g. an adjustment layer with no pixels). AE 2026 measured.
    buf[0x5E] = 0x04 if right > left and bottom > top else 0x00
    struct.pack_into("<I", buf, 0x154, layer_id)
    name = truncate_utf8(layer_name, 255)
    buf[0x158 : 0x158 + len(name)] = name
    return bytes(buf)


def build_rhdr_opti_data() -> bytes:
    """Build the 30-byte Radiance HDR (`RHDR`) `opti` asset-info body.

    AE refuses an empty or generic `opti` for HDR, but the dimensions are
    stored in `sspc` (not this opti), so the body is a fixed template. The
    `asset_type_int` is 0x002e (46), distinguishing it from the generic
    0x0005 and the still-importer 0x0109. Reverse-engineered from AE 2026;
    AE's own opti carries a file-system fingerprint in the trailing 8 bytes
    that AE re-derives on a cache miss, so it is left zero here.
    """
    return (
        b"RHDR"
        + b"\x00\x2e"
        + struct.pack(">I", 30)  # total length (big-endian)
        + b"\x02\x00"
        + b"\x00" * 18
    )


def build_text_opti_data(width: int, height: int) -> bytes:
    """Build the 596-byte `TEXT` `opti` asset-info body for AI/EPS/PDF.

    AE stores this opti for every file imported with source format `TEXT`
    (Illustrator, EPS, PDF). Width and height are big-endian u16 at bytes
    24 and 28. AE caches `sspc` (not this opti) for dimensions, so AE's
    per-file flag bytes (51, 60) and the redundant dimension tail
    (584-589) are not load-bearing and are left zero. Reverse-engineered
    from AE 2026 for ai.ai (612x792), eps.eps (1921x2881), pdf.pdf (595x842).
    """
    buf = bytearray(596)
    buf[0:4] = b"TEXT"
    buf[4:6] = b"\x00\x08"
    struct.pack_into(">I", buf, 6, 596)  # total length
    struct.pack_into(">H", buf, 24, width)
    struct.pack_into(">H", buf, 28, height)
    buf[40:44] = b"\xff\xff\xff\xff"
    return bytes(buf)


def build_ai_layer_opti_data(
    width: int, height: int, layer_name: str, color_space: str | None = None
) -> bytes:
    """Build the 596-byte `TEXT` `opti` for one layer of a layered AI/PDF import.

    When After Effects imports a layered Illustrator/PDF file as a composition,
    it creates one footage item per layer, each referencing the same file with
    its source layer selected. The selection is stored entirely in this opti.
    It extends `build_text_opti_data` with:

    - byte 0x3C: element/page count (1).
    - byte 0x3D: per-layer-reference flag (1; whole-document footage is 0).
    - byte 0x44: the layer name, NUL-terminated.
    - bytes 0x248/0x24C: the redundant page-dimension tail (height/width, BE u16).
    - byte 0x33: 2 (a flag AE also sets for whole-document footage).

    The artwork bounding box (0x10-0x1c, BE signed 16.16) keeps the full-page
    value `build_text_opti_data` already writes; a cropped
    (`COMP_CROPPED_LAYERS`) import would set it to the layer's artwork bounds.
    Byte-verified against AE 2026's import of ai.ai ("Calque 1"/"Calque 2",
    612x792).
    """
    buf = bytearray(build_text_opti_data(width, height))
    # byte 0x33 = document color-space flag: 0x02 for CMYK, 0x08 otherwise
    # (RGB + default). AE 2026-verified: ai.ai (CMYK)=0x02, complex.ai (RGB)=0x08.
    buf[0x33] = 0x02 if color_space == "CMYK" else 0x08
    buf[0x3C] = 0x01
    buf[0x3D] = 0x01
    name = truncate_utf8(layer_name, 255)
    buf[0x44 : 0x44 + len(name)] = name
    struct.pack_into(">H", buf, 0x248, height)
    struct.pack_into(">H", buf, 0x24C, width)
    return bytes(buf)


@register("opti")
@define
class OptiChunk(Chunk):
    """Footage asset info chunk (polymorphic).

    Layout depends on `asset_type` (first 4 bytes). The base class
    dispatches to variant subclasses; unknown asset types fall back
    to raw bytes.
    """

    chunk_type: str = "opti"

    @classmethod
    def read(
        cls,
        fp: IO[bytes],
        size: int,
        *,
        chunk_type: str = "",
        **kwargs: Any,
    ) -> OptiChunk:
        if cls is not OptiChunk:
            # Variant subclass - use its own read
            return super().read(fp, size, chunk_type=chunk_type)  # type: ignore[return-value]  # returns Self
        if size < 6:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        # Peek at discriminator (first 4 bytes = asset_type)
        disc_raw = read_bytes(fp, 6)
        nul = disc_raw.find(b"\x00", 0, 4)
        asset_type = disc_raw[: nul if nul >= 0 else 4].decode("ascii")
        asset_type_int = struct.unpack(">H", disc_raw[4:6])[0]
        fp.seek(-6, 1)
        # Placeholder: asset_type is empty but asset_type_int == 2
        if not asset_type and asset_type_int == 2:
            return PlaceholderOptiChunk.read(
                fp,
                size,
                chunk_type=chunk_type,
            )
        variant_cls = _OPTI_VARIANTS.get(asset_type, OptiChunk)
        if variant_cls is OptiChunk:
            return cls(chunk_type=chunk_type, data=read_bytes(fp, size))
        return variant_cls.read(fp, size, chunk_type=chunk_type)


@define
class SoliOptiChunk(OptiChunk):
    """Solid footage asset (asset_type='Soli').

    All fields are big-endian and fixed-layout -> fmt_field.
    """

    asset_type: str = ascii_field(4, default="Soli")
    asset_type_int: int = u2_field(default=9)
    _pad: bytes = bytes_field(
        8, default=b"\x00\x00\x01\x1a\x3f\x80\x00\x00", repr=False
    )
    color_r: float = f4_field()
    """Solid color red component (0.0-1.0)."""

    color_g: float = f4_field()
    """Solid color green component (0.0-1.0)."""

    color_b: float = f4_field()
    """Solid color blue component (0.0-1.0)."""

    solid_name: str = str_field(256, default="", encoding="utf-8")
    """Solid item name."""

    @property
    def color(self) -> list[float]:
        """Solid color as [R, G, B] in 0.0-1.0 range."""
        return [self.color_r, self.color_g, self.color_b]

    @color.setter
    def color(self, value: list[float]) -> None:
        self.color_r = value[0]
        self.color_g = value[1]
        self.color_b = value[2]


@define
class PsdOptiChunk(OptiChunk):
    """PSD footage asset (asset_type='8BPS')."""

    asset_type: str = ascii_field(4, default="8BPS")
    asset_type_int: int = u2_field(default=265)
    _pad_06: bytes = bytes_field(10, repr=False)
    psd_layer_index: int = u2_field()
    """0-based layer index. 0xFFFF = merged/flattened."""

    _pad_12: bytes = bytes_field(
        12, default=b"\x53\x50\x42\x38\x01\x00\x00\x00\x00\x00\x00\x00", repr=False
    )
    psd_channels: int = u1_field()
    """Number of color channels (3=RGB, 4=RGBA/CMYK)."""

    _pad_1f: bytes = bytes_field(1, repr=False)
    psd_canvas_height: int = u2_field(endian="<")
    """Full PSD canvas height in pixels (LE u2)."""

    _pad_22: bytes = bytes_field(2, repr=False)
    psd_canvas_width: int = u2_field(endian="<")
    """Full PSD canvas width in pixels (LE u2)."""

    _pad_26: bytes = bytes_field(2, repr=False)
    psd_bit_depth: int = u1_field()
    """Bit depth per channel (8 or 16)."""

    _pad_29: bytes = bytes_field(7, default=b"\x00\x03\x00\x00\x00\x00\x00", repr=False)
    psd_layer_count: int = u1_field()
    """Total number of layers in the PSD."""

    _pad_31: bytes = bytes_field(29, repr=False)
    psd_layer_top: int = s4_field(endian="<")
    """Layer bounding box top (LE s4, can be negative)."""

    psd_layer_left: int = s4_field(endian="<")
    """Layer bounding box left (LE s4, can be negative)."""

    psd_layer_bottom: int = s4_field(endian="<")
    """Layer bounding box bottom (LE s4)."""

    psd_layer_right: int = s4_field(endian="<")
    """Layer bounding box right (LE s4)."""

    _pad_5e: bytes = bytes_field(250, repr=False)

    @property
    def psd_group_name(self) -> str:
        """PSD group/folder name (NUL-terminated UTF-8 at end of chunk).

        Empty for a merged import, where the trailing region is all-NUL.
        """
        return self._trailing.split(b"\x00", 1)[0].decode("utf-8")

    @psd_group_name.setter
    def psd_group_name(self, value: str) -> None:
        self._trailing = value.encode("utf-8") if value else b""


@define
class PlaceholderOptiChunk(OptiChunk):
    """Placeholder footage asset (asset_type_int=2)."""

    asset_type: str = ascii_field(4, default="")
    asset_type_int: int = u2_field(default=2)
    _pad: bytes = bytes_field(4, default=b"\x00\x00\x01\x0a", repr=False)
    placeholder_name: str = str_field(256, default="", encoding="utf-8")
    """Placeholder name (256-byte NUL-padded UTF-8)."""


_OPTI_VARIANTS: dict[str, type[OptiChunk]] = {
    "Soli": SoliOptiChunk,
    "8BPS": PsdOptiChunk,
}
