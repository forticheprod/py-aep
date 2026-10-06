"""Regression tests for the layer geometry, parenting and layer-mutation
fixes of the v9 API fuzz campaign.

Expected numbers are After Effects 2026 measurements unless a test says it
checks a law. The `*_v9` fixtures under samples/models/layer/ were built by
AE 2026 headless, which also recorded its own answers next to them:

- `geometry_v9.aep` + `geometry_v9_probe.json`: `sourcePointToComp`,
  `compPointToSource` and `sourceRectAtTime` of the PA_* comps' layers at
  times 0, 0.5, 1, 1.5 and 2.5 s (keys `t0`..`t4`).
- `reparent_copy_v9.aep` (saved BEFORE AE's operations; comp PB's playhead
  is at 1 s) + `reparent_copy_v9_probe.json`: the transform AE wrote after
  `layer.parent = ...` (`parent`), after `copyToComp` (`copy`) and its
  light-source refusals (`light`).
- `text_ink_v9.aep` + `text_ink_v9_probe.json`: text rects of tracked
  justified point text and of box text with inset spacing.
- `reparent_more_v9.aep` (saved BEFORE AE's operations) +
  `reparent_more_v9_probe.json`: `parent =` on auto-oriented layers, 2D
  children of cameras and lights, rig children and a 2:1 pixel-aspect
  comp (`parent`), `copyToComp` of parented layers with the playhead at
  0.5 s (`copy`), point text indents (`text`) and `sourcePointToComp` at
  times 0, 0.5, 1, 2, 2.5 s (`s2c`).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from helpers import parse_project_fresh

from py_aep import parse as parse_aep
from py_aep.enums import LightType
from py_aep.resolvers.transform import Mat4, intersect_layer_plane

SAMPLES = Path(__file__).parent.parent.parent / "samples"
LAYER_DIR = SAMPLES / "models" / "layer"
GEOMETRY = LAYER_DIR / "geometry_v9.aep"
REPARENT = LAYER_DIR / "reparent_copy_v9.aep"
TEXT = LAYER_DIR / "text_ink_v9.aep"
MORE = LAYER_DIR / "reparent_more_v9.aep"
TIMES = [0.0, 0.5, 1.0, 1.5, 2.5]
MORE_TIMES = [0.0, 0.5, 1.0, 2.0, 2.5]
PTS = [[0.0, 0.0], [100.0, 50.0], [-30.0, 70.0]]
CPTS = [[500.0, 400.0], [120.0, 60.0]]


def _json(name: str) -> dict:
    return json.loads((LAYER_DIR / name).read_text(encoding="utf-8"))


GEOMETRY_TRUTH = _json("geometry_v9_probe.json")
REPARENT_TRUTH = _json("reparent_copy_v9_probe.json")
TEXT_TRUTH = _json("text_ink_v9_probe.json")
MORE_TRUTH = _json("reparent_more_v9_probe.json")


def _layer(project, comp_name: str, layer_name: str):
    comp = next(c for c in project.compositions if c.name == comp_name)
    return comp, next(ly for ly in comp.layers if ly.name == layer_name)


def _close(a, b, tol: float) -> bool:
    if isinstance(a, (int, float)):
        return abs(a - b) <= tol
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _rect(layer, time: float) -> list[float]:
    try:
        r = layer.source_rect_at_time(time, False)
    except NotImplementedError as exc:
        pytest.skip(f"text ink unavailable here: {exc}")
    return [r["left"], r["top"], r["width"], r["height"]]


# ---------------------------------------------------------------------------
# Layer.comment
# ---------------------------------------------------------------------------


class TestComment:
    """AE 2026 only reads a comment when ldta byte 0x3c bit 0 is set; it
    clears the bit and drops the `cmta` when the comment is emptied."""

    def test_new_comment_sets_the_flag_and_round_trips(self, tmp_path: Path) -> None:
        project = parse_project_fresh(SAMPLES / "versions/ae2026/complete.aep")
        layer = next(
            c for c in project.compositions if c.name == "DropFrame_Comp"
        ).layers[0]
        layer.comment = "probe comment"
        assert layer._ldta.has_comment
        out = tmp_path / "comment.aep"
        project.save(out)
        again = parse_aep(out).project
        reread = next(
            c for c in again.compositions if c.name == "DropFrame_Comp"
        ).layers[0]
        assert reread.comment == "probe comment"
        assert reread._ldta.has_comment

    def test_emptying_drops_chunk_and_flag(self) -> None:
        project = parse_project_fresh(SAMPLES / "versions/ae2026/complete.aep")
        comp = next(c for c in project.compositions if c.name == "Main_Comp")
        layer = next(ly for ly in comp.layers if ly.name == "Null_Controller")
        assert layer.comment == "Parent null for shapes"
        layer.comment = ""
        assert layer._cmta is None
        assert not layer._ldta.has_comment
        assert all(
            getattr(c, "chunk_type", "") != "cmta" for c in layer._layer_list.chunks
        )

    def test_unflagged_comment_reads_empty(self) -> None:
        project = parse_project_fresh(SAMPLES / "versions/ae2026/complete.aep")
        comp = next(c for c in project.compositions if c.name == "Main_Comp")
        layer = next(ly for ly in comp.layers if ly.name == "Null_Controller")
        layer._ldta.has_comment = False
        assert layer.comment == ""


# ---------------------------------------------------------------------------
# Layer.copy_to_comp / duplicate
# ---------------------------------------------------------------------------


def _copy_truth(src: str, dst: str) -> dict:
    return next(
        r for r in REPARENT_TRUTH["copy"] if r["src"] == src and r["dst"] == dst
    )


class TestCopyToComp:
    def test_key_marker_and_remap_times_keep_seconds(self) -> None:
        for src_name in ("kf_pos", "stretch_kf", "tr_kf"):
            for dst_name in ("PC_D24", "PC_D30_PAR2"):
                project = parse_project_fresh(REPARENT)
                _, src = _layer(project, "PC_SRC", src_name)
                dst = next(c for c in project.compositions if c.name == dst_name)
                copy = src.copy_to_comp(dst)
                truth = _copy_truth(src_name, dst_name)
                keys = [kf.time for kf in copy.transform["ADBE Position"].keyframes]
                assert _close(
                    keys, [k[0] for k in truth["T"]["ADBE Position"]["k"]], 1e-4
                )
                markers = [kf.time for kf in copy.marker.keyframes]
                assert _close(markers, truth["mk"], 1e-4)
                if "tr" in truth:
                    remap = [kf.time for kf in copy["ADBE Time Remapping"].keyframes]
                    assert _close(remap, [k[0] for k in truth["tr"]], 1e-4)

    def test_copy_survives_save(self, tmp_path: Path) -> None:
        project = parse_project_fresh(REPARENT)
        _, src = _layer(project, "PC_SRC", "kf_pos")
        dst = next(c for c in project.compositions if c.name == "PC_D24")
        src.copy_to_comp(dst)
        out = tmp_path / "copy.aep"
        project.save(out)
        _, copy = _layer(parse_aep(out).project, "PC_D24", "kf_pos")
        assert _close(
            [kf.time for kf in copy.transform["ADBE Position"].keyframes],
            [0, 1, 2.48],
            1e-4,
        )

    def test_user_name_kept_without_clash(self) -> None:
        project = parse_project_fresh(REPARENT)
        _, src = _layer(project, "PC_SRC", "tr_kf")
        dst = next(c for c in project.compositions if c.name == "PC_D24")
        assert src.copy_to_comp(dst).name == "tr_kf"
        # Same comp: the source's name clashes, as in AE ("tr_kf 2").
        project = parse_project_fresh(REPARENT)
        comp, src = _layer(project, "PC_SRC", "tr_kf")
        assert src.copy_to_comp(comp).name == "tr_kf 2"

    def test_parented_copy_keeps_its_place(self) -> None:
        for dst_name in ("PC_D24", "PC_D30_PAR2", "PC_SRC"):
            project = parse_project_fresh(REPARENT)
            _, src = _layer(project, "PC_SRC", "fx_ref")
            dst = next(c for c in project.compositions if c.name == dst_name)
            copy = src.copy_to_comp(dst)
            assert copy.parent is None
            assert _close(copy.transform["ADBE Position"].value, [960, 590, 0], 1e-6)
            # Into the 2:1 comp too: AE keeps the values (Scale 100).
            assert _close(copy.transform["ADBE Scale"].value, [100, 100, 100], 1e-6)

    def test_same_comp_copy_clears_refs_keeps_matte_goes_on_top(self) -> None:
        project = parse_project_fresh(REPARENT)
        comp, src = _layer(project, "PC_SRC", "fx_ref")
        copy = src.copy_to_comp(comp)
        assert copy.index == 0
        assert copy.parent is None
        assert copy.effects.properties[0].properties[0].value == 0
        project = parse_project_fresh(REPARENT)
        comp, src = _layer(project, "PC_SRC", "matte_user")
        copy = src.copy_to_comp(comp)
        assert copy.track_matte_layer is not None
        assert copy.track_matte_layer.name == "txt"

    def test_duplicate_keeps_refs(self) -> None:
        """Law: `duplicate()` keeps parent and effect references."""
        project = parse_project_fresh(REPARENT)
        comp, src = _layer(project, "PC_SRC", "fx_ref")
        dup = src.duplicate()
        assert dup.parent is src.parent
        assert (
            dup.effects.properties[0].properties[0].value
            == src.effects.properties[0].properties[0].value
        )
        assert comp.layers.index(dup) == comp.layers.index(src) - 1

    @pytest.mark.parametrize("index", [0, 1, 2])
    def test_parented_copy_bakes_the_parent_at_time_zero(self, index: int) -> None:
        """The source comp's playhead is at 0.5 s; AE still bakes the
        animated parent's transform at 0 (keys remapped by that delta)."""
        truth = MORE_TRUTH["copy"][index]
        project = parse_project_fresh(MORE)
        _, src = _layer(project, "PH_SRC", truth["src"])
        dst = next(c for c in project.compositions if c.name == truth["dst"])
        copy = src.copy_to_comp(dst)
        assert copy.parent is None
        _assert_transform(copy, dst, truth["T"])

    def test_light_source_cleared_across_comps_kept_within(self) -> None:
        project = parse_project_fresh(REPARENT)
        _, src = _layer(project, "PC_SRC", "env_light")
        dst = next(c for c in project.compositions if c.name == "PC_D24")
        copy = src.copy_to_comp(dst)
        assert copy.light_source is None
        assert copy._ldta.source_id == 0xFFFFFFFF
        comp, src = _layer(parse_project_fresh(REPARENT), "PC_SRC", "env_light")
        assert src.copy_to_comp(comp).light_source.name == "env_src"


