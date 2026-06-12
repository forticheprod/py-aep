"""Tests for media-file probing and file-source creation via import_file."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import AlphaMode, ImportAsType
from py_aep import parse as parse_aep
from py_aep.models.import_options import ImportOptions
from py_aep.models.sources.file import FileSource
from py_aep.resolvers.media_probe import probe_media

ASSETS = Path(__file__).parent.parent / "samples" / "assets"
BASE = Path(__file__).parent.parent / "samples" / "models" / "folder" / "folder.aep"


class TestMediaProbe:
    """Media-header probing matches the values AE reads on import."""

    @pytest.mark.parametrize(
        "name,width,height,has_alpha",
        [
            ("image_with_alpha.png", 640, 346, True),
            ("8bits_compressed.png", 25, 26, True),
            ("8bits.tif", 25, 26, True),
            ("8bits_transparency.tif", 25, 26, True),
            ("11_progressive.jpg", 25, 26, False),
            ("tga_16.tga", 25, 26, False),
            ("tga_24.tga", 25, 26, False),
            ("tga_32.tga", 25, 26, True),
            ("bmp.bmp", 25, 26, True),
            ("sequence_001.gif", 146, 93, True),
            ("8bits.psd", 25, 26, True),
            ("8bits.psb", 25, 26, True),
        ],
    )
    def test_still_image(
        self, name: str, width: int, height: int, has_alpha: bool
    ) -> None:
        info = probe_media(ASSETS / name)
        assert info.width == width
        assert info.height == height
        assert info.has_alpha is has_alpha
        assert info.duration == 0.0

    @pytest.mark.parametrize(
        "name,width,height,has_alpha",
        [
            ("new_exr.0002.exr", 2356, 1002, False),
            ("old_exr.00004.exr", 2356, 1002, True),
        ],
    )
    def test_exr(self, name: str, width: int, height: int, has_alpha: bool) -> None:
        info = probe_media(ASSETS / name)
        assert (info.width, info.height) == (width, height)
        assert info.has_alpha is has_alpha

    @pytest.mark.parametrize("name", ["8bits.psd", "8bits.psb"])
    def test_psd_metadata(self, name: str) -> None:
        info = probe_media(ASSETS / name)
        assert (info.width, info.height) == (25, 26)
        assert info.bit_depth == 8
        assert info.layer_count == 2

    def test_wav(self) -> None:
        info = probe_media(ASSETS / "wav.wav")
        assert info.width == 0 and info.height == 0
        assert info.has_audio is True
        assert info.audio_sample_rate == 44100.0
        assert info.duration == pytest.approx(5.9431746, abs=1e-4)

    @pytest.mark.parametrize(
        "name,width,height,fps,has_audio,has_alpha,pixel_aspect",
        [
            ("mov_480.mov", 480, 270, 30.0, True, False, 1.0),
            ("mov_23_976.mov", 480, 270, 23.976, True, False, 1.0),
            ("mov_23_976_no_audio.mov", 480, 270, 23.976, False, False, 1.0),
            ("mov_alpha_small.mov", 320, 240, 25.0, False, True, 1.33333),
        ],
    )
    def test_mov(
        self,
        name: str,
        width: int,
        height: int,
        fps: float,
        has_audio: bool,
        has_alpha: bool,
        pixel_aspect: float,
    ) -> None:
        info = probe_media(ASSETS / name)
        assert (info.width, info.height) == (width, height)
        assert info.frame_rate == pytest.approx(fps, abs=1e-3)
        assert info.has_audio is has_audio
        assert info.has_alpha is has_alpha
        assert info.pixel_aspect == pytest.approx(pixel_aspect, abs=1e-4)

    def test_m4v(self) -> None:
        # MP4 video shares the QuickTime atom tree, so _probe_mov parses it.
        info = probe_media(ASSETS / "m4v.m4v")
        assert (info.width, info.height) == (640, 360)
        assert info.frame_rate == pytest.approx(29.97, abs=1e-3)
        assert info.has_audio is False
        assert info.duration == pytest.approx(13.3467, abs=1e-3)

    def test_aiff(self) -> None:
        info = probe_media(ASSETS / "click.aiff")
        assert info.width == 0 and info.height == 0
        assert info.has_audio is True
        assert info.audio_sample_rate == 44100.0
        assert info.duration == pytest.approx(0.1274376, abs=1e-5)

    def test_unsupported_format_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            probe_media(ASSETS / "mp3.mp3")

    def test_every_importable_format_has_probe(self) -> None:
        # Every extension import_file accepts must have a media probe;
        # otherwise import dies mid-probe with NotImplementedError instead
        # of the early ValueError for unsupported formats.
        from py_aep.data.file_formats import _FILE_FORMATS
        from py_aep.resolvers.media_probe import _PARSERS

        importable = {
            ext for ext, fmt in _FILE_FORMATS.items() if fmt.opti != "unsupported"
        }
        assert importable <= set(_PARSERS)


class TestImportFileSingle:
    """Project.import_file for single files."""

    def test_import_png(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "image_with_alpha.png")
        item = project.import_file(opts)

        assert isinstance(item.main_source, FileSource)
        assert item.name == "image_with_alpha.png"
        assert (item.width, item.height) == (640, 346)
        assert item.main_source.is_still is True
        assert item.main_source.has_alpha is True
        assert item.main_source.alpha_mode == AlphaMode.STRAIGHT
        assert item.main_source.file == str(ASSETS / "image_with_alpha.png")

    def test_import_wav(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "wav.wav"))
        assert item.has_audio is True
        assert item.has_video is False
        assert item.main_source.is_still is False
        assert item.duration == pytest.approx(5.9431746, abs=1e-3)

    def test_import_mov_with_audio(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "mov_480.mov"))
        assert (item.width, item.height) == (480, 270)
        assert item.has_audio is True
        assert item.frame_rate == pytest.approx(30.0, abs=1e-3)

    def test_import_m4v(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "m4v.m4v"))
        assert isinstance(item.main_source, FileSource)
        assert item.name == "m4v.m4v"
        assert (item.width, item.height) == (640, 360)
        assert item.has_video is True
        assert item.has_audio is False
        assert item.frame_rate == pytest.approx(29.97, abs=1e-3)

    def test_import_aiff(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "click.aiff"))
        assert item.has_audio is True
        assert item.has_video is False
        assert item.main_source.is_still is False
        assert item.duration == pytest.approx(0.1274376, abs=1e-5)

    def test_roundtrip_m4v_aiff(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        for name in ("m4v.m4v", "click.aiff"):
            project.import_file(ImportOptions(ASSETS / name))
        out1 = tmp_path / "a.aep"
        project.save(out1)
        out2 = tmp_path / "b.aep"
        parse_aep(out1).project.save(out2)
        assert out1.read_bytes() == out2.read_bytes()

    def test_import_exr_premultiplied(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "old_exr.00004.exr"))
        assert item.main_source.has_alpha is True
        assert item.main_source.alpha_mode == AlphaMode.PREMULTIPLIED

    def test_import_tiff(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "8bits.tif"))
        assert isinstance(item.main_source, FileSource)
        assert item.name == "8bits.tif"
        assert (item.width, item.height) == (25, 26)
        # TIFF carries the 602-byte format-specific opti header.
        assert len(item.main_source._opti.data) == 602

    @pytest.mark.parametrize("name", ["8bits.psd", "8bits.psb"])
    def test_import_psd(self, name: str) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / name))
        assert isinstance(item.main_source, FileSource)
        assert item.name == name
        assert (item.width, item.height) == (25, 26)
        assert item.main_source.is_still is True
        # AE composites a merged PSD to RGBA -> STRAIGHT alpha.
        assert item.main_source.has_alpha is True
        assert item.main_source.alpha_mode == AlphaMode.STRAIGHT
        # The merged-layer opti is exposed via file_attributes.
        attrs = item.main_source.file_attributes
        assert attrs["psd_layer_index"] == 0xFFFF
        assert attrs["psd_bit_depth"] == 8
        assert attrs["psd_channels"] == 4
        assert attrs["psd_layer_count"] == 2
        assert (attrs["psd_canvas_width"], attrs["psd_canvas_height"]) == (25, 26)

    def test_roundtrip_psd(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(ImportOptions(ASSETS / "8bits.psd"))
        out1 = tmp_path / "a.aep"
        project.save(out1)
        out2 = tmp_path / "b.aep"
        parse_aep(out1).project.save(out2)
        assert out1.read_bytes() == out2.read_bytes()

    def test_roundtrip_png(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(ImportOptions(ASSETS / "image_with_alpha.png"))
        out = tmp_path / "out.aep"
        project.save(out)
        reparsed = parse_aep(out).project

        files = [
            it
            for it in reparsed.items.values()
            if isinstance(getattr(it, "main_source", None), FileSource)
        ]
        assert any(it.name == "image_with_alpha.png" for it in files)

    def test_roundtrip_is_idempotent(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        for name in ("image_with_alpha.png", "wav.wav", "mov_480.mov"):
            project.import_file(ImportOptions(ASSETS / name))
        out1 = tmp_path / "a.aep"
        project.save(out1)
        out2 = tmp_path / "b.aep"
        parse_aep(out1).project.save(out2)
        assert out1.read_bytes() == out2.read_bytes()


class TestImportFileSequence:
    """Project.import_file for image sequences."""

    def test_import_exr_sequence(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "new_exr.0002.exr")
        opts.sequence = True
        item = project.import_file(opts)

        assert item.name == "new_exr.[0002-0003].exr"
        assert item.main_source.is_still is False
        assert item.frame_rate == pytest.approx(30.0)
        # two frames at 30 fps
        assert item.duration == pytest.approx(2 / 30, abs=1e-4)

    def test_import_gif_sequence(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "sequence_001.gif")
        opts.sequence = True
        item = project.import_file(opts)
        assert item.name == "sequence_[001-003].gif"
        assert item.main_source.is_still is False

    def test_sequence_roundtrip(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "new_exr.0002.exr")
        opts.sequence = True
        project.import_file(opts)
        out = tmp_path / "seq.aep"
        project.save(out)
        reparsed = parse_aep(out).project
        names = [
            it.name
            for it in reparsed.items.values()
            if isinstance(getattr(it, "main_source", None), FileSource)
        ]
        assert "new_exr.[0002-0003].exr" in names


class TestImportFileErrors:
    """Validation and error handling."""

    def test_non_footage_import_type_raises(self) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "image_with_alpha.png")
        opts.import_as = ImportAsType.COMP
        with pytest.raises(ValueError, match="FOOTAGE"):
            project.import_file(opts)

    def test_unsupported_format_raises(self) -> None:
        project = parse_aep(BASE).project
        with pytest.raises(ValueError, match="Unsupported"):
            project.import_file(ImportOptions(ASSETS / "config.ocio"))

    def test_mp3_rejected_early_with_value_error(self) -> None:
        # .mp3 has no media probe yet; import must fail with a clear
        # ValueError naming the extension, not NotImplementedError
        # mid-probe.
        project = parse_aep(BASE).project
        with pytest.raises(ValueError, match=r"\.mp3"):
            project.import_file(ImportOptions(ASSETS / "mp3.mp3"))


class TestTiffOpti:
    """The reverse-engineered TIFF opti header."""

    def test_build_tiff_opti_data(self) -> None:
        import struct

        from py_aep.binary.footage_chunks import build_tiff_opti_data

        data = build_tiff_opti_data(25, 26)
        assert len(data) == 602
        assert data[:4] == b"TIF "
        assert struct.unpack_from("<I", data, 32)[0] == 26  # height
        assert struct.unpack_from("<I", data, 36)[0] == 25  # width


class TestPsdOpti:
    """The reverse-engineered merged-PSD opti header."""

    def test_build_psd_opti_data(self) -> None:
        import struct

        from py_aep.binary.footage_chunks import build_psd_opti_data

        data = build_psd_opti_data(25, 26, bit_depth=8, layer_count=2)
        assert len(data) == 602
        assert data[:4] == b"8BPS"
        assert data[0x12:0x16] == b"SPB8"  # reversed code
        assert data[0x1E] == 4  # channels (always RGBA)
        assert struct.unpack_from("<I", data, 0x20)[0] == 26  # height
        assert struct.unpack_from("<I", data, 0x24)[0] == 25  # width
        assert struct.unpack_from("<H", data, 0x28)[0] == 8  # bit depth
        assert data[0x30] == 2  # layer count

    def test_flattened_psd_stores_one_layer(self) -> None:
        from py_aep.binary.footage_chunks import build_psd_opti_data

        # A flattened PSD (0 layers) is stored as 1, matching AE.
        data = build_psd_opti_data(1000, 1000, bit_depth=16, layer_count=0)
        assert data[0x30] == 1


class TestReplaceAndProxy:
    """FootageItem.replace* and AVItem.set_proxy* (variations of import_file)."""

    def _png_footage(self):
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "image_with_alpha.png"))
        return project, item

    def test_replace_with_file(self, tmp_path: Path) -> None:
        _, item = self._png_footage()
        item.replace(ASSETS / "mov_480.mov")
        assert isinstance(item.main_source, FileSource)
        assert item.name == "mov_480.mov"
        assert (item.width, item.height) == (480, 270)
        assert item.has_audio is True

    def test_replace_with_sequence(self, tmp_path: Path) -> None:
        _, item = self._png_footage()
        item.replace_with_sequence(ASSETS / "new_exr.0002.exr")
        assert item.name == "new_exr.[0002-0003].exr"
        assert item.main_source.is_still is False

    def test_replace_roundtrip(self, tmp_path: Path) -> None:
        project, item = self._png_footage()
        item.replace(ASSETS / "wav.wav")
        out = tmp_path / "r.aep"
        project.save(out)
        out2 = tmp_path / "r2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()

    def test_set_proxy_with_file(self, tmp_path: Path) -> None:
        _, item = self._png_footage()
        item.set_proxy(ASSETS / "new_exr.0002.exr")
        assert isinstance(item.proxy_source, FileSource)
        assert item.use_proxy is True
        assert item.proxy_source.file == str(ASSETS / "new_exr.0002.exr")

    def test_set_proxy_with_sequence(self, tmp_path: Path) -> None:
        _, item = self._png_footage()
        item.set_proxy_with_sequence(ASSETS / "new_exr.0002.exr")
        assert isinstance(item.proxy_source, FileSource)
        assert item.proxy_source.is_still is False

    def test_set_proxy_roundtrip(self, tmp_path: Path) -> None:
        project, item = self._png_footage()
        item.set_proxy(ASSETS / "mov_480.mov")
        out = tmp_path / "p.aep"
        project.save(out)
        out2 = tmp_path / "p2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()

    def test_replace_with_psd(self) -> None:
        _, item = self._png_footage()
        item.replace(ASSETS / "8bits.psd")
        assert isinstance(item.main_source, FileSource)
        assert item.name == "8bits.psd"
        assert (item.width, item.height) == (25, 26)
        assert item.main_source.file_attributes["psd_layer_index"] == 0xFFFF
