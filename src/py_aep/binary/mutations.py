"""Chunk tree mutation helpers for the binary I/O layer."""

from __future__ import annotations

import struct
from io import BytesIO
from typing import TYPE_CHECKING

from .chunk import Chunk, ListChunk, read_chunks, write_chunk
from .ldat_chunks import (
    GdtaChunk,
    KfColor,
    KfMultiDimensional,
    KfNoValue,
    KfPosition,
    LdatChunk,
    LdatItem,
    LdatItemType,
    Lhd3Chunk,
    ShapePoint,
)
from .misc_chunks import (
    ApidChunk,
    DcuiChunk,
    DropChunk,
    EmbpChunk,
    EpidChunk,
    HdrmChunk,
    IpwsChunk,
    LinlChunk,
    McspChunk,
    OcspChunk,
    PguiChunk,
    PrgbChunk,
    ShphChunk,
    StrtChunk,
)
from .render_chunks import RoutItem
from .scalar_chunks import U4Chunk, Utf8Chunk

if TYPE_CHECKING:
    from typing import Any, Callable

# Keyframe ldat items always use raw type 4; the effective LdatItemType is
# disambiguated by item_size (and spatial context on re-read).
_KEYFRAME_ITEM_TYPE_RAW = 4

# Fixed serialized byte size per keyframe item type.
ITEM_SIZE_BY_TYPE: dict[LdatItemType, int] = {
    LdatItemType.color: 152,
    LdatItemType.three_d_spatial: 128,
    LdatItemType.three_d: 128,
    LdatItemType.two_d_spatial: 104,
    LdatItemType.two_d: 88,
    LdatItemType.orientation: 80,
    LdatItemType.no_value: 64,
    LdatItemType.one_d: 48,
    LdatItemType.marker: 16,
    LdatItemType.shape: 8,
}


def remove_chunks_by_type(
    chunks: list[Chunk],
    chunk_type: str,
) -> None:
    """Remove all chunks of `chunk_type` from the list in-place."""
    i = len(chunks) - 1
    while i >= 0:
        if chunks[i].chunk_type == chunk_type:
            del chunks[i]
        i -= 1


def toggle_flag_chunk(
    chunks: list[Chunk],
    chunk_type: str,
    enable: bool,
    factory: Callable[[], Chunk],
) -> None:
    """Add or remove a single-byte flag chunk.

    When `enable` is true and no chunk of `chunk_type` exists, call
    `factory()` to create one and append it. When false, remove all
    matching chunks.
    """
    has = any(c.chunk_type == chunk_type for c in chunks)
    if enable and not has:
        chunks.append(factory())
    elif not enable and has:
        remove_chunks_by_type(chunks, chunk_type)


def _unflag_markers(
    parent_chunks: list[Chunk],
    target: ListChunk,
) -> None:
    """Clear the `synthetic` flag on tdmn chunks adjacent to `target`."""
    idx = None
    for i, c in enumerate(parent_chunks):
        if c is target:
            idx = i
            break
    if idx is None:
        return
    if idx > 0 and parent_chunks[idx - 1].chunk_type == "tdmn":
        parent_chunks[idx - 1].synthetic = False
    if idx + 1 < len(parent_chunks) and parent_chunks[idx + 1].chunk_type == "tdmn":
        parent_chunks[idx + 1].synthetic = False


def clone_chunk_tree(chunk: Chunk) -> Chunk:
    """Deep-copy a chunk tree via serialize/deserialize round-trip.

    Synthetic chunks are excluded during serialization, so the clone
    contains only real (non-synthetic) chunks.
    """
    buf = BytesIO()
    size = write_chunk(buf, chunk)
    buf.seek(0)
    return read_chunks(buf, size)[0]


def build_keyframe_list(
    item_type: LdatItemType,
    item_size: int,
) -> tuple[ListChunk, Lhd3Chunk, LdatChunk]:
    """Build an empty keyframe container `LIST:list` (lhd3 + ldat).

    The opaque lhd3 counters are seeded to the constant values After
    Effects writes for every animated property (`_count_b=1`,
    `_counter_a=1`, `_counter_b=4`), regardless of keyframe count.

    Returns:
        `(inner, lhd3, ldat)` - the `LIST:list`, its header, and the
        (empty) data chunk. Callers append `LdatItem`s to `ldat.items`
        and keep `lhd3.count` in sync.
    """
    lhd3 = Lhd3Chunk(
        item_size=item_size,
        item_type_raw=_KEYFRAME_ITEM_TYPE_RAW,
        counter_b=4,
    )
    ldat = LdatChunk(items=[], item_type=item_type, item_size=item_size)
    inner = ListChunk(list_type="list", chunks=[lhd3, ldat])
    return inner, lhd3, ldat