# ---------------------------------------------------------------------------
# LightLayer.light_source
# ---------------------------------------------------------------------------


class TestLightSource:
    @pytest.mark.parametrize(
        "target", ["cam_s", "null_s", "adj_s", "env_light", "solid3d_s"]
    )
    def test_refused_like_ae(self, target: str) -> None:
        project = parse_project_fresh(REPARENT)
        comp, env = _layer(project, "PC_SRC", "env_light")
        assert "ERR" in REPARENT_TRUTH["light"][target]["env"]
        before = env._ldta.source_id
        with pytest.raises(ValueError):
            env.light_source = next(ly for ly in comp.layers if ly.name == target)
        assert env._ldta.source_id == before

    def test_other_comp_refused(self) -> None:
        project = parse_project_fresh(REPARENT)
        _, env = _layer(project, "PC_SRC", "env_light")
        _, other = _layer(project, "PC_D24", "other_comp_solid")
        with pytest.raises(ValueError):
            env.light_source = other

    def test_spot_and_point_lights_refuse_a_source(self) -> None:
        """AE 2026 refuses a source on spot and point lights and stores one
        on a parallel light."""
        project = parse_project_fresh(REPARENT)
        comp, spot = _layer(project, "PB", "spot2")
        text = next(ly for ly in comp.layers if ly.name == "c_text")
        assert spot.light_type == LightType.SPOT
        with pytest.raises(ValueError):
            spot.light_source = text
        spot.light_type = LightType.POINT
        with pytest.raises(ValueError):
            spot.light_source = text
        spot.light_type = LightType.PARALLEL
        spot.light_source = text
        assert spot.light_source is text

    def test_text_and_shape_sources_accepted(self) -> None:
        project = parse_project_fresh(REPARENT)
        comp, env = _layer(project, "PC_SRC", "env_light")
        for name in ("txt", "shp", "kf_pos"):
            assert REPARENT_TRUTH["light"][name]["env"] == name
            env.light_source = next(ly for ly in comp.layers if ly.name == name)
            assert env.light_source.name == name

    def test_version_gate(self) -> None:
        project = parse_project_fresh(SAMPLES / "versions/ae2023/complete.aep")
        light = next(ly for c in project.compositions for ly in c.light_layers)
        solid = next(
            ly
            for ly in light.containing_comp.av_layers
            if not ly.three_d_layer and not ly.null_layer
        )
        with pytest.raises(AttributeError, match="24.3"):
            light.light_type = LightType.ENVIRONMENT
        with pytest.raises(AttributeError, match="24.3"):
            light.light_source = solid


