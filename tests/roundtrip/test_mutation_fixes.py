"""regressions: mutation methods.

Every expectation here was measured against After Effects 2026
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import SAMPLES_DIR, parse_app_fresh

from py_aep.binary.utils import find_by_type
from py_aep.enums import PropertyType

PROPERTY_DIR = SAMPLES_DIR / "models" / "property"
LAYER_DIR = SAMPLES_DIR / "models" / "layer"
COMP_DIR = SAMPLES_DIR / "models" / "composition"
EG_DIR = SAMPLES_DIR / "models" / "essential_graphics"


def _walk(group, depth=0):
    if depth > 10:
        return
    for child in group:
        yield child
        if not hasattr(child, "keyframes"):
            yield from _walk(child, depth + 1)


def _layer_refs(app):
    """Every `(comp, layer, property, referenced id, resolves)` layer param."""
    out = []
    for comp in app.project.compositions:
        ids = {lyr.id for lyr in comp.layers}
        for lyr in comp.layers:
            for prop in _walk(lyr):
                tdpi = getattr(prop, "_tdpi", None)
                if tdpi is None or not tdpi.value:
                    continue
                out.append(
                    (
                        comp.name,
                        lyr.name,
                        prop.match_name,
                        tdpi.value,
                        tdpi.value in ids,
                    )
                )
    return out


class TestActiveItemRemoval:
    """Removing the active item left its id in `fcid`, and the parser then
    raised `KeyError` on py's own output. AE writes `fcid = 0`."""

    def test_remove_active_comp_clears_fcid(self, tmp_path: Path) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "gradient.aep")
        assert app.project.active_item is app.project.compositions[0]

        app.project.compositions[0].remove()

        fcid = find_by_type(chunks=app.project._rifx.chunks, chunk_type="fcid")
        assert fcid.value == 0
        assert app.project.active_item is None

        out = tmp_path / "removed.aep"
        app.project.save(out)
        # Used to raise KeyError: 1. `fcid = 0` is the root folder, which is
        # what AE's own saves carry once the active item is gone.
        reparsed = parse_app_fresh(out)
        assert reparsed.project.active_item is reparsed.project.root_folder

    def test_dangling_fcid_parses(self, tmp_path: Path) -> None:
        """A file naming a missing item still parses - AE opens one too."""
        app = parse_app_fresh(PROPERTY_DIR / "gradient.aep")
        find_by_type(chunks=app.project._rifx.chunks, chunk_type="fcid").value = 4242
        out = tmp_path / "dangling.aep"
        app.project.save(out)

        assert parse_app_fresh(out).project.active_item is None


class TestEffectParameterIsNotIndexed:
    """An effect group is a NAMED group in AE (`propertyType` 6213), so its
    parameters cannot be duplicated, removed, moved or renamed. py accepted
    all four, applied them in memory and dropped them on save."""

    def _blur_param(self, app):
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        effect = layer.effects.properties[0]
        return effect, effect.properties[0]

    def test_effect_group_is_named_group(self) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "2_gaussian.aep")
        effect, _param = self._blur_param(app)
        assert effect.property_type == PropertyType.NAMED_GROUP
        assert effect.parent_property.property_type == PropertyType.INDEXED_GROUP

    @pytest.mark.parametrize("op", ["duplicate", "remove", "move_to"])
    def test_parameter_mutation_rejected(self, op: str) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "2_gaussian.aep")
        _effect, param = self._blur_param(app)
        with pytest.raises(ValueError, match="non-indexed group"):
            if op == "move_to":
                param.move_to(1)
            else:
                getattr(param, op)()

    def test_parameter_rename_rejected(self) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "2_gaussian.aep")
        _effect, param = self._blur_param(app)
        with pytest.raises(ValueError, match="not an indexed group"):
            param.name = "Amount"

    def test_effect_itself_still_mutable(self, tmp_path: Path) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "2_gaussian.aep")
        layer = app.project.compositions[0].layers[0]
        assert layer.effects is not None
        before = len(layer.effects.properties)

        layer.effects.properties[0].duplicate()
        out = tmp_path / "dup.aep"
        app.project.save(out)

        app2 = parse_app_fresh(out)
        layer2 = app2.project.compositions[0].layers[0]
        assert layer2.effects is not None
        assert len(layer2.effects.properties) == before + 1


