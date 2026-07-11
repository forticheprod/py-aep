"""Tests for AE preference file parsing and the Preferences model."""

from __future__ import annotations

from pathlib import Path

import pytest

import py_aep
from py_aep.enums import PREFType
from py_aep.parsers.prefs import (
    PrefsFile,
    decode_pref_bool,
    decode_pref_number,
    decode_pref_string,
    find_prefs_file,
)

MACHINE = PREFType.PREF_Type_MACHINE_SPECIFIC
INDEP = PREFType.PREF_Type_MACHINE_INDEPENDENT
INDEP_COMP = PREFType.PREF_Type_MACHINE_INDEPENDENT_COMPOSITION

_MACHINE_PREFS = """\
# Text File Version 1.1
# After Effects Preferences

["Numbers Section"]
\t"Quoted Float" = "30.000000"
\t"Quoted Int" = "999"
\t"Raw Byte" = 01
\t"Raw Word" = 00FF

["Output File Name Template Presets Section v6"]
\t"000" = "Comp Name"00"[compName].[fileExtension]"00
\t"001" = "Comp Folder and Name"00"[compName]/[compName].[fileExtension]"00

["Project Pref Section"]
\t"Project Settings Depth" = "1"
\t"Project Settings Time Display Format" = 01000101180000001000000001000000

["Renderer Preference Section"]
\t"New Composition Default" = "ADBE Calder"
"""

_INDEP_PREFS = """\
# Text File Version 1.1
# After Effects Preferences

["Auto Save"]
\t"Auto Save Folder" = "C:\\Users\\test\\Documents"

["General Section"]
\t"Create New Layers At Time Zero" = 00

["Import Options Preference Section"]
\t"Import Options Default NTSC Dropframe" = 01
\t"Import Options Default Sequence FPS" = "25.000000"
\t"Off Flag" = 00
\t"Quoted False" = "0"
\t"Quoted True" = "1"

["Label Preference Indices Section 5"]
\t"Camera Label Index 2" = "10"
\t"Comp Label Index 2" = "9"
\t"Folder Label Index 2" = "12"
\t"Light Label Index 2" = "11"
\t"Null Label Index" = "6"
\t"Shape Label Index 2" = "13"
\t"Solid Label Index 2" = "4"
\t"Text Label Index" = "3"
\t"Video Label Index 2" = "7"

["Strings Section"]
\t"Bullet" = "HD  "E280A2"  1920x1080"
\t"Long Value" = "part one"\\
\t\t" and part two"

["Template Project"]
\t"New Project Solids Folder" = "Solides"
"""

_INDEP_COMP_PREFS = """\
# Text File Version 1.1
# After Effects Preferences

["Composition Pref Section"]
\t"Composition Settings - Constrain Proportions" = 01
\t"New Composition - Start Timecode Scale" = "2997.000000"

["Composition Preset Names Section v11"]
\t"000" = "HD  "E280A2"  1920x1080 "E280A2" 24 fps"
\t"001" = "-"
\t"002" = "HD  "E280A2"  1920x1080 "E280A2" 29.97 fps"
\t"003" = "HDV  "E280A2"  1440x1080 (1.33) "E280A2" 25 fps"

["Composition Presets Section v11"]
\t"000" = 078004"8"001800000000000100000001
\t"001" = 00000000000000000000000000000000
\t"002" = 078004"8"001DF8"R"0000000100000001
\t"003" = 05A004"8"001900000000000400000003
"""


@pytest.fixture()
def prefs_dir(tmp_path: Path) -> Path:
    (tmp_path / "Adobe After Effects 26.0 Prefs.txt").write_text(
        _MACHINE_PREFS, encoding="utf-8"
    )
    (tmp_path / "Adobe After Effects 26.0 Prefs-indep-general.txt").write_text(
        _INDEP_PREFS, encoding="utf-8"
    )
    (tmp_path / "Adobe After Effects 26.0 Prefs-indep-composition.txt").write_text(
        _INDEP_COMP_PREFS, encoding="utf-8"
    )
    return tmp_path


