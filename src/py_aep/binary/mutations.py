"""Chunk tree mutation helpers for the binary I/O layer."""

from __future__ import annotations

import base64
import struct
import uuid
from io import BytesIO
from typing import TYPE_CHECKING, cast

from ..data.dropdown_control import DROPDOWN_CONTROL
from .chunk import Chunk, ContainerChunk, ListChunk, read_chunks, write_chunk
from .composition_chunks import CsctChunk
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
    EmpdChunk,
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
from .property_chunks import (
    TDSN_SENTINEL,
    CdatChunk,
    Tdb4Chunk,
    TdmnChunk,
    TdsbChunk,
    TdsnChunk,
)
from .render_chunks import RoutItem
from .scalar_chunks import F8Chunk, S4Chunk, U4Chunk, Utf8Chunk

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


def rewrite_owner_tdpi(chunk: Chunk, layer_id: int) -> None:
    """Point effect internal-param (`-0000`) tdpi chunks at `layer_id`.

    Every effect's hidden `-0000` parameter carries the owning layer's
    id in its `tdpi`; AE rewrites these when a layer is duplicated.
    Layer-reference tdpi values (regular value params) keep pointing at
    the referenced layer and are left untouched.
    """
    if not isinstance(chunk, ListChunk):
        return
    chunks = chunk.chunks
    for i, c in enumerate(chunks):
        if (
            c.chunk_type == "tdmn"
            and cast("TdmnChunk", c).value.endswith("-0000")
            and i + 1 < len(chunks)
            and isinstance(chunks[i + 1], ListChunk)
        ):
            for inner in cast("ListChunk", chunks[i + 1]).chunks:
                if inner.chunk_type == "tdpi":
                    cast("S4Chunk", inner).value = layer_id
        elif isinstance(c, ListChunk):
            rewrite_owner_tdpi(c, layer_id)


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


# AE's canonical LIST:LRdr child order: header, output-frames blob,
# render-settings list, item list, settings info.
LRDR_CHILD_ORDER = ("Rhed", "Rout", "list", "LItm", "LSIf")


def build_rq_settings_list(
    *, synthetic: bool = False
) -> tuple[ListChunk, Lhd3Chunk, LdatChunk]:
    """Build the render-queue settings `LIST:list` skeleton (lhd3 + ldat).

    The lhd3 is sized for the 2246-byte render-settings items AE writes; the
    ldat starts synthetic so `write_aep()` skips it until the queue's first
    `add()`. Shared by `RenderQueue._new` and `parse_render_queue`'s
    degenerate-file rebuild so the two skeletons cannot drift.

    Returns:
        `(inner, lhd3, ldat)` - the `LIST:list`, its header, and the data
        chunk.
    """
    lhd3 = Lhd3Chunk(item_size=2246, item_type_raw=1, counter_b=1)
    ldat = LdatChunk(synthetic=True)
    inner = ListChunk(list_type="list", synthetic=synthetic, chunks=[lhd3, ldat])
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
    omtn = Chunk(chunk_type="omtn")
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
        U4Chunk(chunk_type="blsi"),
    ]


def _build_cctl(
    name: str,
    uuid_str: str,
    controller_type: int,
    value_chunks: list[Chunk],
    comp_id: int,
    layer_id: int,
    path_json: str,
) -> tuple[ListChunk, Utf8Chunk, U4Chunk]:
    """Assemble a `LIST:CCtl` Essential Graphics controller.

    Layout per the AE 2025 `essential_graphics` fixtures: localized name
    (CpS2), Premiere caption (CapS), uuid, CTyp, the type-specific value
    chunks, then the controlled-property reference (CprC + CPrp holding
    the source comp item id, the source layer id and the root-to-leaf
    path JSON).

    Returns `(cctl, name_utf8, ctyp)` so callers can bind the editable
    chunks to the controller model.
    """
    name_utf8 = Utf8Chunk(value=name)
    cps2 = ListChunk(
        list_type="CpS2",
        chunks=[CsctChunk(), name_utf8, Utf8Chunk(value="en_US")],
    )
    caps = ListChunk(
        list_type="CapS",
        chunks=[CsctChunk(), U4Chunk(chunk_type="CapL"), Utf8Chunk(value=name)],
    )
    ctyp = U4Chunk(chunk_type="CTyp", value=controller_type)
    cprp = ListChunk(
        list_type="CPrp",
        chunks=[
            U4Chunk(chunk_type="CCId", value=comp_id),
            U4Chunk(chunk_type="CLId", value=layer_id),
            Utf8Chunk(value=path_json),
        ],
    )
    cctl = ListChunk(
        list_type="CCtl",
        chunks=[
            cps2,
            caps,
            Utf8Chunk(value=uuid_str),
            ctyp,
            *value_chunks,
            U4Chunk(chunk_type="CprC", value=1),
            cprp,
        ],
    )
    return cctl, name_utf8, ctyp


