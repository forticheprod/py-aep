"""Enumerate the layers of a Photoshop (PSD/PSB) file as a group tree.

After Effects imports a layered `.psd`/`.psb` as a composition with one footage
layer per Photoshop layer, and each layer group as a nested composition. The
layers come from the file's Layer and Mask Information section, stored bottom
layer first. A group spans a hidden bounding divider (`lsct` 3) at its bottom
and an open/closed folder header (`lsct` 1/2, carrying the group name) at its
top. `read_psd_layers` returns the reconstructed tree of leaf layers and groups.
"""

from __future__ import annotations

import itertools
import struct
import warnings
import zlib
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Union

from .media_probe import PSB_8BYTE_KEYS as _PSB_8BYTE_KEYS
from .media_probe import psd_layer_record_count, read_bounded

if TYPE_CHECKING:
    import os


class UnsupportedPsdLayersError(ValueError):
    """Raised when a `.psd`/`.psb` file's layers cannot be enumerated."""


class FlattenedPsdError(UnsupportedPsdLayersError):
    """Raised when a `.psd`/`.psb` is flattened (has no layer records).

    A subclass of [UnsupportedPsdLayersError][] so callers can tell a flattened
    document (which can still be imported as a single-layer composition) apart
    from an invalid file.
    """


class PsdStyleBlocks(NamedTuple):
    """Raw per-layer style-related tagged blocks, for `resolvers.psd_styles`.

    Kept as raw bytes so enumerating layers stays cheap; the effects
    descriptor is only parsed when styles are actually imported.
    """

    effects: bytes | None
    """The effects descriptor block body (`lmfx` when present, else `lfx2`;
    `lfxs` for a group header). `None` when the layer carries blend-options
    blocks (`iOpa`/`infx`/`brst`) but no styles - Photoshop's Fill slider
    is independent of layer styles, and AE imports it either way."""

    fill_opacity: int | None
    """`iOpa` fill opacity byte (0-255), or `None` when absent."""

    blend_interior: bool | None
    """`infx` "Blend Interior Effects as Group" flag, or `None` when absent."""

    channel_restrictions: bytes
    """`brst` channel-restrictions block body (empty when absent)."""


class PsdLayer(NamedTuple):
    """A leaf layer of a Photoshop document, in the order AE imports it."""

    name: str
    """Layer name (Unicode `luni` name if present, else the Pascal name)."""

    layer_id: int
    """Photoshop layer id (`lyid`); when the file stores none, the record
    index + 2, as After Effects numbers such layers."""

    bounds: tuple[int, int, int, int]
    """Content bounding box as `(left, top, right, bottom)` in canvas pixels."""

    record_index: int
    """Zero-based position of this layer's record in the full document layer
    list (counting group divider/header records), used as AE's opti layer
    index."""

    is_adjustment: bool
    """`True` when the layer is an adjustment layer (Levels, Hue/Saturation,
    ...)."""

    style_blocks: PsdStyleBlocks | None = None
    """Raw layer-style tagged blocks, or `None` when the record carries no
    effects descriptor."""

    vector_mask: bytes | None = None
    """Raw `vmsk`/`vsms` vector-mask block body (path records), or `None`
    when the layer has no vector mask. Shape layers carry one too - AE
    imports both as an AE mask on the comp layer. Decoded by
    `resolvers.psd_paths`."""

    clipped: bool = False
    """`True` when the layer is clipped to the layer below (the record's
    clipping byte). AE auto-precomposes a base + its clipped layers into
    a nested comp, with preserve-transparency on the clipped ones."""

    is_fill: bool = False
    """`True` for a fill layer (solid color, gradient or pattern - the
    `SoCo`/`GdFl`/`PtFl` blocks; a shape layer is one). Its content is
    unbounded: the record's pixels are only Photoshop's rasterized preview."""

    mask_box: tuple[int, int, int, int] | None = None
    """Where the layer shows through its enabled raster layer mask, as
    `(left, top, right, bottom)` canvas pixels: the bounds of the pixels
    whose alpha and mask are both non-zero, over the record bounds (over the
    canvas for a fill layer). `None` when the layer has no such mask."""

    has_transparency: bool = True
    """`False` when the record has no transparency channel: Photoshop's
    Background layer, which After Effects imports without alpha."""

    visible: bool = True
    """`False` when the layer is hidden in Photoshop; After Effects imports
    it with the comp layer's video switch off."""


