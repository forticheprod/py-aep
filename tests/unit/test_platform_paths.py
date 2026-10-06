"""Tests for platform path styles and the `alas` relative-path counts."""

from __future__ import annotations

import json

import pytest

from py_aep.binary.utils import PENDING_ASCENDCOUNT, alas_platform, build_als2_list
from py_aep.resolvers.platform_paths import platform_path, relative_path_counts

SHOT = r"\\serge\as_serie\fabrication\episodes\e203\final_compo\s030"


@pytest.mark.parametrize(
    ("path", "macos"),
    [
        # Windows AE opens /Users/x as C:\Users\x (measured); the inverse.
        (r"C:\Users\x\a.png", "/Users/x/a.png"),
        (r"c:\Users\x\a.png", "/Users/x/a.png"),
        ("C:/Users/x/a.png", "/Users/x/a.png"),
        ("C:\\", "/"),
        (r"D:\media\a.png", "/Volumes/D/media/a.png"),
        ("D:\\", "/Volumes/D"),
        (r"\\serge\as_serie\shot\a.png", "/Volumes/as_serie/shot/a.png"),
        (r"\\serge\as_serie", "/Volumes/as_serie"),
        ("/Users/x/a.png", "/Users/x/a.png"),
        ("relative/a.png", "relative/a.png"),
    ],
)
def test_platform_path_macos(path: str, macos: str) -> None:
    assert platform_path(path, windows=False) == macos


@pytest.mark.parametrize(
    ("path", "windows"),
    [
        # What Windows AE resolves a macOS path to (measured on AE 2026).
        ("/Users/x/a.png", r"C:\Users\x\a.png"),
        ("/Volumes/v/a.png", r"C:\Volumes\v\a.png"),
        (r"C:\Users\x\a.png", r"C:\Users\x\a.png"),
        (r"\\server\share\a.png", r"\\server\share\a.png"),
        ("relative/a.png", "relative/a.png"),
    ],
)
def test_platform_path_windows(path: str, windows: str) -> None:
    assert platform_path(path, windows=True) == windows


@pytest.mark.parametrize(
    ("project", "target", "is_folder", "expected"),
    [
        # AE 2026 Windows saves of samples/models/import/*.aep.
        (
            r"C:\repo\samples\models\import\x.aep",
            r"C:\repo\samples\assets\aif.aif",
            False,
            (3, 2),
        ),
        # A sequence folder counts one level inside it.
        (
            r"C:\repo\samples\models\import\x.aep",
            r"C:\repo\samples\assets",
            True,
            (3, 2),
        ),
        # A render output folder too (samples/models/output_module).
        (
            r"C:\Users\a\git\py-aep\samples\models\output_module\o.aep",
            r"C:\Users\a\Downloads",
            True,
            (6, 2),
        ),
        # Production projects saved on a UNC share.
        (
            SHOT + r"\work\p.aep",
            SHOT + r"\preview\interne\20230313\x.mov",
            False,
            (2, 4),
        ),
        (
            SHOT + r"\work\p.aep",
            r"\\serge\as_serie\lab\compo\SEQ_SPE\BANK\TEXTURES\PAPER",
            True,
            (7, 7),
        ),
        # Same folder; Windows paths compare case-insensitively.
        (r"C:\Repo\a.aep", r"c:\repo\b.png", False, (1, 1)),
        # A macOS save (media_gap_formats.aep).
        (
            "/Volumes/O/overlay/samples/models/import/media_gap_formats.aep",
            "/Volumes/O/overlay/samples/assets/aif.aif",
            False,
            (3, 2),
        ),
        ("/Users/a/proj/p.aep", "/Users/a/media/b.png", False, (2, 2)),
    ],
)
def test_counts(
    project: str, target: str, is_folder: bool, expected: tuple[int, int]
) -> None:
    assert relative_path_counts(project, target, target_is_folder=is_folder) == expected


@pytest.mark.parametrize(
    ("project", "target"),
    [
        (r"C:\p\a.aep", r"D:\p\b.png"),  # another drive
        (r"C:\p\a.aep", r"\\server\share\b.png"),  # a UNC share
        (r"\\server\one\a.aep", r"\\server\two\b.png"),  # another share
        ("/Users/a/a.aep", "/Volumes/D/b.png"),  # another macOS volume
        ("/Volumes/C/a.aep", "/Volumes/D/b.png"),
        ("/Users/a/a.aep", r"C:\p\b.png"),  # another path style
        (r"C:\p\a.aep", "relative\\b.png"),
    ],
)
def test_no_relative_path(project: str, target: str) -> None:
    assert relative_path_counts(project, target, target_is_folder=False) == (0, 0)


def test_counts_survive_the_platform_mapping() -> None:
    # Mapping the project and the target alike keeps the host's counts.
    pairs = [
        (r"C:\p\shots\a.aep", r"C:\media\b.png"),
        (r"C:\p\a.aep", r"D:\media\b.png"),
        (SHOT + r"\work\p.aep", SHOT + r"\preview\x.mov"),
    ]
    for project, target in pairs:
        host = relative_path_counts(project, target, target_is_folder=False)
        mapped = relative_path_counts(
            platform_path(project, windows=False),
            platform_path(target, windows=False),
            target_is_folder=False,
        )
        assert mapped == host


@pytest.mark.parametrize(
    ("path", "code"),
    [("/Users/a/b.png", 2), (r"C:\a\b.png", 1), (r"\\server\share\b.png", 1)],
)
def test_alas_platform_follows_path_style(path: str, code: int) -> None:
    assert alas_platform(path) == code
    alas = build_als2_list(path, target_is_folder=False).chunks[0]
    data = json.loads(alas.value)  # type: ignore[attr-defined]
    assert data["platform"] == code
    assert data["ascendcount_base"] == data["ascendcount_target"] == PENDING_ASCENDCOUNT