def build_slider_cctl(
    name: str,
    uuid_str: str,
    value: float,
    slider_min: float,
    slider_max: float,
    comp_id: int,
    layer_id: int,
    path_json: str,
) -> tuple[ListChunk, Utf8Chunk, U4Chunk]:
    """Build a Slider (CTyp 2) controller. `CVal`/`CDef` both take the
    property's value at add time, matching AE."""
    value_chunks: list[Chunk] = [
        Chunk(chunk_type="CVal", data=struct.pack(">d", value)),
        Chunk(chunk_type="CDef", data=struct.pack(">d", value)),
        F8Chunk(chunk_type="Smin", value=slider_min),
        F8Chunk(chunk_type="Smax", value=slider_max),
    ]
    return _build_cctl(name, uuid_str, 2, value_chunks, comp_id, layer_id, path_json)


def build_checkbox_cctl(
    name: str,
    uuid_str: str,
    value: bool,
    comp_id: int,
    layer_id: int,
    path_json: str,
) -> tuple[ListChunk, Utf8Chunk, U4Chunk]:
    """Build a Checkbox (CTyp 1) controller."""
    byte = b"\x01" if value else b"\x00"
    value_chunks: list[Chunk] = [
        Chunk(chunk_type="CVal", data=byte),
        Chunk(chunk_type="CDef", data=byte),
    ]
    return _build_cctl(name, uuid_str, 1, value_chunks, comp_id, layer_id, path_json)


def build_color_cctl(
    name: str,
    uuid_str: str,
    rgba: list[float],
    comp_id: int,
    layer_id: int,
    path_json: str,
) -> tuple[ListChunk, Utf8Chunk, U4Chunk]:
    """Build a Color (CTyp 4) controller. `rgba` is 4 floats in 0-1."""
    data = struct.pack(">4f", *rgba)
    value_chunks: list[Chunk] = [
        Chunk(chunk_type="CVal", data=data),
        Chunk(chunk_type="CDef", data=data),
    ]
    return _build_cctl(name, uuid_str, 4, value_chunks, comp_id, layer_id, path_json)


def build_text_cctl(
    name: str,
    uuid_str: str,
    text: str,
    font_caps_json: str,
    comp_id: int,
    layer_id: int,
    path_json: str,
) -> tuple[ListChunk, Utf8Chunk, U4Chunk]:
    """Build a Source Text (CTyp 6) controller.

    The two `CFEd` / `CSEd` byte flags mirror the `capProp*Edit` booleans
    of `font_caps_json` (all disabled); the second JSON is the
    no-alternate-source reference AE writes for a fresh controller.
    """
    value_chunks: list[Chunk] = [
        Utf8Chunk(value=text),
        Utf8Chunk(value=text),
        Chunk(chunk_type="CFEd", data=b"\x00"),
        Chunk(chunk_type="CSEd", data=b"\x00"),
        Chunk(chunk_type="CFEd", data=b"\x00"),
        Utf8Chunk(value=font_caps_json),
        Utf8Chunk(value='{"compId":-1,"isEnabled":false,"layerId":-1}'),
        Chunk(chunk_type="CTov", data=b"\x07\x00\x00\x00"),
    ]
    return _build_cctl(name, uuid_str, 6, value_chunks, comp_id, layer_id, path_json)


_NULL_UUID = "00000000-0000-0000-0000-000000000000"


