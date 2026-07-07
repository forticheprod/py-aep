"""Tests for adding properties to a composition's Essential Graphics panel
(Motion Graphics template controllers)."""

from __future__ import annotations

import io
from pathlib import Path

from helpers import get_comp, parse_project_fresh

from py_aep import parse as parse_aep
from py_aep.binary.chunk import ListChunk, write_chunk
from py_aep.enums import PropertyValueType

EG_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "essential_graphics"
)
BASE = EG_DIR / "base.aep"


def _primary(project) -> object:
    # base.aep: comp 'primary' (id 1) holds one solid layer (layer_id 15).
    return get_comp(project, "primary")


def _opacity(comp) -> object:
    layer = comp.layers[0]
    return next(p for p in layer.transform if p.match_name == "ADBE Opacity")


def _effect_param(comp, effect_mn: str, param_mn: str, layer_index: int = 0):
    effects = next(
        p
        for p in comp.layers[layer_index].properties
        if p.match_name == "ADBE Effect Parade"
    )
    effect = next(p for p in effects.properties if p.match_name == effect_mn)
    return next(p for p in effect.properties if p.match_name == param_mn)


def _cif3_cctls(comp) -> list[ListChunk]:
    cif3 = next(
        c
        for c in comp._item_list.chunks
        if isinstance(c, ListChunk) and c.list_type == "CIF3"
    )
    return [
        c for c in cif3.chunks if isinstance(c, ListChunk) and c.list_type == "CCtl"
    ]


def _chunk_bytes(chunk) -> bytes:
    buf = io.BytesIO()
    write_chunk(buf, chunk)
    return buf.getvalue()


def _cctl_count(comp) -> dict[str, int]:
    """Number of CCtl children per CIF container of a comp."""
    counts: dict[str, int] = {}
    for cif in comp._item_list.chunks:
        if isinstance(cif, ListChunk) and cif.list_type in ("CIFO", "CIF2", "CIF3"):
            counts[cif.list_type] = sum(
                1
                for c in cif.chunks
                if isinstance(c, ListChunk) and c.list_type == "CCtl"
            )
    return counts


class TestCanAddProperty:
    def test_opacity_can_be_added(self) -> None:
        comp = _primary(parse_project_fresh(BASE))
        assert _opacity(comp).can_add_to_motion_graphics_template(comp) is True

    def test_position_cannot_be_added(self) -> None:
        # Position is a 2D/3D point, not a supported controller type.
        comp = _primary(parse_project_fresh(BASE))
        pos = next(
            p for p in comp.layers[0].transform if p.match_name == "ADBE Position"
        )
        assert pos.can_add_to_motion_graphics_template(comp) is False

    def test_wrong_comp_cannot_be_added(self) -> None:
        project = parse_project_fresh(BASE)
        comp = _primary(project)
        other = get_comp(project, "main")
        # The property's layer lives in 'primary', not 'main'.
        assert _opacity(comp).can_add_to_motion_graphics_template(other) is False

    def test_already_added_reports_false(self) -> None:
        comp = _primary(parse_project_fresh(BASE))
        op = _opacity(comp)
        assert op.add_to_motion_graphics_template(comp) is True
        assert op.can_add_to_motion_graphics_template(comp) is False

    def test_mask_property_can_be_added(self) -> None:
        # Mask Opacity lives under ADBE Mask Atom inside the indexed Mask
        # Parade: the mask atom node carries its 0-based parade position
        # (AE 2026 headless run), so the path is unambiguous and addable.
        project = parse_project_fresh(EG_DIR.parent / "property" / "mask_add.aep")
        comp = project.compositions[0]
        mask = comp.layers[0].masks[0]
        mask_opacity = next(
            p for p in mask.properties if p.match_name == "ADBE Mask Opacity"
        )
        assert mask_opacity.property_value_type == PropertyValueType.OneD
        assert mask_opacity.can_add_to_motion_graphics_template(comp) is True

    def test_added_effect_param_reports_false(self) -> None:
        # The Slider Control param is already exposed in this fixture; the
        # (match_name, prop_index) pair comparison must catch it.
        project = parse_project_fresh(EG_DIR / "slider_controller.aep")
        comp = get_comp(project, "primary")
        slider = _effect_param(comp, "ADBE Slider Control", "ADBE Slider Control-0001")
        assert slider.property_value_type == PropertyValueType.OneD
        assert slider.can_add_to_motion_graphics_template(comp) is False

    def test_dropdown_param_cannot_be_added(self) -> None:
        # A dropdown param is 1-D but AE exposes it as a type-13 Dropdown
        # controller (menu entries included), which py_aep does not build.
        project = parse_project_fresh(EG_DIR / "dropdown_controller.aep")
        comp = get_comp(project, "primary")
        effects = next(
            p for p in comp.layers[0].properties if p.match_name == "ADBE Effect Parade"
        )
        pseudo = next(
            p for p in effects.properties if p.match_name.startswith("Pseudo/")
        )
        menu = pseudo.properties[0]
        assert menu.can_add_to_motion_graphics_template(comp) is False


