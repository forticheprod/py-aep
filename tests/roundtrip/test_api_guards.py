"""Guards added after the 2026-06 API fuzz campaign.

Each test pins a validation that prevents writing a .aep After Effects
cannot open (see scripts/dev/apifuzz/FINDINGS.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import get_comp

from py_aep import parse as parse_aep

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models"


class TestValueSetterOnKeyframedProperty:
    def test_set_value_raises_with_keyframes(self) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "keyframe_1D.aep")
        comp = app.project.compositions[0]
        prop = next(p for lyr in comp.layers for p in lyr.transform if p.keyframes)
        with pytest.raises(ValueError, match="keyframes"):
            prop.value = 12.0

    def test_set_value_on_static_property_still_works(self) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "all_animated.aep")
        comp = app.project.compositions[0]
        rot = next(
            p for p in comp.av_layers[0].transform if p.match_name == "ADBE Rotate Z"
        )
        assert not rot.keyframes
        rot.value = 45.0
        assert rot.value == 45.0


class TestSetAlternateSource:
    EG = SAMPLES_DIR / "essential_graphics" / "media_replacement.aep"

    @staticmethod
    def _override_leaf(app):
        host = next(
            c for c in app.project.compositions if c.name == "image_with_alpha 2"
        )
        layer = next(la for la in host.layers if la.essential_property_uuids)
        overrides = next(
            p for p in layer.properties if p.match_name == "ADBE Layer Overrides"
        )
        return layer, overrides.properties[0]

    def test_set_alternate_source_roundtrips(self, tmp_path: Path) -> None:
        app = parse_aep(self.EG)
        _, alt = self._override_leaf(app)
        master = next(
            c for c in app.project.compositions if c.name == "image_with_alpha"
        )
        alt.alternate_source = master
        out = tmp_path / "media.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        _, alt2 = self._override_leaf(app2)
        assert alt2.alternate_source is not None
        assert alt2.alternate_source.id == master.id

    def test_set_alternate_source_footage_autowraps(self, tmp_path: Path) -> None:
        # A FootageItem argument is wrapped in a host-sized comp (named
        # `{leaf name}_{unique footage basename}`) inside a root-level
        # `Media Replacement Comps` folder, matching AE's UI. Verified in AE
        # 2026: the wrapper's cdta clones the host comp and AE opens+resaves it.
        from py_aep.models.items.composition import CompItem

        app = parse_aep(self.EG)
        _, alt = self._override_leaf(app)
        host = next(
            c for c in app.project.compositions if c.name == "image_with_alpha 2"
        )
        gif = next(
            it
            for it in app.project.items.values()
            if it.name == "sequence_[001-003].gif"
        )
        before = set(app.project.items)
        alt.alternate_source = gif
        created = set(app.project.items) - before
        assert len(created) == 1  # only the wrapper comp

        out = tmp_path / "media.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        _, alt2 = self._override_leaf(app2)
        wrapper = alt2.alternate_source
        assert isinstance(wrapper, CompItem)
        assert wrapper.name == "image_with_alpha.png_sequence"
        assert wrapper.parent_folder.name == "Media Replacement Comps"
        assert (wrapper.width, wrapper.height) == (host.width, host.height)
        assert wrapper.duration == host.duration
        # cdta cloned from the host comp (not add_comp's fresh skeleton).
        assert wrapper._cdta.shutter_phase == host._cdta.shutter_phase
        assert wrapper._cdta.time_divisor == host._cdta.time_divisor
        assert wrapper.num_layers == 1
        assert wrapper.layers[0].source.name == "sequence_[001-003].gif"

    def test_set_alternate_source_reuses_wrapper_folder(self) -> None:
        # The `Media Replacement Comps` folder is reused, not duplicated.
        app = parse_aep(self.EG)
        _, alt = self._override_leaf(app)
        gif = next(
            it
            for it in app.project.items.values()
            if it.name == "sequence_[001-003].gif"
        )
        folders_before = [
            it
            for it in app.project.items.values()
            if type(it).__name__ == "FolderItem"
            and it.name == "Media Replacement Comps"
        ]
        alt.alternate_source = gif
        folders_after = [
            it
            for it in app.project.items.values()
            if type(it).__name__ == "FolderItem"
            and it.name == "Media Replacement Comps"
        ]
        assert len(folders_before) == 1
        assert len(folders_after) == 1  # reused, not a second folder

    def test_set_alternate_source_on_non_slot_raises(self) -> None:
        app = parse_aep(self.EG)
        layer, _ = self._override_leaf(app)
        master = next(
            c for c in app.project.compositions if c.name == "image_with_alpha"
        )
        pos = layer.transform.property("ADBE Position")
        with pytest.raises(ValueError, match="media replacement"):
            pos.alternate_source = master


class TestParentValidation:
    def _two_layers(self):
        app = parse_aep(SAMPLES_DIR / "property" / "all_animated.aep")
        comp = app.project.compositions[0]
        return app, comp.layers[0], comp.layers[1]

    def test_self_parent_raises(self) -> None:
        _, a, _ = self._two_layers()
        with pytest.raises(ValueError, match="itself"):
            a.parent = a

    def test_self_parent_with_jump_raises(self) -> None:
        _, a, _ = self._two_layers()
        with pytest.raises(ValueError, match="itself"):
            a.set_parent_with_jump(a)

    def test_cycle_raises(self) -> None:
        _, a, b = self._two_layers()
        a.set_parent_with_jump(b)
        with pytest.raises(ValueError, match="descendants"):
            b.set_parent_with_jump(a)

    def test_cycle_via_setter_raises(self) -> None:
        _, a, b = self._two_layers()
        a.set_parent_with_jump(b)
        with pytest.raises(ValueError, match="descendants"):
            b.parent = a

    def test_cross_comp_parent_raises(self) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        src = get_comp(app.project, "type_null").layers[0]
        other = get_comp(app.project, "type_camera").layers[0]
        with pytest.raises(ValueError, match="same composition"):
            src.set_parent_with_jump(other)
        with pytest.raises(ValueError, match="same composition"):
            src.parent = other

    def test_parenting_animated_layer_matches_extendscript(self) -> None:
        """ExtendScript remaps every position keyframe into the new
        parent's space and leaves keyframed anchor / scale / rotation
        untouched. Expected values measured live in AE 2026 (gt_probe1
        and gt_probe_anchor)."""
        app = parse_aep(SAMPLES_DIR / "property" / "all_animated.aep")
        comp = lyr = None
        for c in app.project.compositions:
            for la in c.layers:
                if la.name == "XF":
                    comp, lyr = c, la
        assert lyr is not None
        anchor = next(p for p in lyr.transform if p.match_name == "ADBE Anchor Point")
        anchor.set_value_at_time(0.0, [10.0, 20.0, 0.0])
        anchor.set_value_at_time(1.0, [70.0, 80.0, 0.0])
        null = comp.add_null()
        next(p for p in null.transform if p.match_name == "ADBE Position").value = [
            10.0,
            20.0,
            0.0,
        ]
        next(p for p in null.transform if p.match_name == "ADBE Rotate Z").value = 30.0

        lyr.parent = null

        # Anchor keyframes are in layer-source space; AE never touches them.
        assert [k.value for k in anchor.keyframes] == [
            [10.0, 20.0, 0.0],
            [70.0, 80.0, 0.0],
        ]

        pos = next(p for p in lyr.transform if p.match_name == "ADBE Position")
        expected = [
            [117.942286340599, 24.2820323027551, 0.0],
            [564.352447854375, -2.51288694035714, 50.0],
        ]
        for kf, exp in zip(pos.keyframes, expected):
            assert kf.value == pytest.approx(exp, abs=1e-6)
        scale = next(p for p in lyr.transform if p.match_name == "ADBE Scale")
        rot = next(p for p in lyr.transform if p.match_name == "ADBE Rotate Z")
        assert [k.value for k in scale.keyframes] == [
            [50.0, 50.0, 100.0],
            [150.0, 150.0, 100.0],
        ]
        assert [k.value for k in rot.keyframes] == [0.0, 90.0]


class TestUnicodeNames:
    """AE 2026 stores layer / solid names as UTF-8 in the fixed-width
    legacy fields (measured via gt_unicode_names.aep), so any unicode
    name round-trips."""

    def test_layer_rename_unicode_roundtrips(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "all_animated.aep")
        lyr = app.project.compositions[0].layers[0]
        lyr.name = "测试✨layer"
        out = tmp_path / "u.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        assert app2.project.compositions[0].layers[0].name == "测试✨layer"

    def test_add_text_cjk_roundtrips(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        comp = get_comp(app.project, "type_text")
        comp.add_text("你好")
        out = tmp_path / "t.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        comp2 = get_comp(app2.project, "type_text")
        assert comp2.layers[0].name == "你好"

    def test_add_solid_emoji_name_roundtrips(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        comp = get_comp(app.project, "type_null")
        comp.add_solid([1.0, 0.0, 0.0], "solid \U0001f600")
        out = tmp_path / "s.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        comp2 = get_comp(app2.project, "type_null")
        assert comp2.layers[0].name == "solid \U0001f600"

    def test_text_document_content_supports_unicode(self, tmp_path: Path) -> None:
        """Text CONTENT goes through the COS layer which handles any
        unicode; only legacy name fields are restricted."""
        app = parse_aep(SAMPLES_DIR / "layer" / "type.aep")
        comp = get_comp(app.project, "type_text")
        prop = next(
            p for p in comp.text_layers[0].text if p.match_name == "ADBE Text Document"
        )
        doc = prop.value
        doc.text = "你好 \U0001f600"
        prop.value = doc
        out = tmp_path / "cjk_text.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        comp2 = get_comp(app2.project, "type_text")
        prop2 = next(
            p for p in comp2.text_layers[0].text if p.match_name == "ADBE Text Document"
        )
        assert prop2.value.text == "你好 \U0001f600"


class TestLongKeyframeTimes:
    """Keyframe times are a signed 32-bit count of internal-timebase
    units (measured via gt_long_keys.aep), so hour-range times work."""

    def test_far_keyframe_roundtrips(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "keyframe_1D.aep")
        comp = app.project.compositions[0]
        prop = next(p for lyr in comp.layers for p in lyr.transform if p.keyframes)
        prop.set_value_at_time(9999.0, prop.keyframes[0].value)
        out = tmp_path / "far.aep"
        app.project.save(out)
        app2 = parse_aep(out)
        comp2 = app2.project.compositions[0]
        prop2 = next(p for lyr in comp2.layers for p in lyr.transform if p.keyframes)
        assert prop2.keyframes[-1].time == pytest.approx(9999.0)

    def test_nearby_keyframe_still_works(self, tmp_path: Path) -> None:
        app = parse_aep(SAMPLES_DIR / "property" / "keyframe_1D.aep")
        comp = app.project.compositions[0]
        prop = next(p for lyr in comp.layers for p in lyr.transform if p.keyframes)
        prop.set_value_at_time(2.0, prop.keyframes[0].value)
        app.project.save(tmp_path / "ok.aep")


class TestAtomicSave:
    def test_failed_save_leaves_no_file(self, tmp_path: Path, monkeypatch) -> None:
        import py_aep.models.project as project_mod

        app = parse_aep(SAMPLES_DIR / "folder" / "folder.aep")

        def boom(*args, **kwargs):
            raise RuntimeError("simulated write failure")

        monkeypatch.setattr(project_mod, "write_aep", boom)
        target = tmp_path / "out.aep"
        with pytest.raises(RuntimeError):
            app.project.save(target)
        assert not target.exists()
        assert list(tmp_path.iterdir()) == []