class TestPrefsFileParsing:
    def test_sections_and_keys(self) -> None:
        prefs = PrefsFile.from_text(_MACHINE_PREFS)
        assert (
            prefs.get_raw("Renderer Preference Section", "New Composition Default")
            == '"ADBE Calder"'
        )
        assert prefs.get_raw("Numbers Section", "Raw Byte") == "01"

    def test_missing_returns_none(self) -> None:
        prefs = PrefsFile.from_text(_MACHINE_PREFS)
        assert prefs.get_raw("Numbers Section", "Nope") is None
        assert prefs.get_raw("Nope Section", "Quoted Int") is None

    def test_continuation_lines(self) -> None:
        prefs = PrefsFile.from_text(_INDEP_PREFS)
        raw = prefs.get_raw("Strings Section", "Long Value")
        assert raw is not None
        assert decode_pref_string(raw) == "part one and part two"

    def test_find_prefs_file(self, prefs_dir: Path) -> None:
        machine = find_prefs_file(prefs_dir, MACHINE)
        assert machine is not None and machine.name.endswith(" Prefs.txt")
        indep = find_prefs_file(prefs_dir, INDEP)
        assert indep is not None and indep.name.endswith("-indep-general.txt")
        assert (
            find_prefs_file(prefs_dir, PREFType.PREF_Type_MACHINE_SPECIFIC_TEXT) is None
        )


class TestValueDecoding:
    def test_number_forms(self) -> None:
        assert decode_pref_number('"999"') == 999
        assert isinstance(decode_pref_number('"999"'), int)
        assert decode_pref_number('"30.000000"') == pytest.approx(30.0)
        assert decode_pref_number("01") == 1
        assert decode_pref_number("00FF") == 255

    def test_bool_forms(self) -> None:
        assert decode_pref_bool("01") is True
        assert decode_pref_bool("00") is False
        assert decode_pref_bool('"1"') is True
        assert decode_pref_bool('"0"') is False

    def test_string_hex_escapes(self) -> None:
        # AE writes non-ASCII characters as hex escapes outside quotes.
        assert decode_pref_string('"HD  "E280A2"  1920x1080"') == "HD  •  1920x1080"

    def test_string_backslashes_preserved(self) -> None:
        assert (
            decode_pref_string('"C:\\Users\\test\\Documents"')
            == "C:\\Users\\test\\Documents"
        )