class TestLayerReferencesFollowTheirLayer:
    """A layer-reference effect param (`tdpi`) that names a layer the
    destination comp does not contain makes AE refuse the whole file:
    "Can't find layer ID=N in composition X"."""

    def test_copy_to_comp_clears_the_reference(self, tmp_path: Path) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "effects.aep")
        comps = app.project.compositions
        source = next(c for c in comps if c.layers)
        target = next(c for c in comps if c is not source)

        source.layers[0].copy_to_comp(target)

        out = tmp_path / "copied.aep"
        app.project.save(out)
        unresolved = [r for r in _layer_refs(parse_app_fresh(out)) if not r[4]]
        assert unresolved == []

    def test_precompose_keeps_the_reference_resolvable(self, tmp_path: Path) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "effects.aep")
        comp = next(c for c in app.project.compositions if len(c.layers) >= 1)

        comp.precompose([0], "Pre")

        out = tmp_path / "pre.aep"
        app.project.save(out)
        unresolved = [r for r in _layer_refs(parse_app_fresh(out)) if not r[4]]
        assert unresolved == []


class TestCopyToCompTransform:
    """AE keeps a copied layer where it was and materializes the chunk to
    hold it; py re-derived the destination comp's centre instead."""

    def test_position_survives_a_different_sized_comp(self) -> None:
        app = parse_app_fresh(COMP_DIR / "duplicate.aep")
        comps = app.project.compositions
        source = next(c for c in comps if c.layers)
        target = next(
            c
            for c in comps
            if c is not source and (c.width, c.height) != (source.width, source.height)
        )
        layer = source.layers[0]
        before = layer.property("Transform").property("Position").value

        copy = layer.copy_to_comp(target)

        assert copy.property("Transform").property("Position").value == before

    def test_timebase_is_restamped_to_the_destination(self) -> None:
        app = parse_app_fresh(PROPERTY_DIR / "effect_point_speed.aep")
        comps = app.project.compositions
        source = next(c for c in comps if c.layers)
        target = next(
            c for c in comps if c is not source and c.frame_rate != source.frame_rate
        )

        copy = source.layers[0].copy_to_comp(target)

        want = target._cdta.internal_timebase
        assert source.layers[0].stretch == 100.0
        bases = {
            prop._tdb4._time_base
            for prop in _walk(copy)
            if getattr(prop, "_tdb4", None) is not None
            and not prop._tdbs.synthetic
            and prop._tdb4._time_base
        }
        assert bases == {want}

    def test_a_stretched_copy_keeps_its_own_timebase(self) -> None:
        """A stretched layer counts ticks against `comp base * |stretch|`, so
        the restamp has to carry the stretch across too (issue #225 item 4)."""
        app = parse_app_fresh(LAYER_DIR / "layer_timing.aep")
        source = next(c for c in app.project.compositions if c.name == "stretch_200")
        target = next(c for c in app.project.compositions if c.name == "startTime_5")
        assert source.layers[0].stretch == 200.0

        copy = source.layers[0].copy_to_comp(target)

        want = target._cdta.internal_timebase * 2
        bases = {
            prop._tdb4._time_base
            for prop in _walk(copy)
            if getattr(prop, "_tdb4", None) is not None
            and not prop._tdbs.synthetic
            and prop._tdb4._time_base
        }
        assert bases == {want}


class TestPrecomposeSideEffects:
    def test_moved_layer_keeps_its_anchor_point(self) -> None:
        """A synthetic cdat holds user units; re-resolving it scaled the
        anchor by the layer size a second time (50 read back as 5000)."""
        app = parse_app_fresh(PROPERTY_DIR / "keyframe_1D.aep")
        comp = app.project.compositions[0]
        before = (
            comp.layers[0].property("Transform").property("ADBE Anchor Point").value
        )

        new_comp = comp.precompose([0], "Pre")

        after = (
            new_comp.layers[0].property("Transform").property("ADBE Anchor Point").value
        )
        assert after == before

    def test_leave_attributes_drops_essential_overrides(self, tmp_path: Path) -> None:
        """AE drops the overrides (3 -> 0); they point into the old source."""
        app = parse_app_fresh(EG_DIR / "multiple_controllers.aep")
        comp = next(c for c in app.project.compositions if c.name == "main")
        layer = comp.layers[0]
        overrides = layer.property("ADBE Layer Overrides")
        assert len(overrides.properties) == 3

        comp.precompose([0], "PreKeep", False)

        assert len(comp.layers[0].property("ADBE Layer Overrides").properties) == 0
        out = tmp_path / "kept.aep"
        app.project.save(out)
        app2 = parse_app_fresh(out)
        comp2 = next(c for c in app2.project.compositions if c.name == "main")
        assert len(comp2.layers[0].property("ADBE Layer Overrides").properties) == 0