def build_media_cctl(
    name: str,
    uuid_str: str,
    width: int,
    height: int,
    in_units: int,
    out_units: int,
    timebase: int,
    thumbnail_name: str,
    comp_id: int,
    layer_id: int,
    path_json: str,
) -> tuple[ListChunk, Utf8Chunk, U4Chunk]:
    """Build a Media Replacement (CTyp 14) controller.

    Decoded from the AE 2025 `media_replacement.aep` fixture: the two null
    uuids are the not-yet-assigned alternate source, `CSMw`/`CSMh` the
    source item's pixel dimensions, `CSMs`/`CSMe` the layer's in/out points
    in the comp's internal timebase units (verified: out 30.03003s x 23976
    = 720000), `CSMt` that timebase, and the trailing Utf8 a thumbnail
    cache file name AE regenerates on open. `CSMp` (8 bytes), `CCEx` and
    `CSMd` are written as the constants AE emits for a fresh controller;
    their semantics are undecoded.
    """
    value_chunks: list[Chunk] = [
        Utf8Chunk(value=_NULL_UUID),
        Utf8Chunk(value=_NULL_UUID),
        U4Chunk(chunk_type="CSMw", value=width),
        U4Chunk(chunk_type="CSMh", value=height),
        U4Chunk(chunk_type="CSMs", value=in_units),
        U4Chunk(chunk_type="CSMe", value=out_units),
        U4Chunk(chunk_type="CSMt", value=timebase),
        Chunk(chunk_type="CSMp", data=b"\x00\x00\x00\x00\x00\x00\x00\x01"),
        Chunk(chunk_type="CCEx", data=b"\x01"),
        Utf8Chunk(value=thumbnail_name),
        U4Chunk(chunk_type="CSMd", value=2),
    ]
    return _build_cctl(name, uuid_str, 14, value_chunks, comp_id, layer_id, path_json)


def build_pin_list(
    sspc: Chunk,
    opti: Chunk,
    *,
    is_solid: bool = False,
    path_chunks: list[Chunk] | None = None,
    embedded_profile_name: str | None = None,
    layer_name: str = "",
) -> ListChunk:
    """Build a complete `LIST:Pin` with required companion chunks.

    `path_chunks` (the `LIST:Als2` path and, for sequences, the
    prefix/extension `Utf8` chunks) are inserted between the leading
    empty `Utf8` and `opti`. File sources pass them; solid/placeholder
    sources (no file path) pass nothing.

    `layer_name` fills the `Utf8` slot after `sspc`: AE stores the
    referenced layer's name there when the footage is a single layer of a
    layered file (chosen-layer or comp import), and leaves it empty
    otherwise.

    When `embedded_profile_name` is given, the source's embedded color
    profile is recorded in `LIST:CLRS` as an `empd` flag plus a `Utf8`
    name (matching AE); pass `None` for sources with no embedded profile.
    """
    clrs_chunks: list[Chunk] = [EpidChunk(), ApidChunk()]
    if embedded_profile_name is not None:
        clrs_chunks.append(EmpdChunk())
        clrs_chunks.append(Utf8Chunk(value=embedded_profile_name))
    clrs_chunks.extend(
        [
            LinlChunk(),
            EmbpChunk(),
            IpwsChunk(),
        ]
    )
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
            Utf8Chunk(value=layer_name),
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


def build_default_path_shape(time_base: int) -> tuple[TdmnChunk, ListChunk]:
    """Build the `(tdmn, LIST:om-s)` pair for a new Path element's
    `ADBE Vector Shape` property.

    AE writes an empty bezier path (no vertices) with a unit bounding
    box for `addProperty("ADBE Vector Shape - Group")`; the chunk
    layout mirrors a static mask path (`tdbs` with empty `cdat` plus
    the `omks > shap` value container).

    Args:
        time_base: The comp's internal timebase (`cdta.internal_timebase`).
    """
    tdb4 = Tdb4Chunk(
        spatial_static_flags=7,
        pad2a=1,
        value_hint_type=2,
        cvot_flags=7,
        time_base=time_base,
        no_value_flags=1,
        type_flags=8,
        spatial_marker=True,
    )
    tdbs = ListChunk(
        list_type="tdbs",
        chunks=[
            TdsbChunk(),
            TdsnChunk.new(TDSN_SENTINEL),
            tdb4,
            CdatChunk(pad=b"\x00\x00\x00\x00"),
        ],
    )
    shap = ListChunk(
        list_type="shap",
        chunks=[
            ShphChunk(flags=9, bottom_right_x=1.0, bottom_right_y=1.0),
            ListChunk(
                list_type="list",
                chunks=[Lhd3Chunk(item_size=8, item_type_raw=4, counter_b=4)],
            ),
            Chunk(chunk_type="omtn"),
        ],
    )
    oms = ListChunk(
        list_type="om-s",
        chunks=[tdbs, ListChunk(list_type="omks", chunks=[shap])],
    )
    return TdmnChunk(value="ADBE Vector Shape"), oms