class TestPreferences:
    def test_get_number(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        assert prefs.get_pref_as_number("Numbers Section", "Quoted Int") == 999
        assert prefs.get_pref_as_number(
            "Import Options Preference Section",
            "Import Options Default Sequence FPS",
            INDEP,
        ) == pytest.approx(25.0)

    def test_get_bool(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        section = "Import Options Preference Section"
        assert prefs.get_pref_as_bool(section, "Quoted True", INDEP) is True
        assert prefs.get_pref_as_bool(section, "Quoted False", INDEP) is False
        assert (
            prefs.get_pref_as_bool(
                section, "Import Options Default NTSC Dropframe", INDEP
            )
            is True
        )
        assert prefs.get_pref_as_bool(section, "Off Flag", INDEP) is False

    def test_get_string(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        assert (
            prefs.get_pref_as_string(
                "Renderer Preference Section", "New Composition Default"
            )
            == "ADBE Calder"
        )
        assert (
            prefs.get_pref_as_string("Auto Save", "Auto Save Folder", INDEP)
            == "C:\\Users\\test\\Documents"
        )

    def test_pref_type_routing(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        # The key exists in the composition file only.
        assert prefs.get_pref_as_bool(
            "Composition Pref Section",
            "Composition Settings - Constrain Proportions",
            INDEP_COMP,
        )
        with pytest.raises(KeyError):
            prefs.get_pref_as_bool(
                "Composition Pref Section",
                "Composition Settings - Constrain Proportions",
                MACHINE,
            )

    def test_missing_key_raises_or_defaults(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        with pytest.raises(KeyError):
            prefs.get_pref_as_number("Numbers Section", "Nope")
        assert prefs.get_pref_as_number("Numbers Section", "Nope", default=7) == 7
        assert prefs.get_pref_as_string("Numbers Section", "Nope", default="x") == "x"
        assert prefs.get_pref_as_bool("Numbers Section", "Nope", default=True) is True

    def test_have_pref(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        assert prefs.have_pref("Numbers Section", "Quoted Int") is True
        assert prefs.have_pref("Numbers Section", "Nope") is False

    def test_no_prefs_dir(self) -> None:
        prefs = py_aep.Preferences()
        with pytest.raises(KeyError):
            prefs.get_pref_as_number("Numbers Section", "Quoted Int")
        assert prefs.get_pref_as_number("A", "B", default=5) == 5
        assert prefs.have_pref("A", "B") is False
        # Overrides work without any preference files.
        prefs.set_pref_as_number("A", "B", 12)
        assert prefs.get_pref_as_number("A", "B") == 12

    def test_overrides_take_precedence(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        prefs.set_pref_as_number("Numbers Section", "Quoted Int", 5)
        assert prefs.get_pref_as_number("Numbers Section", "Quoted Int") == 5
        prefs.set_pref_as_string(
            "Renderer Preference Section", "New Composition Default", "ADBE Escher"
        )
        assert (
            prefs.get_pref_as_string(
                "Renderer Preference Section", "New Composition Default"
            )
            == "ADBE Escher"
        )
        prefs.set_pref_as_bool("Numbers Section", "Raw Byte", False)
        assert prefs.get_pref_as_bool("Numbers Section", "Raw Byte") is False

    def test_override_cross_type_reads(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        prefs.set_pref_as_number("Numbers Section", "Quoted Int", 5)
        assert prefs.get_pref_as_string("Numbers Section", "Quoted Int") == "5"
        assert prefs.get_pref_as_bool("Numbers Section", "Quoted Int") is True

    def test_overrides_never_touch_disk(self, prefs_dir: Path) -> None:
        target = prefs_dir / "Adobe After Effects 26.0 Prefs.txt"
        before = target.read_bytes()
        prefs = py_aep.Preferences(prefs_dir)
        prefs.set_pref_as_number("Numbers Section", "Quoted Int", 5)
        prefs.delete_pref("Numbers Section", "Raw Byte")
        assert target.read_bytes() == before

    def test_delete_pref_masks_file_value(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        prefs.delete_pref("Numbers Section", "Quoted Int")
        assert prefs.have_pref("Numbers Section", "Quoted Int") is False
        with pytest.raises(KeyError):
            prefs.get_pref_as_number("Numbers Section", "Quoted Int")
        assert prefs.get_pref_as_number("Numbers Section", "Quoted Int", default=1) == 1

    def test_reload_discards_overrides(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        prefs.set_pref_as_number("Numbers Section", "Quoted Int", 5)
        prefs.delete_pref("Numbers Section", "Raw Byte")
        prefs.reload()
        assert prefs.get_pref_as_number("Numbers Section", "Quoted Int") == 999
        assert prefs.get_pref_as_number("Numbers Section", "Raw Byte") == 1

    def test_validation(self, prefs_dir: Path) -> None:
        prefs = py_aep.Preferences(prefs_dir)
        with pytest.raises(ValueError):
            prefs.get_pref_as_number("", "Quoted Int")
        with pytest.raises(ValueError):
            prefs.get_pref_as_number("Numbers Section", "Quoted Int", 1234)
        with pytest.raises(TypeError):
            prefs.set_pref_as_bool("A", "B", 1)
        with pytest.raises(TypeError):
            prefs.set_pref_as_string("A", "B", 5)
        with pytest.raises(TypeError):
            prefs.set_pref_as_number("A", "B", "5")


class TestApplicationPreferences:
    def test_app_preferences_object(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        assert isinstance(app.preferences, py_aep.Preferences)
        assert app.preferences is app.project._preferences


class TestCreationWiring:
    """Creation defaults resolve from prefs, with AE factory fallbacks."""

    def test_labels_from_prefs(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 1.0, 25.0)
        assert comp._idta.label == 9
        assert app.project.root_folder.add_folder("F")._idta.label == 12
        solid = comp.add_solid([1.0, 0.0, 0.0])
        assert solid._ldta.label == 4
        assert solid.source._idta.label == 4
        assert comp.add_null()._ldta.label == 6
        assert comp.add_text("hi")._ldta.label == 3
        assert comp.add_shape()._ldta.label == 13
        assert comp.add_camera("cam", [50.0, 50.0])._ldta.label == 10
        assert comp.add_light("light", [50.0, 50.0])._ldta.label == 11

    def test_labels_factory_defaults(self) -> None:
        # Probed in AE 2026 with factory label preferences.
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 1.0, 25.0)
        assert comp._idta.label == 15
        assert app.project.root_folder.add_folder("F")._idta.label == 2
        solid = comp.add_solid([1.0, 0.0, 0.0])
        assert solid._ldta.label == 1
        assert solid.source._idta.label == 1
        assert comp.add_null()._ldta.label == 1
        assert comp.add_text("hi")._ldta.label == 1
        assert comp.add_shape()._ldta.label == 8
        assert comp.add_camera("cam", [50.0, 50.0])._ldta.label == 4
        assert comp.add_light("light", [50.0, 50.0])._ldta.label == 6

    def test_label_override(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        app.preferences.set_pref_as_number(
            "Label Preference Indices Section 5", "Comp Label Index 2", 16, INDEP
        )
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 1.0, 25.0)
        assert comp._idta.label == 16

    def test_solids_folder_name_from_prefs(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        assert app.project._solids_folder_name == "Solides"
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 1.0, 25.0)
        comp.add_solid([1.0, 0.0, 0.0])
        assert [f.name for f in app.project.root_folder.folders] == ["Solides"]

    def test_solids_folder_name_stamped_in_saved_file(
        self, prefs_dir: Path, tmp_path: Path
    ) -> None:
        # The pref is stamped into the sfnm chunk at new(); a fresh parse
        # (without any prefs dir) reads the stored name back.
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        out = tmp_path / "out.aep"
        app.project.save(out)
        reparsed = py_aep.parse(out)
        assert reparsed.project._solids_folder_name == "Solides"

    def test_solids_folder_name_factory_default(self) -> None:
        app = py_aep.new()
        assert app.project._solids_folder_name == "Solids"


class TestCompositionPresets:
    def test_parse_presets(self, prefs_dir: Path) -> None:
        presets = py_aep.Preferences(prefs_dir).composition_presets()
        # The "-" separator entry is skipped.
        assert len(presets) == 3
        hd24, hd2997, hdv = presets
        assert "1920x1080" in hd24.name and "24 fps" in hd24.name
        assert (hd24.width, hd24.height) == (1920, 1080)
        assert hd24.frame_rate == pytest.approx(24.0)
        assert hd24.pixel_aspect == pytest.approx(1.0)
        assert hd2997.frame_rate == pytest.approx(29.97, abs=1e-3)
        assert (hdv.width, hdv.height) == (1440, 1080)
        assert hdv.frame_rate == pytest.approx(25.0)
        assert hdv.pixel_aspect == pytest.approx(4 / 3)

    def test_no_prefs_dir(self) -> None:
        assert py_aep.Preferences().composition_presets() == []

    def test_add_comp_from_preset(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        comp = app.project.root_folder.add_comp_from_preset("C", "1440x1080", 5.0)
        assert (comp.width, comp.height) == (1440, 1080)
        assert comp.pixel_aspect == pytest.approx(4 / 3)
        assert comp.frame_rate == pytest.approx(25.0)
        assert comp.duration == pytest.approx(5.0)
        assert comp.name == "C"

    def test_add_comp_from_preset_ntsc_rate(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        comp = app.project.root_folder.add_comp_from_preset("C", "29.97", 5.0)
        assert comp.frame_rate == pytest.approx(29.97, abs=1e-3)

    def test_add_comp_from_preset_ambiguous(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        with pytest.raises(ValueError, match="matched 2"):
            app.project.root_folder.add_comp_from_preset("C", "1920x1080", 5.0)

    def test_add_comp_from_preset_unknown(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        with pytest.raises(ValueError, match="matched 0"):
            app.project.root_folder.add_comp_from_preset("C", "8K", 5.0)

    def test_add_comp_from_preset_without_prefs(self) -> None:
        app = py_aep.new()
        with pytest.raises(ValueError, match="no composition presets"):
            app.project.root_folder.add_comp_from_preset("C", "HD", 5.0)


# Two presets tie at 1440x1080 @ 25 fps ("First" then "Second"), plus a
# 60 fps entry; the resize label must pick the lowest fps, later on tie.
_TIE_COMP_PREFS = """\
# Text File Version 1.1
# After Effects Preferences

["Composition Preset Names Section v11"]
\t"000" = "First  "E280A2"  1440x1080 "E280A2" 25 fps"
\t"001" = "Second  "E280A2"  1440x1080 "E280A2" 25 fps"
\t"002" = "Fast  "E280A2"  1440x1080 "E280A2" 60 fps"

["Composition Presets Section v11"]
\t"000" = 05A004"8"001900000000000400000003
\t"001" = 05A004"8"001900000000000400000003
\t"002" = 05A004"8"003C00000000000400000003
"""


class TestResizeToStrings:
    """The "Resize to" label map derives from comp presets (lowest fps
    per resolution, later preset on tie), probed in AE 2026; the hardcoded
    table is the factory fallback when no preferences dir is provided."""

    def test_derives_lowest_fps_per_resolution(self, prefs_dir: Path) -> None:
        from py_aep.models.renderqueue.settings import build_resize_to_strings

        # Fixture presets: HD 1920x1080 @ 24 and @ 29.97 - lowest wins.
        resize = build_resize_to_strings(py_aep.Preferences(prefs_dir))
        assert resize[(1920, 1080)] == "HD  •  1920x1080 • 24 fps"
        assert resize[(1440, 1080)] == "HDV  •  1440x1080 (1.33) • 25 fps"

    def test_tie_break_prefers_later_preset(self, tmp_path: Path) -> None:
        from py_aep.models.renderqueue.settings import build_resize_to_strings

        prefs = tmp_path / "prefs"
        prefs.mkdir()
        (prefs / "Adobe After Effects 26.0 Prefs-indep-composition.txt").write_text(
            _TIE_COMP_PREFS, encoding="utf-8"
        )
        resize = build_resize_to_strings(py_aep.Preferences(prefs))
        assert resize[(1440, 1080)] == "Second  •  1440x1080 • 25 fps"

    def test_fallback_without_prefs(self) -> None:
        from py_aep.models.renderqueue.settings import (
            _RESIZE_TO_STRINGS,
            build_resize_to_strings,
        )

        assert build_resize_to_strings(py_aep.Preferences()) is _RESIZE_TO_STRINGS

    def test_fallback_holds_ae_verified_collision_labels(self) -> None:
        # AE 2026 getSetting("Resize to") ground truth for factory presets.
        from py_aep.models.renderqueue.settings import _RESIZE_TO_STRINGS

        assert _RESIZE_TO_STRINGS[(1920, 1080)] == "HD  •  1920x1080 • 24 fps"
        assert _RESIZE_TO_STRINGS[(3840, 2160)] == "UHD (4K)  •  3840x2160 • 23.976 fps"


class TestOutputNameTemplatePresets:
    def test_parse(self, prefs_dir: Path) -> None:
        presets = py_aep.Preferences(prefs_dir).output_name_template_presets()
        assert presets == {
            "Comp Name": "[compName].[fileExtension]",
            "Comp Folder and Name": "[compName]/[compName].[fileExtension]",
        }

    def test_no_prefs_dir(self) -> None:
        assert py_aep.Preferences().output_name_template_presets() == {}


class TestNewProjectSettings:
    """py_aep.new() inherits the last-used Project Settings preferences."""

    def test_depth_and_time_display_from_prefs(self, prefs_dir: Path) -> None:
        from py_aep.enums import BitsPerChannel

        project = py_aep.new(ae_preferences_dir=prefs_dir).project
        assert project.bits_per_channel is BitsPerChannel.SIXTEEN
        for chunk in (project._nnhd, project._nhed):
            assert chunk.time_display_type == 1
            assert chunk.footage_timecode_display_start_type == 0
            assert chunk.frames_use_feet_frames
            assert chunk.timecode_default_base == 24
            assert chunk.frames_count_type == 1

    def test_factory_defaults_without_prefs(self) -> None:
        from py_aep.enums import BitsPerChannel

        project = py_aep.new().project
        assert project.bits_per_channel is BitsPerChannel.EIGHT
        for chunk in (project._nnhd, project._nhed):
            assert chunk.time_display_type == 0
            assert chunk.timecode_default_base == 30
            assert chunk.frames_count_type == 2


class TestCreateLayersAtCurrentTime:
    """The "Create New Layers At Time Zero" preference (off in the fixture)."""

    def test_layers_anchor_at_comp_time(self, prefs_dir: Path) -> None:
        # AE 2026 probed: start = in = comp.time, out shifted by the same
        # amount, for every scripted layer-creation method.
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        comp.time = 2.0
        solid = comp.add_solid([1.0, 0.0, 0.0])
        assert solid.start_time == pytest.approx(2.0)
        assert solid.in_point == pytest.approx(2.0)
        assert solid.out_point == pytest.approx(7.0)
        text = comp.add_text("hi")
        assert text.start_time == pytest.approx(2.0)

    def test_no_shift_at_time_zero(self, prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        solid = comp.add_solid([1.0, 0.0, 0.0])
        assert solid.start_time == pytest.approx(0.0)

    def test_pref_on_keeps_layers_at_zero(self) -> None:
        # Factory default (no prefs dir): layers start at time zero.
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        comp.time = 2.0
        solid = comp.add_solid([1.0, 0.0, 0.0])
        assert solid.start_time == pytest.approx(0.0)

    def test_duplicate_keeps_source_timing(self, prefs_dir: Path) -> None:
        # AE 2026 probed: duplicate() keeps the source layer's timing and
        # does not re-anchor at the current time.
        app = py_aep.new(ae_preferences_dir=prefs_dir)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        comp.time = 2.0
        solid = comp.add_solid([1.0, 0.0, 0.0])
        comp.time = 4.0
        dup = solid.duplicate()
        assert dup.start_time == pytest.approx(2.0)


class TestDefaultOutPoints:
    """The still/synthetic default out-point preferences (probed in AE
    2026: value/scale seconds; solids, nulls, text, shape, camera and
    light follow the synthetic preference)."""

    @pytest.fixture()
    def outpoint_prefs_dir(self, tmp_path: Path) -> Path:
        (tmp_path / "Adobe After Effects 26.0 Prefs-indep-general.txt").write_text(
            '["Main Pref Section v2"]\n'
            '\t"Pref_DEFAULT_STILL_OUT_POINT v2" = "75/25"\n'
            '\t"Pref_DEFAULT_SYNTHETIC_OUT_POINT v2" = "50/25"\n',
            encoding="utf-8",
        )
        return tmp_path

    def test_synthetic_layers_follow_pref(self, outpoint_prefs_dir: Path) -> None:
        app = py_aep.new(ae_preferences_dir=outpoint_prefs_dir)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        assert comp.add_solid([1.0, 0.0, 0.0]).out_point == pytest.approx(2.0)
        assert comp.add_null().out_point == pytest.approx(2.0)
        assert comp.add_text("x").out_point == pytest.approx(2.0)
        assert comp.add_shape().out_point == pytest.approx(2.0)
        assert comp.add_camera("c", [50.0, 50.0]).out_point == pytest.approx(2.0)
        assert comp.add_light("l", [50.0, 50.0]).out_point == pytest.approx(2.0)

    def test_solid_duration_arg_ignored(self, outpoint_prefs_dir: Path) -> None:
        # AE 2026 probed: addSolid's duration argument has no effect on
        # the layer span even with a custom synthetic out point.
        app = py_aep.new(ae_preferences_dir=outpoint_prefs_dir)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        solid = comp.add_solid([1.0, 0.0, 0.0], duration=8.0)
        assert solid.out_point == pytest.approx(2.0)

    def test_factory_defaults_span_comp_duration(self) -> None:
        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        assert comp.add_solid([1.0, 0.0, 0.0], duration=3.0).out_point == (
            pytest.approx(5.0)
        )
        assert comp.add_text("x").out_point == pytest.approx(5.0)


_CUSTOM_TEXT_STYLE = """\
# Text File Version 1.1
# After Effects Preferences

["Text Style Sheet"]
\t"Baseline Shift" = "5.000000"
\t"Fill Blue" = "0.750000"
\t"Fill Green" = "0.500000"
\t"Fill Red" = "0.250000"
\t"Font Family Name" = "Arial"
\t"Font PostScript Name" = "ArialMT"
\t"Font Style Name" = "Regular"
\t"Render Fill" = 01
\t"Render Stroke" = 01
\t"Size" = "48.000000"
\t"Stroke Blue" = "0.000000"
\t"Stroke Green" = "0.200000"
\t"Stroke Red" = "0.100000"
\t"Stroke Width" = "5.000000"
\t"Tracking" = "50"
"""

# A factory AE 2026 style sheet (matches the baked COS template).
_FACTORY_TEXT_STYLE = """\
# Text File Version 1.1
# After Effects Preferences

["Text Style Sheet"]
\t"Baseline Shift" = "0.000000"
\t"Fill Blue" = "0.921569"
\t"Fill Green" = "0.921569"
\t"Fill Red" = "0.921569"
\t"Font Family Name" = "Myriad Pro"
\t"Font PostScript Name" = "MyriadPro-Regular"
\t"Font Style Name" = "Regular"
\t"Render Fill" = 01
\t"Render Stroke" = 00
\t"Size" = "36.000000"
\t"Stroke Blue" = "0.000000"
\t"Stroke Green" = "0.000000"
\t"Stroke Red" = "0.000000"
\t"Stroke Width" = "1.000000"
\t"Tracking" = "0"
"""


def _text_style_dir(tmp_path: Path, sheet: str) -> Path:
    prefs = tmp_path / "prefs"
    prefs.mkdir(exist_ok=True)
    (prefs / "Adobe After Effects 26.0 Prefs-text.txt").write_text(
        sheet, encoding="utf-8"
    )
    return prefs


def _btdk_bytes(layer: object) -> bytes:
    import io

    from py_aep.binary.utils import recursive_find

    matches = recursive_find(layer._layer_list.chunks, list_type="btdk")  # type: ignore[attr-defined]
    assert len(matches) == 1
    buf = io.BytesIO()
    matches[0].write(buf)
    return buf.getvalue()


class TestTextStyleSheet:
    """Scripted addText honors the character-level Text Style Sheet
    (probed in AE 2026; read at AE startup, paragraph sheet not applied)."""

    def test_add_text_honors_style_sheet(self, tmp_path: Path) -> None:
        prefs = _text_style_dir(tmp_path, _CUSTOM_TEXT_STYLE)
        app = py_aep.new(ae_preferences_dir=prefs)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        td = comp.add_text("probe").text.source_text.value
        assert td.font == "ArialMT"
        assert td.font_size == pytest.approx(48.0)
        assert td.fill_color == pytest.approx([0.25, 0.5, 0.75])
        assert td.tracking == pytest.approx(50.0)
        assert td.baseline_shift == pytest.approx(5.0)
        assert td.apply_stroke is True
        assert td.stroke_width == pytest.approx(5.0)
        assert td.stroke_color == pytest.approx([0.1, 0.2, 0.0])

    def test_no_prefs_is_byte_identical_to_template(self) -> None:
        # Without a prefs dir, add_text must not change a single byte of
        # the baked COS template (btdk is byte-format-sensitive).
        import io

        app = py_aep.new()
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        layer_bytes = _btdk_bytes(comp.add_text("probe"))
        buf = io.BytesIO()
        py_aep.TextDocument("probe")._btdk_body.write(buf)
        assert layer_bytes == buf.getvalue()

    def test_identity_fields_are_not_rewritten(self, tmp_path: Path) -> None:
        # Sheet values matching the template (size/tracking/baseline/
        # stroke flags) must not be rewritten. Font/Fill are excluded here
        # only to keep the assertion clear of the fill's sub-1e-6
        # serialization boundary; they are exercised elsewhere.
        sheet = "\n".join(
            line
            for line in _FACTORY_TEXT_STYLE.splitlines()
            if "Font" not in line and "Fill" not in line
        )
        prefs = _text_style_dir(tmp_path, sheet)
        app_prefs = py_aep.new(ae_preferences_dir=prefs)
        comp_prefs = app_prefs.project.root_folder.add_comp(
            "C", 100, 100, 1.0, 5.0, 25.0
        )
        app_plain = py_aep.new()
        comp_plain = app_plain.project.root_folder.add_comp(
            "C", 100, 100, 1.0, 5.0, 25.0
        )
        assert _btdk_bytes(comp_prefs.add_text("probe")) == _btdk_bytes(
            comp_plain.add_text("probe")
        )

    def test_factory_sheet_matches_ae_addtext(self, tmp_path: Path) -> None:
        # The template now matches AE 2026's own factory addText output
        # (MyriadPro-Regular, size 36, fill 0.921569, no stroke), so
        # applying the factory sheet is a no-op that stays on AE's values.
        prefs = _text_style_dir(tmp_path, _FACTORY_TEXT_STYLE)
        app = py_aep.new(ae_preferences_dir=prefs)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        td = comp.add_text("probe").text.source_text.value
        assert td.font == "MyriadPro-Regular"
        assert td.font_size == pytest.approx(36.0)
        assert td.fill_color == pytest.approx([0.921569] * 3, abs=1e-5)
        assert not td.apply_stroke

    def test_box_text_honors_style_sheet(self, tmp_path: Path) -> None:
        prefs = _text_style_dir(tmp_path, _CUSTOM_TEXT_STYLE)
        app = py_aep.new(ae_preferences_dir=prefs)
        comp = app.project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        td = comp.add_box_text([80.0, 40.0], "boxed").text.source_text.value
        assert td.font == "ArialMT"
        assert td.font_size == pytest.approx(48.0)
