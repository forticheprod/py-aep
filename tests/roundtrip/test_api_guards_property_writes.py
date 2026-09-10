from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import parse as parse_aep
from py_aep.enums.property import KeyframeInterpolationType
from py_aep.models.properties.keyframe_ease import KeyframeEase

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models"


def _leaves(app, predicate):
    """Every leaf property in `app` satisfying `predicate`."""
    found = []
    for comp in app.project.compositions:
        for layer in comp.layers:
            stack = [layer]
            while stack:
                group = stack.pop()
                for child in group:
                    if hasattr(child, "keyframes"):
                        if predicate(child):
                            found.append(child)
                    elif hasattr(child, "__iter__"):
                        stack.append(child)
    return found


def _first_leaf(app, predicate):
    hits = _leaves(app, predicate)
    assert hits, "no property matched"
    return hits[0]


class TestPropertyNameGuard:
    """Renaming is only legal for a child of an indexed group.

    A rename on any other property materialized it, and for synthetic
    MARKER / NO_VALUE properties that wrote a `LIST:tdbs` carrying no
    `cdat` and no `tdum`/`tduM`, which AE 2026 rejects outright ("file is
    damaged"). AE refuses the same write: "Can not set name this property,
    because parent is not an INDEXED_GROUP".
    """

    PT = SAMPLES_DIR / "property" / "property_types.aep"

    def test_marker_property_rename_rejected(self) -> None:
        app = parse_aep(self.PT)
        marker = _first_leaf(app, lambda p: p.match_name == "ADBE Marker")
        with pytest.raises(ValueError, match="indexed group"):
            marker.name = "my markers"

    def test_layer_style_no_value_rename_rejected(self) -> None:
        app = parse_aep(self.PT)
        gradient = _first_leaf(
            app, lambda p: p.match_name.endswith("outerGlow/gradient")
        )
        with pytest.raises(ValueError, match="indexed group"):
            gradient.name = "grad"

    def test_transform_group_rename_rejected(self) -> None:
        app = parse_aep(self.PT)
        group = app.project.compositions[0].layers[0]["ADBE Transform Group"]
        with pytest.raises(ValueError, match="indexed group"):
            group.name = "Xform"

    def test_transform_leaf_rename_rejected(self) -> None:
        app = parse_aep(self.PT)
        prop = _first_leaf(app, lambda p: p.match_name == "ADBE Opacity")
        with pytest.raises(ValueError, match="indexed group"):
            prop.name = "Alpha"

    def test_mask_rename_still_round_trips(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "mask.aep")
        renamed = 0
        for comp in app.project.compositions:
            for layer in comp.layers:
                for mask in layer.masks or []:
                    mask.name = "Kept Mask"
                    renamed += 1
        assert renamed
        out = tmp_path / "mask_rename.aep"
        app.project.save(out)
        names = [
            mask.name
            for comp in parse_aep(out).project.compositions
            for layer in comp.layers
            for mask in (layer.masks or [])
        ]
        assert names and all(name == "Kept Mask" for name in names)

    def test_effect_rename_still_round_trips(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "effects.aep")
        effect = None
        for comp in app.project.compositions:
            for layer in comp.layers:
                for candidate in layer.effects or []:
                    effect = candidate
                    break
                if effect is not None:
                    break
            if effect is not None:
                break
        assert effect is not None
        effect.name = "Renamed Effect"
        out = tmp_path / "effect_rename.aep"
        app.project.save(out)
        names = [
            fx.name
            for comp in parse_aep(out).project.compositions
            for layer in comp.layers
            for fx in (layer.effects or [])
        ]
        assert "Renamed Effect" in names

    def test_layer_rename_unaffected(self, tmp_path: Path) -> None:
        """A Layer is a PropertyBase but its name is a layer attribute."""
        app = parse_aep(self.PT)
        app.project.compositions[0].layers[0].name = "Still Renameable"
        out = tmp_path / "layer_rename.aep"
        app.project.save(out)
        renamed = parse_aep(out).project.compositions[0].layers[0].name
        assert renamed == "Still Renameable"


class TestDimensionsReadOnly:
    """`dimensions` drives how the value block is decoded.

    Writing it left py_aep misreading its own file: a 4-component colour
    saved with `dimensions = 5` read back as
    `[255.0, 255.0, 255.0, 255.0, 0.0]` while AE read the correct
    `[1, 1, 1, 1]`.
    """

    def test_dimensions_rejects_write(self) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "property_2D_position.aep")
        pos = _first_leaf(app, lambda p: p.match_name == "ADBE Position")
        before = pos.dimensions
        with pytest.raises(AttributeError, match="read-only"):
            pos.dimensions = 5
        assert pos.dimensions == before