class TestAddProperty:
    def test_add_registers_controller(self) -> None:
        comp = _primary(parse_project_fresh(BASE))
        op = _opacity(comp)
        assert op.add_to_motion_graphics_template_as(comp, "My Opacity") is True
        assert comp.motion_graphics_template_controller_names == ["My Opacity"]
        ctrl = comp.motion_graphics_controllers[0]
        assert ctrl.controller_type == 2  # Slider
        assert ctrl.source_comp_id == comp.id
        assert ctrl.source_layer_id == comp.layers[0]._ldta.layer_id
        assert [r.match_name for r in ctrl.source_property_path] == [
            "ADBE Transform Group",
            "ADBE Opacity",
        ]

    def test_add_bumps_every_cif_container(self) -> None:
        comp = _primary(parse_project_fresh(BASE))
        assert set(_cctl_count(comp).values()) == {0}
        _opacity(comp).add_to_motion_graphics_template(comp)
        # AE keeps the CIFO/CIF2/CIF3 copies in sync.
        assert _cctl_count(comp) == {"CIFO": 1, "CIF2": 1, "CIF3": 1}

    def test_add_default_name_is_property_name(self) -> None:
        comp = _primary(parse_project_fresh(BASE))
        op = _opacity(comp)
        assert op.add_to_motion_graphics_template(comp) is True
        assert comp.motion_graphics_template_controller_names == [op.name]

    def test_add_returns_false_when_already_added(self) -> None:
        comp = _primary(parse_project_fresh(BASE))
        op = _opacity(comp)
        assert op.add_to_motion_graphics_template(comp) is True
        assert op.add_to_motion_graphics_template(comp) is False
        assert len(comp.motion_graphics_controllers) == 1

    def test_add_survives_roundtrip(self, tmp_path: Path) -> None:
        project = parse_project_fresh(BASE)
        comp = _primary(project)
        _opacity(comp).add_to_motion_graphics_template_as(comp, "Fade")
        out = tmp_path / "mgt.aep"
        project.save(out)
        comp2 = _primary(parse_aep(out).project)
        assert comp2.motion_graphics_template_controller_names == ["Fade"]
        ctrl = comp2.motion_graphics_controllers[0]
        assert ctrl.controller_type == 2
        assert ctrl.source_comp_id == comp2.id
        assert ctrl.source_layer_id == comp2.layers[0]._ldta.layer_id
        assert [r.match_name for r in ctrl.source_property_path] == [
            "ADBE Transform Group",
            "ADBE Opacity",
        ]

    def test_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        project = parse_project_fresh(BASE)
        comp = _primary(project)
        _opacity(comp).add_to_motion_graphics_template_as(comp, "Fade")
        out = tmp_path / "mgt.aep"
        project.save(out)
        out2 = tmp_path / "mgt2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()