# AE-exact `ADBE Mask Shape` om-s written when a mask's rotoBezier is
# enabled: the implicit default full-frame rectangle materialized as an
# explicit roto-bezier path. Geometry is normalized [0, 1] (so it is
# comp/layer-size independent); only the embedded tdb4 time_base is
# comp-specific and is patched per call. Captured from AE 2026
# (rotoBezier=true on a freshly added mask); py_aep round-trips it
# byte-identically.
_DEFAULT_ROTO_MASK_SHAPE_OMS = (
    "4c495354000001c26f6d2d734c495354000000b67464627374647362000000040100000174"
    "64736e0000000e55746638000000062d5f305f2f2d746462340000007cdb99000100070001"
    "00020007000060003f1a36e2eb1c432d3ff00000000000003ff00000000000003ff0000000"
    "0000003ff00000000000000001000800000000000000000000000000000000000000010000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000006364617400000004000000004c495354000000f86f6d6b734c495354000000ec"
    "736861707368706800000018b3de020100000000000000003f8000003f800000010000004c"
    "495354000000a86c6973746c6864330000003400d00bee000000000000000c000000040000"
    "000800000004000000010000001000000000000000000000000000000000000000006c6461"
    "740000006000000000000000000000000000000000000000003f800000000000003f800000"
    "000000003f8000003f8000003f8000003f8000003f8000003f8000003f8000003f80000000"
    "0000003f800000000000003f8000000000000000000000000000006f6d746e000000103f80"
    "00003f8000003f8000003f800000"
)


def build_default_mask_shape(
    time_base: int, *, roto_bezier: bool = False
) -> tuple[TdmnChunk, ListChunk]:
    """Build the `(tdmn, LIST:om-s)` pair AE writes for `ADBE Mask Shape`
    when a path-less mask first materializes one.

    A freshly added mask has no Mask Shape subtree (AE treats it as the
    implicit default full-frame rectangle); enabling rotoBezier or setting
    a path materializes that default as an explicit path. The geometry is
    normalized, so only the comp's internal timebase varies.

    Args:
        time_base: The comp's internal timebase (`cdta.internal_timebase`).
        roto_bezier: Whether the mask-shape `tdsb` roto flag is set. The
            baked template originates from an enable-rotoBezier capture
            (flag on); a plain bezier path write clears it, matching AE
            (psd_vector_mask fixtures).
    """
    raw = bytes.fromhex(_DEFAULT_ROTO_MASK_SHAPE_OMS)
    oms = cast("ListChunk", read_chunks(BytesIO(raw), len(raw))[0])
    tdbs = cast("ListChunk", oms.chunks[0])
    for c in tdbs.chunks:
        if isinstance(c, Tdb4Chunk):
            c._time_base = time_base
        elif isinstance(c, TdsbChunk):
            c.roto_bezier = roto_bezier
    return TdmnChunk(value="ADBE Mask Shape"), oms