class TestExpressionEnabledGuard:
    """`expression_enabled` must honour `can_set_expression`.

    AE throws for a hidden / non-expressible property ("Can not set
    expression with this property, because the property or a parent
    property is hidden"); py_aep accepted the write and materialized the
    property.
    """

    PT = SAMPLES_DIR / "property" / "property_types.aep"

    def test_rejected_when_expressions_impossible(self) -> None:
        app = parse_aep(self.PT)
        target = _first_leaf(app, lambda p: not p.can_set_expression)
        with pytest.raises(ValueError, match="cannot take an expression"):
            target.expression_enabled = True

    def test_allowed_when_expressions_possible(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "all_animated.aep")
        comp = app.project.compositions[0]
        rot = next(
            p for p in comp.av_layers[0].transform if p.match_name == "ADBE Rotate Z"
        )
        assert rot.can_set_expression
        rot.expression = "time * 2"
        rot.expression_enabled = True
        out = tmp_path / "expr_enabled.aep"
        app.project.save(out)
        comp2 = parse_aep(out).project.compositions[0]
        rot2 = next(
            p for p in comp2.av_layers[0].transform if p.match_name == "ADBE Rotate Z"
        )
        assert rot2.expression_enabled is True

    def test_disabling_never_raises(self) -> None:
        """Turning it off is legal whatever the property."""
        app = parse_aep(self.PT)
        for comp in app.project.compositions:
            for layer in comp.layers:
                for prop in layer.transform:
                    prop.expression_enabled = False


class TestTemporalEaseSetterWritesThrough:
    """Assigning `in_temporal_ease` / `out_temporal_ease` must persist.

    A user-built `KeyframeEase` is detached from any chunk, so the setter
    used to stash the list on the Python object and lose it on save -
    leaving no working way to set keyframe ease (ExtendScript's
    `setTemporalEaseAtKey` does persist).
    """

    BEZ = SAMPLES_DIR / "property" / "keyframe_bezier_multi_ease_1D.aep"

    @staticmethod
    def _animated(app):
        return _first_leaf(app, lambda p: bool(p.keyframes))

    def test_middle_keyframe_round_trips(self, tmp_path: Path) -> None:
        app = parse_aep(self.BEZ)
        prop = self._animated(app)
        keyframe = prop.keyframes[1]
        count = len(keyframe.in_temporal_ease)
        keyframe.in_temporal_ease = [KeyframeEase(0.0, 66.0) for _ in range(count)]
        keyframe.out_temporal_ease = [KeyframeEase(0.0, 12.0) for _ in range(count)]

        out = tmp_path / "ease_middle.aep"
        app.project.save(out)
        reparsed = self._animated(parse_aep(out)).keyframes[1]
        assert reparsed.in_temporal_ease[0].influence == pytest.approx(66.0)
        assert reparsed.out_temporal_ease[0].influence == pytest.approx(12.0)

    def test_boundary_keyframe_round_trips(self, tmp_path: Path) -> None:
        """The getter returns computed copies here; the write must not."""
        app = parse_aep(self.BEZ)
        prop = self._animated(app)
        first = prop.keyframes[0]
        first.in_interpolation_type = KeyframeInterpolationType.BEZIER
        first.out_interpolation_type = KeyframeInterpolationType.BEZIER
        count = len(first.out_temporal_ease)
        first.out_temporal_ease = [KeyframeEase(0.0, 44.0) for _ in range(count)]

        out = tmp_path / "ease_boundary.aep"
        app.project.save(out)
        reparsed = self._animated(parse_aep(out)).keyframes[0]
        assert reparsed.out_temporal_ease[0].influence == pytest.approx(44.0)

    def test_speed_round_trips(self, tmp_path: Path) -> None:
        app = parse_aep(self.BEZ)
        prop = self._animated(app)
        keyframe = prop.keyframes[1]
        count = len(keyframe.in_temporal_ease)
        keyframe.in_temporal_ease = [KeyframeEase(25.0, 50.0) for _ in range(count)]

        out = tmp_path / "ease_speed.aep"
        app.project.save(out)
        reparsed = self._animated(parse_aep(out)).keyframes[1]
        assert reparsed.in_temporal_ease[0].speed == pytest.approx(25.0)

    def test_wrong_length_rejected(self) -> None:
        app = parse_aep(self.BEZ)
        keyframe = self._animated(app).keyframes[1]
        with pytest.raises(ValueError, match="expects"):
            keyframe.in_temporal_ease = [KeyframeEase(0.0, 5.0)] * 99

    def test_non_ease_value_rejected(self) -> None:
        app = parse_aep(self.BEZ)
        keyframe = self._animated(app).keyframes[1]
        with pytest.raises(ValueError, match="KeyframeEase"):
            keyframe.in_temporal_ease = [0.5]  # type: ignore[list-item]


class TestMotionGraphicsPredicateAgreesWithBuilder:
    """`can_add_to_motion_graphics_template` must predict the builder.

    `ADBE Layer Source Alternate` reports a Slider control with
    `value is None`, so the predicate said `True` and the builder raised
    `TypeError: float() argument must be ... not 'NoneType'`.
    """

    EG = SAMPLES_DIR / "essential_graphics" / "base.aep"

    def test_every_addable_property_actually_adds(self) -> None:
        app = parse_aep(self.EG)
        checked = 0
        for comp in app.project.compositions:
            for prop in _leaves(app, lambda p: True):
                if prop.can_add_to_motion_graphics_template(comp):
                    prop.add_to_motion_graphics_template(comp)
                    checked += 1
        assert checked

    def test_value_less_slider_is_not_addable(self) -> None:
        app = parse_aep(self.EG)
        targets = _leaves(app, lambda p: p.match_name == "ADBE Layer Source Alternate")
        assert targets
        comp = app.project.compositions[0]
        for prop in targets:
            assert prop.value is None
            assert not prop.can_add_to_motion_graphics_template(comp)
