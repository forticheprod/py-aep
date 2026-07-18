"""Enumerate the layers of a Photoshop (PSD/PSB) file as a group tree.

After Effects imports a layered `.psd`/`.psb` as a composition with one footage
layer per Photoshop layer, and each layer group as a nested composition. The
layers come from the file's Layer and Mask Information section, stored bottom
layer first. A group spans a hidden bounding divider (`lsct` 3) at its bottom
and an open/closed folder header (`lsct` 1/2, carrying the group name) at its
top. `read_psd_layers` returns the reconstructed tree of leaf layers and groups.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Union

from .media_probe import PSB_8BYTE_KEYS as _PSB_8BYTE_KEYS
from .media_probe import psd_layer_record_count

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
    """Photoshop layer id (`lyid`); 0 when the file stores none."""

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


def read_psd_layers(file: str | os.PathLike[str]) -> list[PsdNode]:
    """Return the layer tree of a Photoshop file (bottom layer first).

    Args:
        file: Path to a `.psd` or `.psb` file.

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
            record_count, remaining = psd_layer_record_count(fp, is_psb)
            if record_count == 0:
                raise flattened
            data = fp.read(remaining)
        off = 0

        chan_len_size = 8 if is_psb else 4
        records: list[_Record] = []
        for index in range(record_count):
            top, left, bottom, right = struct.unpack(">iiii", data[off : off + 16])
            off += 16
            num_channels = struct.unpack(">H", data[off : off + 2])[0]
            off += 2
            off += num_channels * (2 + chan_len_size)
            off += 8  # blend mode signature (4) + key (4)
            clipped = data[off + 1] != 0  # opacity, CLIPPING, flags, filler
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
            ) = _parse_layer_extra(extra, is_psb)
            records.append(
                _Record(
                    name=layer_name,
                    layer_id=layer_id,
                    bounds=(left, top, right, bottom),
                    record_index=index,
                    section_divider=section_divider,
                    is_adjustment=is_adjustment,
                    style_blocks=style_blocks,
                    vector_mask=vector_mask,
                    clipped=clipped,
                )
            )
    except (struct.error, UnicodeDecodeError) as exc:
        raise UnsupportedPsdLayersError(
            f"{name}: malformed PSD/PSB layer data."
        ) from exc
    return _build_layer_tree(records)


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
                )
            )
    # Defensive: an unbalanced file leaves open scopes; surface their contents.
    while len(stack) > 1:
        orphans = stack.pop()
        stack[-1].extend(orphans)
    return root


def _parse_layer_extra(
    extra: bytes, is_psb: bool
) -> tuple[str, int, int, bool, PsdStyleBlocks | None, bytes | None]:
    """Extract `(name, layer_id, section_divider, is_adjustment, style_blocks,
    vector_mask)`.

    `section_divider` is the `lsct` value: 0 (or absent) for a normal layer,
    1/2 for an open/closed group header, 3 for the hidden bounding divider that
    ends a group. `is_adjustment` is `True` when an adjustment-type key is
    present. `style_blocks` carries the raw layer-style tagged blocks, `None`
    when the record has no effects descriptor. `vector_mask` is the raw
    `vmsk`/`vsms` block body, `None` when the layer has no vector mask.
    """
    pos = 0
    # Layer mask data and blending-ranges sub-blocks (4-byte lengths in both).
    pos += 4 + struct.unpack(">I", extra[pos : pos + 4])[0]
    pos += 4 + struct.unpack(">I", extra[pos : pos + 4])[0]
    # Legacy Pascal name, padded so (1 + length) is a multiple of 4.
    pascal_len = extra[pos]
    pascal = extra[pos + 1 : pos + 1 + pascal_len].decode("latin-1")
    pos += 1 + pascal_len
    pos += (4 - ((1 + pascal_len) % 4)) % 4
    # Remaining bytes are additional layer info blocks.
    unicode_name: str | None = None
    layer_id = 0
    section_divider = 0
    is_adjustment = False
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
    )