class PsdGroup(NamedTuple):
    """A layer group; AE imports it as a nested composition.

    `style_blocks` carries the styles Photoshop allows on the GROUP itself;
    the import does not apply them (a warning surfaces the drop)."""

    name: str
    """Group name (from the folder header record)."""

    layer_id: int
    """Photoshop layer id (`lyid`) of the group header."""

    children: list[PsdLayer | PsdGroup]
    """The group's contents, bottom layer first."""

    style_blocks: PsdStyleBlocks | None = None
    """Raw layer-style tagged blocks of the group header record, or `None`
    when the group carries no effects descriptor."""

    visible: bool = True
    """`False` when the group is hidden in Photoshop."""


PsdNode = Union[PsdLayer, PsdGroup]


# Adjustment-layer additional-info keys (one is present per adjustment type).
_ADJUSTMENT_KEYS = frozenset(
    {
        b"brit",
        b"levl",
        b"curv",
        b"expA",
        b"vibA",
        b"hue ",
        b"hue2",
        b"blnc",
        b"blwh",
        b"phfl",
        b"mixr",
        b"clrL",
        b"nvrt",
        b"post",
        b"thrs",
        b"grdm",
        b"selc",
    }
)


# Fill-layer additional-info keys: solid color, gradient and pattern fills.
_FILL_KEYS = frozenset({b"SoCo", b"GdFl", b"PtFl"})

# Maps every byte to 0 (zero) or 1 (non-zero), so rows of samples can be
# combined with integer AND / OR.
_NONZERO = bytes([0] + [1] * 255)

# The largest document the PSB format allows (PSD: 30,000 px). No canvas,
# layer or mask Photoshop writes is wider or taller, so a larger rectangle is
# a corrupt record - decoding it would allocate rows of absurd size.
_MAX_EXTENT = 300_000

# The most a channel's bytes can inflate when decoded: deflate's 1032:1
# limit (raw data is 1:1, PackBits at most 64:1). A rectangle whose decoded
# size would need more than that from its bytes is a corrupt record.
_MAX_INFLATION = 1032


class _Record(NamedTuple):
    """One raw layer record, before the group tree is rebuilt."""

    name: str
    layer_id: int
    bounds: tuple[int, int, int, int]
    record_index: int
    section_divider: int
    is_adjustment: bool
    style_blocks: PsdStyleBlocks | None = None
    vector_mask: bytes | None = None
    clipped: bool = False
    is_fill: bool = False
    mask_box: tuple[int, int, int, int] | None = None
    has_transparency: bool = True
    visible: bool = True


class _UserMask(NamedTuple):
    """An enabled raster layer mask painted by the user (not the one
    Photoshop renders from a vector mask)."""

    channel_id: int
    bounds: tuple[int, int, int, int]
    default: int


