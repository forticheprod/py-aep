"""The `alas` path records py_aep writes: path style and relative counts."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from helpers import get_rqi, parse_project_fresh

from py_aep import FileSource, FootageItem, ImportOptions
from py_aep import parse as parse_aep
from py_aep.binary.utils import PENDING_ASCENDCOUNT, parse_alas_data
from py_aep.resolvers.platform_paths import platform_path

SAMPLES = Path(__file__).parent.parent.parent / "samples"
ASSETS = SAMPLES / "assets"
BASE = SAMPLES / "models" / "folder" / "folder.aep"
#: The platform this machine is not.
OTHER = "macos" if os.name == "nt" else "windows"


def _counts(source: FileSource) -> tuple[int, int]:
    data = parse_alas_data(source._pin.chunks)
    return data["ascendcount_base"], data["ascendcount_target"]


def _sources(project: object) -> dict[str, FileSource]:
    """File sources by kind: `"file"` or `"sequence"`."""
    out = {}
    for item in project.footages:  # type: ignore[attr-defined]
        if isinstance(item, FootageItem) and isinstance(item.main_source, FileSource):
            kind = "sequence" if item.main_source._target_is_folder else "file"
            out[kind] = item.main_source
    return out


def _project_with_media(tmp_path: Path, platform: str | None = None) -> object:
    media = tmp_path / "media"
    (media / "seq").mkdir(parents=True)
    shutil.copy2(ASSETS / "image_with_alpha.png", media / "img.png")
    for n in (1, 2):
        shutil.copy2(ASSETS / "image_with_alpha.png", media / "seq" / f"s_{n:04d}.png")
    project = parse_aep(BASE, platform=platform).project
    project.import_file(ImportOptions(media / "img.png"))
    opts = ImportOptions(media / "seq" / "s_0001.png")
    opts.sequence = True
    project.import_file(opts)
    return project


class TestSaveFillsCounts:
    def test_counts_for_the_saved_location(self, tmp_path: Path) -> None:
        project = _project_with_media(tmp_path)
        out = tmp_path / "proj" / "shots" / "p.aep"
        project.save(out)  # type: ignore[attr-defined]
        sources = _sources(parse_project_fresh(out))
        # proj/shots/p.aep vs media/img.png and media/seq/<frame>.
        assert _counts(sources["file"]) == (3, 2)
        assert _counts(sources["sequence"]) == (3, 3)

    def test_each_save_recomputes(self, tmp_path: Path) -> None:
        project = _project_with_media(tmp_path)
        project.save(tmp_path / "a.aep")  # type: ignore[attr-defined]
        project.save(tmp_path / "deep" / "b.aep")  # type: ignore[attr-defined]
        assert _counts(_sources(parse_project_fresh(tmp_path / "a.aep"))["file"]) == (
            1,
            2,
        )
        assert _counts(
            _sources(parse_project_fresh(tmp_path / "deep" / "b.aep"))["file"]
        ) == (2, 2)
        # The in-memory records stay pending for the next save.
        for source in _sources(project).values():
            assert _counts(source) == (PENDING_ASCENDCOUNT, PENDING_ASCENDCOUNT)

    def test_parsed_records_keep_ae_counts(self, tmp_path: Path) -> None:
        # Records parsed from a file keep AE's counts wherever py_aep saves it,
        # so parse then save stays byte-identical.
        sample = SAMPLES / "models" / "essential_graphics" / "media_replacement.aep"
        before = {k: _counts(s) for k, s in _sources(parse_aep(sample).project).items()}
        out = tmp_path / "x.aep"
        parse_aep(sample).project.save(out)
        after = {k: _counts(s) for k, s in _sources(parse_project_fresh(out)).items()}
        assert after == before
        assert out.read_bytes() == sample.read_bytes()

    def test_render_output_path(self, tmp_path: Path) -> None:
        project = parse_aep(
            SAMPLES / "models" / "renderqueue" / "render_settings.aep"
        ).project
        om = get_rqi(project, "base").output_modules[0]
        om.file_template = str(tmp_path / "renders") + os.sep + "out.[fileExtension]"
        out = tmp_path / "proj" / "p.aep"
        project.save(out)
        data = get_rqi(parse_aep(out).project, "base").output_modules[0]._alas_data
        # proj/p.aep vs a file inside renders/.
        assert (data["ascendcount_base"], data["ascendcount_target"]) == (2, 2)


class TestPathStyleFollowsPlatform:
    """A project for the other platform stores its paths in that style."""

    def test_footage_paths(self, tmp_path: Path) -> None:
        project = _project_with_media(tmp_path, platform=OTHER)
        windows = OTHER == "windows"
        sources = _sources(project)
        for kind, host in (
            ("file", tmp_path / "media" / "img.png"),
            ("sequence", tmp_path / "media" / "seq"),
        ):
            data = parse_alas_data(sources[kind]._pin.chunks)
            assert data["fullpath"] == platform_path(str(host), windows=windows)
            assert data["platform"] == (1 if windows else 2)

    def test_counts_match_the_host_layout(self, tmp_path: Path) -> None:
        # The save path is mapped like the footage, so the counts are the
        # ones a save on this machine gets.
        project = _project_with_media(tmp_path, platform=OTHER)
        out = tmp_path / "proj" / "shots" / "p.aep"
        project.save(out)  # type: ignore[attr-defined]
        sources = _sources(parse_project_fresh(out))
        assert _counts(sources["file"]) == (3, 2)
        assert _counts(sources["sequence"]) == (3, 3)

    def test_reload_reads_the_host_file(self, tmp_path: Path) -> None:
        if os.name == "nt" and not str(tmp_path).upper().startswith("C:"):
            pytest.skip("only the system drive maps back to a macOS path")
        source = _sources(_project_with_media(tmp_path, platform=OTHER))["file"]
        source.reload()
        assert source._sspc.width == 640
