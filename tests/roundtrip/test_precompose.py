"""Tests for CompItem.precompose().

Mutation tests parse a fresh (uncached) copy via `parse_aep` and assert
results survive a save / re-parse round-trip. AE-side ground truth
(AE 2026 fixtures) is documented in .claude/plans/precompose.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import get_comp

from py_aep import parse as parse_aep

SAMPLES = Path(__file__).parent.parent.parent / "samples" / "models"


def _fresh(rel: str):
    return parse_aep(str(SAMPLES / rel))


class TestPrecomposeMove:
    """move_all_attributes=True (default)."""

    def test_two_layers_roundtrip(self, tmp_path: Path) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        new_comp = comp.precompose([0, 1], "Pre-comp 1")

        assert new_comp.name == "Pre-comp 1"
        assert [ly.name for ly in new_comp.layers] == ["Gray Solid 1", "Gray Solid 2"]
        assert len(comp.layers) == 1
        repl = comp.layers[0]
        assert repl.source is new_comp

        out = tmp_path / "precomp.aep"
        app.project.save(out)
        app2 = parse_aep(str(out))
        comp2 = get_comp(app2.project, "Comp 1")
        nc2 = get_comp(app2.project, "Pre-comp 1")
        assert [ly.name for ly in nc2.layers] == ["Gray Solid 1", "Gray Solid 2"]
        assert comp2.layers[0].source is nc2

    def test_settings_inherited(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        new_comp = comp.precompose([0], "PC")
        assert new_comp.width == comp.width
        assert new_comp.height == comp.height
        assert new_comp.duration == comp.duration
        assert new_comp.frame_rate == comp.frame_rate
        assert new_comp.bg_color == comp.bg_color

    def test_replacement_at_topmost_moved_index(self, tmp_path: Path) -> None:
        app = _fresh("property/all_animated.aep")
        comp = get_comp(app.project, "type_camera")
        assert [ly.name for ly in comp.layers] == [
            "Hello",
            "Shape Layer 1",
            "XF",
            "CameraLayer",
        ]
        comp.precompose([1, 2], "PC mid")
        assert [ly.name for ly in comp.layers] == ["Hello", "PC mid", "CameraLayer"]

        out = tmp_path / "mid.aep"
        app.project.save(out)
        comp2 = get_comp(parse_aep(str(out)).project, "type_camera")
        assert [ly.name for ly in comp2.layers] == ["Hello", "PC mid", "CameraLayer"]

    def test_new_comp_stored_alphabetically(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        comp.precompose([0], "PC alpha")
        names = [item.name for item in app.project.root_folder.items]
        # AE stores folder children in display order; the new comp lands
        # between 'Comp 1' and 'Solids'.
        assert names == ["Comp 1", "PC alpha", "Solids"]

    def test_indices_deduped_and_sorted(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        new_comp = comp.precompose([1, 0, 1], "PC dup")
        assert [ly.name for ly in new_comp.layers] == ["Gray Solid 1", "Gray Solid 2"]

    def test_parent_link_inside_set_remapped(self, tmp_path: Path) -> None:
        app = _fresh("layer/layer_misc.aep")
        comp = get_comp(app.project, "parent")
        new_comp = comp.precompose([0, 1], "PC par")
        child = next(ly for ly in new_comp.layers if ly.name == "ChildLayer")
        null = next(ly for ly in new_comp.layers if ly.name == "ParentNull")
        assert child._ldta.parent_id == null.id

        out = tmp_path / "par.aep"
        app.project.save(out)
        nc2 = get_comp(parse_aep(str(out)).project, "PC par")
        child2 = next(ly for ly in nc2.layers if ly.name == "ChildLayer")
        assert child2.parent is not None
        assert child2.parent.name == "ParentNull"

    def test_parent_stays_child_unparented(self) -> None:
        app = _fresh("layer/layer_misc.aep")
        comp = get_comp(app.project, "parent")
        new_comp = comp.precompose([0], "PC orphan")
        assert new_comp.layers[0]._ldta.parent_id == 0

    def test_parent_moved_stayer_retargets_to_replacement(self) -> None:
        app = _fresh("layer/layer_misc.aep")
        comp = get_comp(app.project, "parent")
        comp.precompose([1], "PC repl")
        child = next(ly for ly in comp.layers if ly.name == "ChildLayer")
        repl = next(ly for ly in comp.layers if ly.name == "PC repl")
        assert child._ldta.parent_id == repl.id

    def test_matte_pair_moved_together(self) -> None:
        app = _fresh("layer/track_matte_yes.aep")
        comp = get_comp(app.project, "Comp 1")
        new_comp = comp.precompose([0, 1], "PC matte")
        user = next(ly for ly in new_comp.layers if ly.name == "Gray Solid 2")
        matte = next(ly for ly in new_comp.layers if ly.name == "Gray Solid 1")
        assert user._ldta.matte_layer_id == matte.id

    def test_matte_stays_copied_into_precomp(self, tmp_path: Path) -> None:
        app = _fresh("layer/track_matte_yes.aep")
        comp = get_comp(app.project, "Comp 1")
        new_comp = comp.precompose([0], "PC copy")
        # AE copies the unmoved matte layer below its user; the original
        # stays untouched in the parent comp.
        assert [ly.name for ly in new_comp.layers] == ["Gray Solid 2", "Gray Solid 1"]
        user, copy = new_comp.layers
        assert user._ldta.matte_layer_id == copy.id
        assert [ly.name for ly in comp.layers] == ["PC copy", "Gray Solid 1"]

        out = tmp_path / "mattecopy.aep"
        app.project.save(out)
        nc2 = get_comp(parse_aep(str(out)).project, "PC copy")
        user2, copy2 = nc2.layers
        assert user2._ldta.matte_layer_id == copy2.id

    def test_matte_moved_user_retargets_to_replacement(self) -> None:
        app = _fresh("layer/track_matte_yes.aep")
        comp = get_comp(app.project, "Comp 1")
        comp.precompose([1], "PC target")
        user = next(ly for ly in comp.layers if ly.name == "Gray Solid 2")
        repl = next(ly for ly in comp.layers if ly.name == "PC target")
        assert user._ldta.matte_layer_id == repl.id
        # The replacement keeps serving as matte, so it inherits the
        # moved matte layer's video-off state.
        assert repl.enabled is False

    def test_all_layer_kinds_move(self, tmp_path: Path) -> None:
        app = _fresh("property/all_animated.aep")
        comp = get_comp(app.project, "type_camera")
        new_comp = comp.precompose([0, 1, 2, 3], "PC all")
        assert [ly.name for ly in new_comp.layers] == [
            "Hello",
            "Shape Layer 1",
            "XF",
            "CameraLayer",
        ]
        assert [ly.name for ly in comp.layers] == ["PC all"]

        out = tmp_path / "allkinds.aep"
        app.project.save(out)
        nc2 = get_comp(parse_aep(str(out)).project, "PC all")
        assert len(nc2.layers) == 4


class TestPrecomposeLeaveAttributes:
    """move_all_attributes=False."""

    def test_source_swap_roundtrip(self, tmp_path: Path) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        retained = comp.layers[1]
        original_source = retained.source
        new_comp = comp.precompose([1], "PC leave", move_all_attributes=False)

        # The retained layer object survives with its source swapped.
        assert comp.layers[1] is retained
        assert retained.source is new_comp
        assert [ly.source for ly in new_comp.layers] == [original_source]

        out = tmp_path / "leave.aep"
        app.project.save(out)
        app2 = parse_aep(str(out))
        comp2 = get_comp(app2.project, "Comp 1")
        nc2 = get_comp(app2.project, "PC leave")
        assert comp2.layers[1].source is nc2
        assert nc2.layers[0].source.name == "Gray Solid 2"

    def test_new_comp_sized_from_source(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        solid = comp.add_solid([1.0, 0.0, 0.0], "SmallRed", 400, 300)
        new_comp = comp.precompose([0], "PC small", move_all_attributes=False)
        assert (new_comp.width, new_comp.height) == (400, 300)
        # Duration / frame rate stay inherited from the parent comp.
        assert new_comp.duration == comp.duration
        assert new_comp.frame_rate == comp.frame_rate
        assert solid.source is new_comp

    def test_multiple_indices_raise(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        with pytest.raises(ValueError):
            comp.precompose([0, 1], "PC bad", move_all_attributes=False)

    def test_sourceless_layer_raises(self) -> None:
        app = _fresh("property/all_animated.aep")
        comp = get_comp(app.project, "type_shape")
        assert comp.layers[0].source is None
        with pytest.raises(ValueError):
            comp.precompose([0], "PC bad", move_all_attributes=False)


class TestPrecomposeValidation:
    def test_empty_indices_raise(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        with pytest.raises(ValueError):
            comp.precompose([], "PC bad")

    def test_out_of_range_raises(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        with pytest.raises(ValueError):
            comp.precompose([5], "PC bad")
        with pytest.raises(ValueError):
            comp.precompose([-1], "PC bad")

    def test_invalid_name_raises(self) -> None:
        app = _fresh("layer/gray_solid_1_above.aep")
        comp = get_comp(app.project, "Comp 1")
        with pytest.raises((TypeError, ValueError)):
            comp.precompose([0], 123)  # type: ignore[arg-type]
