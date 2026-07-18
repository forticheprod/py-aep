"""Footage chunk types: sspc (source settings), opti (asset info).

SspcChunk uses `fmt_field()` for all fixed-layout fields with `BitField`
descriptors for alpha flags.
OptiChunk uses variant subclass dispatch: SoliOptiChunk, PsdOptiChunk and
TextOptiChunk (fmt_field, some LE), PlaceholderOptiChunk. The `build_*`
opti builders serialize the typed variant chunks, so the read and write
paths share one layout definition.
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
    _reserved_b8: bytes = bytes_field(1, repr=False)
    frame_range_set: bool = bool_field()
    """Byte 0xB9: `True` when the sequence was imported with a user-set
    frame range. AE sets it for ranged imports only - a sequence with
    missing interior frames but no range keeps 0 (probed range fixtures,
    AE 2026)."""

    _reserved_ba: bytes = bytes_field(2, repr=False)
    layer_id: int = u4_field(default=0xFFFFFFFF)
    """Byte 0xBC: Photoshop layer id (`lyid`) when the footage references a
    single layer of a layered file; `0xFFFFFFFF` otherwise (merged,
    whole-file, and AI/PDF layers, which have no ids)."""

    layer_index: int = u4_field(default=0xFFFFFFFF)
    """Byte 0xC0: 0-based index of the referenced layer (PSD: document
    record index counting group dividers; AI/PDF: OCG order). `0xFFFFFFFF`
    for merged/whole-file footage; placeholders store `0xFFFFFFFE`."""

    _reserved_c4: bytes = bytes_field(3, repr=False)
    full_frame: bool = bool_field()
    """Byte 0xC7: `True` when the footage spans its full source frame
    (including a chosen layer imported at Document Size), `False` for a
    layer cropped to its content box (`COMP_CROPPED_LAYERS` or a chosen
    layer imported at Layer Size). Written only for file footage;
    solids/placeholders leave it `False`."""

    _reserved_c8: bytes = bytes_field(2, repr=False)
    _reserved_ca: bytes = bytes_field(6, repr=False)
    data_size: int = u4_field()
    """Byte 0xD0: cached source data size. For a PSD layer (chosen or
    comp-imported) the content box's pixel bytes (`w * h * 4` at 8 bpc);
    for merged PSD footage the canvas equivalent; for whole files (PNG,
    AI, ...) the file size on disk. AE re-derives it on a cache miss, so
    `0` is accepted."""
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


def build_tiff_opti_data(width: int, height: int, bit_depth: int = 8) -> bytes:
    """Build the 602-byte still-importer TIFF `opti` asset-info body.

    Unlike PNG/EXR, AE does not re-read a TIFF from the located file, so it
    needs this header for both stills and image sequences (an empty or generic
    header crashes AE in both cases - AE 2026 measured). The header is
    identical for 3- and 4-channel TIFFs. The channel count is always 4 (AE
    composites to RGBA). PSD uses the same still-importer layout via
    `PsdOptiChunk`.
    """
    code = b"TIF "
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
        + b"\x02\x00"
    ).ljust(602, b"\x00")


def build_psd_opti_data(
    width: int, height: int, bit_depth: int = 8, layer_count: int = 1
) -> bytes:
    """Build the 602-byte merged-PSD/PSB `opti` asset-info body.

    AE 2026 measured: AE itself writes an empty opti for PSD imports (both
    stills and sequences), but it also accepts the 602-byte header produced
    here on re-open without error. It stores layer metadata (index,
    dimensions, bit depth, layer count) that AE exposes in its "Interpret
    Footage" dialog; the layout lives on `PsdOptiChunk`, which this
    serializes with the merged defaults (0xFFFFFFFF layer-index sentinel,
    empty trailing name).

    Args:
        width: Full PSD canvas width in pixels.
        height: Full PSD canvas height in pixels.
        bit_depth: Bits per channel (8, 16, or 32).
        layer_count: Number of layers in the PSD. A flattened document (0
            layers) is stored as 1, matching AE.
    """
    chunk = PsdOptiChunk(
        psd_canvas_width=width,
        psd_canvas_height=height,
        psd_bit_depth=bit_depth,
        psd_layer_count=min(max(layer_count, 1), 255),
    )
    chunk.psd_group_name = ""
    return chunk.tobytes()


def build_psd_flattened_opti_data(
    width: int, height: int, bit_depth: int, channels: int
) -> bytes:
    """Build the 602-byte `8BPS` `opti` for a FLATTENED PSD/PSB imported as a
    one-layer composition.

    AE writes a full opti (not the empty one it uses for footage) for this
    merged-still comp layer. It differs from the merged `build_psd_opti_data`
    in three bytes (AE 2026 byte-verified against a real flattened RGB PSD):

    - 0x0A (`psd_flattened`): 1 (a merged/flattened-reference flag;
      per-layer optis leave 0).
    - 0x1E (`psd_channels`): the file's real channel count (3 for RGB, 4 for
      RGBA), not the composited-to-4 value the merged builder uses.
    - 0x30 (`psd_layer_count`): the true layer count, 0 (the merged builder
      clamps this to 1).
    """
    chunk = PsdOptiChunk(
        psd_flattened=True,
        psd_channels=channels,
        psd_canvas_width=width,
        psd_canvas_height=height,
        psd_bit_depth=bit_depth,
        psd_layer_count=0,
    )
    chunk.psd_group_name = ""
    return chunk.tobytes()


def build_psd_layer_opti_data(
    canvas_width: int,
    canvas_height: int,
    bit_depth: int,
    layer_count: int,
    layer_index: int,
    layer_id: int,
    layer_name: str,
    bounds: tuple[int, int, int, int],
    is_adjustment: bool = False,
) -> bytes:
    """Build the 602-byte `8BPS` `opti` for one layer of a layered PSD import.

    When After Effects imports a layered Photoshop file as a composition, it
    creates one footage item per layer, each referencing the same file with its
    source layer selected. The selection is stored in this opti, identically for
    a whole-canvas (`COMP`) or cropped (`COMP_CROPPED_LAYERS`) import - the crop
    only changes the footage `sspc` dimensions and the comp-layer transform, not
    this opti. It differs from the merged `build_psd_opti_data` (which keeps
    the `0xFFFFFFFF` layer-index sentinel and an empty trailing name) in:

    - `psd_layer_index`: the 0-based layer index, clearing the merged sentinel.
    - `psd_layer_top/left/bottom/right`: the layer's content bounding box
      (LE s32), i.e. the layer record's rectangle - NOT the canvas.
    - `psd_layer_channels`: 4 (RGBA) for a raster layer - including a fully
      transparent one with an empty content box - and 0 for an adjustment
      layer (which contributes no pixel channels).
    - `psd_layer_id`: the Photoshop layer id (`lyid`, LE u32).
    - the trailing name block (`psd_group_name`): the layer name,
      NUL-terminated UTF-8.

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
    chunk = PsdOptiChunk(
        psd_layer_index=layer_index,
        psd_canvas_width=canvas_width,
        psd_canvas_height=canvas_height,
        psd_bit_depth=bit_depth,
        psd_layer_count=min(max(layer_count, 1), 255),
        psd_layer_top=top,
        psd_layer_left=left,
        psd_layer_bottom=bottom,
        psd_layer_right=right,
        # 4 (RGBA) for a raster layer - even a fully transparent one whose
        # content box is empty (psd_clipping_mask "Layer 1") - and 0 for an
        # adjustment layer, which has no pixel channels (grouped_layers
        # "hue/sat adj"). AE 2026 measured; the empty content box alone does
        # NOT drop the channels.
        psd_layer_channels=0x00 if is_adjustment else 0x04,
        psd_layer_id=layer_id,
    )
    chunk.psd_group_name = layer_name
    return chunk.tobytes()


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
    (Illustrator, EPS, PDF). AE caches `sspc` (not this opti) for
    dimensions, so AE's per-file flag bytes (0x33, 0x3C) and the redundant
    dimension tail (0x248-0x24D) are not necessary and are left zero.
    Reverse-engineered from AE 2026 for ai.ai (612x792), eps.eps
    (1921x2881), pdf.pdf (595x842); the layout lives on `TextOptiChunk`.
    """
    return TextOptiChunk(text_width=width, text_height=height).tobytes()


def build_ai_layer_opti_data(
    width: int,
    height: int,
    layer_name: str,
    color_space: str | None = None,
    artwork_bounds: tuple[float, float, float, float] | None = None,
) -> bytes:
    """Build the 596-byte `TEXT` `opti` for one layer of a layered AI/PDF import.

    When After Effects imports a layered Illustrator/PDF file as a composition,
    it creates one footage item per layer, each referencing the same file with
    its source layer selected. The selection is stored entirely in this opti.
    It extends `build_text_opti_data` with:

    - `text_color_space` (0x33): the document color-space flag.
    - `text_element_count` (0x3C): element/page count (1).
    - `text_layer_reference` (0x3D): per-layer-reference flag (`True`;
      whole-document footage is `False`).
    - `text_layer_name` (0x44): the layer name, NUL-terminated.
    - `text_page_height`/`text_page_width` (0x248/0x24C): the redundant
      page-dimension tail (BE u16).

    Bytes 0x10-0x1F hold the artwork bounding box as `(x0, y0, x1, y1)` in
    page points, four signed BE 16.16 values. Document Size keeps the
    full-page box `(0, 0, width, height)` that `build_text_opti_data`
    already writes (its "dimensions at 24/28" are that box's integral x1/y1
    parts). A chosen layer imported at Layer Size stores the layer's actual
    artwork box - fractional, and offset from the page origin - from which
    AE derives the integer footage pixel dimensions by ceiling the box size
    with a 1px floor (an empty layer stores a `1/65536` epsilon box).
    Byte-verified against AE 2026's import of ai.ai ("Calque 1"/"Calque 2",
    612x792) and its Choose Layer footage imports at both Footage
    Dimensions settings (`ai_choose_layer*.aep`: Calque 1 artwork box
    112.748, 239.507, 593.931, 675.999 -> 482x437 footage).

    Args:
        width: Document width in points.
        height: Document height in points.
        layer_name: The referenced layer's name.
        color_space: The document color space (`"CMYK"` flags byte 0x33).
        artwork_bounds: The layer's artwork box `(x0, y0, x1, y1)` in page
            points for a Layer Size import; `None` keeps the full-page box
            (Document Size and comp imports).
    """
    chunk = TextOptiChunk(
        text_width=width,
        text_height=height,
        # Document color-space flag: 0x02 for CMYK, 0x08 otherwise (RGB +
        # default). AE 2026-verified: ai.ai (CMYK)=0x02, complex.ai (RGB)=0x08.
        text_color_space=0x02 if color_space == "CMYK" else 0x08,
        text_element_count=1,
        text_layer_reference=True,
        text_layer_name=truncate_utf8(layer_name, 255).decode("utf-8"),
        text_page_height=height,
        text_page_width=width,
    )
    buf = bytearray(chunk.tobytes())
    if artwork_bounds is not None:
        # Layer Size import: overlay the layer's artwork box as four signed
        # BE 16.16 values, replacing the full-page x0/y0/x1/y1 that the typed
        # fields wrote (the fractional/offset bytes live in TextOptiChunk
        # padding, so a parse round-trip stays byte-faithful).
        struct.pack_into(">4i", buf, 0x10, *(round(v * 65536) for v in artwork_bounds))
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
    """PSD footage asset (asset_type='8BPS').

    Fixed 602-byte still-importer layout (AE 2026): 344 bytes of typed
    fields plus the 258-byte trailing layer-name block exposed via
    `psd_group_name`. Field defaults reproduce AE's merged-import header,
    so the `build_psd_*_opti_data` builders only set what differs.
    """

    asset_type: str = ascii_field(4, default="8BPS")
    asset_type_int: int = u2_field(default=265)
    _total_length: int = u4_field(default=602, repr=False)
    """Total opti body length AE bakes into the header."""

    psd_flattened: bool = bool_field()
    """`True` for the merged still of a flattened (layerless) file imported
    as a one-layer composition; per-layer and plain merged optis leave it
    `False`."""

    _pad_0b: bytes = bytes_field(3, default=b"\x00\x01\x01", repr=False)
    psd_layer_index: int = u4_field(default=0xFFFFFFFF)
    """0-based layer index. 0xFFFFFFFF = merged/flattened."""

    _pad_12: bytes = bytes_field(12, default=b"SPB8\x01" + b"\x00" * 7, repr=False)
    psd_channels: int = u1_field(default=4)
    """Number of color channels (3=RGB, 4=RGBA/CMYK). The still importer
    composites the merge to RGBA, so merged/per-layer optis store 4."""

    _pad_1f: bytes = bytes_field(1, repr=False)
    psd_canvas_height: int = u4_field(endian="<")
    """Full PSD canvas height in pixels (LE u4)."""

    psd_canvas_width: int = u4_field(endian="<")
    """Full PSD canvas width in pixels (LE u4)."""

    psd_bit_depth: int = u1_field(default=8)
    """Bit depth per channel (8, 16, or 32). Low byte of a LE u2 whose high
    byte stays 0 in `_pad_29`."""

    _pad_29: bytes = bytes_field(7, default=b"\x00\x03\x00\x00\x00\x00\x00", repr=False)
    psd_layer_count: int = u1_field(default=1)
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

    psd_layer_channels: int = u1_field()
    """Channel count of the referenced layer: 4 (RGBA) for pixel content,
    0 for an empty content box (e.g. an adjustment layer) and for merged
    imports."""

    _pad_5f: bytes = bytes_field(245, repr=False)
    psd_layer_id: int = u4_field(endian="<")
    """Photoshop layer id (`lyid`, LE u4); 0 for merged/flattened."""

    @property
    def psd_group_name(self) -> str:
        """PSD group/folder name (NUL-terminated UTF-8 at end of chunk).

        Empty for a merged import, where the trailing region is all-NUL.
        """
        return self._trailing.split(b"\x00", 1)[0].decode("utf-8")

    @psd_group_name.setter
    def psd_group_name(self, value: str) -> None:
        # AE writes a fixed 602-byte opti: keep the trailing name block
        # NUL-padded to 258 bytes so the chunk size is preserved.
        self._trailing = truncate_utf8(value, 255).ljust(258, b"\x00")


@define
class TextOptiChunk(OptiChunk):
    """AI/EPS/PDF footage asset (asset_type='TEXT').

    Fixed 596-byte layout (AE 2026). For a layered Illustrator/PDF import
    each footage item selects its source layer via `text_layer_name` and
    `text_layer_reference`; whole-document footage (and EPS) leaves them
    zero. Field defaults reproduce AE's whole-document header, so the
    `build_*_opti_data` builders only set what differs.
    """

    asset_type: str = ascii_field(4, default="TEXT")
    asset_type_int: int = u2_field(default=8)
    _total_length: int = u4_field(default=596, repr=False)
    """Total opti body length AE bakes into the header."""

    _pad_0a: bytes = bytes_field(14, repr=False)
    text_width: int = u2_field()
    """Artwork/page width in pixels: the integer part of the BE 16.16
    artwork-bbox right at 0x18 (the bbox left/top at 0x10/0x14 stay 0 for a
    full-page import)."""

    _pad_1a: bytes = bytes_field(2, repr=False)
    text_height: int = u2_field()
    """Artwork/page height in pixels (integer part of the 16.16 bbox
    bottom at 0x1C)."""

    _pad_1e: bytes = bytes_field(10, repr=False)
    _pad_28: bytes = bytes_field(4, default=b"\xff\xff\xff\xff", repr=False)
    _pad_2c: bytes = bytes_field(7, repr=False)
    text_color_space: int = u1_field()
    """Document color-space flag: 0x02 = CMYK, 0x08 = RGB/default. Not
    necessary for whole-document footage, where builders leave 0."""

    _pad_34: bytes = bytes_field(8, repr=False)
    text_element_count: int = u1_field()
    """Element/page count (1 for a per-layer reference)."""

    text_layer_reference: bool = bool_field()
    """`True` when this opti references a single source layer."""

    _pad_3e: bytes = bytes_field(6, repr=False)
    text_layer_name: str = str_field(256)
    """Selected source layer name (NUL-padded UTF-8); empty for
    whole-document footage."""

    _pad_144: bytes = bytes_field(260, repr=False)
    text_page_height: int = u2_field()
    """Redundant page-dimension tail (height); 0 for whole-document."""

    _pad_24a: bytes = bytes_field(2, repr=False)
    text_page_width: int = u2_field()
    """Redundant page-dimension tail (width); 0 for whole-document."""

    _pad_24e: bytes = bytes_field(6, repr=False)


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
    "TEXT": TextOptiChunk,
}