def build_vector_element(
    match_name: str,
    name: str,
    *,
    subgroups: tuple[tuple[str, int, int], ...] = (),
    path_time_base: int | None = None,
) -> tuple[TdmnChunk, ListChunk]:
    """Build the `(tdmn, LIST:tdgp)` pair AE writes for a freshly added
    shape element.

    A new element is a named, otherwise empty group: child properties
    stay at AE-side defaults and are synthesized on parse rather than
    written to binary. `subgroups` lists the mandatory empty subgroups
    some elements carry as `(match_name, tdsb lock flags)` pairs.

    Args:
        match_name: The element match name (e.g. `ADBE Vector Shape - Rect`).
        name: The instance name AE bakes into the tdsn (`"Base N"`).
        subgroups: Mandatory empty subgroups to write inside the element,
            as `(match_name, tdsb lock flags, tdsb enable flags)` triples.
        path_time_base: For the Path element (`ADBE Vector Shape -
            Group`), the comp's internal timebase; adds the default
            empty `ADBE Vector Shape` bezier property.
    """
    chunks: list[Chunk] = [TdsbChunk(), TdsnChunk.new(name)]
    if path_time_base is not None:
        chunks.extend(build_default_path_shape(path_time_base))
    for sub_match_name, lock_flags, enable_flags in subgroups:
        chunks.append(TdmnChunk(value=sub_match_name))
        chunks.append(
            ListChunk(
                list_type="tdgp",
                chunks=[
                    TdsbChunk(lock_flags=lock_flags, enable_flags=enable_flags),
                    TdsnChunk.new(TDSN_SENTINEL),
                    TdmnChunk(value="ADBE Group End"),
                ],
            )
        )
    chunks.append(TdmnChunk(value="ADBE Group End"))
    return TdmnChunk(value=match_name), ListChunk(list_type="tdgp", chunks=chunks)


def build_text_selector(
    match_name: str,
    name: str,
    *,
    has_advanced: bool,
) -> tuple[TdmnChunk, ListChunk]:
    """Build the `(tdmn, LIST:tdgp)` pair AE writes for a freshly added
    text selector.

    A new selector is a named group `[tdsb, tdsn("X Selector N"),
    group end]` whose value children are synthesized on parse. The
    Range Selector additionally carries an empty `ADBE Text Range
    Advanced` subgroup in binary (its children are synthesized too);
    Wiggly and Expression selectors do not.

    Args:
        match_name: The selector match name (e.g. `ADBE Text Selector`).
        name: The instance name AE bakes into the tdsn (`"Base N"`).
        has_advanced: Whether to write the empty Advanced subgroup
            (Range Selector only).
    """
    chunks: list[Chunk] = [TdsbChunk(), TdsnChunk.new(name)]
    if has_advanced:
        chunks.append(TdmnChunk(value="ADBE Text Range Advanced"))
        chunks.append(
            ListChunk(
                list_type="tdgp",
                chunks=[
                    TdsbChunk(),
                    TdsnChunk.new(TDSN_SENTINEL),
                    TdmnChunk(value="ADBE Group End"),
                ],
            )
        )
    chunks.append(TdmnChunk(value="ADBE Group End"))
    return TdmnChunk(value=match_name), ListChunk(list_type="tdgp", chunks=chunks)


def build_text_animator(name: str) -> tuple[TdmnChunk, ListChunk]:
    """Build the `(tdmn, LIST:tdgp)` pair AE writes for a freshly added
    text animator.

    A new animator is `[tdsb, tdsn("Animator N"), Animator Properties
    (empty), group end]`. The empty `ADBE Text Animator Properties`
    subgroup is in binary; its 103-property pool and the (also empty)
    `ADBE Text Selectors` group are synthesized on parse.

    Args:
        name: The instance name AE bakes into the tdsn (`"Animator N"`).
    """
    properties_tdgp = ListChunk(
        list_type="tdgp",
        chunks=[
            TdsbChunk(),
            TdsnChunk.new(TDSN_SENTINEL),
            TdmnChunk(value="ADBE Group End"),
        ],
    )
    tdgp = ListChunk(
        list_type="tdgp",
        chunks=[
            TdsbChunk(),
            TdsnChunk.new(name),
            TdmnChunk(value="ADBE Text Animator Properties"),
            properties_tdgp,
            TdmnChunk(value="ADBE Group End"),
        ],
    )
    return TdmnChunk(value="ADBE Text Animator"), tdgp


