"""Image-sequence import details, measured against AE 2026.

Alphabetical sequences (`force_alphabetical`), frame-number padding and the
duration a sequence's conform rate rewrites. Every expected value is what
AE 2026 wrote for the same folder and call.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import py_aep
from py_aep import FootageItem, ImportOptions, Project
from py_aep import parse as parse_aep
from py_aep.binary.scalar_chunks import U4LeChunk
from py_aep.binary.utils import UNDEFINED_FRAME, find_by_list_type

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"
BASE = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "folder" / "folder.aep"
)


def _folder(tmp_path: Path, *names: str) -> Path:
    """A folder named `shots` holding a copy of one still per name."""
    frame = (ASSETS / "image_with_alpha.png").read_bytes()
    folder = tmp_path / "shots"
    folder.mkdir()
    for name in names:
        (folder / name).write_bytes(frame)
    return folder


def _import(file: Path, *, alphabetical: bool) -> tuple[Project, FootageItem]:
    project = parse_aep(BASE).project
    opts = ImportOptions(file)
    opts.sequence = True
    opts.force_alphabetical = alphabetical
    return project, project.import_file(opts)


def _reparsed(project: Project, item: FootageItem, tmp_path: Path) -> FootageItem:
    out = tmp_path / "sequence.aep"
    project.save(out)
    return next(f for f in parse_aep(out).project.footages if f.id == item.id)


class TestAlphabeticalSequence:
    """`force_alphabetical` takes every file of the type in the folder."""

    # Every .png, case-insensitively by name (n_10 before n_2); x.jpg and the
    # subfolder's file are left out.
    ORDER = [
        "a_001.png",
        "a_002.png",
        "b.png",
        "c_010.png",
        "D.PNG",
        "n_10.png",
        "n_2.png",
    ]

    def _mixed(self, tmp_path: Path) -> Path:
        folder = _folder(tmp_path, *self.ORDER, "x.jpg")
        (folder / "sub").mkdir()
        (folder / "sub" / "z.png").write_bytes((folder / "b.png").read_bytes())
        return folder

    @pytest.mark.parametrize("picked", ["a_001.png", "b.png", "D.PNG"])
    def test_takes_every_file_of_the_type(self, tmp_path: Path, picked: str) -> None:
        _, item = _import(self._mixed(tmp_path) / picked, alphabetical=True)
        assert item.main_source.file_names == self.ORDER
        # The first file in order, whichever one was picked.
        assert Path(item.main_source.file).name == "a_001.png"
        assert item.name == "shots"
        assert item.duration == 7 / 30

    def test_stored_like_ae(self, tmp_path: Path) -> None:
        project, item = _import(self._mixed(tmp_path) / "a_001.png", alphabetical=True)
        reparsed = _reparsed(project, item, tmp_path)
        source = reparsed.main_source
        sspc = source._sspc
        assert (sspc.start_frame, sspc.end_frame, sspc.frame_padding) == (
            UNDEFINED_FRAME,
            UNDEFINED_FRAME,
            0,
        )
        assert (sspc._reserved_a8, sspc._reserved_b8, sspc._reserved_ba) == (
            b"\x00\x00\x00\x01",
            b"\x00",
            b"\x00\x00",
        )
        assert sspc._source_stamp[0] == 1
        assert (sspc.duration_dividend, sspc.duration_divisor) == (7, 30)
        stvc = find_by_list_type(chunks=source._pin.chunks, list_type="StVc")
        assert isinstance(stvc.chunks[0], U4LeChunk)
        assert stvc.chunks[0].chunk_type == "StVS"
        assert stvc.chunks[0].value == 7
        assert source.file_names == self.ORDER
        assert reparsed.name == "shots"

    def test_numbered_import_keeps_the_prefix(self, tmp_path: Path) -> None:
        _, item = _import(self._mixed(tmp_path) / "a_001.png", alphabetical=False)
        assert item.name == "a_[001-002].png"
        assert item.duration == 2 / 30

    def test_unnumbered_file_needs_alphabetical_order(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="numbered filename"):
            _import(self._mixed(tmp_path) / "b.png", alphabetical=False)

    def test_replacing_a_placeholder_keeps_its_rate(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        item = project.import_placeholder("PH", 640, 480, 24.0, 10.0)
        item.replace_with_sequence(self._mixed(tmp_path) / "a_001.png", True)
        assert item.name == "shots"
        sspc = item.main_source._sspc
        assert (sspc.duration_dividend, sspc.duration_divisor) == (7, 24)

    def test_reload_relists_the_folder(self, tmp_path: Path) -> None:
        folder = self._mixed(tmp_path)
        _, item = _import(folder / "a_001.png", alphabetical=True)
        (folder / "zz.png").write_bytes((folder / "b.png").read_bytes())
        item.main_source.reload()
        source = item.main_source
        assert source.file_names == [*self.ORDER, "zz.png"]
        assert item.duration == 8 / 30
        stvc = find_by_list_type(chunks=source._pin.chunks, list_type="StVc")
        assert stvc.chunks[0].value == 8


class TestSequencePadding:
    """The padding is the first frame's digit count, and `sspc` byte 0xB8
    marks zero-padded frame numbers."""

    @pytest.mark.parametrize(
        ("names", "picked", "name", "first", "padding", "zero_padded"),
        [
            (
                [f"s{n}.png" for n in range(1, 13)],
                "s12.png",
                "s[1-12].png",
                "s1.png",
                1,
                b"\x00",
            ),
            (
                ["p410.png", "p411.png", "p412.png"],
                "p410.png",
                "p[410-412].png",
                "p410.png",
                3,
                b"\x00",
            ),
            (
                ["z_0410.png", "z_0411.png", "z_0412.png"],
                "z_0411.png",
                "z_[0410-0412].png",
                "z_0410.png",
                4,
                b"\x01",
            ),
        ],
    )
    def test_matches_ae(
        self,
        tmp_path: Path,
        names: list[str],
        picked: str,
        name: str,
        first: str,
        padding: int,
        zero_padded: bytes,
    ) -> None:
        project, item = _import(_folder(tmp_path, *names) / picked, alphabetical=False)
        reparsed = _reparsed(project, item, tmp_path)
        assert reparsed.name == name
        assert Path(reparsed.main_source.file).name == first
        assert reparsed.main_source._sspc.frame_padding == padding
        assert reparsed.main_source._sspc._reserved_b8 == zero_padded


class TestSequenceConformFrameRate:
    @pytest.mark.parametrize(
        ("rate", "dividend", "divisor"), [(24.0, 3, 24), (29.97, 300, 2997)]
    )
    def test_stores_unreduced_frames_over_the_rate(
        self, tmp_path: Path, rate: float, dividend: int, divisor: int
    ) -> None:
        """The frame count over the rate to the nearest thousandth."""
        folder = _folder(tmp_path, "shot_0001.png", "shot_0002.png", "shot_0003.png")
        _, item = _import(folder / "shot_0001.png", alphabetical=False)
        item.main_source.conform_frame_rate = rate
        sspc = item.main_source._sspc
        assert (sspc.duration_dividend, sspc.duration_divisor) == (dividend, divisor)
        assert sspc.conform_frame_rate == 0.0


class TestAnimatedGifSequence:
    """A first frame with a timeline of its own (`gif.gif`: 14 frames at
    10 fps) sets the sequence's rate and duration, and a replace keeps them
    (AE 2026)."""

    @staticmethod
    def _gifs(tmp_path: Path, first: str = "gif.gif") -> Path:
        folder = tmp_path / "gifs"
        folder.mkdir()
        (folder / "m_001.gif").write_bytes((ASSETS / first).read_bytes())
        (folder / "m_002.gif").write_bytes((ASSETS / "gif.gif").read_bytes())
        return folder / "m_001.gif"

    def test_takes_the_first_files_timeline(self, tmp_path: Path) -> None:
        _, item = _import(self._gifs(tmp_path), alphabetical=False)
        assert item.name == "m_[001-002].gif"
        assert item.frame_rate == 10.0
        assert item.duration == 1.4
        sspc = item.main_source._sspc
        assert (sspc.duration_dividend, sspc.duration_divisor) == (14, 10)

    @pytest.mark.parametrize("old", ["placeholder", "sequence", "conformed movie"])
    def test_a_replace_keeps_its_rate(self, tmp_path: Path, old: str) -> None:
        project = parse_aep(BASE).project
        if old == "placeholder":
            item = project.import_placeholder("PH", 640, 480, 24.0, 10.0)
        elif old == "sequence":
            opts = ImportOptions(ASSETS / "sequence_001.gif")
            opts.sequence = True
            item = project.import_file(opts)
            item.main_source.conform_frame_rate = 25.0
        else:
            item = project.import_file(ImportOptions(ASSETS / "mov_480.mov"))
            item.main_source.conform_frame_rate = 25.0
        item.replace_with_sequence(self._gifs(tmp_path), False)
        assert item.frame_rate == 10.0
        assert item.duration == 1.4

    def test_a_still_first_frame_uses_the_usual_rule(self, tmp_path: Path) -> None:
        _, item = _import(self._gifs(tmp_path, "sequence_001.gif"), alphabetical=False)
        assert item.frame_rate == 30.0
        assert item.duration == 2 / 30


class TestCachedDataSize:
    """`sspc` byte 0xD0: the file's size, or for a sequence the first frame's
    size times the file count (AE 2026 on macOS and Windows)."""

    def test_file(self) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "image_with_alpha.png"))
        size = (ASSETS / "image_with_alpha.png").stat().st_size
        assert item.main_source._sspc.data_size == size

    def test_sequence(self) -> None:
        # sequence_001..003.gif are 4928, 5332 and 5223 bytes; AE's
        # `imio_sequence.aep` fixture stores 3 x 4928.
        _, item = _import(ASSETS / "sequence_001.gif", alphabetical=False)
        assert item.main_source._sspc.data_size == 3 * 4928


class TestPlatform:
    """`parse` / `new` take the After Effects platform the project is for; a
    BMP/GIF sequence gets that platform's importer code (AE refuses the
    other one)."""

    def test_defaults_to_the_host(self) -> None:
        host = "windows" if os.name == "nt" else "macos"
        assert parse_aep(BASE).project._platform == host
        assert py_aep.new().project._platform == host

    def test_rejects_an_unknown_platform(self) -> None:
        with pytest.raises(ValueError, match="must be one of"):
            parse_aep(BASE, platform="linux")
        with pytest.raises(ValueError, match="must be one of"):
            py_aep.new(platform="linux")

    @pytest.mark.parametrize(
        ("platform", "code"), [("windows", "STIL"), ("macos", "IMIO")]
    )
    def test_gif_sequence_code(self, platform: str, code: str) -> None:
        project = parse_aep(BASE, platform=platform).project
        opts = ImportOptions(ASSETS / "sequence_001.gif")
        opts.sequence = True
        item = project.import_file(opts)
        assert item.main_source._sspc.source_format_type == code
        # Every path that builds a sequence follows the project's platform.
        item.replace_with_sequence(ASSETS / "sequence_001.gif")
        assert item.main_source._sspc.source_format_type == code
        item.set_proxy_with_sequence(ASSETS / "sequence_001.gif")
        assert item.proxy_source._sspc.source_format_type == code

    @pytest.mark.parametrize(
        ("platform", "code", "heic_alpha"),
        [("windows", "STIL", False), ("macos", "IMIO", True)],
    )
    def test_still_paths(self, platform: str, code: str, heic_alpha: bool) -> None:
        # Stills take the platform's importer code too, and Windows AE
        # stores HEIC without alpha (windows_stills.aep), on every path.
        project = parse_aep(BASE, platform=platform).project
        item = project.import_file(ImportOptions(ASSETS / "bmp.bmp"))
        assert item.main_source._sspc.source_format_type == code
        item.set_proxy(ASSETS / "gif.gif")
        assert item.proxy_source._sspc.source_format_type == code
        item.replace(ASSETS / "gif.gif")
        assert item.main_source._sspc.source_format_type == code
        item.replace(ASSETS / "heic_alpha.heic")
        assert item.main_source.has_alpha is heic_alpha

    def test_new_project(self) -> None:
        project = py_aep.new(platform="macos").project
        opts = ImportOptions(ASSETS / "sequence_001.gif")
        opts.sequence = True
        assert project.import_file(opts).main_source._sspc.source_format_type == "IMIO"
