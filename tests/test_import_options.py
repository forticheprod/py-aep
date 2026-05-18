"""Tests for the ImportOptions parameter container."""

from __future__ import annotations

from pathlib import Path

from py_aep.enums import ImportAsType
from py_aep.models import ImportOptions


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

    def test_can_import_as_footage_always_true(self) -> None:
        opts = ImportOptions(Path("video.mp4"))
        assert opts.can_import_as(ImportAsType.FOOTAGE) is True

    def test_can_import_as_project_for_aep(self) -> None:
        opts = ImportOptions(Path("project.aep"))
        assert opts.can_import_as(ImportAsType.PROJECT) is True

    def test_can_import_as_project_for_aet(self) -> None:
        opts = ImportOptions(Path("template.aet"))
        assert opts.can_import_as(ImportAsType.PROJECT) is True

    def test_can_import_as_project_for_png(self) -> None:
        opts = ImportOptions(Path("image.png"))
        assert opts.can_import_as(ImportAsType.PROJECT) is False

    def test_can_import_as_comp_for_psd(self) -> None:
        opts = ImportOptions(Path("design.psd"))
        assert opts.can_import_as(ImportAsType.COMP) is True

    def test_can_import_as_comp_for_ai(self) -> None:
        opts = ImportOptions(Path("vector.ai"))
        assert opts.can_import_as(ImportAsType.COMP) is True

    def test_can_import_as_comp_for_pdf(self) -> None:
        opts = ImportOptions(Path("doc.pdf"))
        assert opts.can_import_as(ImportAsType.COMP) is True

    def test_can_import_as_comp_for_png(self) -> None:
        opts = ImportOptions(Path("image.png"))
        assert opts.can_import_as(ImportAsType.COMP) is False

    def test_can_import_as_comp_cropped_for_psd(self) -> None:
        opts = ImportOptions(Path("design.psd"))
        assert opts.can_import_as(ImportAsType.COMP_CROPPED_LAYERS) is True

    def test_can_import_as_comp_cropped_for_mp4(self) -> None:
        opts = ImportOptions(Path("video.mp4"))
        assert opts.can_import_as(ImportAsType.COMP_CROPPED_LAYERS) is False

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

    def test_can_import_as_project_case_insensitive(self) -> None:
        opts = ImportOptions(Path("PROJECT.AEP"))
        assert opts.can_import_as(ImportAsType.PROJECT) is True