class TestEffectParamPaths:
    """The CPrp index model, pinned against AE's own stored path JSONs."""

    def _stored_json(self, comp, ctrl_name: str) -> str:
        # The CPrp JSON of the named controller, straight from the chunks.
        for cctl in _cif3_cctls(comp):
            cps2 = next(c for c in cctl.chunks if getattr(c, "list_type", "") == "CpS2")
            name = next(c.value for c in cps2.chunks if c.chunk_type == "Utf8")
            if name != ctrl_name:
                continue
            cprp = next(c for c in cctl.chunks if getattr(c, "list_type", "") == "CPrp")
            return next(c.value for c in cprp.chunks if c.chunk_type == "Utf8")
        raise AssertionError(f"controller {ctrl_name!r} not found")

    def _py_json(self, prop) -> str:
        from py_aep.resolvers.motion_graphics import (
            _path_json,
            _source_property_path,
        )

        resolved = _source_property_path(prop)
        assert resolved is not None
        return _path_json(resolved[0])

    def test_second_effect_param_matches_ae(self) -> None:
        # Slider Control is the SECOND effect (after Fill) -> parade index 1;
        # its visible param sits at parT slot 1 (slot 0 is the hidden header).
        project = parse_project_fresh(EG_DIR / "slider_controller.aep")
        comp = get_comp(project, "primary")
        prop = _effect_param(comp, "ADBE Slider Control", "ADBE Slider Control-0001")
        assert self._py_json(prop) == self._stored_json(comp, "Intensity")

    def test_first_effect_deep_param_matches_ae(self) -> None:
        # Fill is the only effect -> parade index 0; Fill-0002 sits at parT
        # slot 3 (after the header, -0001 and -0007).
        project = parse_project_fresh(EG_DIR / "fill_color_added.aep")
        comp = get_comp(project, "primary")
        prop = _effect_param(comp, "ADBE Fill", "ADBE Fill-0002")
        assert self._py_json(prop) == self._stored_json(comp, "Fill Color")

    def test_both_orders_in_one_stack_match_ae(self) -> None:
        project = parse_project_fresh(EG_DIR / "group_controller.aep")
        comp = next(c for c in project.compositions if c.motion_graphics_controllers)
        blur = _effect_param(comp, "ADBE Gaussian Blur 2", "ADBE Gaussian Blur 2-0001")
        fill = _effect_param(comp, "ADBE Fill", "ADBE Fill-0002")
        assert self._py_json(blur) == self._stored_json(
            comp, "Gaussian Blur Blurriness"
        )
        assert self._py_json(fill) == self._stored_json(comp, "Fill Color")

    def test_effect_param_add_roundtrips(self, tmp_path: Path) -> None:
        # Fill-0006 (Fill Opacity) is not exposed in the slider fixture:
        # Fill -> parade index 0, -0006 -> parT slot 4.
        project = parse_project_fresh(EG_DIR / "slider_controller.aep")
        comp = get_comp(project, "primary")
        prop = _effect_param(comp, "ADBE Fill", "ADBE Fill-0006")
        assert prop.can_add_to_motion_graphics_template(comp) is True
        assert prop.add_to_motion_graphics_template_as(comp, "Fill Opacity") is True
        out = tmp_path / "effect.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "primary")
        ctrl = next(
            c for c in comp2.motion_graphics_controllers if c.name == "Fill Opacity"
        )
        assert [(r.match_name, r.prop_index) for r in ctrl.source_property_path] == [
            ("ADBE Effect Parade", None),
            ("ADBE Fill", 0),
            ("ADBE Fill-0006", 4),
        ]


class TestIndexAwareResolution:
    def test_controller_path_resolves_to_exact_param(self) -> None:
        from py_aep.resolvers.essential_properties import _walk_source_property

        project = parse_project_fresh(EG_DIR / "multiple_controllers.aep")
        comp = get_comp(project, "primary")
        layer = comp.layers[0]
        ctrl = next(
            c for c in comp.motion_graphics_controllers if c.name == "Background Color"
        )
        resolved = _walk_source_property(layer, ctrl.source_property_path)
        expected = _effect_param(comp, "ADBE Fill", "ADBE Fill-0002")
        assert resolved is expected


