"""Tests for the ImportOptions parameter container."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.enums import ImportAsType
from py_aep.models import CURRENT_VALUE, ImportOptions


class TestImportOptions:
    """Tests for the ImportOptions parameter container."""

    def test_constructor(self) -> None:
        opts = ImportOptions(Path("footage/shot.png"))
        assert opts.file == Path("footage/shot.png")
        assert opts.import_as == ImportAsType.FOOTAGE
        assert opts.sequence is False
        assert opts.force_alphabetical is False

    def test_constructor_accepts_path(self) -> None:
        opts = ImportOptions(Path("footage/shot.png"))
        assert isinstance(opts.file, Path)

    def test_file_setter(self) -> None:
        opts = ImportOptions(Path("a.png"))
        opts.file = Path("b.psd")
        assert opts.file == Path("b.psd")

    def test_import_as_setter(self) -> None:
        opts = ImportOptions(Path("a.psd"))
        opts.import_as = ImportAsType.COMP
        assert opts.import_as == ImportAsType.COMP

    def test_sequence_setter(self) -> None:
        opts = ImportOptions(Path("frame001.png"))
        opts.sequence = True
        assert opts.sequence is True

    def test_force_alphabetical_setter(self) -> None:
        opts = ImportOptions(Path("frame001.png"))
        opts.force_alphabetical = True
        assert opts.force_alphabetical is True

    # --- can_import_as ---
    # AE 2026 capability per extension (measured via
    # scripts/jsx/can_import_as_matrix.jsx). can_import_as additionally gates
    # on py_aep's own import support, so an extension that is AE-capable but
    # whose format is unimplemented (absent from data.file_formats, e.g.
    # .svg / .aep / .aet) returns False here for every type.

    _MATRIX: dict[str, set[ImportAsType]] = {
        # Still images / audio / video: footage only.
        ".png": {ImportAsType.FOOTAGE},
        ".jpg": {ImportAsType.FOOTAGE},
        ".tif": {ImportAsType.FOOTAGE},
        ".tga": {ImportAsType.FOOTAGE},
        ".bmp": {ImportAsType.FOOTAGE},
        ".gif": {ImportAsType.FOOTAGE},
        ".mp3": {ImportAsType.FOOTAGE},
        ".wav": {ImportAsType.FOOTAGE},
        # Layered Photoshop: footage, comp, and comp-cropped.
        ".psd": {
            ImportAsType.FOOTAGE,
            ImportAsType.COMP,
            ImportAsType.COMP_CROPPED_LAYERS,
        },
        ".psb": {
            ImportAsType.FOOTAGE,
            ImportAsType.COMP,
            ImportAsType.COMP_CROPPED_LAYERS,
        },
        # Multi-channel EXR: footage or comp-cropped, but NOT plain comp.
        ".exr": {ImportAsType.FOOTAGE, ImportAsType.COMP_CROPPED_LAYERS},
        # SVG: comp-cropped only - not even footage.
        ".svg": {ImportAsType.COMP_CROPPED_LAYERS},
        # QuickTime: footage or project.
        ".mov": {ImportAsType.FOOTAGE, ImportAsType.PROJECT},
        # Project / template: project only - not footage.
        ".aep": {ImportAsType.PROJECT},
        ".aet": {ImportAsType.PROJECT},
    }

    def test_can_import_as_matches_matrix(self) -> None:
        from py_aep.data.file_formats import (
            COMP_CONVERSION_EXTENSIONS,
            get_file_format,
        )

        all_types = [
            ImportAsType.FOOTAGE,
            ImportAsType.COMP,
            ImportAsType.COMP_CROPPED_LAYERS,
            ImportAsType.PROJECT,
        ]
        for ext, expected in self._MATRIX.items():
            # can_import_as is gated by what py_aep can actually import, so an
            # AE-capable extension with no implemented format yields False.
            # Comp-conversion formats (e.g. SVG) are implemented without a
            # media-format entry.
            if ext in COMP_CONVERSION_EXTENSIONS:
                implemented = True
            else:
                try:
                    get_file_format(ext)
                    implemented = True
                except ValueError:
                    implemented = False
            opts = ImportOptions(Path("asset" + ext))
            for t in all_types:
                # PROJECT import is unimplemented for every format, so
                # can_import_as never returns True for it (even where AE can).
                want = (
                    t in expected and t != ImportAsType.PROJECT
                    if implemented
                    else False
                )
                assert opts.can_import_as(t) is want, f"{ext} / {t.name}"

    def test_can_import_as_unknown_extension_all_false(self) -> None:
        opts = ImportOptions(Path("data.xyz"))
        assert opts.can_import_as(ImportAsType.FOOTAGE) is False
        assert opts.can_import_as(ImportAsType.COMP) is False
        assert opts.can_import_as(ImportAsType.COMP_CROPPED_LAYERS) is False
        assert opts.can_import_as(ImportAsType.PROJECT) is False

    def test_can_import_as_accepts_int(self) -> None:
        opts = ImportOptions(Path("design.psd"))
        assert opts.can_import_as(int(ImportAsType.COMP)) is True

    # --- is_file_name_numbered ---

    def test_numbered_filename(self) -> None:
        opts = ImportOptions(Path("frame001.png"))
        is_numbered, first = opts.is_file_name_numbered()
        assert is_numbered is True
        assert first == 1

    def test_numbered_filename_large(self) -> None:
        opts = ImportOptions(Path("shot_1234.exr"))
        is_numbered, first = opts.is_file_name_numbered()
        assert is_numbered is True
        assert first == 1234

    def test_not_numbered_filename(self) -> None:
        opts = ImportOptions(Path("background.png"))
        is_numbered, first = opts.is_file_name_numbered()
        assert is_numbered is False
        assert first == 0

    def test_numbered_no_prefix(self) -> None:
        opts = ImportOptions(Path("0042.tiff"))
        is_numbered, first = opts.is_file_name_numbered()
        assert is_numbered is True
        assert first == 42

    # --- repr ---

    def test_repr(self) -> None:
        opts = ImportOptions(Path("shot.png"))
        r = repr(opts)
        assert "ImportOptions" in r
        assert "shot.png" in r
        assert "FOOTAGE" in r

    # --- case insensitive extension matching ---

    def test_can_import_as_case_insensitive(self) -> None:
        opts = ImportOptions(Path("FILE.PSD"))
        assert opts.can_import_as(ImportAsType.COMP) is True

    def test_can_import_as_project_always_false(self) -> None:
        # AE can import a .mov as a project, but py_aep does not implement
        # PROJECT import for any format, so can_import_as gates it out.
        opts = ImportOptions(Path("CLIP.MOV"))
        assert opts.can_import_as(ImportAsType.PROJECT) is False


class TestImportOptionsLayerSelection:
    """layer_index / layer_dimensions (py_aep extensions)."""

    def test_defaults(self) -> None:
        opts = ImportOptions(Path("a.psd"))
        assert opts.layer_index is None
        assert opts.layer_dimensions is None

    def test_layer_index_setter(self) -> None:
        opts = ImportOptions(Path("a.psd"))
        opts.layer_index = 0
        assert opts.layer_index == 0
        opts.layer_index = 3
        assert opts.layer_index == 3
        opts.layer_index = None
        assert opts.layer_index is None

    def test_layer_index_rejects_negative(self) -> None:
        opts = ImportOptions(Path("a.psd"))
        with pytest.raises(ValueError):
            opts.layer_index = -1

    def test_layer_index_rejects_non_int(self) -> None:
        opts = ImportOptions(Path("a.psd"))
        with pytest.raises(TypeError):
            opts.layer_index = "Layer 1"  # type: ignore[assignment]

    def test_layer_index_rejects_current_value(self) -> None:
        # CURRENT_VALUE only makes sense for replace: an import has no
        # current binding to keep.
        opts = ImportOptions(Path("a.psd"))
        with pytest.raises(ValueError, match="only valid for FootageItem.replace"):
            opts.layer_index = CURRENT_VALUE  # type: ignore[assignment]

    def test_current_value_repr(self) -> None:
        assert repr(CURRENT_VALUE) == "CURRENT_VALUE"

    def test_layer_dimensions_setter(self) -> None:
        opts = ImportOptions(Path("a.psd"))
        opts.layer_dimensions = "layer"
        assert opts.layer_dimensions == "layer"
        opts.layer_dimensions = "document"
        assert opts.layer_dimensions == "document"
        opts.layer_dimensions = None
        assert opts.layer_dimensions is None

    def test_layer_dimensions_rejects_unknown(self) -> None:
        opts = ImportOptions(Path("a.psd"))
        with pytest.raises(ValueError):
            opts.layer_dimensions = "canvas"
