"""Typed builders for the view-state skeleton of a new composition item.

After Effects writes ~180 chunks of viewer state into every comp item
(`LIST:dats`, `cdrp`, `comr`, eleven viewer pseudo-layers in `DLay` /
`SLay` / `CLay` / `SecL` lists, `Ewst` blocks, `CIFO`/`CIF2`/`CIF3`,
`Gide`) and hard-crashes opening a comp without them. The viewer layers
are built from `data/comp_skeleton_specs.py` (generated from AE 2026
ground truth by `scripts/dev/gen_comp_skeleton.py`); `$`-prefixed spec
strings are expressions over the comp parameters, evaluated here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..data.comp_skeleton_specs import COMP_VIEW_LAYER_SPECS
from .chunk import Chunk, ListChunk
from .composition_chunks import CdtaChunk, CsctChunk
from .item_chunks import IdpcChunk, IdtaChunk, IideChunk
from .layer_chunks import LdtaChunk
from .misc_chunks import ClassicPrdaChunk, PrinChunk
from .mutations import build_gide_list, build_ovg2
from .property_chunks import (
    CdatChunk,
    OtdaChunk,
    Tdb4Chunk,
    TdmnChunk,
    TdsbChunk,
    TdsnChunk,
    TdumChunk,
)
from .scalar_chunks import U1Chunk, U2Chunk, U4Chunk, Utf8Chunk

if TYPE_CHECKING:
    from typing import Any, Callable


def build_item_view_chunks() -> list[Chunk]:
    """Build the `fvdv` ... `fifl` view-data septet AE writes after every
    item's `LIST:Item` (and twice after each comp viewer layer)."""
    return [
        U4Chunk(chunk_type="fvdv", value=3),
        U1Chunk(chunk_type="fiop"),
        U4Chunk(chunk_type="ftts"),
        U1Chunk(chunk_type="foac"),
        U1Chunk(chunk_type="fiac"),
        U2Chunk(chunk_type="fipc"),
        U4Chunk(chunk_type="fifl"),
    ]


def build_layer_view_block() -> list[Chunk]:
    """Build the per-layer view block AE writes after each layer's LIST
    (an empty `Ewst` plus two view-data septets)."""
    return [
        ListChunk(list_type="Ewst", chunks=[]),
        *build_item_view_chunks(),
        *build_item_view_chunks(),
    ]