# ---------------------------------------------------------------------------
# Layer.parent
# ---------------------------------------------------------------------------

_PARENT_OPS = {
    "c_anim_par2d": "p_anim2d",
    "c3d_anim": "p_anim3d",
    "c_tiny": "p_tiny",
    "c_zero": "p_zero",
    "cam2": "p_rot3d",
    "spot2": "p_rot3d",
    "light_pt": "p_rot3d",
    "c_along": "p_rs",
    "c2d_under_orient": "p_orient",
    "c2d_under_orientx": "p_orientx",
    "c_reparent": "p_anim2d",
    "c_stretch_kf": "p_anim2d",
    "c_neg": "p_rs",
    "c_sep": "p_rs",
    "c_unparent": None,
    "cam_unparent": None,
}
_COMPARED = (
    "ADBE Anchor Point",
    "ADBE Position",
    "ADBE Scale",
    "ADBE Orientation",
    "ADBE Rotate X",
    "ADBE Rotate Y",
    "ADBE Rotate Z",
)


def _angle_close(a: float, b: float, tol: float) -> bool:
    return abs((a - b + 180.0) % 360.0 - 180.0) <= tol


_MORE_PARENT_OPS = [
    ("PH", "h_along3d", "h_rot3d"),
    ("PH", "h_along2d_static", "h_rot2d"),
    ("PH", "h_c2d_under_cam", "h_cam"),
    ("PH", "h_c2d_under_spot", "h_spot"),
    ("PH", "h_c2d_under_point", "h_point"),
    ("PH", "h_cam1node", "h_rot3d"),
    ("PH", "h_parallel", "h_rot3d"),
    ("PH", "h_cam2_kfpoi", "h_rot3d"),
    ("PH_PAR2", "h_p2_2dchild", "h_p2_null"),
    ("PH_PAR2", "h_p2_sqchild", "h_p2_null"),
    ("PH_PAR2", "h_p2_3dchild", "h_p2_null3d"),
]