def read_psd_layers(
    file: str | os.PathLike[str], *, mask_boxes: bool = True
) -> list[PsdNode]:
    """Return the layer tree of a Photoshop file (bottom layer first).

    Args:
        file: Path to a `.psd` or `.psb` file.
        mask_boxes: Decode each raster layer mask's channel data for
            `PsdLayer.mask_box` (a full decode of the masked layers'
            pixels). `False` leaves it `None`, for callers that only
            need names and indices.

    Returns:
        Top-level nodes bottom-first: [PsdLayer][] leaves and [PsdGroup][]
        groups (groups nest recursively).

    Raises:
        UnsupportedPsdLayersError: If the file is not a valid PSD/PSB.
        FlattenedPsdError: If the file has no layer records (a flattened
            document) - a subclass of `UnsupportedPsdLayersError`.
    """
    name = Path(file).name
    flattened = FlattenedPsdError(f"{name}: flattened document (no layer records).")
    # The byte-level parse below trusts the file layout; a truncated or
    # corrupt PSD would otherwise surface a raw struct.error/UnicodeDecodeError.
    # Convert those to the documented domain exception (FlattenedPsdError, a
    # subclass, still propagates since it is neither of the caught types).
    try:
        # Read only up to the Layer Info block: the layer records precede the
        # channel image data, which dominates a PSD's size.
        with Path(file).open("rb") as fp:
            header = fp.read(26)
            if header[:4] != b"8BPS":
                raise UnsupportedPsdLayersError(f"{name}: not a valid PSD/PSB file.")
            is_psb = struct.unpack(">H", header[4:6])[0] == 2
            canvas_h, canvas_w = struct.unpack(">II", header[14:22])
            depth = struct.unpack(">H", header[22:24])[0]
            if not (0 < canvas_w <= _MAX_EXTENT and 0 < canvas_h <= _MAX_EXTENT):
                raise UnsupportedPsdLayersError(
                    f"{name}: invalid canvas size {canvas_w}x{canvas_h}."
                )
            record_count, remaining = psd_layer_record_count(fp, is_psb)
            if record_count == 0:
                raise flattened
            data = read_bounded(fp, remaining)
        off = 0

        chan_len_size = 8 if is_psb else 4
        records: list[_Record] = []
        channel_lists: list[list[tuple[int, int]]] = []
        user_masks: list[_UserMask | None] = []
        for index in range(record_count):
            top, left, bottom, right = struct.unpack(">iiii", data[off : off + 16])
            off += 16
            num_channels = struct.unpack(">H", data[off : off + 2])[0]
            off += 2
            channels = []
            for _ in range(num_channels):
                channel_id = struct.unpack(">h", data[off : off + 2])[0]
                length = int.from_bytes(data[off + 2 : off + 2 + chan_len_size], "big")
                channels.append((channel_id, length))
                off += 2 + chan_len_size
            channel_lists.append(channels)
            off += 8  # blend mode signature (4) + key (4)
            clipped = data[off + 1] != 0  # opacity, CLIPPING, flags, filler
            # Flags bit 1 marks a layer hidden in Photoshop; AE 2026 imports
            # it with the comp layer's video switch off (synthetic
            # hidden_layer.psd, COMP and COMP_CROPPED_LAYERS).
            visible = not data[off + 2] & 0x02
            off += 4
            extra_len = struct.unpack(">I", data[off : off + 4])[0]
            off += 4
            extra = data[off : off + extra_len]
            off += extra_len
            (
                layer_name,
                layer_id,
                section_divider,
                is_adjustment,
                style_blocks,
                vector_mask,
                is_fill,
                mask_data,
            ) = _parse_layer_extra(extra, is_psb)
            user_masks.append(
                _user_mask(mask_data, name, layer_name) if mask_boxes else None
            )
            has_transparency = any(cid == -1 for cid, _ in channels)
            if index == 0 and not has_transparency and not section_divider:
                # Photoshop's Background layer (the bottom record, with no
                # transparency channel): AE 2026 names it "Background"
                # whatever the file stores - a French Photoshop's
                # "Arrière-plan" imports as "Background" (footage_depth.aep,
                # psd_rgb8_bg_layer.psd / psd_rgb16_bg_layer.psd).
                layer_name = "Background"
            records.append(
                _Record(
                    name=layer_name,
                    # Without an `lyid` block AE 2026 numbers the layers from
                    # 2 in record order (synthetic PSDs with no ids).
                    layer_id=index + 2 if layer_id is None else layer_id,
                    bounds=(left, top, right, bottom),
                    record_index=index,
                    section_divider=section_divider,
                    is_adjustment=is_adjustment,
                    style_blocks=style_blocks,
                    vector_mask=vector_mask,
                    clipped=clipped,
                    is_fill=is_fill,
                    has_transparency=has_transparency,
                    visible=visible,
                )
            )
        # The channel image data follows the records, each record's channels
        # in its channel-list order.
        for index, channels in enumerate(channel_lists):
            rec = records[index]
            mask = user_masks[index]
            # Where each channel's data lies: only a masked record's alpha
            # and mask channels are read, so nothing else is copied.
            spans: dict[int, tuple[int, int]] = {}
            for channel_id, length in channels:
                spans[channel_id] = (off, off + length)
                off += length
            if mask is None or rec.is_adjustment or rec.section_divider:
                continue
            region = (0, 0, canvas_w, canvas_h) if rec.is_fill else rec.bounds
            if region[2] <= region[0] or region[3] <= region[1]:
                continue
            area = (region[2] - region[0]) * (region[3] - region[1])
            source = len(data) if rec.is_fill else sum(n for _, n in channels)
            if area > _MAX_INFLATION * source:
                raise UnsupportedPsdLayersError(
                    f"{name}: layer {rec.name!r} is larger than its pixel data."
                )
            alpha = None if rec.is_fill else spans.get(-1)
            mask_span = spans.get(mask.channel_id)
            records[index] = rec._replace(
                mask_box=_visible_box(
                    region,
                    None if alpha is None else data[alpha[0] : alpha[1]],
                    mask,
                    None if mask_span is None else data[mask_span[0] : mask_span[1]],
                    depth,
                    is_psb,
                )
            )
    except (struct.error, UnicodeDecodeError, zlib.error, IndexError) as exc:
        raise UnsupportedPsdLayersError(
            f"{name}: malformed PSD/PSB layer data."
        ) from exc
    return _build_layer_tree(records)