def build_kf_data(item_type: LdatItemType, num_value: int) -> Any:
    """Build a fresh keyframe-data payload of `item_type`.

    Speed / influence are seeded to zero (LINEAR defaults). The caller
    sets the actual value afterwards (e.g. via `Keyframe.value`).
    """
    if item_type == LdatItemType.color:
        return KfColor()
    if item_type in (LdatItemType.two_d_spatial, LdatItemType.three_d_spatial):
        return KfPosition(
            value=[0.0] * num_value,
            in_spatial_tangents=[0.0] * num_value,
            out_spatial_tangents=[0.0] * num_value,
            spatial_flags=1,
        )
    if item_type == LdatItemType.no_value:
        return KfNoValue()
    return KfMultiDimensional(
        value=[0.0] * num_value,
        in_speed=[0.0] * num_value,
        in_influence=[0.0] * num_value,
        out_speed=[0.0] * num_value,
        out_influence=[0.0] * num_value,
    )


def build_ldat_item(kf_data: Any, *, spatial: bool) -> LdatItem:
    """Wrap a keyframe-data payload in an `LdatItem` with LINEAR defaults."""
    return LdatItem(
        time_units=0,
        in_interpolation_type=1,
        out_interpolation_type=1,
        temporal_flags=7 if spatial else 0,
        kf_data=kf_data,
    )


def set_orientation_item_values(item: LdatItem, values: list[float]) -> None:
    """Mirror orientation angles into a keyframe item's trailing bytes.

    AE stores a copy of the otda angles after the 1D ease data of each
    orientation keyframe item: 8 zero bytes + 3 little-endian doubles.
    """
    item._trailing = b"\x00" * 8 + struct.pack("<3d", *values[:3])


def build_parallel_ldat_item(
    item_type: LdatItemType,
    orientation_values: list[float] | None = None,
) -> LdatItem:
    """Build a keyframe-header `LdatItem` for a complex (parallel-container) property.

    Shape, gradient, orientation, marker and text properties store the real
    per-keyframe value in a sibling container (omks / GCky / otky / mrky /
    btdk); this header item carries only timing/ease plus type-specific
    padding. Layouts reverse-engineered from AE 2026 output.
    """
    item_size = ITEM_SIZE_BY_TYPE[item_type]
    if item_type == LdatItemType.orientation:
        kf_data: Any = KfMultiDimensional(
            value=[0.0],
            in_speed=[0.0],
            in_influence=[0.0],
            out_speed=[0.0],
            out_influence=[0.0],
        )
        interp, flags = 1, 1
    elif item_type == LdatItemType.no_value:  # shape, gradient
        kf_data = KfNoValue()
        interp, flags = 1, 1
    elif item_type == LdatItemType.marker:  # marker, text (HOLD - no interpolation)
        kf_data = b"\x00" * 8
        interp, flags = 3, 0
    else:
        raise ValueError(f"unsupported parallel item type {item_type!r}")
    body_len = 8 + (
        len(kf_data) if isinstance(kf_data, bytes) else len(kf_data.tobytes())
    )
    item = LdatItem(
        time_units=0,
        in_interpolation_type=interp,
        out_interpolation_type=interp,
        temporal_flags=flags,
        kf_data=kf_data,
        trailing=b"\x00" * (item_size - body_len),
    )
    if item_type == LdatItemType.orientation and orientation_values is not None:
        set_orientation_item_values(item, orientation_values)
    return item


def build_shap(
    bbox: tuple[float, float, float, float],
    *,
    open_path: bool,
    points: list[ShapePoint],
) -> ListChunk:
    """Build a `shap` LIST chunk: `shph` + point `LIST:list` + empty `omtn`.

    `bbox` is `(top_left_x, top_left_y, bottom_right_x, bottom_right_y)`;
    `points` are the normalized bezier control points (3 per vertex).
    """
    shph = ShphChunk()
    shph.open = open_path
    shph.top_left_x, shph.top_left_y, shph.bottom_right_x, shph.bottom_right_y = bbox
    n_verts = len(points) // 3
    lhd3 = Lhd3Chunk(
        count=len(points),
        item_size=8,
        item_type_raw=4,
        count_b=n_verts,
        counter_a=1,
        counter_b=4 * n_verts,
    )
    ldat = LdatChunk(items=list(points), item_type=LdatItemType.shape, item_size=8)
    inner = ListChunk(list_type="list", chunks=[lhd3, ldat])
    omtn = Chunk(chunk_type="omtn", data=b"")
    return ListChunk(list_type="shap", chunks=[shph, inner, omtn])