def _assert_transform(child, comp, truth: dict) -> None:
    for match_name in _COMPARED:
        if match_name not in truth:
            continue
        prop = child.transform[match_name]
        expected = truth[match_name]
        got = prop.value_at_time(comp.time) if prop.keyframes else prop.value
        exp = expected["v"]
        scalars = [got] if isinstance(got, (int, float)) else list(got)
        wanted = [exp] if isinstance(exp, (int, float)) else list(exp)
        for g, w in zip(scalars, wanted):
            if "Orientation" in match_name or "Rotate" in match_name:
                assert _angle_close(g, w, 1e-3), (match_name, got, exp)
            else:
                assert abs(g - w) <= 1e-3 * max(1.0, abs(w)), (match_name, got, exp)
        if expected["k"]:
            for kf, (time, value) in zip(prop.keyframes, expected["k"]):
                assert abs(kf.time - time) < 1e-4
                assert _close(
                    kf.value if isinstance(kf.value, list) else [kf.value],
                    value if isinstance(value, list) else [value],
                    1e-3,
                )


class TestParent:
    @pytest.mark.parametrize("child_name", sorted(_PARENT_OPS))
    def test_matches_ae(self, child_name: str) -> None:
        project = parse_project_fresh(REPARENT)
        comp, child = _layer(project, "PB", child_name)
        parent_name = _PARENT_OPS[child_name]
        parent = (
            next(ly for ly in comp.layers if ly.name == parent_name)
            if parent_name
            else None
        )
        child.parent = parent
        _assert_transform(child, comp, REPARENT_TRUTH["parent"][child_name]["after"])

    @pytest.mark.parametrize(
        ("comp_name", "child_name", "parent_name"), _MORE_PARENT_OPS
    )
    def test_more_matches_ae(
        self, comp_name: str, child_name: str, parent_name: str
    ) -> None:
        project = parse_project_fresh(MORE)
        comp, child = _layer(project, comp_name, child_name)
        child.parent = next(ly for ly in comp.layers if ly.name == parent_name)
        _assert_transform(child, comp, MORE_TRUTH["parent"][child_name]["after"])

    def test_pixel_aspect_comp(self) -> None:
        project = parse_project_fresh(REPARENT)
        comp, child = _layer(project, "PB_PAR2", "c3d_under_par2")
        child.parent = next(ly for ly in comp.layers if ly.name == "p_par2_rot")
        _assert_transform(
            child, comp, REPARENT_TRUTH["parent"]["c3d_under_par2"]["after"]
        )

    def test_zero_scale_parent_is_set_without_compensation(self) -> None:
        project = parse_project_fresh(REPARENT)
        comp, child = _layer(project, "PB", "c_zero")
        child.parent = next(ly for ly in comp.layers if ly.name == "p_zero")
        assert child.parent is not None
        assert child.parent.name == "p_zero"
        assert child.transform["ADBE Position"].value[:2] == [300.0, 200.0]


