"""Tests for RenderQueue model parsing."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from py_aep.binary.render_chunks import (
    OutputModuleSettingsItem,
    RenderSettingsItem,
)
from py_aep.enums import (
    OutputChannels,
    OutputColorDepth,
)
from py_aep.parsers.templates import parse_output_templates, parse_render_templates
from py_aep.resolvers.output import resolve_output_filename

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "renderqueue"
OM_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "output_module"
)
BUGS_DIR = Path(__file__).parent.parent.parent / "samples" / "bugs"
AE_PREFS_DIR = os.getenv("AE_PREFS_DIR")
OCS_SAMPLES_DIR = (
    Path(__file__).parent.parent.parent
    / "samples"
    / "models"
    / "output_module"
    / "output_color_space"
)


class TestResolveOutputFilename:
    """Unit tests for resolve_output_filename()."""

    def test_empty_template(self) -> str:
        assert resolve_output_filename("") == ""

    @pytest.mark.parametrize(
        "template, kwargs, expected",
        [
            ("[projectName]", {"project_name": "MyProject"}, "MyProject"),
            ("[compName]", {"comp_name": "Comp 1"}, "Comp 1"),
            (
                "[renderSettingsName]",
                {"render_settings_name": "Best Settings"},
                "Best Settings",
            ),
            ("[outputModuleName]", {"output_module_name": "Lossless"}, "Lossless"),
            ("[width]", {"width": 1920}, "1920"),
            ("[height]", {"height": 1080}, "1080"),
            ("[frameRate]", {"frame_rate": 30.0}, "30"),
            ("[frameRate]", {"frame_rate": 29.97}, "29.97"),
            ("[compressor]", {"compressor": "H.264"}, "H.264"),
            ("[COMPNAME]", {"comp_name": "MyComp"}, "MyComp"),
        ],
    )
    def test_single_token(
        self, template: str, kwargs: dict[str, object], expected: str
    ) -> None:
        assert resolve_output_filename(template, **kwargs) == expected

    def test_aspect_ratio(self) -> None:
        result = resolve_output_filename("[aspectRatio]", width=1920, height=1080)
        assert result == "16x9"

    @pytest.mark.parametrize(
        "channels, expected",
        [
            (OutputChannels.RGB, "RGB"),
            (OutputChannels.RGBA, "RGBA"),
            (OutputChannels.ALPHA, "Alpha"),
        ],
    )
    def test_channels(self, channels: OutputChannels, expected: str) -> None:
        assert resolve_output_filename("[channels]", channels=channels) == expected

    @pytest.mark.parametrize(
        "depth, expected",
        [
            (8, "8bit"),
            (16, "16bit"),
            (32, "32bit"),
        ],
    )
    def test_project_color_depth(self, depth: int, expected: str) -> None:
        assert (
            resolve_output_filename("[projectColorDepth]", project_color_depth=depth)
            == expected
        )

    @pytest.mark.parametrize(
        "color_depth, expected",
        [
            (OutputColorDepth.MILLIONS_OF_COLORS, "Millions"),
            (OutputColorDepth.MILLIONS_OF_COLORS_PLUS, "Millions+"),
            (OutputColorDepth.TRILLIONS_OF_COLORS, "Trillions"),
            (OutputColorDepth.TRILLIONS_OF_COLORS_PLUS, "Trillions+"),
            (OutputColorDepth.FLOATING_POINT, "Floating Point"),
            (OutputColorDepth.FLOATING_POINT_PLUS, "Floating Point+"),
        ],
    )
    def test_output_color_depth(
        self, color_depth: OutputColorDepth, expected: str
    ) -> None:
        assert (
            resolve_output_filename(
                "[outputColorDepth]", output_color_depth=color_depth
            )
            == expected
        )

    def test_file_extension(self) -> None:
        result = resolve_output_filename(
            "[compName].[fileExtension]", comp_name="MyComp", file_extension="mp4"
        )
        assert result == "MyComp.mp4"

    def test_combined_template(self) -> None:
        result = resolve_output_filename(
            "[projectName]_[compName]_[width]x[height].[fileExtension]",
            project_name="Proj",
            comp_name="Comp1",
            width=1920,
            height=1080,
            file_extension="mov",
        )
        assert result == "Proj_Comp1_1920x1080.mov"

    @pytest.mark.parametrize(
        "template, kwargs, expected",
        [
            ("[startTimecode]", {"start_time": 0.0, "frame_rate": 24.0}, "0-00-00-00"),
            ("[endTimecode]", {"end_time": 10.0, "frame_rate": 24.0}, "0-00-10-00"),
            (
                "[durationTimecode]",
                {"duration_time": 5.0, "frame_rate": 24.0},
                "0-00-05-00",
            ),
        ],
    )
    def test_timecode(
        self, template: str, kwargs: dict[str, object], expected: str
    ) -> None:
        assert resolve_output_filename(template, **kwargs) == expected

    def test_project_folder_empty(self) -> None:
        result = resolve_output_filename(
            "[projectFolder][compName]", comp_name="MyComp"
        )
        assert result == "MyComp"


class TestRenderTemplatesDefaultIndex:
    """The prefs default index is remapped to the filtered template list.

    Regression: parse_render_templates filtered out empty-named entries
    but returned the raw "Default RS Index", so any skipped entry before
    the default shifted the selection to the wrong template.
    """

    @staticmethod
    def _write_render_prefs(
        prefs_dir: Path, default_idx: int, names: list[str]
    ) -> None:
        # The prefs item is the 2246-byte AEP layout minus the last 64 bytes.
        raw = b"\x00" * 32
        for name in names:
            raw += RenderSettingsItem(template_name=name).tobytes()[:2182]
        (prefs_dir / "Adobe After Effects 26.0 Prefs-indep-render.txt").write_text(
            '["Render Settings Preference Section"]\n'
            '\t"Render Settings List" = ' + raw.hex() + "\n"
            '\t"Default RS Index" = "' + str(default_idx) + '"\n',
            encoding="utf-8",
        )

    @staticmethod
    def _write_output_prefs(
        prefs_dir: Path, default_idx: int, names: list[str]
    ) -> None:
        raw = b"\x00" * 32 + OutputModuleSettingsItem().tobytes() * len(names)
        lines = [
            '["Output Module Preference Section"]',
            '\t"Output Module List v28" = ' + raw.hex(),
            '\t"Default OM Index" = "' + str(default_idx) + '"',
        ]
        for i, name in enumerate(names):
            lines.append(f'\t"Output Module Spec Strings Name #{i}" = "{name}"')
        (prefs_dir / "Adobe After Effects 26.0 Prefs-indep-output.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def test_render_default_shifts_past_filtered_entry(self, tmp_path: Path) -> None:
        # Empty-named entry at raw index 0; raw default index 2 ("Best").
        self._write_render_prefs(tmp_path, 2, ["", "Draft", "Best"])
        templates, default = parse_render_templates(tmp_path)
        assert [t.clean_template_name for t in templates] == ["Draft", "Best"]
        assert default == 1
        assert templates[default].clean_template_name == "Best"

    def test_render_default_filtered_out_yields_none(self, tmp_path: Path) -> None:
        # The default entry itself has an empty name -> no default.
        self._write_render_prefs(tmp_path, 0, ["", "Draft", "Best"])
        _templates, default = parse_render_templates(tmp_path)
        assert default is None

    def test_output_default_shifts_past_hidden_entry(self, tmp_path: Path) -> None:
        # _HIDDEN entry at raw index 0; raw default index 1 ("Lossless").
        self._write_output_prefs(tmp_path, 1, ["_HIDDEN X", "Lossless", "TIFF"])
        templates, default = parse_output_templates(tmp_path)
        assert [t.name for t in templates] == ["Lossless", "TIFF"]
        assert default == 0
        assert templates[default].name == "Lossless"