class TestIndexedGroupControllers:
    """indexed_group_controllers.aep: 8 controllers AE 2026 created on
    masks, shape contents, text animators and effect topic-group params.
    Every stored path must resolve, and py must rebuild it identically."""

    FIXTURE = EG_DIR / "indexed_group_controllers.aep"

    def _comp(self, project):
        return next(c for c in project.compositions if c.motion_graphics_controllers)

    def test_every_ae_path_roundtrips_through_py(self) -> None:
        # Bidirectional check per controller: resolve AE's stored path to
        # the source property (read side), then rebuild the path from that
        # property (write side) and compare with what AE stored.
        from py_aep.resolvers.essential_properties import _walk_source_property
        from py_aep.resolvers.motion_graphics import _source_property_path

        project = parse_project_fresh(self.FIXTURE)
        comp = self._comp(project)
        assert len(comp.motion_graphics_controllers) == 8
        for ctrl in comp.motion_graphics_controllers:
            layer = comp.layers_by_id[ctrl.source_layer_id]
            resolved = _walk_source_property(layer, ctrl.source_property_path)
            assert resolved is not None, ctrl.name
            rebuilt = _source_property_path(resolved)
            assert rebuilt is not None, ctrl.name
            assert [(n.match_name, n.prop_index) for n in rebuilt[0]] == [
                (r.match_name, r.prop_index) for r in ctrl.source_property_path
            ], ctrl.name

    def test_sibling_controllers_resolve_to_distinct_objects(self) -> None:
        # The whole point of the indices: same match names, different
        # siblings. Mask 1/2 opacities, shape fill 1/2, animator 1/2.
        from py_aep.resolvers.essential_properties import _walk_source_property

        project = parse_project_fresh(self.FIXTURE)
        comp = self._comp(project)
        by_name = {c.name: c for c in comp.motion_graphics_controllers}
        for a_name, b_name in (
            ("Mask1 Opacity", "Mask2 Opacity"),
            ("Fill Color 1", "Fill Color 2"),
            ("Anim Opacity 1", "Anim Opacity 2"),
        ):
            a_ctrl, b_ctrl = by_name[a_name], by_name[b_name]
            layer = comp.layers_by_id[a_ctrl.source_layer_id]
            a = _walk_source_property(layer, a_ctrl.source_property_path)
            b = _walk_source_property(layer, b_ctrl.source_property_path)
            assert a is not None and b is not None
            assert a.match_name == b.match_name
            assert a is not b

    def test_add_indexed_sibling_roundtrips(self, tmp_path: Path) -> None:
        # Mask 2's Expansion is not exposed yet: adding it must store the
        # mask atom's positional index and survive a save/reparse.
        project = parse_project_fresh(self.FIXTURE)
        comp = self._comp(project)
        solid = next(lyr for lyr in comp.layers if lyr.masks)
        expansion = next(
            p for p in solid.masks[1].properties if p.match_name == "ADBE Mask Offset"
        )
        assert expansion.can_add_to_motion_graphics_template(comp) is True
        assert (
            expansion.add_to_motion_graphics_template_as(comp, "Mask2 Expansion")
            is True
        )
        out = tmp_path / "indexed.aep"
        project.save(out)
        comp2 = self._comp(parse_aep(out).project)
        ctrl = next(
            c for c in comp2.motion_graphics_controllers if c.name == "Mask2 Expansion"
        )
        assert [(r.match_name, r.prop_index) for r in ctrl.source_property_path] == [
            ("ADBE Mask Parade", None),
            ("ADBE Mask Atom", 1),
            ("ADBE Mask Offset", None),
        ]

    def test_effect_topic_group_param_matches_ae(self) -> None:
        # Fractal Noise's Scale (-0010) sits inside the "Transform" topic
        # group in the UI; AE stores the flat parT slot (10) and no
        # topic-group node - py must rebuild exactly that.
        from py_aep.resolvers.motion_graphics import _source_property_path

        project = parse_project_fresh(self.FIXTURE)
        comp = self._comp(project)
        solid = next(lyr for lyr in comp.layers if lyr.masks)
        effects = next(
            p for p in solid.properties if p.match_name == "ADBE Effect Parade"
        )
        fx = next(p for p in effects.properties if p.match_name == "ADBE Fractal Noise")
        prop = next(
            p for p in fx.properties if p.match_name == "ADBE Fractal Noise-0010"
        )
        resolved = _source_property_path(prop)
        assert resolved is not None
        assert [(n.match_name, n.prop_index) for n in resolved[0]] == [
            ("ADBE Effect Parade", None),
            ("ADBE Fractal Noise", 0),
            ("ADBE Fractal Noise-0010", 10),
        ]
        # Already exposed by the AE run, so re-adding reports False.
        assert prop.can_add_to_motion_graphics_template(comp) is False