# ---------------------------------------------------------------------------
# Point conversions
# ---------------------------------------------------------------------------

_POINT_LAYERS = [
    ("PA_MAIN", "child2d_of_3d"),
    ("PA_MAIN", "child3d_of_3d"),
    ("PA_MAIN", "path_hold"),
    ("PA_MAIN", "zscale0_3d"),
    ("PA_MAIN", "tiny_scale_3d"),
    ("PA_MAIN", "stale3d_2d"),
    ("PA_MAIN", "child3d_of_stale2d"),
    ("PA_MAIN", "child2d_of_stale2d"),
    ("PA_MAIN", "path_stationary"),
    ("PA_MAIN", "path_offset_stretch"),
    ("PA_CAM", "plain3d_rigcam"),
    ("PA_CAM", "towards_rigcam"),
    ("PA_CAM", "cam_rig"),
    ("PA_CAMLATE", "plain3d_latecam"),
    ("PA_CAMLATE", "towards_latecam"),
    ("PA_PAR2", "rot30_par2"),
    ("PA_PAR2", "path_par2"),
    ("PA_PAR2", "rotx_par2"),
    ("PA_PAR2", "squarepx_in_par2"),
]
_MORE_S2C = [
    ("PH", "h_s2c_under_cam"),
    ("PH", "h_s2c_under_null_orient"),
    ("PH", "h_s2c_under_light"),
    ("PH", "v_down3"),
    ("PH_PAR2", "h_p2_s2c_sq_under_null"),
    ("PH_PAR2", "h_p2_s2c_par2_under_null"),
    ("PH_PAR2", "h_p2_s2c_text"),
    ("PH_PAR2", "h_p2_s2c_precomp"),
    ("PH_PAR2", "h_p2_s2c_3d_cam"),
]


class TestPointConversions:
    @pytest.mark.parametrize(("comp_name", "layer_name"), _POINT_LAYERS)
    def test_matches_ae(self, comp_name: str, layer_name: str) -> None:
        project = parse_project_fresh(GEOMETRY)
        _, layer = _layer(project, comp_name, layer_name)
        truth = GEOMETRY_TRUTH[f"{comp_name}/{layer_name}"]
        for index, time in enumerate(TIMES):
            row = truth[f"t{index}"]
            for point, expected in zip(PTS, row["s2c"]):
                got = layer.source_point_to_comp(point, time)
                assert _close(
                    got, expected, 1e-2 * max(1.0, max(abs(v) for v in expected)) * 1e-1
                ), (time, point, got, expected)
            for point, expected in zip(CPTS, row["c2s"]):
                if not isinstance(expected, list) or expected == [0, 0]:
                    continue
                got = layer.comp_point_to_source(point, time)
                tol = 1e-3 * max(1.0, max(abs(v) for v in expected))
                assert _close(got, expected, max(tol, 1e-2)), (
                    time,
                    point,
                    got,
                    expected,
                )

    @pytest.mark.parametrize(("comp_name", "layer_name"), _MORE_S2C)
    def test_more_matches_ae(self, comp_name: str, layer_name: str) -> None:
        """2D children of cameras / lights / oriented nulls, a 3-key vertical
        path, and layers of a 2:1 pixel-aspect comp."""
        project = parse_project_fresh(MORE)
        _, layer = _layer(project, comp_name, layer_name)
        rows = MORE_TRUTH["s2c"][f"{comp_name}/{layer_name}"]
        for index, time in enumerate(MORE_TIMES):
            for point, expected in zip(PTS, rows[index]):
                got = layer.source_point_to_comp(point, time)
                assert _close(got, expected, 1e-3), (time, point, got, expected)

    def test_x_scale_zero_plane_raises(self) -> None:
        project = parse_project_fresh(GEOMETRY)
        _, layer = _layer(project, "PA_MAIN", "xscale0_2d")
        with pytest.raises(ValueError, match="degenerate"):
            layer.comp_point_to_source([500.0, 400.0], 0.0)

    def test_overflow_raises(self) -> None:
        project = parse_project_fresh(GEOMETRY)
        # A 2D layer scaled to 110 %: 1.7e308 * 1.1 overflows to inf.
        _, layer = _layer(project, "PA_MAIN", "stale3d_2d")
        with pytest.raises(ValueError, match="overflow"):
            layer.source_point_to_comp([1.7e308, 1.7e308], 0.0)

    def test_camera_default_position(self) -> None:
        project = parse_project_fresh(SAMPLES / "models/view/draft3d_false.aep")
        comp = project.compositions[0]
        camera = comp.camera_layers[0]
        # AE 2026 (the sample's ExtendScript export): [960, 53.5, -2424.24242418]
        assert _close(
            camera.transform["ADBE Position"].value, [960.0, 53.5, -2424.24242418], 1e-5
        )
        layer = next(ly for ly in comp.layers if ly.name == "Dark Gray Solid 1")
        # The camera sits on the default comp camera: c2s is the identity.
        assert _close(
            layer.comp_point_to_source([100.0, 100.0], 0.0), [100.0, 100.0], 1e-6
        )