def _evaluate(value: Any, env: dict[str, float]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return eval(value[1:], {"__builtins__": {}}, dict(env))  # noqa: S307
    return value


def _build_tdbs(spec: dict[str, Any], env: dict[str, float]) -> ListChunk:
    tdb4 = Tdb4Chunk(**{k: _evaluate(v, env) for k, v in spec["tdb4"].items()})
    if tdb4._spatial_marker and not tdb4.color and not tdb4.no_value:
        # AE writes the comp's pixel aspect into spatial point tdb4s
        # (not orientation / color, despite their spatial marker).
        tdb4.pixel_aspect = env["PAR"]
    chunks: list[Chunk] = [
        TdsbChunk(**spec.get("tdsb", {})),
        TdsnChunk.new(spec["tdsn"]),
        tdb4,
    ]
    if "cdat" in spec:
        chunks.append(
            CdatChunk(values=[float(_evaluate(v, env)) for v in spec["cdat"]])
        )
    if "tdum" in spec:
        chunks.append(TdumChunk(chunk_type="tdum", values=list(spec["tdum"])))
    if "tduM" in spec:
        chunks.append(TdumChunk(chunk_type="tduM", values=list(spec["tduM"])))
    return ListChunk(list_type="tdbs", chunks=chunks)


def _build_extras(extras: list[tuple[str, str]]) -> list[Chunk]:
    out: list[Chunk] = []
    for kind, payload in extras:
        if kind == "OvG2":
            out.append(build_ovg2())
        else:
            out.append(Chunk(chunk_type=kind, data=bytes.fromhex(payload)))
    return out


def _build_tdgp(spec: dict[str, Any], env: dict[str, float]) -> ListChunk:
    chunks: list[Chunk] = [
        TdsbChunk(**spec.get("tdsb", {})),
        TdsnChunk.new(spec.get("tdsn", "")),
    ]
    for node in spec["children"]:
        kind, match_name, body = node[0], node[1], node[2]
        chunks.append(TdmnChunk(value=match_name))
        if len(node) > 3:
            chunks.extend(_build_extras(node[3]))
        if kind == "group":
            chunks.append(_build_tdgp(body, env))
        elif kind == "prop":
            chunks.append(_build_tdbs(body, env))
        elif kind == "orientation":
            otda_values = [float(_evaluate(v, env)) for v in body["otda"]]
            inner = {k: v for k, v in body.items() if k != "otda"}
            otky = ListChunk(list_type="otky", chunks=[OtdaChunk(values=otda_values)])
            chunks.append(
                ListChunk(
                    list_type="otst",
                    chunks=[_build_tdbs(inner, env), otky],
                )
            )
        else:
            raise ValueError(f"unknown spec node kind {kind!r}")
    chunks.append(TdmnChunk(value="ADBE Group End"))
    return ListChunk(list_type="tdgp", chunks=chunks)


def _build_view_layer(
    spec: dict[str, Any],
    env: dict[str, float],
    layer_id: int,
) -> ListChunk:
    ldta_kwargs = {k: _evaluate(v, env) for k, v in spec["ldta"].items()}
    ldta = LdtaChunk(layer_id=layer_id, **ldta_kwargs)
    gide, _lhd3, _inner = build_gide_list()
    return ListChunk(
        list_type=spec["list_type"],
        chunks=[
            ldta,
            Utf8Chunk(value=spec["name"]),
            _build_tdgp(spec["tdgp"], env),
            gide,
        ],
    )


def build_cps2(name: str) -> tuple[ListChunk, Utf8Chunk]:
    """Build a `LIST:CpS2` template-name block (`CsCt` + name + locale).

    Returns `(cps2, name_utf8)` so callers can keep a reference to the
    name chunk for later edits.
    """
    name_utf8 = Utf8Chunk(value=name)
    cps2 = ListChunk(
        list_type="CpS2",
        chunks=[CsctChunk(), name_utf8, Utf8Chunk(value="en_US")],
    )
    return cps2, name_utf8


def _build_cif(list_type: str) -> ListChunk:
    cps2, _name_utf8 = build_cps2("Untitled")
    return ListChunk(
        list_type=list_type,
        chunks=[
            cps2,
            ListChunk(
                list_type="CapS",
                chunks=[
                    CsctChunk(),
                    U4Chunk(chunk_type="CapL"),
                    Utf8Chunk(value="Untitled"),
                ],
            ),
            Chunk(chunk_type="CPTm", data=b"\x00\x00\x00\x00\x00\x00\x00\x01"),
            Chunk(chunk_type="CROI", data=b"\x00" * 8),
            U4Chunk(chunk_type="CcCt"),
        ],
    )


def _duration_units(duration: float, frame_rate: float, timebase: int) -> int:
    """Duration in timebase units, rounded to whole frames like AE."""
    frames = round(duration * frame_rate)
    units_per_frame = round(timebase / frame_rate)
    return frames * units_per_frame


def _build_cdta(
    width: int,
    height: int,
    pixel_aspect: float,
    duration: float,
    frame_rate: float,
) -> CdtaChunk:
    """Build a `cdta` matching AE's new-comp field encoding (600-based
    cursor / work-area divisors, duration in timebase units)."""
    cdta = CdtaChunk(width=width, height=height)
    cdta.frame_rate = frame_rate
    cdta._update_timebase(frame_rate)
    timebase = cdta.internal_timebase
    cdta.time_dividend = 0
    cdta.time_divisor = 600
    cdta.work_area_start_dividend = 0
    cdta.work_area_start_divisor = 600
    cdta.work_area_end_divisor = 600
    cdta.duration_dividend = _duration_units(duration, frame_rate, timebase)
    cdta.duration_divisor = timebase
    cdta.pixel_aspect = pixel_aspect
    cdta.display_start_time_dividend = 0
    return cdta


def build_new_comp_item(
    *,
    item_id: int,
    name: str,
    width: int,
    height: int,
    pixel_aspect: float,
    duration: float,
    frame_rate: float,
    allocate_layer_id: Callable[[], int],
    label: int = 15,
) -> tuple[ListChunk, IdtaChunk, Utf8Chunk, ListChunk]:
    """Build the complete `LIST:Item` chunk tree AE 2026 writes for
    `app.project.items.addComp()`.

    `label` is the "Comp Label Index 2" label preference (AE factory
    value 15). Returns `(item_list, idta, name_utf8, gide)`.
    """
    iide = IideChunk(value=item_id)
    idpc = IdpcChunk()
    idta = IdtaChunk(item_type=4, item_id=item_id, label=label, flags_17=0x20)
    name_utf8 = Utf8Chunk(value=name)
    cdta = _build_cdta(width, height, pixel_aspect, duration, frame_rate)
    prin = ListChunk(list_type="PRin", chunks=[PrinChunk(), ClassicPrdaChunk()])

    env: dict[str, float] = {
        "W2": width / 2.0,
        "H2": height / 2.0,
        "ZV": width * pixel_aspect / 0.72,
        "TB": cdta.internal_timebase,
        "DUR_UNITS": _duration_units(duration, frame_rate, cdta.internal_timebase),
        "PAR": pixel_aspect,
    }

    children: list[Chunk] = [
        iide,
        idpc,
        idta,
        name_utf8,
        ListChunk(
            list_type="dats",
            chunks=[Chunk(chunk_type="numS", data=b"\x00" * 4)],
        ),
        cdta,
        U1Chunk(chunk_type="cdrp"),
        Chunk(chunk_type="comr", data=b"\x00"),
        prin,
    ]
    for spec in COMP_VIEW_LAYER_SPECS:
        children.append(_build_view_layer(spec, env, allocate_layer_id()))
        children.extend(build_layer_view_block())
    children.extend(_build_cif(t) for t in ("CIFO", "CIF2", "CIF3"))
    gide, _lhd3, _inner = build_gide_list()
    children.append(gide)

    item_list = ListChunk(list_type="Item", chunks=children)
    return item_list, idta, name_utf8, gide
