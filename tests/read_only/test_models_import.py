"""Tests for media-file probing and file-source creation via import_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import ImportAsType
from py_aep import parse as parse_aep
from py_aep.models.import_options import ImportOptions

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"
BASE = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "folder" / "folder.aep"
)
IMPORT_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "import"


class TestImportFileErrors:
    """Validation and error handling."""

    def test_non_footage_import_type_raises(self) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "image_with_alpha.png")
        opts.import_as = ImportAsType.PROJECT
        with pytest.raises(ValueError, match="PROJECT import"):
            project.import_file(opts)

    def test_comp_import_unsupported_format_raises(self) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "image_with_alpha.png")
        opts.import_as = ImportAsType.COMP
        with pytest.raises(ValueError, match="COMP import"):
            project.import_file(opts)

    def test_ai_cropped_layers_not_implemented(self) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "ai.ai")
        opts.import_as = ImportAsType.COMP_CROPPED_LAYERS
        with pytest.raises(ValueError, match="COMP_CROPPED_LAYERS"):
            project.import_file(opts)

    def test_unsupported_format_raises(self) -> None:
        project = parse_aep(BASE).project
        with pytest.raises(ValueError, match="Unsupported"):
            project.import_file(ImportOptions(ASSETS / "config.ocio"))

    def test_deferred_format_rejected_early_with_value_error(self) -> None:
        # .c4d import is deferred; import must fail with a clear ValueError
        # naming the extension, not NotImplementedError mid-probe.
        project = parse_aep(BASE).project
        with pytest.raises(ValueError, match=r"\.c4d"):
            project.import_file(ImportOptions(ASSETS / "c4d.c4d"))
