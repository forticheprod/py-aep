"""CompItem.duplicate() validated against After Effects' own duplicate.

`samples/models/composition/duplicate.aep` carries the ground truth: comp
`DupSrc` (parenting, track matte, expression pick-whip, a Set Matte
layer-param effect, an Essential Graphics slider controller, and a precomp
layer `Inner` with an Essential Properties override) together with AE
2026's own `comp.duplicate()` result `DupSrc 2` of that same comp. py's
duplicate of `DupSrc` must be reference-graph-isomorphic to AE's (ids are
free variables) and byte-identical after id/uuid normalization, up to
three AE-confirmed non-necessary families that AE's own resave also
normalizes: `cdta.time_divisor` (re-derived), viewer-pseudo-layer
`tdb4._expr_flags` (zeroed), and the layer-level `LIST:parT` effect param
defs (stripped as redundant with project-level `EfdG`; py keeps the clone
since it is necessary for uninstalled effects).

Regenerate the fixture with `scripts/jsx/generate_duplicate_sample.jsx`.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, cast

from helpers import parse_project_fresh

from py_aep.binary.chunk import ListChunk
from py_aep.binary.utils import (
    filter_by_list_type,
    filter_by_type,
    find_by_list_type,
    recursive_find,
)

if TYPE_CHECKING:
    from typing import Any

    from py_aep.binary.chunk import Chunk
    from py_aep.binary.layer_chunks import LdtaChunk
    from py_aep.binary.scalar_chunks import S4Chunk, Utf8Chunk
    from py_aep.models.items.composition import CompItem
    from py_aep.models.project import Project

SAMPLE = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "composition"
    / "duplicate.aep"
)
EG_SAMPLE = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "essential_graphics"
    / "media_replacement.aep"
)
AE2018_SAMPLE = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "versions"
    / "ae2018"
    / "complete.aep"
)


def _comp(project: Project, name: str) -> CompItem:
    return next(c for c in project.compositions if c.name == name)


def _ldta_in_order(comp: CompItem) -> list[LdtaChunk]:
    return [
        cast("LdtaChunk", c)
        for c in recursive_find(comp._item_list.chunks, chunk_type="ldta")
    ]


def _all_ids(project: Project) -> list[int]:
    return [
        ld.layer_id for comp in project.compositions for ld in _ldta_in_order(comp)
    ] + list(project.items.keys())


def _graph(comp: CompItem) -> dict[str, Any]:
    """Reference graph with layer ids as free variables (ldta positions)."""
    pos = {ld.layer_id: i for i, ld in enumerate(_ldta_in_order(comp))}
    layers = []
    for layer in comp.layers:
        ld = layer._ldta
        matte = ld.matte_layer_id
        layers.append(
            {
                "name": layer.name,
                "parent": pos.get(ld.parent_id) if ld.parent_id else None,
                "matte": pos.get(matte) if matte else None,
                "source": ld.source_id,
                "override_uuids": list(layer.essential_property_uuids),
            }
        )
    tdpi = [
        pos.get(cast("S4Chunk", c).value, ("ext", cast("S4Chunk", c).value))
        for c in recursive_find(comp._item_list.chunks, chunk_type="tdpi")
    ]
    eg = [
        {
            "name": ctrl.name,
            "comp_is_self": ctrl.source_comp_id == comp.id,
            "layer_pos": pos.get(ctrl.source_layer_id or -1),
        }
        for ctrl in comp.motion_graphics_controllers
    ]
    return {"layers": layers, "tdpi": tdpi, "eg": eg}


def _cctls(comp: CompItem) -> list[ListChunk]:
    """Every LIST:CCtl across the CIFO/CIF2/CIF3 containers, in order."""
    out: list[ListChunk] = []
    for cif in comp._item_list.chunks:
        if isinstance(cif, ListChunk) and cif.list_type in ("CIFO", "CIF2", "CIF3"):
            out.extend(filter_by_list_type(chunks=cif.chunks, list_type="CCtl"))
    return out


def _chunk_bytes(chunk: Chunk) -> bytes:
    buf = io.BytesIO()
    chunk.write(buf)
    return buf.getvalue()


class TestDuplicateAgainstAE:
    def test_reference_graph_isomorphic_to_ae(self) -> None:
        project = parse_project_fresh(SAMPLE)
        py_dup = _comp(project, "DupSrc").duplicate()
        ae_dup = _comp(project, "DupSrc 2")
        assert _graph(py_dup) == _graph(ae_dup)

    def test_id_uniqueness_and_counter_invariant(self) -> None:
        project = parse_project_fresh(SAMPLE)
        _comp(project, "DupSrc").duplicate()
        ids = _all_ids(project)
        assert len(ids) == len(set(ids))
        # AE trusts head.next_item_id on open without rescanning (probed in
        # AE 2026): a counter at or below a live id makes AE mint duplicate
        # ids, so the invariant is necessary.
        assert project._head.next_item_id > max(ids)

    def test_name_and_placement(self) -> None:
        project = parse_project_fresh(SAMPLE)
        src = _comp(project, "DupSrc")
        dup = src.duplicate()
        # AE numbering: "DupSrc 2" is taken by AE's own duplicate.
        assert dup.name == "DupSrc 3"
        folder_items = src.parent_folder.items
        assert folder_items.index(dup) == folder_items.index(src) + 1
        assert project.items[dup.id] is dup

    def test_eg_controller_identity(self) -> None:
        project = parse_project_fresh(SAMPLE)
        src = _comp(project, "DupSrc")
        dup = src.duplicate()
        src_uuids = {c.uuid for c in src.motion_graphics_controllers}
        dup_ctrls = dup.motion_graphics_controllers
        assert len(dup_ctrls) == len(src.motion_graphics_controllers)
        assert not ({c.uuid for c in dup_ctrls} & src_uuids)
        # The three CIF containers must carry the SAME fresh uuid per
        # controller (AE keeps them in sync; matched by old uuid).
        uuids_per_container = [
            cast(
                "Utf8Chunk", filter_by_type(chunks=c.chunks, chunk_type="Utf8")[0]
            ).value
            for c in _cctls(dup)
        ]
        assert len(set(uuids_per_container)) == len(dup_ctrls)
        # CCId retargeted at the duplicate; CVal/CDef zeroed like AE (the
        # cached controller value is re-derived by AE at runtime).
        for cctl in _cctls(dup):
            cprp = find_by_list_type(chunks=cctl.chunks, list_type="CPrp")
            ccid = next(c for c in cprp.chunks if c.chunk_type == "CCId")
            assert cast("Any", ccid).value == dup.id
            for chunk in cctl.chunks:
                if chunk.chunk_type in ("CVal", "CDef"):
                    assert chunk.data == b"\x00" * len(chunk.data)

    def test_sources_and_overrides_shared(self) -> None:
        project = parse_project_fresh(SAMPLE)
        src = _comp(project, "DupSrc")
        dup = src.duplicate()
        # Layer sources (solid footage, the Inner precomp) are shared.
        assert [la._ldta.source_id for la in dup.layers] == [
            la._ldta.source_id for la in src.layers
        ]
        # Layer-side Essential Properties override uuids reference the
        # SOURCE comp's controllers and must stay verbatim.
        assert [la.essential_property_uuids for la in dup.layers] == [
            la.essential_property_uuids for la in src.layers
        ]
        # used_in gains the duplicate on every shared source.
        project._ensure_used_in_linked()
        inner = _comp(project, "Inner")
        dup2 = src.duplicate()
        assert dup2 in inner._used_in

    def test_normalized_byte_parity_with_ae(self) -> None:
        """After id/uuid/name normalization plus the three documented
        AE-normalization families, every direct child chunk of the item
        block is byte-identical to AE's own duplicate."""
        project = parse_project_fresh(SAMPLE)
        src = _comp(project, "DupSrc")
        ae_dup = _comp(project, "DupSrc 2")
        py_dup = src.duplicate()

        py_ldta = _ldta_in_order(py_dup)
        ae_ldta = _ldta_in_order(ae_dup)
        assert len(py_ldta) == len(ae_ldta)
        # Both duplicates are clones of the same original, so ldta chunk
        # order is the exact pairing between their id spaces.
        id_map = {p.layer_id: a.layer_id for p, a in zip(py_ldta, ae_ldta)}
        id_map[py_dup.id] = ae_dup.id

        for ld in py_ldta:
            ld.layer_id = id_map[ld.layer_id]
            if ld.parent_id in id_map:
                ld.parent_id = id_map[ld.parent_id]
            matte = ld.matte_layer_id
            if matte is not None and matte in id_map:
                ld.matte_layer_id = id_map[matte]
        for c in recursive_find(py_dup._item_list.chunks, chunk_type="tdpi"):
            tdpi = cast("S4Chunk", c)
            if tdpi.value in id_map:
                tdpi.value = id_map[tdpi.value]
        py_dup._idta.item_id = ae_dup.id
        for chunk in py_dup._item_list.chunks:
            if chunk.chunk_type == "iide":
                cast("Any", chunk).value = ae_dup.id
        for py_c, ae_c in zip(_cctls(py_dup), _cctls(ae_dup)):
            py_u = filter_by_type(chunks=py_c.chunks, chunk_type="Utf8")
            ae_u = filter_by_type(chunks=ae_c.chunks, chunk_type="Utf8")
            cast("Utf8Chunk", py_u[0]).value = cast("Utf8Chunk", ae_u[0]).value
            # CCId/CLId map through the same id pairing - a semantic remap,
            # not a copy from AE.
            cprp = find_by_list_type(chunks=py_c.chunks, list_type="CPrp")
            for chunk in cprp.chunks:
                if chunk.chunk_type in ("CCId", "CLId"):
                    ref = cast("Any", chunk)
                    if ref.value in id_map:
                        ref.value = id_map[ref.value]
        py_dup.name = ae_dup.name
        # Documented family 1: AE re-derives the comp's time divisor; AE
        # accepts either value (its resave keeps py's).
        py_dup._cdta.time_divisor = ae_dup._cdta.time_divisor
        # Documented family 2: AE zeroes the stale viewer-pseudo-layer
        # expression-flags byte; AE's own resave zeroes it everywhere.
        ae_flags = iter(
            cast("Any", t)._expr_flags
            for t in recursive_find(ae_dup._item_list.chunks, chunk_type="tdb4")
        )
        for t in recursive_find(py_dup._item_list.chunks, chunk_type="tdb4"):
            cast("Any", t)._expr_flags = next(ae_flags)
        # Documented family 3: AE strips layer-level parT effect param
        # defs (redundant with EfdG); py keeps them - they are the only
        # param source for uninstalled effects. Align for the comparison.
        py_part = list(recursive_find(py_dup._item_list.chunks, list_type="parT"))
        ae_part = list(recursive_find(ae_dup._item_list.chunks, list_type="parT"))
        assert len(py_part) == len(ae_part)
        for py_p, ae_p in zip(py_part, ae_part):
            cast("ListChunk", py_p).chunks = list(cast("ListChunk", ae_p).chunks)

        ae_children = ae_dup._item_list.chunks
        py_children = py_dup._item_list.chunks
        assert len(ae_children) == len(py_children)
        for i, (a, p) in enumerate(zip(ae_children, py_children)):
            assert _chunk_bytes(a) == _chunk_bytes(p), f"child {i} differs"

    def test_roundtrip_reparse(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLE)
        dup_name = _comp(project, "DupSrc").duplicate().name
        out = tmp_path / "dup.aep"
        project.save(out)

        project2 = parse_project_fresh(out)
        dup = _comp(project2, dup_name)
        a = next(la for la in dup.layers if la.name == "A")
        b = next(la for la in dup.layers if la.name == "B")
        assert b.parent is a
        assert a._ldta.matte_layer_id == b.id
        assert a.transform.property("ADBE Opacity").expression_enabled
        inner_layer = next(la for la in dup.layers if la.name == "Inner")
        overrides = next(
            p for p in inner_layer.properties if p.match_name == "ADBE Layer Overrides"
        )
        assert [p.value for p in overrides.properties] == [42.0]
        assert [c.source_comp_id for c in dup.motion_graphics_controllers] == [dup.id]
        ids = _all_ids(project2)
        assert len(ids) == len(set(ids))
        assert project2._head.next_item_id > max(ids)