class TestAddLayerMediaReplacement:
    MEDIA = EG_DIR / "media_replacement.aep"

    def test_solid_layer_cannot_be_added(self) -> None:
        # base.aep's only 'primary' layer is a solid: not a Media Replacement
        # layer, so it is not addable.
        comp = _primary(parse_project_fresh(BASE))
        layer = comp.layers[0]
        assert layer.can_add_to_motion_graphics_template(comp) is False

    def test_already_exposed_layer_reports_false(self) -> None:
        project = parse_project_fresh(self.MEDIA)
        comp = get_comp(project, "image_with_alpha")
        assert comp.layers[0].can_add_to_motion_graphics_template(comp) is False

    def test_add_precomp_layer_roundtrips(self, tmp_path: Path) -> None:
        project = parse_project_fresh(self.MEDIA)
        comp = get_comp(project, "image_with_alpha 2")
        layer = comp.layers[0]
        assert layer.can_add_to_motion_graphics_template(comp) is True
        assert layer.add_to_motion_graphics_template(comp) is True
        assert layer.can_add_to_motion_graphics_template(comp) is False
        out = tmp_path / "media.aep"
        project.save(out)
        comp2 = get_comp(parse_aep(out).project, "image_with_alpha 2")
        ctrl = comp2.motion_graphics_controllers[0]
        assert ctrl.controller_type == 14
        assert ctrl.name == layer.name
        assert ctrl.source_comp_id == comp2.id
        assert ctrl.source_layer_id == comp2.layers[0]._ldta.layer_id
        assert [r.match_name for r in ctrl.source_property_path] == [
            "ADBE Source Options Group",
            "ADBE Layer Source Alternate",
        ]
        # The decoded source-media fields survive the round-trip.
        cctl = _cif3_cctls(comp2)[0]
        by_type = {c.chunk_type: c for c in cctl.chunks}
        assert by_type["CSMw"].value == 640
        assert by_type["CSMh"].value == 346
        assert by_type["CSMs"].value == 0
        assert by_type["CSMe"].value == 720000
        assert by_type["CSMt"].value == 23976

    def test_builder_matches_fixture_bytes(self) -> None:
        # Byte parity: rebuilding the fixture's own controller from its
        # decoded inputs must reproduce AE's CCtl exactly.
        project = parse_project_fresh(self.MEDIA)
        comp = get_comp(project, "image_with_alpha")
        fixture_cctl = _cif3_cctls(comp)[0]
        by_type = {c.chunk_type: c for c in fixture_cctl.chunks}
        utf8s = [c for c in fixture_cctl.chunks if c.chunk_type == "Utf8"]
        uuid_str = utf8s[0].value
        thumbnail = utf8s[3].value
        cprp = next(
            c for c in fixture_cctl.chunks if getattr(c, "list_type", "") == "CPrp"
        )
        path_json = next(c.value for c in cprp.chunks if c.chunk_type == "Utf8")

        from py_aep.binary.mutations import build_media_cctl

        built, _name, _ctyp = build_media_cctl(
            "image_with_alpha.png",
            uuid_str,
            640,
            346,
            0,
            720000,
            23976,
            thumbnail,
            2,
            14,
            path_json,
        )
        assert _chunk_bytes(built) == _chunk_bytes(fixture_cctl)
        assert by_type["CSMd"].value == 2