def build_gide_list() -> tuple[ListChunk, Lhd3Chunk, ListChunk]:
    """Build an empty `LIST:Gide` guide container.

    Returns:
        (gide, lhd3, inner) - the outer Gide list, header chunk,
        and inner `LIST:list`.  Callers can append an `LdatChunk`
        to *inner* when guide data is needed.
    """
    lhd3 = Lhd3Chunk(item_size=16, item_type_raw=2)
    inner = ListChunk(list_type="list", chunks=[lhd3])
    gide = ListChunk(list_type="Gide", chunks=[GdtaChunk(), inner])
    return gide, lhd3, inner


def build_ovg2() -> ListChunk:
    """Build the `LIST:OvG2(CprC)` block AE writes after a Layer
    Overrides tdmn."""
    return ListChunk(list_type="OvG2", chunks=[U4Chunk(chunk_type="CprC")])


def build_source_alternate_extras() -> list[Chunk]:
    """Build the `blsv`/`blsi` pair AE writes after a Layer Source
    Alternate tdmn."""
    return [
        U4Chunk(chunk_type="blsv", value=1),
        U4Chunk(chunk_type="blsi", value=0),
    ]


def build_pin_list(
    sspc: Chunk,
    opti: Chunk,
    *,
    is_solid: bool = False,
    path_chunks: list[Chunk] | None = None,
) -> ListChunk:
    """Build a complete `LIST:Pin` with required companion chunks.

    `path_chunks` (the `LIST:Als2` path and, for sequences, the
    prefix/extension `Utf8` chunks) are inserted between the leading
    empty `Utf8` and `opti`. File sources pass them; solid/placeholder
    sources (no file path) pass nothing.
    """
    clrs_chunks: list[Chunk] = [
        EpidChunk(),
        ApidChunk(),
        LinlChunk(),
        EmbpChunk(),
        IpwsChunk(),
    ]
    if is_solid:
        clrs_chunks.append(DcuiChunk())
        clrs_chunks.append(PrgbChunk())
    clrs_chunks.extend(
        [
            McspChunk(),
            Utf8Chunk(),
            OcspChunk(),
            Utf8Chunk(),
            HdrmChunk(),
            Utf8Chunk(value="{}"),
        ]
    )
    clrs = ListChunk(list_type="CLRS", chunks=clrs_chunks)

    mnfo = ListChunk(
        list_type="mnfo",
        chunks=[StrtChunk(), DropChunk()],
    )

    return ListChunk(
        list_type="Pin ",
        chunks=[
            sspc,
            Utf8Chunk(),
            *(path_chunks or []),
            opti,
            PguiChunk.new(),
            clrs,
            mnfo,
            Utf8Chunk(),
        ],
    )


def build_rout_block() -> list[RoutItem]:
    """Build the fixed block of `Rout` entries AE writes per render queue
    item (`ROUT_ITEMS_PER_RQ_ITEM` = 1 render flag + 4 slot entries).

    `state` is a position-dependent slot type code: 0x11 at positions
    0/1/3, 0x7B at position 2, 0x88 at position 4.
    """
    return [
        RoutItem(flags=0x40, state=0x11),
        RoutItem(flags=0x80, state=0x11),
        RoutItem(flags=0xA0, state=0x7B),
        RoutItem(flags=0x80, state=0x11),
        RoutItem(flags=0xA0, state=0x88),
    ]


def build_om_container() -> ListChunk:
    """Build an empty output-module metadata container (`LIST:list` with
    lhd3 + ldat) for a new render queue item.

    `count_b`/`counter_a`/`counter_b` stay at 1 to match real files; only
    `count` tracks the output module count.
    """
    lhd3 = Lhd3Chunk(count=0, item_size=128, item_type_raw=1, counter_b=1)
    ldat = LdatChunk(items=[], item_type=LdatItemType.litm, item_size=128)
    return ListChunk(list_type="list", chunks=[lhd3, ldat])
