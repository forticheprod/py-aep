"""Regression tests pinning the binary skeleton of newly created items.

After Effects 2026 rejects (or crashes on) files whose new layers / comps
lack the chunk skeleton it writes itself. These tests assert the WRITTEN
bytes (save -> re-read) match the ground-truth structure measured from AE
(see scripts/dev/apifuzz/FINDINGS.md).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from conftest import get_comp

from py_aep import parse as parse_aep
from py_aep.binary.chunk import Chunk, read_aep
from py_aep.binary.misc_chunks import ClassicPrdaChunk
from py_aep.binary.utils import (
    filter_by_list_type,
    find_by_list_type,
    find_by_type,
    recursive_find,
)

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models"
PRDA_CLASSIC_DEFAULT = bytes.fromhex(
    "000000010000000000000000"
)  # default 3D render-options blob (Classic)


def _saved_rifx(app, tmp_path):
    out = tmp_path / "out.aep"
    app.project.save(out)
    with out.open("rb") as f:
        rifx, _ = read_aep(f)
    return rifx


def _find_comp_item(rifx, comp_name):
    fold = find_by_list_type(chunks=rifx.chunks, list_type="Fold")
    for ch in recursive_find(fold.chunks, list_type="Item"):
        utf8 = find_by_type(chunks=ch.chunks, chunk_type="Utf8")
        idta = find_by_type(chunks=ch.chunks, chunk_type="idta")
        if utf8.value == comp_name and idta.item_type == 4:
            return ch
    pytest.fail(f"comp {comp_name!r} not found in saved file")


def _find_prda(rifx, comp_name: str) -> Chunk:
    item = _find_comp_item(rifx, comp_name)
    prin = find_by_list_type(chunks=item.chunks, list_type="PRin")
    return find_by_type(chunks=prin.chunks, chunk_type="prda")


def _top_layer(rifx, comp_name):
    item = _find_comp_item(rifx, comp_name)
    return filter_by_list_type(chunks=item.chunks, list_type="Layr")[0]


def _match_name_stream(tdgp):
    out = []
    for ch in tdgp.chunks:
        if ch.chunk_type == "tdmn":
            out.append(ch.value)
    return out


class TestNewLayerSkeleton:
    def test_root_tdgp_ends_with_group_end(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        get_comp(app.project, "type_null").add_null()
        rifx = _saved_rifx(app, tmp_path)
        layer = _top_layer(rifx, "type_null")
        tdgp = find_by_list_type(chunks=layer.chunks, list_type="tdgp")
        stream = _match_name_stream(tdgp)
        assert stream[-1] == "ADBE Group End"

    def test_no_zero_time_base_written(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        comp = get_comp(app.project, "type_null")
        comp.add_null()
        comp.add_camera("Cam")
        comp.add_light("Light")
        rifx = _saved_rifx(app, tmp_path)
        item = _find_comp_item(rifx, "type_null")
        bases = {t._time_base for t in recursive_find(item.chunks, chunk_type="tdb4")}
        assert 0 not in bases

    def test_time_remapping_has_value_and_bounds(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        get_comp(app.project, "type_null").add_null()
        rifx = _saved_rifx(app, tmp_path)
        layer = _top_layer(rifx, "type_null")
        tdgp = find_by_list_type(chunks=layer.chunks, list_type="tdgp")
        idx = next(
            i
            for i, c in enumerate(tdgp.chunks)
            if c.chunk_type == "tdmn" and c.value == "ADBE Time Remapping"
        )
        tdbs = tdgp.chunks[idx + 1]
        kinds = [getattr(c, "list_type", c.chunk_type) for c in tdbs.chunks]
        assert "cdat" in kinds
        assert "tdum" in kinds and "tduM" in kinds

    def test_layer_overrides_followed_by_ovg2(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        get_comp(app.project, "type_null").add_null()
        rifx = _saved_rifx(app, tmp_path)
        layer = _top_layer(rifx, "type_null")
        tdgp = find_by_list_type(chunks=layer.chunks, list_type="tdgp")
        idx = next(
            i
            for i, c in enumerate(tdgp.chunks)
            if c.chunk_type == "tdmn" and c.value == "ADBE Layer Overrides"
        )
        nxt = tdgp.chunks[idx + 1]
        assert getattr(nxt, "list_type", None) == "OvG2"

    def test_source_alternate_blsv_blsi_and_empty_cdat(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        get_comp(app.project, "type_null").add_null()
        rifx = _saved_rifx(app, tmp_path)
        layer = _top_layer(rifx, "type_null")
        root = find_by_list_type(chunks=layer.chunks, list_type="tdgp")
        idx = next(
            i
            for i, c in enumerate(root.chunks)
            if c.chunk_type == "tdmn" and c.value == "ADBE Source Options Group"
        )
        inner = root.chunks[idx + 1]
        kinds = [getattr(c, "list_type", c.chunk_type) for c in inner.chunks]
        j = kinds.index("blsv")
        assert kinds[j + 1] == "blsi"
        tdbs = inner.chunks[j + 2]
        cdat = find_by_type(chunks=tdbs.chunks, chunk_type="cdat")
        assert len(cdat.values) == 0  # 4-zero-byte no-value marker

    def test_empty_parade_groups_not_written(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        get_comp(app.project, "type_null").add_null()
        rifx = _saved_rifx(app, tmp_path)
        layer = _top_layer(rifx, "type_null")
        tdgp = find_by_list_type(chunks=layer.chunks, list_type="tdgp")
        stream = _match_name_stream(tdgp)
        for omitted in ("ADBE MTrackers", "ADBE Mask Parade", "ADBE Effect Parade"):
            assert omitted not in stream

    def test_static_orientation_written_as_otst(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        get_comp(app.project, "type_null").add_null()
        rifx = _saved_rifx(app, tmp_path)
        layer = _top_layer(rifx, "type_null")
        root = find_by_list_type(chunks=layer.chunks, list_type="tdgp")
        idx = next(
            i
            for i, c in enumerate(root.chunks)
            if c.chunk_type == "tdmn" and c.value == "ADBE Transform Group"
        )
        transform = root.chunks[idx + 1]
        j = next(
            i
            for i, c in enumerate(transform.chunks)
            if c.chunk_type == "tdmn" and c.value == "ADBE Orientation"
        )
        wrapper = transform.chunks[j + 1]
        assert getattr(wrapper, "list_type", None) == "otst"

    def test_camera_position_and_poi(self) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        comp = get_comp(app.project, "type_null")
        cam = comp.add_camera("Cam")
        pos = next(p for p in cam.transform if p.match_name == "ADBE Position")
        anchor = next(p for p in cam.transform if p.match_name == "ADBE Anchor Point")
        zoom = round(comp.width / 0.72, 8)
        assert pos.value == [0.0, 0.0, -zoom]
        assert anchor.value == [comp.width / 2, comp.height / 2, 0.0]


class TestNewCompSkeleton:
    def test_full_view_state_skeleton_written(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        app.project.root_folder.add_comp("MinComp", 1280, 720, 1.0, 10.0, 30.0)
        rifx = _saved_rifx(app, tmp_path)
        item = _find_comp_item(rifx, "MinComp")
        kinds = [getattr(c, "list_type", c.chunk_type) for c in item.chunks]
        for required in ("dats", "cdrp", "comr", "DLay", "SecL", "CIFO", "Gide"):
            assert required in kinds, f"missing {required} in new comp item"
        assert kinds.count("SLay") == 6
        assert kinds.count("CLay") == 3

    def test_comp_params_patched_into_template(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        comp = app.project.root_folder.add_comp(
            "OtherComp", 1920, 1080, 2.0, 4.5, 23.976
        )
        comp_id = comp.id
        rifx = _saved_rifx(app, tmp_path)
        item = _find_comp_item(rifx, "OtherComp")
        cdta = find_by_type(chunks=item.chunks, chunk_type="cdta")
        assert cdta.width == 1920 and cdta.height == 1080
        assert cdta.pixel_aspect == 2.0
        assert cdta.internal_timebase == 23976
        iide = find_by_type(chunks=item.chunks, chunk_type="iide")
        idta = find_by_type(chunks=item.chunks, chunk_type="idta")
        assert iide.value == comp_id and idta.item_id == comp_id
        # viewer pseudo-layers rebased onto the comp's timebase
        bases = {t._time_base for t in recursive_find(item.chunks, chunk_type="tdb4")}
        assert bases == {23976}

    def test_reparse_roundtrip(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        comp = app.project.root_folder.add_comp("RT", 1280, 720, 1.0, 10.0, 30.0)
        comp.add_solid([0.5, 0.5, 0.5], "S")
        out = tmp_path / "rt.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        comp2 = next(c for c in app2.project.compositions if c.name == "RT")
        assert comp2.frame_rate == pytest.approx(30.0)
        assert [lyr.name for lyr in comp2.layers] == ["S"]


class TestNewCompPrda:
    def test_new_comp_prda_is_classic_variant(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        app.project.root_folder.add_comp("PrdaComp", 1280, 720, 1.0, 10.0, 30.0)
        rifx = _saved_rifx(app, tmp_path)
        prda = _find_prda(rifx, "PrdaComp")
        assert isinstance(prda, ClassicPrdaChunk)
        assert prda.shadow_map_resolution == 0

    def test_new_comp_prda_bytes_match_after_effects(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")
        app.project.root_folder.add_comp("PrdaComp", 1280, 720, 1.0, 10.0, 30.0)
        rifx = _saved_rifx(app, tmp_path)
        buf = BytesIO()
        _find_prda(rifx, "PrdaComp").write(buf)
        assert buf.getvalue() == PRDA_CLASSIC_DEFAULT