def _user_mask(mask: bytes, file_name: str, layer_name: str) -> _UserMask | None:
    """The enabled, user-painted raster mask described by a record's layer
    mask data, or `None`.

    Photoshop also renders a vector mask into the mask channel (flags bit
    3); AE ignores that copy and applies the path itself. When a layer has
    both, the painted mask is the "real" one (channel -3).
    """
    if len(mask) < 18:
        return None
    top, left, bottom, right = struct.unpack(">iiii", mask[:16])
    default, flags = mask[16], mask[17]
    pos = 18
    if flags & 0x10:
        parameters = mask[pos]
        pos += 1
        if parameters & 0x03:
            warnings.warn(
                f"{file_name}: the density / feather of layer {layer_name!r}'s "
                "mask is not modeled; its footage is sized as if unmasked",
                stacklevel=3,
            )
            return None
        pos += (1 if parameters & 0x04 else 0) + (8 if parameters & 0x08 else 0)
    if len(mask) - pos >= 18:
        real_flags, real_default = mask[pos], mask[pos + 1]
        top, left, bottom, right = struct.unpack(">iiii", mask[pos + 2 : pos + 18])
        if real_flags & 0x02:
            return None
        return _UserMask(-3, (left, top, right, bottom), real_default)
    if flags & 0x0A:
        # Disabled (bit 1), or rendered from the vector mask (bit 3).
        return None
    return _UserMask(-2, (left, top, right, bottom), default)


def _visible_box(
    region: tuple[int, int, int, int],
    alpha: bytes | None,
    mask: _UserMask,
    mask_data: bytes | None,
    depth: int,
    is_psb: bool,
) -> tuple[int, int, int, int]:
    """The bounds of the pixels of `region` where the layer's alpha (fully
    opaque when `alpha` is `None`) and its mask are both non-zero, as AE
    crops a masked layer (measured on AE 2026 with alpha holes under the
    mask). An empty result is `(0, 0, 0, 0)`."""
    rl, rt, rr, rb = region
    width = rr - rl
    ml, mt, mr, mb = mask.bounds
    mask_rows = (
        _channel_flags(mask_data, mr - ml, mb - mt, depth, is_psb)
        if mask_data is not None and mr > ml and mb > mt
        else []
    )
    alpha_rows = (
        _channel_flags(alpha, width, rb - rt, depth, is_psb)
        if alpha is not None
        else None
    )
    default_row = (b"\x01" if mask.default else b"\x00") * width
    # Outside its rectangle the mask takes its default color, so with a black
    # default only the rectangle's rows can show.
    rows = range(rt, rb) if mask.default else range(max(rt, mt), min(rb, mb))
    x0, x1 = max(ml, rl), min(mr, rr)
    min_x = min_y = max_x = max_y = None
    for y in rows:
        row = bytearray(default_row)
        if mask_rows and mt <= y < mb and x0 < x1:
            row[x0 - rl : x1 - rl] = mask_rows[y - mt][x0 - ml : x1 - ml]
        visible = int.from_bytes(row, "big")
        if alpha_rows is not None:
            visible &= int.from_bytes(alpha_rows[y - rt], "big")
        if not visible:
            continue
        # Column of the most / least significant set byte.
        first = width - 1 - (visible.bit_length() - 1) // 8
        last = width - 1 - ((visible & -visible).bit_length() - 1) // 8
        min_x = first if min_x is None else min(min_x, first)
        max_x = last if max_x is None else max(max_x, last)
        if min_y is None:
            min_y = y
        max_y = y
    if min_x is None or max_x is None or min_y is None or max_y is None:
        return (0, 0, 0, 0)
    return (rl + min_x, min_y, rl + max_x + 1, max_y + 1)