class TestDuplicateEdgeCases:
    def test_media_replacement_blsi_kept(self, tmp_path: Path) -> None:
        # The alternate-source slot's blsi holds an ITEM id (the wrapper
        # comp) - shared with the original, never remapped.
        project = parse_project_fresh(EG_SAMPLE)
        host = _comp(project, "image_with_alpha 2")
        original = next(la for la in host.layers if la.essential_property_uuids)
        orig_alt = next(
            p for p in original.properties if p.match_name == "ADBE Layer Overrides"
        ).properties[0]
        assert orig_alt.alternate_source is not None

        dup = host.duplicate()
        out = tmp_path / "dup.aep"
        project.save(out)

        project2 = parse_project_fresh(out)
        dup2 = _comp(project2, dup.name)
        layer = next(la for la in dup2.layers if la.essential_property_uuids)
        assert layer.essential_property_uuids == original.essential_property_uuids
        alt = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Overrides"
        ).properties[0]
        assert alt.can_set_alternate_source is True
        assert alt.alternate_source is not None
        assert alt.alternate_source.id == orig_alt.alternate_source.id

    def test_pre_ae23_no_matte_field(self) -> None:
        # Pre-AE23 ldta has no matte_layer_id (None) - duplicate must not
        # materialize the optional field.
        project = parse_project_fresh(AE2018_SAMPLE)
        src = next(c for c in project.compositions if c.layers)
        dup = src.duplicate()
        assert dup.num_layers == src.num_layers
        assert all(ld.matte_layer_id is None for ld in _ldta_in_order(dup))
        ids = _all_ids(project)
        assert len(ids) == len(set(ids))