class TestMatrixLaws:
    def test_tiny_uniform_scale_inverts(self) -> None:
        m = Mat4.identity()
        for axis in range(3):
            m[axis][axis] = 3e-4
        inv = m.inverse()
        assert math.isclose(inv[0][0], 1 / 3e-4)

    def test_plane_intersection_ignores_z_scale(self) -> None:
        """Law: a layer's Z scale does not move its z=0 plane."""
        m = Mat4.identity()
        m[2][2] = 0.0
        m[0][3], m[1][3] = 10.0, 20.0
        assert _close(
            intersect_layer_plane(m, [5.0, 6.0, -100.0], [0.0, 0.0, 1.0]),
            [-5.0, -14.0],
            1e-12,
        )


# ---------------------------------------------------------------------------
# sourceRectAtTime
# ---------------------------------------------------------------------------


class TestSourceRect:
    @pytest.mark.parametrize("layer_name", ["shape_anim_offset", "text_anim_offset"])
    def test_time_is_layer_time(self, layer_name: str) -> None:
        project = parse_project_fresh(GEOMETRY)
        _, layer = _layer(project, "PA_TIME", layer_name)
        truth = GEOMETRY_TRUTH[f"PA_TIME/{layer_name}"]
        for index, time in enumerate(TIMES):
            assert _close(_rect(layer, time), truth[f"t{index}"]["rect"], 1e-3)

    @pytest.mark.parametrize("name", sorted(TEXT_TRUTH["text"]))
    def test_tracking_and_box_inset(self, name: str) -> None:
        project = parse_project_fresh(TEXT)
        _, layer = _layer(project, "PF_TEXT", name)
        # 0.006 px: AE's first box baseline sits that much lower than the
        # composer's for Arial (unmodelled residual).
        assert _close(_rect(layer, 0.0), TEXT_TRUTH["text"][name]["rect"], 1e-2)

    @pytest.mark.parametrize("name", sorted(MORE_TRUTH["text"]))
    def test_point_text_indents(self, name: str) -> None:
        project = parse_project_fresh(MORE)
        _, layer = _layer(project, "PH_TEXT", name)
        assert _close(_rect(layer, 0.0), MORE_TRUTH["text"][name]["rect"], 1e-2)

    def test_three_d_model_layer(self) -> None:
        project = parse_project_fresh(LAYER_DIR / "three_d_model_layer.aep")
        layer = project.compositions[0].layers[0]
        # AE 2026 (the sample's ExtendScript export): anchor [0, 0, 0].
        assert layer.transform["ADBE Anchor Point"].value == [0.0, 0.0, 0.0]
        assert _close(layer.source_point_to_comp([0.0, 0.0], 0.0), [960.0, 540.0], 1e-6)
        with pytest.raises(NotImplementedError, match="3D model"):
            layer.source_rect_at_time(0.0, False)