def _channel_flags(
    chunk: bytes, width: int, height: int, depth: int, is_psb: bool
) -> list[bytes]:
    """Decode one channel's image data to rows of 0 / 1 bytes, 1 where a
    sample is non-zero.

    Handles the four PSD compressions: raw, PackBits RLE (8-bit and 16-bit
    documents), and zlib with or without prediction (written for 16/32-bit).
    """
    compression = struct.unpack(">H", chunk[:2])[0]
    sample = max(depth // 8, 1)
    row_len = width * sample
    if (
        width > _MAX_EXTENT
        or height > _MAX_EXTENT
        or row_len * height > _MAX_INFLATION * len(chunk)
    ):
        raise UnsupportedPsdLayersError(
            f"channel data ({len(chunk)} bytes) too short for {width}x{height}"
        )
    body = chunk[2:]
    if compression == 1:
        count_size = 4 if is_psb else 2
        counts_end = height * count_size
        pos = counts_end
        raw = bytearray()
        for y in range(height):
            n = int.from_bytes(body[y * count_size : (y + 1) * count_size], "big")
            raw += _unpack_bits(body[pos : pos + n], row_len)
            pos += n
    elif compression in (2, 3):
        # Bounded by the rectangle, not by whatever the stream inflates to.
        raw = bytearray(zlib.decompressobj().decompress(body, max(row_len * height, 1)))
    else:
        raw = bytearray(body)
    rows = []
    for y in range(height):
        row = bytes(raw[y * row_len : (y + 1) * row_len])
        if compression == 3:
            row = _undo_prediction(row, width, sample)
        if sample == 1:
            rows.append(row.translate(_NONZERO))
            continue
        # A sample is non-zero when any of its bytes is: interleaved bytes
        # for 16-bit, byte planes (after prediction) for 32-bit.
        planes = (
            [row[i * width : (i + 1) * width] for i in range(sample)]
            if compression == 3 and sample == 4
            else [row[i::sample] for i in range(sample)]
        )
        combined = 0
        for plane in planes:
            combined |= int.from_bytes(plane.translate(_NONZERO), "big")
        rows.append(combined.to_bytes(width, "big"))
    return rows


def _unpack_bits(data: bytes, size: int) -> bytes:
    out = bytearray()
    i = 0
    while len(out) < size and i < len(data):
        n = data[i]
        i += 1
        if n < 128:
            out += data[i : i + n + 1]
            i += n + 1
        elif n > 128:
            out += data[i : i + 1] * (257 - n)
            i += 1
    return bytes(out[:size].ljust(size, b"\x00"))


def _undo_prediction(row: bytes, width: int, sample: int) -> bytes:
    """Undo the zlib-with-prediction delta coding of one row: per 16-bit
    sample for 16-bit documents, over the whole row's bytes (stored as byte
    planes) for 8 and 32-bit ones."""
    if sample == 2:
        values = struct.unpack(f">{width}H", row)
        return struct.pack(
            f">{width}H", *(v & 0xFFFF for v in itertools.accumulate(values))
        )
    return bytes(v & 0xFF for v in itertools.accumulate(row))


def _build_layer_tree(records: list[_Record]) -> list[PsdNode]:
    """Rebuild the group tree from a flat, bottom-first record list.

    A bounding divider (`lsct` 3) opens a group scope; the matching folder
    header (`lsct` 1/2) closes it and names the group. Groups nest via a stack.
    """
    root: list[PsdNode] = []
    stack: list[list[PsdNode]] = [root]
    for rec in records:
        if rec.section_divider == 3:
            stack.append([])
        elif rec.section_divider in (1, 2):
            children = stack.pop() if len(stack) > 1 else []
            stack[-1].append(
                PsdGroup(
                    name=rec.name,
                    layer_id=rec.layer_id,
                    children=children,
                    style_blocks=rec.style_blocks,
                    visible=rec.visible,
                )
            )
        else:
            stack[-1].append(
                PsdLayer(
                    name=rec.name,
                    layer_id=rec.layer_id,
                    bounds=rec.bounds,
                    record_index=rec.record_index,
                    is_adjustment=rec.is_adjustment,
                    style_blocks=rec.style_blocks,
                    vector_mask=rec.vector_mask,
                    clipped=rec.clipped,
                    is_fill=rec.is_fill,
                    mask_box=rec.mask_box,
                    has_transparency=rec.has_transparency,
                    visible=rec.visible,
                )
            )
    # Defensive: an unbalanced file leaves open scopes; surface their contents.
    while len(stack) > 1:
        orphans = stack.pop()
        stack[-1].extend(orphans)
    return root


def _parse_layer_extra(
    extra: bytes, is_psb: bool
) -> tuple[
    str, int | None, int, bool, PsdStyleBlocks | None, bytes | None, bool, bytes
]:
    """Extract `(name, layer_id, section_divider, is_adjustment, style_blocks,
    vector_mask, is_fill, mask_data)`; `layer_id` is `None` without an `lyid`
    block.

    `section_divider` is the `lsct` value: 0 (or absent) for a normal layer,
    1/2 for an open/closed group header, 3 for the hidden bounding divider that
    ends a group. `is_adjustment` is `True` when an adjustment-type key is
    present. `style_blocks` carries the raw layer-style tagged blocks, `None`
    when the record has no effects descriptor. `vector_mask` is the raw
    `vmsk`/`vsms` block body, `None` when the layer has no vector mask.
    `is_fill` is `True` when a fill-layer key is present. `mask_data` is the
    layer mask data sub-block body (empty when the layer has no mask).
    """
    pos = 0
    # Layer mask data and blending-ranges sub-blocks (4-byte lengths in both).
    mask_len = struct.unpack(">I", extra[pos : pos + 4])[0]
    mask_data = extra[pos + 4 : pos + 4 + mask_len]
    pos += 4 + mask_len
    pos += 4 + struct.unpack(">I", extra[pos : pos + 4])[0]
    # Legacy Pascal name, padded so (1 + length) is a multiple of 4.
    pascal_len = extra[pos]
    pascal = extra[pos + 1 : pos + 1 + pascal_len].decode("latin-1")
    pos += 1 + pascal_len
    pos += (4 - ((1 + pascal_len) % 4)) % 4
    # Remaining bytes are additional layer info blocks.
    unicode_name: str | None = None
    layer_id: int | None = None
    section_divider = 0
    is_adjustment = False
    is_fill = False
    lfx2: bytes | None = None
    lmfx: bytes | None = None
    lfxs: bytes | None = None
    fill_opacity: int | None = None
    blend_interior: bool | None = None
    channel_restrictions = b""
    vmsk: bytes | None = None
    vsms: bytes | None = None
    while pos + 12 <= len(extra):
        signature = extra[pos : pos + 4]
        if signature not in (b"8BIM", b"8B64"):
            break
        key = extra[pos + 4 : pos + 8]
        if is_psb and key in _PSB_8BYTE_KEYS:
            block_len = struct.unpack(">Q", extra[pos + 8 : pos + 16])[0]
            block_start = pos + 16
        else:
            block_len = struct.unpack(">I", extra[pos + 8 : pos + 12])[0]
            block_start = pos + 12
        block = extra[block_start : block_start + block_len]
        if key == b"luni":
            char_count = struct.unpack(">I", block[:4])[0]
            unicode_name = (
                block[4 : 4 + char_count * 2].decode("utf-16-be").rstrip("\x00")
            )
        elif key == b"lyid":
            layer_id = struct.unpack(">I", block[:4])[0]
        elif key == b"lsct" and block_len >= 4:
            section_divider = struct.unpack(">I", block[:4])[0]
        elif key in _ADJUSTMENT_KEYS:
            is_adjustment = True
        elif key in _FILL_KEYS:
            is_fill = True
        elif key == b"lfx2":
            lfx2 = block
        elif key == b"lmfx":
            lmfx = block
        elif key == b"lfxs":
            # Group headers store their styles under `lfxs` (same descriptor
            # layout as `lfx2`; probed Photoshop 2026, psd_group_styles.psd).
            lfxs = block
        elif key == b"vmsk":
            vmsk = block
        elif key == b"vsms":
            # CS6+ variant of vmsk (written when the mask needs the newer
            # feature set); same path-record layout.
            vsms = block
        elif key == b"iOpa" and block_len >= 1:
            fill_opacity = block[0]
        elif key == b"infx" and block_len >= 1:
            blend_interior = block[0] != 0
        elif key == b"brst":
            channel_restrictions = block
        pos = block_start + block_len + (block_len & 1)  # blocks padded to even
    # Photoshop writes lmfx (and drops lfx2) when any style has multiple
    # instances; prefer it when both somehow exist. Groups carry lfxs
    # instead (a group record never has lfx2/lmfx).
    effects = lmfx if lmfx is not None else lfx2
    if effects is None:
        effects = lfxs
    # Photoshop writes an `infx` block (False) on every ordinary layer, so
    # only a user deviation counts: Fill away from 100% (`iOpa` present),
    # Blend Interior checked, or a channel restriction.
    has_blend_data = (
        fill_opacity is not None or bool(blend_interior) or bool(channel_restrictions)
    )
    style_blocks = (
        PsdStyleBlocks(effects, fill_opacity, blend_interior, channel_restrictions)
        if effects is not None or has_blend_data
        else None
    )
    return (
        unicode_name if unicode_name is not None else pascal,
        layer_id,
        section_divider,
        is_adjustment,
        style_blocks,
        vsms if vsms is not None else vmsk,
        is_fill,
        mask_data,
    )