def build_expression_control(
    match_name: str,
    display_name: str,
    part_bytes: bytes,
    *,
    tdsn_name: str,
    time_base: int,
    layer_id: int,
    layer_param_name: str | None = None,
) -> tuple[TdmnChunk, ListChunk]:
    """Build the `(tdmn, LIST:sspc)` pair AE writes for a freshly added
    expression-control effect.

    The parameter definitions (`LIST:parT`) are baked plugin data from
    `data/effect_controls.py`. The instance tdgp carries the hidden
    `-0000` internal parameter (a 1-D scalar whose `tdpi` points at the
    containing layer) and the named Compositing Options group; value
    parameters stay at their defaults and are omitted from binary,
    except the Layer Control's, which AE always writes.

    Args:
        match_name: The effect match name (e.g. `ADBE Slider Control`).
        display_name: The default effect name, written to `fnam`.
        part_bytes: This control's serialized `LIST:parT` chunk.
        tdsn_name: The instance name for the effect tdsn - the unnamed
            sentinel for a first instance, `"Name N"` for later ones.
        time_base: The comp's internal timebase (`cdta.internal_timebase`).
        layer_id: Id of the layer the effect is applied to.
        layer_param_name: When set, also write the `-0001` value
            parameter to the tdgp, with this tdsn display name.
    """
    part = read_chunks(BytesIO(part_bytes), len(part_bytes))[0]

    def param_tdbs(name: str, enable_flags: int) -> ListChunk:
        tdb4 = Tdb4Chunk(
            value_hint_type=1,
            time_base=time_base,
            type_flags=4,
            property_category=4,
            pad7a=128,
        )
        return ListChunk(
            list_type="tdbs",
            chunks=[
                TdsbChunk(enable_flags=enable_flags),
                TdsnChunk.new(name),
                tdb4,
                CdatChunk(values=[0.0] * 5),
                S4Chunk(chunk_type="tdpi", value=layer_id),
                S4Chunk(chunk_type="tdps"),
            ],
        )

    tdgp_chunks: list[Chunk] = [
        TdsbChunk(),
        TdsnChunk.new(tdsn_name),
        TdmnChunk(value=match_name + "-0000"),
        param_tdbs("", 3),
    ]
    if layer_param_name is not None:
        tdgp_chunks += [
            TdmnChunk(value=match_name + "-0001"),
            param_tdbs(layer_param_name, 1),
        ]
    tdgp_chunks += [
        TdmnChunk(value="ADBE Effect Built In Params"),
        ListChunk(
            list_type="tdgp",
            chunks=[
                TdsbChunk(),
                TdsnChunk.new("Compositing Options"),
                TdmnChunk(value="ADBE Group End"),
            ],
        ),
        TdmnChunk(value="ADBE Group End"),
    ]
    # AE writes an all-zero pgui GUID for every expression control
    # (verified on Slider/Color/Checkbox/Point/Layer + dropdown, AE 2026);
    # PguiChunk() defaults to 16 zero bytes.
    pgui = PguiChunk()
    sspc = ListChunk(
        list_type="sspc",
        chunks=[
            ContainerChunk(chunk_type="fnam", chunks=[Utf8Chunk(value=display_name)]),
            part,
            ListChunk(list_type="tdgp", chunks=tdgp_chunks),
            pgui,
        ],
    )
    return TdmnChunk(value=match_name), sspc


def build_dropdown_control(
    *,
    tdsn_name: str,
    time_base: int,
    layer_id: int,
) -> tuple[TdmnChunk, ListChunk]:
    """Build a Dropdown Menu Control - a pseudo-effect whose match name
    is generated fresh per instance.

    The match name is `"Pseudo/@@" + base64(uuid4 bytes)` (standard
    alphabet, padding stripped), always 31 chars - the same length as
    the captured placeholder in `DROPDOWN_CONTROL["part"]`, so a
    byte-level substitution into the baked `parT` preserves chunk
    sizes. The tdgp is the same as a value-less control (only the
    `-0000` internal param); the Menu enum + items live in the `parT`.

    Args:
        tdsn_name: The instance name for the effect tdsn.
        time_base: The comp's internal timebase.
        layer_id: Id of the layer the effect is applied to.
    """
    match_name = "Pseudo/@@" + base64.b64encode(uuid.uuid4().bytes).decode(
        "ascii"
    ).rstrip("=")
    part_bytes = bytes.fromhex(DROPDOWN_CONTROL["part"]).replace(
        DROPDOWN_CONTROL["placeholder"].encode("ascii"),
        match_name.encode("ascii"),
    )
    return build_expression_control(
        match_name,
        DROPDOWN_CONTROL["name"],
        part_bytes,
        tdsn_name=tdsn_name,
        time_base=time_base,
        layer_id=layer_id,
    )
