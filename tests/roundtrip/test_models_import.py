"""Tests for media-file probing and file-source creation via import_file."""

from __future__ import annotations

import io
import struct
from pathlib import Path

import pytest

from py_aep import AlphaMode, ImportAsType
from py_aep import parse as parse_aep
from py_aep.binary.footage_chunks import (
    build_ai_layer_opti_data,
    build_psd_flattened_opti_data,
    build_psd_layer_opti_data,
    build_text_opti_data,
)
from py_aep.models.import_options import CURRENT_VALUE, ImportOptions
from py_aep.models.items.composition import CompItem
from py_aep.models.items.folder import FolderItem
from py_aep.models.items.footage import FootageItem
from py_aep.models.sources.file import FileSource
from py_aep.resolvers.ai_layers import (
    UnsupportedAiLayersError,
    read_ai_color_profile,
    read_ai_color_space,
    read_ai_layers,
)
from py_aep.resolvers.media_probe import probe_media
from py_aep.resolvers.psd_layers import (
    FlattenedPsdError,
    PsdGroup,
    PsdLayer,
    UnsupportedPsdLayersError,
    _build_layer_tree,
    _Record,
    read_psd_layers,
)

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"
BASE = (
    Path(__file__).parent.parent.parent / "samples" / "models" / "folder" / "folder.aep"
)
IMPORT_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "import"


def _ae_layer_opti(project: object, layer_name: str) -> bytes | None:
    """Extract AE's per-layer TEXT opti for `layer_name` from a parsed fixture."""
    for item in project.items.values():  # type: ignore[attr-defined]
        source = getattr(item, "main_source", None)
        if isinstance(source, FileSource):
            if getattr(source._opti, "text_layer_name", None) == layer_name:
                return source._opti.tobytes()
    return None


def _comp_opts(file: Path) -> ImportOptions:
    opts = ImportOptions(file)
    opts.import_as = ImportAsType.COMP
    return opts


def _embedded_profile(source: FileSource) -> str | None:
    """The embedded-profile name from a FileSource's CLRS (Utf8 after empd)."""
    chunks = source._clrs.chunks
    types = [c.chunk_type for c in chunks]
    if "empd" not in types:
        return None
    return chunks[types.index("empd") + 1].value


def _ae_psd_layer_opti(project: object, group_name: str) -> bytes | None:
    """Extract AE's per-layer 8BPS opti for `group_name` from a parsed fixture."""
    for item in project.items.values():  # type: ignore[attr-defined]
        source = getattr(item, "main_source", None)
        if (
            isinstance(source, FileSource)
            and getattr(source._opti, "asset_type", "") == "8BPS"
        ):
            if source._opti.psd_group_name == group_name:
                buffer = io.BytesIO()
                source._opti.write(buffer)
                return buffer.getvalue()
    return None


def _opti_bytes(source: FileSource) -> bytes:
    buffer = io.BytesIO()
    source._opti.write(buffer)
    return buffer.getvalue()


def _sspc_bytes(source: FileSource) -> bytes:
    buffer = io.BytesIO()
    source._sspc.write(buffer)
    return buffer.getvalue()


def _psd_footage(project: object) -> dict[str, FootageItem]:
    """Map layer group-name -> the per-layer 8BPS footage item."""
    out: dict[str, FootageItem] = {}
    for item in project.items.values():  # type: ignore[attr-defined]
        if isinstance(item, FootageItem) and isinstance(item.main_source, FileSource):
            opti = item.main_source._opti
            if getattr(opti, "asset_type", "") == "8BPS":
                out[opti.psd_group_name] = item
    return out


def _cropped_opts(file: Path) -> ImportOptions:
    opts = ImportOptions(file)
    opts.import_as = ImportAsType.COMP_CROPPED_LAYERS
    return opts


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
        assert attrs["psd_layer_index"] == 0xFFFFFFFF
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

    def test_item_labels_by_kind(self, tmp_path: Path) -> None:
        # AE 2026 probed: still=5, audio=7, video=3 (Label Preference
        # Indices Section 5 factory values).
        project = parse_aep(BASE).project
        png = project.import_file(ImportOptions(ASSETS / "image_with_alpha.png"))
        assert png._idta.label == 5
        wav = project.import_file(ImportOptions(ASSETS / "wav.wav"))
        assert wav._idta.label == 7
        mov = project.import_file(ImportOptions(ASSETS / "mov_480.mov"))
        assert mov._idta.label == 3

    def test_add_layer_spans_and_labels(self, tmp_path: Path) -> None:
        # AE 2026 probed: layers.add() spans the source duration for timed
        # footage, the still default (comp duration) for stills with the
        # explicit duration honored, and the layer label mirrors the
        # item's label at add time.
        project = parse_aep(BASE).project
        comp = project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        png = project.import_file(ImportOptions(ASSETS / "image_with_alpha.png"))
        mov = project.import_file(ImportOptions(ASSETS / "mov_480.mov"))
        wav = project.import_file(ImportOptions(ASSETS / "wav.wav"))

        still_layer = comp.add(png)
        assert still_layer.out_point == pytest.approx(comp.duration)
        assert still_layer._ldta.label == 5
        mov_layer = comp.add(mov)
        assert mov_layer.out_point == pytest.approx(mov.duration)
        assert mov.duration > comp.duration  # source, not comp, duration
        assert mov_layer._ldta.label == 3
        wav_layer = comp.add(wav)
        assert wav_layer.out_point == pytest.approx(wav.duration)
        assert wav_layer._ldta.label == 7

        still_3s = comp.add(png, 3.0)
        assert still_3s.out_point == pytest.approx(3.0)

        from py_aep.enums import Label

        png.label = Label.BROWN  # 12: the layer mirrors the item label
        assert comp.add(png)._ldta.label == 12

    def test_add_nested_comp_spans_its_duration(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        outer = project.root_folder.add_comp("Outer", 100, 100, 1.0, 5.0, 25.0)
        inner = project.root_folder.add_comp("Inner", 100, 100, 1.0, 2.0, 25.0)
        layer = outer.add(inner)
        assert layer.out_point == pytest.approx(2.0)

    def test_import_sequence_fps_pref(self, tmp_path: Path) -> None:
        # "Import Options Default Sequence FPS" drives the rate of
        # sequences with no native frame rate (30 fps without prefs).
        prefs_dir = tmp_path / "prefs"
        prefs_dir.mkdir()
        (prefs_dir / "Adobe After Effects 26.0 Prefs-indep-general.txt").write_text(
            '["Import Options Preference Section"]\n'
            '\t"Import Options Default Sequence FPS" = "25.000000"\n',
            encoding="utf-8",
        )
        project = parse_aep(BASE, ae_preferences_dir=prefs_dir).project
        opts = ImportOptions(ASSETS / "new_exr.0002.exr")
        opts.sequence = True
        item = project.import_file(opts)
        assert item.frame_rate == pytest.approx(25.0)
        assert item.duration == pytest.approx(2 / 25, abs=1e-4)

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
        assert item.main_source.file_attributes["psd_layer_index"] == 0xFFFFFFFF


class TestImportGapFormats:
    """import_file for formats AE handles that py-aep newly supports.

    Expected values are AE 2026 ground truth (see the import-gap-matrix notes).
    """

    @pytest.mark.parametrize(
        ("filename", "source_format", "width", "height"),
        [
            ("crystal.fbx", "LDOM", 1920, 1080),
            ("txt.txt", "", 0, 0),
            ("csv.csv", "", 0, 0),
            ("json.json", "nosj", 0, 0),
            ("m4a.m4a", "MOoV", 0, 0),
            ("mgjson.mgjson", "sjgm", 0, 0),
            ("mp3.mp3", "MP3A", 0, 0),
            ("aac.aac", "MPEG", 0, 0),
            ("swf.swf", "SWF ", 640, 360),
            ("mpeg.mpeg", "MPEO", 640, 360),
            ("hdr.hdr", "RHDR", 640, 426),
            ("ai.ai", "TEXT", 612, 792),
            ("eps.eps", "TEXT", 1921, 2881),
            ("pdf.pdf", "TEXT", 595, 842),
            ("wmv.wmv", "WMED", 640, 360),
        ],
    )
    def test_import_source_format_and_dims(
        self, filename: str, source_format: str, width: int, height: int
    ) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / filename))
        assert isinstance(item.main_source, FileSource)
        assert item.main_source._sspc.source_format_type == source_format
        assert (item.width, item.height) == (width, height)

    def test_m4a_duration_uses_edit_list(self) -> None:
        # AAC pre-roll makes the raw mdhd duration ~46ms too long; the elst
        # edit-list correction yields AE's 13.839s.
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "m4a.m4a"))
        assert item.duration == pytest.approx(13.839, abs=0.01)
        assert item.main_source._sspc.audio_sample_rate == 44100.0

    def test_aac_duration_and_audio(self) -> None:
        # ADTS frame-scan duration; AE 2026 decodes to 105.790s (the ~0.02s
        # delta is decoder priming, which AE re-derives from the file on open).
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "aac.aac"))
        assert item.main_source._sspc.source_format_type == "MPEG"
        assert item.duration == pytest.approx(105.79, abs=0.05)
        assert item.main_source._sspc.audio_sample_rate == 44100.0
        assert item.has_audio is True
        assert (item.width, item.height) == (0, 0)

    def test_mgjson_duration_from_samples(self) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "mgjson.mgjson"))
        assert item.duration == pytest.approx(468.033, abs=0.01)

    def test_swf_has_alpha_and_frame_rate(self) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "swf.swf"))
        assert item.main_source.has_alpha is True
        assert item.frame_rate == pytest.approx(29.96, abs=0.05)

    def test_text_format_has_alpha(self) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "ai.ai"))
        assert item.main_source.has_alpha is True

    def test_fbx_sets_premultiplied_alpha_flag(self) -> None:
        # AE 2026 sets the sspc premultiplied bit for an imported FBX scene
        # even though alpha_mode_raw stays 0 (straight). Verified against an
        # AE-resaved crystal.fbx.
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "crystal.fbx"))
        sspc = item.main_source._sspc
        assert sspc.premultiplied is True
        assert sspc.alpha_mode_raw == 0

    def test_import_roundtrip_is_byte_identical(self, tmp_path: Path) -> None:
        # A newly supported format (custom RHDR opti) must survive
        # parse -> save -> reparse byte-identically.
        project = parse_aep(BASE).project
        project.import_file(ImportOptions(ASSETS / "hdr.hdr"))
        out = tmp_path / "g.aep"
        project.save(out)
        out2 = tmp_path / "g2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()


class TestImportAiComp:
    """Layered Illustrator (.ai) import as a composition, vs AE ground truth."""

    def test_read_ai_layers_document_order(self) -> None:
        assert read_ai_layers(ASSETS / "ai.ai") == ["Calque 1", "Calque 2"]

    def test_read_ai_layers_non_pdf_raises(self) -> None:
        # Saved without PDF compatibility: artwork is a compressed PGF block
        # with no Optional Content Groups, so layers cannot be enumerated.
        with pytest.raises(UnsupportedAiLayersError):
            read_ai_layers(ASSETS / "ai_no_pdf.ai")

    def test_import_structure(self) -> None:
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "ai.ai"))
        assert comp.name == "ai"
        assert (comp.width, comp.height) == (612, 792)
        # Footage layers (not shape layers), stacked in reverse document order.
        assert [layer.name for layer in comp.layers] == ["Calque 2", "Calque 1"]
        folders = [
            it
            for it in project.items.values()
            if isinstance(it, FolderItem) and it.name == "ai Layers"
        ]
        assert len(folders) == 1
        footage = folders[0].items
        assert len(footage) == 2
        for item in footage:
            assert isinstance(item.main_source, FileSource)
            assert item.main_source.file.endswith("ai.ai")

    def test_per_layer_opti_matches_ae(self) -> None:
        fixture = parse_aep(IMPORT_DIR / "ai_comp.aep").project
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "ai.ai"))
        for layer in comp.layers:
            source = layer.source.main_source
            assert isinstance(source, FileSource)
            mine = source._opti.tobytes()
            # ai.ai is CMYK (Coated FOGRA39), so the opti color-space flag = 0x02.
            assert mine == build_ai_layer_opti_data(612, 792, layer.name, "CMYK")
            assert mine == _ae_layer_opti(fixture, layer.name)

    def test_per_layer_sspc_byte_c9_is_text_zero(self) -> None:
        # Byte 0xC9 of the sspc reserved template is 0x00 for TEXT (AI/EPS/PDF)
        # footage, not the 0x02 that raster/media writes. Regression guard: it
        # was hardcoded 0x02 for all formats - a divergence invisible to the
        # opti-only check above (verified against ai_comp.aep: 0xC9 = 0x00).
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "ai.ai"))
        for layer in comp.layers:
            source = layer.source.main_source
            assert isinstance(source, FileSource)
            assert source._sspc.source_format_type == "TEXT"
            assert _sspc_bytes(source)[0xC4:0xCA] == b"\x00\x00\x00\x01\x00\x00"

    def test_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / "ai.ai"))
        out = tmp_path / "ai_comp.aep"
        project.save(out)
        out2 = tmp_path / "ai_comp2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()

    def test_comp_and_layer_metadata_matches_ae(self) -> None:
        # Comp shutter phase and per-layer ldta flags match AE's import (the
        # only remaining delta is `label`, which is preference-driven).
        fixture = parse_aep(IMPORT_DIR / "ai_comp.aep").project
        ae_comp = next(
            it
            for it in fixture.items.values()
            if isinstance(it, CompItem) and it.name == "ai"
        )
        comp = parse_aep(BASE).project.import_file(_comp_opts(ASSETS / "ai.ai"))
        assert comp.shutter_phase == ae_comp.shutter_phase == -90
        for layer, ae_layer in zip(comp.layers, ae_comp.layers):
            assert layer._ldta._reserved_3b == ae_layer._ldta._reserved_3b == 1
            assert layer._ldta._reserved_3c == ae_layer._ldta._reserved_3c == 0
            assert layer._ldta.name_set is ae_layer._ldta.name_set is True

    def test_embedded_profile_name_extraction(self) -> None:
        assert (
            read_ai_color_profile(ASSETS / "ai.ai")
            == "Coated FOGRA39 (ISO 12647-2:2004)"
        )
        # A non-PDF file has no extractable embedded profile.
        assert read_ai_color_profile(ASSETS / "txt.txt") is None

    def test_comp_footage_records_embedded_profile(self) -> None:
        comp = parse_aep(BASE).project.import_file(_comp_opts(ASSETS / "ai.ai"))
        for layer in comp.layers:
            profile = _embedded_profile(layer.source.main_source)
            assert profile == "Coated FOGRA39 (ISO 12647-2:2004)"

    def test_footage_import_records_embedded_profile(self) -> None:
        item = parse_aep(BASE).project.import_file(ImportOptions(ASSETS / "ai.ai"))
        assert (
            _embedded_profile(item.main_source) == "Coated FOGRA39 (ISO 12647-2:2004)"
        )

    def test_complex_multiartboard_comp(self) -> None:
        # A complex multi-artboard .ai (groups, text, effects, 2 artboards)
        # imports as ONE comp at the document/first-artboard size, with one
        # flat footage layer per Illustrator layer. Nested sublayers are
        # flattened into their parent's layer (no nested comps), and the extra
        # artboard does not create extra comps (AE 2026-verified).
        comp = parse_aep(BASE).project.import_file(_comp_opts(ASSETS / "complex.ai"))
        assert (comp.width, comp.height) == (400, 300)
        assert [layer.name for layer in comp.layers] == [
            "Empty Layer",
            "Artboard 2 Layer",
            "Parent Layer",
            "Effects Layer",
            "Text Layer",
            "Shapes",
            "Background",
            "Calque 1",
        ]
        for layer in comp.layers:
            assert isinstance(layer.source.main_source, FileSource)

    def test_color_space_extraction(self) -> None:
        # The opti color-space flag (byte 0x33) is derived from the embedded
        # ICC's data color space: RGB for complex.ai, CMYK for ai.ai.
        assert read_ai_color_space(ASSETS / "complex.ai") == "RGB"
        assert read_ai_color_space(ASSETS / "ai.ai") == "CMYK"

    def test_complex_comp_per_layer_opti_matches_ae(self) -> None:
        # Full per-layer opti byte-match for an RGB multi-artboard file
        # (exercises the color-space flag 0x33 = 0x08 for RGB).
        fixture = parse_aep(IMPORT_DIR / "complex_comp.aep").project
        ae = {
            s._opti.text_layer_name: s._opti.tobytes()
            for s in (
                it.main_source
                for it in fixture.items.values()
                if isinstance(getattr(it, "main_source", None), FileSource)
            )
            if getattr(s._opti, "asset_type", "") == "TEXT"
        }
        comp = parse_aep(BASE).project.import_file(_comp_opts(ASSETS / "complex.ai"))
        for layer in comp.layers:
            mine = layer.source.main_source._opti.tobytes()
            assert mine == ae[layer.name]


class TestImportEpsComp:
    """EPS import as a composition, vs AE 2026 ground truth.

    EPS is single-stream PostScript with no Optional Content Groups, so AE
    rasterizes it to a one-layer comp (confirmed: AE 2026 imports eps.eps as a
    1-layer comp). Unlike a real AI layer, the footage carries the bare TEXT
    opti (no per-layer name/index/bbox).
    """

    def test_import_structure(self) -> None:
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "eps.eps"))
        assert isinstance(comp, CompItem)
        assert comp.name == "eps"
        assert (comp.width, comp.height) == (1921, 2881)
        assert [layer.name for layer in comp.layers] == ["eps.eps"]
        folders = [
            it
            for it in project.items.values()
            if isinstance(it, FolderItem) and it.name == "eps Layers"
        ]
        assert len(folders) == 1
        footage = folders[0].items
        assert len(footage) == 1
        assert isinstance(footage[0].main_source, FileSource)
        assert footage[0].main_source.file.endswith("eps.eps")

    def test_opti_is_bare_text(self) -> None:
        # The footage opti is the plain TEXT body (dimensions only); the
        # per-layer name/index/bbox an AI layer carries stay zero. Byte-matched
        # against AE 2026's eps.eps comp import.
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "eps.eps"))
        source = comp.layers[0].source.main_source
        assert isinstance(source, FileSource)
        assert source._sspc.source_format_type == "TEXT"
        assert source._opti.tobytes() == build_text_opti_data(1921, 2881)

    def test_layer_name_not_set(self) -> None:
        # The single layer is named after the source item, so AE leaves the
        # ldta name_set bit off (verified against AE's import).
        comp = parse_aep(BASE).project.import_file(_comp_opts(ASSETS / "eps.eps"))
        assert comp.layers[0]._ldta.name_set is False

    def test_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / "eps.eps"))
        out = tmp_path / "eps_comp.aep"
        project.save(out)
        out2 = tmp_path / "eps_comp2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()


class TestImportPsdComp:
    """Layered Photoshop (.psd/.psb) import as a composition, vs AE ground truth.

    `8bits.psd`/`.psb` both have two layers: "black" (lyid 3, bottom) and
    "white with mask" (lyid 4, top), on a 25x26 canvas.
    """

    @pytest.mark.parametrize("name", ["8bits.psd", "8bits.psb"])
    def test_read_psd_layers_document_order(self, name: str) -> None:
        layers = read_psd_layers(ASSETS / name)
        assert [(layer.name, layer.layer_id) for layer in layers] == [
            ("black", 3),
            ("white with mask", 4),
        ]

    def test_read_psd_layers_bad_signature_raises(self) -> None:
        with pytest.raises(UnsupportedPsdLayersError):
            read_psd_layers(ASSETS / "image_with_alpha.png")

    @pytest.mark.parametrize("name", ["8bits.psd", "8bits.psb"])
    def test_import_structure(self, name: str) -> None:
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / name))
        assert comp.name == "8bits"
        assert (comp.width, comp.height) == (25, 26)
        # Footage layers, stacked top layer first (reverse document order).
        assert [layer.name for layer in comp.layers] == ["white with mask", "black"]
        folders = [
            it
            for it in project.items.values()
            if isinstance(it, FolderItem) and it.name == "8bits Layers"
        ]
        assert len(folders) == 1
        footage = folders[0].items
        assert len(footage) == 2
        for item in footage:
            assert isinstance(item.main_source, FileSource)
            assert item.main_source.file.endswith(name)

    @pytest.mark.parametrize(
        "name,fixture", [("8bits.psd", "psd_comp.aep"), ("8bits.psb", "psb_comp.aep")]
    )
    def test_per_layer_opti_matches_ae(self, name: str, fixture: str) -> None:
        info = probe_media(ASSETS / name)
        layers = read_psd_layers(ASSETS / name)
        fixture_project = parse_aep(IMPORT_DIR / fixture).project
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / name))
        index_by_name = {layer.name: i for i, layer in enumerate(layers)}
        for comp_layer in comp.layers:
            source = comp_layer.source.main_source
            assert isinstance(source, FileSource)
            buffer = io.BytesIO()
            source._opti.write(buffer)
            mine = buffer.getvalue()
            psd_layer = layers[index_by_name[comp_layer.name]]
            assert mine == build_psd_layer_opti_data(
                info.width,
                info.height,
                info.bit_depth,
                len(layers),
                index_by_name[comp_layer.name],
                psd_layer.layer_id,
                comp_layer.name,
                psd_layer.bounds,
            )
            assert mine == _ae_psd_layer_opti(fixture_project, comp_layer.name)

    @pytest.mark.parametrize("name", ["8bits.psd", "8bits.psb"])
    def test_roundtrip_byte_identical(self, name: str, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / name))
        out = tmp_path / "comp.aep"
        project.save(out)
        out2 = tmp_path / "comp2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()

    def test_comp_and_layer_metadata_matches_ae(self) -> None:
        # Comp shutter phase and per-layer ldta flags match AE's import (these
        # come from the shared AVLayer/add_comp path the .ai import also uses).
        fixture = parse_aep(IMPORT_DIR / "psd_comp.aep").project
        ae_comp = next(
            it
            for it in fixture.items.values()
            if isinstance(it, CompItem) and it.name == "8bits"
        )
        comp = parse_aep(BASE).project.import_file(_comp_opts(ASSETS / "8bits.psd"))
        assert comp.shutter_phase == ae_comp.shutter_phase == -90
        for layer, ae_layer in zip(comp.layers, ae_comp.layers):
            assert layer._ldta._reserved_3b == ae_layer._ldta._reserved_3b == 1
            assert layer._ldta._reserved_3c == ae_layer._ldta._reserved_3c == 0
            assert layer._ldta.name_set is ae_layer._ldta.name_set is True


def _flattened_footage_opti(project: object) -> bytes:
    """Serialized opti of the single merged 8BPS footage in a flattened import."""
    for item in project.items.values():  # type: ignore[attr-defined]
        source = getattr(item, "main_source", None)
        if isinstance(source, FileSource) and (
            getattr(source._opti, "asset_type", "") == "8BPS"
        ):
            return _opti_bytes(source)
    raise AssertionError("no 8BPS footage found")


class TestImportPsdFlattened:
    """Flattened (layerless) PSD import as a one-layer composition.

    AE 2026 imports a flattened `.psd`/`.psb` as COMP by creating a one-layer
    composition of the merged still: a `<stem> Layers` folder with one footage
    item and a comp with a single full-canvas layer named after the file
    (verified headless against AE 2026; fixture `flattened_rgb_comp.aep`).
    `flattened_rgb.psd` is a real 25x26 RGB Photoshop flatten (present
    layer/mask section, layer count 0); `flattened.psd` is the other flavor (a
    0-length layer/mask section) that the parser must not crash on.
    """

    @pytest.mark.parametrize("name", ["flattened.psd", "flattened_rgb.psd"])
    def test_read_psd_layers_flattened_raises(self, name: str) -> None:
        # Both flattened encodings must raise cleanly (not crash on 0-length).
        with pytest.raises(FlattenedPsdError):
            read_psd_layers(ASSETS / name)
        assert issubclass(FlattenedPsdError, UnsupportedPsdLayersError)

    def test_import_structure(self) -> None:
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "flattened_rgb.psd"))
        assert comp.name == "flattened_rgb"
        assert (comp.width, comp.height) == (25, 26)
        assert comp.shutter_phase == -90
        assert [layer.name for layer in comp.layers] == ["flattened_rgb.psd"]
        folders = [
            it
            for it in project.items.values()
            if isinstance(it, FolderItem) and it.name == "flattened_rgb Layers"
        ]
        assert len(folders) == 1
        footage = folders[0].items
        assert len(footage) == 1
        assert isinstance(footage[0].main_source, FileSource)
        assert footage[0].main_source.file.endswith("flattened_rgb.psd")

    def test_cropped_import_also_one_layer(self) -> None:
        # A flattened file has a single full-canvas layer, so COMP_CROPPED_LAYERS
        # yields the same one-layer comp as COMP (AE 2026 verified).
        project = parse_aep(BASE).project
        comp = project.import_file(_cropped_opts(ASSETS / "flattened_rgb.psd"))
        assert [layer.name for layer in comp.layers] == ["flattened_rgb.psd"]
        assert (comp.width, comp.height) == (25, 26)

    def test_opti_matches_ae(self) -> None:
        info = probe_media(ASSETS / "flattened_rgb.psd")
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "flattened_rgb.psd"))
        source = comp.layers[0].source.main_source
        assert isinstance(source, FileSource)
        mine = _opti_bytes(source)
        assert mine == build_psd_flattened_opti_data(
            info.width, info.height, info.bit_depth, info.channels
        )
        # Gold standard: byte-identical to AE 2026's own flattened-import opti.
        fixture = parse_aep(IMPORT_DIR / "flattened_rgb_comp.aep").project
        assert mine == _flattened_footage_opti(fixture)

    def test_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / "flattened_rgb.psd"))
        out = tmp_path / "comp.aep"
        project.save(out)
        out2 = tmp_path / "comp2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()


class TestImportPsdCropped:
    """COMP_CROPPED_LAYERS for layered PSD, vs AE ground truth.

    `layer_bounds.psd` is a 60x40 doc whose three layers occupy distinct content
    boxes: "red box" (lyid 2, L4 T6 R24 B20), "green box" (lyid 3, L30 T10 R55
    B34), "blue dot" (lyid 4, L12 T24 R22 B36).
    """

    def test_read_layer_bounds(self) -> None:
        layers = read_psd_layers(ASSETS / "layer_bounds.psd")
        assert [(layer.name, layer.layer_id, layer.bounds) for layer in layers] == [
            ("red box", 2, (4, 6, 24, 20)),
            ("green box", 3, (30, 10, 55, 34)),
            ("blue dot", 4, (12, 24, 22, 36)),
        ]

    def test_cropped_structure(self) -> None:
        project = parse_aep(BASE).project
        comp = project.import_file(_cropped_opts(ASSETS / "layer_bounds.psd"))
        assert comp.name == "layer_bounds"
        assert (comp.width, comp.height) == (60, 40)
        assert [layer.name for layer in comp.layers] == [
            "blue dot",
            "green box",
            "red box",
        ]
        footage = _psd_footage(project)
        # Each footage item is cropped to its layer's content box.
        assert (footage["red box"].width, footage["red box"].height) == (20, 14)
        assert (footage["green box"].width, footage["green box"].height) == (25, 24)
        assert (footage["blue dot"].width, footage["blue dot"].height) == (10, 12)

    def test_cropped_matches_ae(self) -> None:
        # Per-layer opti, footage dims, and layer anchor/position match AE.
        fixture = parse_aep(IMPORT_DIR / "layer_bounds_cropped.aep").project
        ae_footage = _psd_footage(fixture)
        ae_comp = next(
            it
            for it in fixture.items.values()
            if isinstance(it, CompItem) and it.name == "layer_bounds"
        )
        ae_xform = {layer.name: layer.transform for layer in ae_comp.layers}

        project = parse_aep(BASE).project
        comp = project.import_file(_cropped_opts(ASSETS / "layer_bounds.psd"))
        for layer in comp.layers:
            source = layer.source.main_source
            assert isinstance(source, FileSource)
            assert _opti_bytes(source) == _opti_bytes(
                ae_footage[layer.name].main_source
            )
            assert (source._sspc.width, source._sspc.height) == (
                ae_footage[layer.name].main_source._sspc.width,
                ae_footage[layer.name].main_source._sspc.height,
            )
            for prop in ("ADBE Anchor Point", "ADBE Position"):
                assert layer.transform[prop].value == ae_xform[layer.name][prop].value

    def test_cropped_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(_cropped_opts(ASSETS / "layer_bounds.psd"))
        out = tmp_path / "cropped.aep"
        project.save(out)
        out2 = tmp_path / "cropped2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()

    def test_margined_comp_opti_uses_content_bounds(self) -> None:
        # A whole-canvas (COMP) import of margined layers keeps full-size footage
        # but stores each layer's content box in the opti (guards the bbox fix).
        fixture = parse_aep(IMPORT_DIR / "layer_bounds_comp.aep").project
        ae_footage = _psd_footage(fixture)
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "layer_bounds.psd"))
        for layer in comp.layers:
            source = layer.source.main_source
            assert isinstance(source, FileSource)
            assert (source._sspc.width, source._sspc.height) == (60, 40)
            assert _opti_bytes(source) == _opti_bytes(
                ae_footage[layer.name].main_source
            )

    def test_sspc_full_frame_flag_matches_ae(self) -> None:
        # AE tags file footage with a reserved template at 0xC4:0xCA; byte 0xC7
        # is 1 for full-frame footage and 0 for a cropped layer region.
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(ASSETS / "image_with_alpha.png"))
        assert isinstance(item.main_source, FileSource)
        assert _sspc_bytes(item.main_source)[0xC4:0xCA] == b"\x00\x00\x00\x01\x00\x02"

        cropped = parse_aep(BASE).project.import_file(
            _cropped_opts(ASSETS / "layer_bounds.psd")
        )
        for layer in cropped.layers:
            source = layer.source.main_source
            assert isinstance(source, FileSource)
            assert _sspc_bytes(source)[0xC4:0xCA] == b"\x00\x00\x00\x00\x00\x02"


class TestImportPsdGroups:
    """Grouped/complex PSDs. AE imports a layer group as a nested composition
    and flags adjustment layers. `grouped_layers.psd` has a group ("MyGroup"
    with "in group A"/"in group B"), plus text, smart-object, adjustment,
    masked, and plain raster layers and an alpha channel.
    """

    def test_read_layers_returns_group_tree(self) -> None:
        nodes = read_psd_layers(ASSETS / "grouped_layers.psd")
        # Top level, bottom first: plain, masked, text, smart, adjustment, then
        # the "MyGroup" group on top.
        assert [n.name for n in nodes] == [
            "plain raster",
            "masked raster",
            "my text",
            "smart obj",
            "hue/sat adj",
            "MyGroup",
        ]
        group = nodes[-1]
        assert isinstance(group, PsdGroup)
        assert [child.name for child in group.children] == ["in group A", "in group B"]
        # Adjustment detection.
        adj = next(n for n in nodes if n.name == "hue/sat adj")
        assert isinstance(adj, PsdLayer) and adj.is_adjustment is True

    def test_build_layer_tree_nested(self) -> None:
        # Pure tree builder on a synthetic nested-group record list (bottom
        # first): bg, [Outer: [Inner: x], y], top.
        def rec(name, lsct=0, idx=0):
            return _Record(name, idx, (0, 0, 0, 0), idx, lsct, False)

        records = [
            rec("bg", 0, 0),
            rec("<outer>", 3, 1),
            rec("<inner>", 3, 2),
            rec("x", 0, 3),
            rec("Inner", 1, 4),
            rec("y", 0, 5),
            rec("Outer", 1, 6),
            rec("top", 0, 7),
        ]
        tree = _build_layer_tree(records)
        assert [n.name for n in tree] == ["bg", "Outer", "top"]
        outer = tree[1]
        assert isinstance(outer, PsdGroup)
        assert [n.name for n in outer.children] == ["Inner", "y"]
        inner = outer.children[0]
        assert isinstance(inner, PsdGroup)
        assert [n.name for n in inner.children] == ["x"]

    def test_group_becomes_nested_comp(self) -> None:
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "grouped_layers.psd"))
        assert comp.name == "grouped_layers"
        # MyGroup is a nested-comp layer; the adjustment layer is flagged.
        info = {layer.name: layer for layer in comp.layers}
        my_group = info["MyGroup"]
        assert isinstance(my_group.source, CompItem)
        assert [layer.name for layer in my_group.source.layers] == [
            "in group B",
            "in group A",
        ]
        assert info["hue/sat adj"].adjustment_layer is True
        assert info["plain raster"].adjustment_layer is False

    def test_group_matches_ae(self) -> None:
        # Main + nested comp layer structure and per-leaf opti match AE.
        fixture = parse_aep(IMPORT_DIR / "grouped_layers_comp.aep").project
        ae_main = next(
            it
            for it in fixture.items.values()
            if isinstance(it, CompItem) and it.name == "grouped_layers"
        )
        project = parse_aep(BASE).project
        comp = project.import_file(_comp_opts(ASSETS / "grouped_layers.psd"))
        assert [layer.name for layer in comp.layers] == [
            layer.name for layer in ae_main.layers
        ]
        for layer, ae_layer in zip(comp.layers, ae_main.layers):
            assert layer.adjustment_layer == ae_layer.adjustment_layer
            # AE collapses the group precomp and leaves its layer name unset.
            assert layer.collapse_transformation == ae_layer.collapse_transformation
            assert layer._ldta.name_set == ae_layer._ldta.name_set
        ae_footage = _psd_footage(fixture)
        mine_footage = _psd_footage(project)
        for name, source in mine_footage.items():
            assert _opti_bytes(source.main_source) == _opti_bytes(
                ae_footage[name].main_source
            )

    def test_grouped_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / "grouped_layers.psd"))
        out = tmp_path / "g.aep"
        project.save(out)
        out2 = tmp_path / "g2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()

    def test_grouped_cropped_import(self) -> None:
        # COMP_CROPPED_LAYERS on a grouped PSD: still builds the nested comp.
        project = parse_aep(BASE).project
        comp = project.import_file(_cropped_opts(ASSETS / "grouped_layers.psd"))
        my_group = next(layer for layer in comp.layers if layer.name == "MyGroup")
        assert isinstance(my_group.source, CompItem)


class TestLayeredImportFolderOrder:
    """The `<stem> Layers` folder is stored case-insensitive alphabetically by
    item name (the AE Project-panel order), not the document order py_aep builds
    the items in. Verified against the grouped_layers / layer_bounds AE fixtures
    (whose stored Sfdr order matches the alphabetical sort, not the item ids).
    """

    def _folder_order(self, project: object) -> list[str]:
        folder = next(
            it
            for it in project.items.values()  # type: ignore[attr-defined]
            if isinstance(it, FolderItem) and it.name.endswith(" Layers")
        )
        return [it.name for it in folder.items]

    def test_grouped_layers_matches_ae(self) -> None:
        # The "MyGroup" nested comp is interleaved alphabetically among the
        # footage ("my text" < "MyGroup" because space < "g"), not front-inserted.
        fixture = parse_aep(IMPORT_DIR / "grouped_layers_comp.aep").project
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / "grouped_layers.psd"))
        assert self._folder_order(project) == self._folder_order(fixture)
        assert self._folder_order(project) == [
            "hue/sat adj/grouped_layers.psd",
            "in group A/grouped_layers.psd",
            "in group B/grouped_layers.psd",
            "masked raster/grouped_layers.psd",
            "my text/grouped_layers.psd",
            "MyGroup",
            "plain raster/grouped_layers.psd",
            "smart obj/grouped_layers.psd",
        ]

    def test_layer_bounds_is_alphabetical_not_document_order(self) -> None:
        # Document order is red, green, blue; AE stores blue, green, red - so
        # this pins the alphabetical sort rather than document/append order.
        fixture = parse_aep(IMPORT_DIR / "layer_bounds_comp.aep").project
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / "layer_bounds.psd"))
        assert self._folder_order(project) == [
            "blue dot/layer_bounds.psd",
            "green box/layer_bounds.psd",
            "red box/layer_bounds.psd",
        ]
        assert self._folder_order(project) == self._folder_order(fixture)


# ---------------------------------------------------------------------------
# Chosen-layer footage import ("Choose Layer" in AE's import dialog)
# ---------------------------------------------------------------------------

# sspc byte offsets where py's still-image imports are known to diverge from
# AE 2026: time divisors (0x2C-0x2D), undecoded still-import flag bytes
# (0x3F-0x41, 0x4F), the _reserved_6f region (0x6F-0x73, an unknown byte AE
# moves between 0x71 and 0x72 across import/replace), and the _reserved_74
# filesystem fingerprint (0x74-0x7C). The layer-binding region (0xBC-0xD3)
# is deliberately NOT masked.
_SSPC_NOISE = (
    frozenset(range(0x2C, 0x2E))
    | frozenset({0x3F, 0x40, 0x41, 0x4F})
    | frozenset(range(0x6F, 0x7D))
)


def _layer_opts(
    file: Path, layer: int | None = None, dims: str | None = None
) -> ImportOptions:
    opts = ImportOptions(file)
    if layer is not None:
        opts.layer_index = layer
    if dims is not None:
        opts.layer_dimensions = dims
    return opts


def _footage_parts(project: object) -> tuple[str, bytes, bytes, str]:
    """(item name, sspc bytes, opti bytes, post-sspc Pin Utf8) of the single
    file footage item."""
    for item in project.items.values():  # type: ignore[attr-defined]
        if isinstance(item, FootageItem) and isinstance(item.main_source, FileSource):
            src = item.main_source
            pin = src._pin.chunks
            sspc_i = next(i for i, c in enumerate(pin) if c.chunk_type == "sspc")
            return (
                item.name,
                _sspc_bytes(src),
                src._opti.tobytes(),
                pin[sspc_i + 1].value,
            )
    raise AssertionError("no file footage item in project")


def _assert_sspc_matches(
    ae: bytes, mine: bytes, extra_noise: frozenset = frozenset()
) -> None:
    assert len(ae) == len(mine)
    noise = _SSPC_NOISE | extra_noise
    diffs = [
        f"0x{off:03x}: ae={ae[off]:02x} py={mine[off]:02x}"
        for off in range(len(ae))
        if off not in noise and ae[off] != mine[off]
    ]
    assert not diffs, diffs


class TestChooseLayerImport:
    """FOOTAGE import of a single layer, vs AE 2026 chooser fixtures.

    `choose_layer.psd` is a 60x40 RGB/8 doc; bottom-to-top: `solo` (lyid 2,
    L4 T6 R24 B20), `twin` (lyid 3), group `grp` holding `inner` (lyid 6),
    `twin` (lyid 4). The duplicate `twin` names are intentional.
    `list_layers` (top first): `["twin", "inner", "twin", "solo"]`, so
    `solo` is index 3 and `inner` index 1.
    """

    @pytest.mark.parametrize(
        "fixture,asset,layer,dims",
        [
            ("choose_layer_merged.aep", "choose_layer.psd", None, None),
            ("choose_layer_solo_doc.aep", "choose_layer.psd", 3, None),
            ("choose_layer_solo_doc.aep", "choose_layer.psd", 3, "document"),
            ("choose_layer_solo_layer.aep", "choose_layer.psd", 3, "layer"),
            ("choose_layer_inner.aep", "choose_layer.psd", 1, None),
            ("ai_choose_layer.aep", "ai.ai", 0, None),
        ],
    )
    def test_matches_ae_fixture(
        self, fixture: str, asset: str, layer: int | None, dims: str | None
    ) -> None:
        # Name-matched byte parity of the load-bearing chunks: opti and the
        # post-sspc Utf8 exactly, sspc outside the known still-import noise.
        ae_name, ae_sspc, ae_opti, ae_utf8 = _footage_parts(
            parse_aep(IMPORT_DIR / fixture).project
        )
        project = parse_aep(BASE).project
        project.import_file(_layer_opts(ASSETS / asset, layer, dims))
        name, sspc, opti, utf8 = _footage_parts(project)
        assert name == ae_name
        assert opti == ae_opti
        assert utf8 == ae_utf8
        _assert_sspc_matches(ae_sspc, sspc)

    def test_layer_size_dimensions(self) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(_layer_opts(ASSETS / "choose_layer.psd", 3, "layer"))
        # solo content box is L4 T6 R24 B20 -> 20x14.
        assert (item.width, item.height) == (20, 14)

    def test_source_layer_name_property(self) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(_layer_opts(ASSETS / "choose_layer.psd", 3))
        assert isinstance(item, FootageItem)
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source.layer_name == "solo"
        merged = project.import_file(_layer_opts(ASSETS / "choose_layer.psd"))
        assert isinstance(merged, FootageItem)
        merged_source = merged.main_source
        assert isinstance(merged_source, FileSource)
        assert merged_source.layer_name == ""

    def test_duplicate_names_disambiguated_by_index(self) -> None:
        # Both `twin` layers (indices 0 and 2, lyid 4 and 3) are
        # individually addressable - the reason selection is by index.
        project = parse_aep(BASE).project
        top = project.import_file(_layer_opts(ASSETS / "choose_layer.psd", 0))
        bottom = project.import_file(_layer_opts(ASSETS / "choose_layer.psd", 2))
        assert isinstance(top, FootageItem) and isinstance(bottom, FootageItem)
        top_source, bottom_source = top.main_source, bottom.main_source
        assert isinstance(top_source, FileSource)
        assert isinstance(bottom_source, FileSource)
        assert top_source.layer_name == bottom_source.layer_name == "twin"
        assert top_source._sspc.layer_id == 4
        assert bottom_source._sspc.layer_id == 3

    def test_out_of_range_layer_index_raises(self) -> None:
        project = parse_aep(BASE).project
        with pytest.raises(ValueError, match="layer_index 4 out of range"):
            project.import_file(_layer_opts(ASSETS / "choose_layer.psd", 4))

    def test_layer_index_with_comp_import_raises(self) -> None:
        opts = _layer_opts(ASSETS / "choose_layer.psd", 3)
        opts.import_as = ImportAsType.COMP
        with pytest.raises(ValueError, match="FOOTAGE only"):
            parse_aep(BASE).project.import_file(opts)

    def test_layer_index_with_sequence_raises(self) -> None:
        opts = _layer_opts(ASSETS / "choose_layer.psd", 3)
        opts.sequence = True
        with pytest.raises(ValueError, match="sequence"):
            parse_aep(BASE).project.import_file(opts)

    def test_layer_dimensions_without_layer_index_raises(self) -> None:
        opts = ImportOptions(ASSETS / "choose_layer.psd")
        opts.layer_dimensions = "layer"
        with pytest.raises(ValueError, match="requires layer_index"):
            parse_aep(BASE).project.import_file(opts)

    def test_layer_index_non_layered_file_raises(self) -> None:
        project = parse_aep(BASE).project
        with pytest.raises(ValueError, match="layered"):
            project.import_file(_layer_opts(ASSETS / "image_with_alpha.png", 0))

    def test_ai_layer_size_not_implemented(self) -> None:
        project = parse_aep(BASE).project
        with pytest.raises(NotImplementedError, match="artwork bounds"):
            project.import_file(_layer_opts(ASSETS / "ai.ai", 0, "layer"))

    @pytest.mark.parametrize(
        "fixture,layer,expected_box,expected_size",
        [
            # Calque 1 has artwork: its box is fractional and offset from
            # the page origin; AE ceils the box size to 482x437 footage px.
            (
                "ai_choose_layer1_size.aep",
                "Calque 1",
                (112.748, 239.5073, 593.931, 675.999),
                (482, 437),
            ),
            # Calque 2 is empty: AE stores a 1/65536-epsilon box and floors
            # the footage at 1x1.
            (
                "ai_choose_layer_size.aep",
                "Calque 2",
                (0.0, 0.0, 1 / 65536, 1 / 65536),
                (1, 1),
            ),
        ],
    )
    def test_ai_layer_size_opti_stores_artwork_bounds(
        self,
        fixture: str,
        layer: str,
        expected_box: tuple[float, float, float, float],
        expected_size: tuple[int, int],
    ) -> None:
        # An AI Layer Size import stores the layer's artwork bounding box
        # (4x signed BE 16.16 at 0x10, page points) in place of the
        # full-page box; py cannot compute the box (it would require
        # rendering the PDF content), but the builder reproduces AE's opti
        # byte-for-byte given the box, pinning the 16.16 layout.
        _name, sspc, ae_opti, _utf8 = _footage_parts(
            parse_aep(IMPORT_DIR / fixture).project
        )
        box = tuple(v / 65536 for v in struct.unpack(">4i", ae_opti[0x10:0x20]))
        assert box == pytest.approx(expected_box, abs=1e-4)
        assert ae_opti == build_ai_layer_opti_data(
            612, 792, layer, "CMYK", artwork_bounds=box
        )
        # sspc holds the derived integer dims and the Layer Size markers.
        assert struct.unpack(">H", sspc[0x20:0x22])[0] == expected_size[0]
        assert struct.unpack(">H", sspc[0x24:0x26])[0] == expected_size[1]
        assert sspc[0xC7] == 0  # full_frame off, like a PSD Layer Size

    def test_roundtrip_byte_identical(self, tmp_path: Path) -> None:
        project = parse_aep(BASE).project
        project.import_file(_layer_opts(ASSETS / "choose_layer.psd", 3))
        project.import_file(_layer_opts(ASSETS / "ai.ai", 0))
        out = tmp_path / "chooser.aep"
        project.save(out)
        out2 = tmp_path / "chooser2.aep"
        parse_aep(out).project.save(out2)
        assert out.read_bytes() == out2.read_bytes()

    def test_reparse_keeps_binding(self, tmp_path: Path) -> None:
        # Disk round-trip, not in-memory: the saved bytes must decode back
        # to the same layer binding.
        project = parse_aep(BASE).project
        project.import_file(_layer_opts(ASSETS / "choose_layer.psd", 1))
        out = tmp_path / "chooser.aep"
        project.save(out)
        name, sspc, _opti, utf8 = _footage_parts(parse_aep(out).project)
        assert name == "inner/choose_layer.psd"
        assert utf8 == "inner"
        assert sspc[0xBC:0xC4] == bytes.fromhex("0000000600000003")


class TestChooseLayerReplace:
    """FootageItem.replace layer rebinding, vs the AE replace fixtures.

    `choose_layer_v2.psd` `list_layers` (top first):
    `["extra", "twin", "solo"]`, so `extra` is index 0 and `solo` index 2.
    """

    def _import(self, layer: int | None, dims: str | None = None) -> tuple:
        project = parse_aep(BASE).project
        item = project.import_file(
            _layer_opts(ASSETS / "choose_layer.psd", layer, dims)
        )
        assert isinstance(item, FootageItem)
        return project, item

    def test_replace_explicit_index_rebinds(self) -> None:
        # AE re-derives index/lyid/bounds/layer_count from the new file.
        project, item = self._import(3)
        item.replace(ASSETS / "choose_layer_v2.psd", layer_index=2)
        ae = _footage_parts(
            parse_aep(IMPORT_DIR / "choose_layer_replace_same.aep").project
        )
        name, sspc, opti, utf8 = _footage_parts(project)
        assert name == ae[0] == "solo/choose_layer_v2.psd"
        assert opti == ae[2]
        assert utf8 == ae[3]
        _assert_sspc_matches(ae[1], sspc)

    def test_replace_with_flat_file_drops_binding(self) -> None:
        project, item = self._import(3)
        item.replace(ASSETS / "image_with_alpha.png")
        ae = _footage_parts(
            parse_aep(IMPORT_DIR / "choose_layer_replace_flat.aep").project
        )
        name, sspc, _opti, utf8 = _footage_parts(project)
        assert name == ae[0] == "image_with_alpha.png"
        assert utf8 == ae[3] == ""
        # py's empty opti and unwritten 0xD0 cache size for plain stills are
        # pre-existing accepted divergences, so mask 0xD0-0xD3 here.
        _assert_sspc_matches(ae[1], sspc, frozenset(range(0xD0, 0xD4)))
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source.layer_name == ""
        assert source._sspc.layer_id == 0xFFFFFFFF
        assert source._sspc.layer_index == 0xFFFFFFFF

    @pytest.mark.parametrize("initial_layer", [None, 3])
    def test_replace_without_index_goes_merged(self, initial_layer: int | None) -> None:
        # layer_index=None always replaces with the merged document -
        # consistent with import_file - whether the current source was
        # merged or bound to a single layer.
        project, item = self._import(initial_layer)
        item.replace(ASSETS / "choose_layer_v2.psd")
        ae = _footage_parts(
            parse_aep(IMPORT_DIR / "choose_layer_replace_from_merged.aep").project
        )
        name, sspc, opti, utf8 = _footage_parts(project)
        assert name == ae[0] == "choose_layer_v2.psd"
        assert opti == ae[2]
        assert utf8 == ae[3] == ""
        _assert_sspc_matches(ae[1], sspc)

    def test_replace_current_value_rebinds_same_record(self) -> None:
        # `solo` has record index 0 in both files, so CURRENT_VALUE lands on
        # the same layer AE's Replace Footage dialog preselects - the
        # replace_same fixture applies unchanged.
        project, item = self._import(3)
        item.replace(ASSETS / "choose_layer_v2.psd", layer_index=CURRENT_VALUE)
        ae = _footage_parts(
            parse_aep(IMPORT_DIR / "choose_layer_replace_same.aep").project
        )
        name, sspc, opti, utf8 = _footage_parts(project)
        assert name == ae[0] == "solo/choose_layer_v2.psd"
        assert opti == ae[2]
        assert utf8 == ae[3]
        _assert_sspc_matches(ae[1], sspc)

    def test_replace_current_value_from_merged_raises(self) -> None:
        _project, item = self._import(None)
        with pytest.raises(ValueError, match="CURRENT_VALUE requires"):
            item.replace(ASSETS / "choose_layer_v2.psd", layer_index=CURRENT_VALUE)

    def test_replace_current_value_missing_record_raises(self) -> None:
        # `inner` is record index 3 in choose_layer.psd; v2's leaf records
        # are [0, 1, 2], so the stored index does not resolve.
        _project, item = self._import(1)
        with pytest.raises(ValueError, match="stored index 3"):
            item.replace(ASSETS / "choose_layer_v2.psd", layer_index=CURRENT_VALUE)

    def test_replace_current_value_flat_file_raises(self) -> None:
        _project, item = self._import(3)
        with pytest.raises(ValueError, match="layered"):
            item.replace(ASSETS / "image_with_alpha.png", layer_index=CURRENT_VALUE)

    def test_replace_out_of_range_index_raises(self) -> None:
        _project, item = self._import(1)
        with pytest.raises(ValueError, match="layer_index 3 out of range"):
            item.replace(ASSETS / "choose_layer_v2.psd", layer_index=3)

    def test_replace_flat_with_explicit_layer_raises(self) -> None:
        _project, item = self._import(3)
        with pytest.raises(ValueError, match="layered"):
            item.replace(ASSETS / "image_with_alpha.png", layer_index=0)

    def test_replace_explicit_layer_binds(self) -> None:
        # An explicit layer_index binds even from a merged source.
        _project, item = self._import(None)
        item.replace(ASSETS / "choose_layer_v2.psd", layer_index=0)
        assert item.name == "extra/choose_layer_v2.psd"
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source.layer_name == "extra"

    def test_replace_preserves_layer_size(self) -> None:
        _project, item = self._import(3, "layer")
        item.replace(ASSETS / "choose_layer_v2.psd", layer_index=2)
        # v2 solo content box is L10 T10 R40 B30 -> 30x20, still Layer Size.
        assert (item.width, item.height) == (30, 20)
        source = item.main_source
        assert isinstance(source, FileSource)
        assert not source._sspc.full_frame

    def test_replace_layer_dimensions_document_overrides_current(self) -> None:
        # Current binding is Layer Size; an explicit "document" forces the
        # full canvas instead of preserving it.
        _project, item = self._import(3, "layer")
        item.replace(
            ASSETS / "choose_layer_v2.psd", layer_index=2, layer_dimensions="document"
        )
        assert (item.width, item.height) != (30, 20)
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source._sspc.full_frame

    def test_replace_layer_dimensions_layer_overrides_current(self) -> None:
        # Current binding is Document Size; an explicit "layer" forces the
        # layer content box (v2 solo box L10 T10 R40 B30 -> 30x20).
        _project, item = self._import(3)
        item.replace(
            ASSETS / "choose_layer_v2.psd", layer_index=2, layer_dimensions="layer"
        )
        assert (item.width, item.height) == (30, 20)
        source = item.main_source
        assert isinstance(source, FileSource)
        assert not source._sspc.full_frame

    def test_replace_invalid_layer_dimensions_raises(self) -> None:
        _project, item = self._import(3)
        with pytest.raises(ValueError, match="must be one of"):
            item.replace(
                ASSETS / "choose_layer_v2.psd", layer_index=2, layer_dimensions="huge"
            )


class TestCompImportLayerBinding:
    """COMP imports write the same per-layer sspc binding + Pin Utf8 as AE."""

    @pytest.mark.parametrize(
        "fixture,asset",
        [
            ("layer_bounds_comp.aep", "layer_bounds.psd"),
            ("grouped_layers_comp.aep", "grouped_layers.psd"),
            ("flattened_rgb_comp.aep", "flattened_rgb.psd"),
            ("ai_comp.aep", "ai.ai"),
        ],
    )
    def test_per_layer_binding_matches_ae(self, fixture: str, asset: str) -> None:
        def by_name(project: object) -> dict[str, tuple[bytes, str]]:
            out: dict[str, tuple[bytes, str]] = {}
            for item in project.items.values():  # type: ignore[attr-defined]
                if isinstance(item, FootageItem) and isinstance(
                    item.main_source, FileSource
                ):
                    src = item.main_source
                    pin = src._pin.chunks
                    sspc_i = next(
                        i for i, c in enumerate(pin) if c.chunk_type == "sspc"
                    )
                    out[item.name] = (_sspc_bytes(src), pin[sspc_i + 1].value)
            return out

        ae = by_name(parse_aep(IMPORT_DIR / fixture).project)
        project = parse_aep(BASE).project
        project.import_file(_comp_opts(ASSETS / asset))
        mine = by_name(project)
        assert set(ae) <= set(mine)
        for name, (ae_sspc, ae_utf8) in ae.items():
            sspc, utf8 = mine[name]
            assert utf8 == ae_utf8, name
            _assert_sspc_matches(ae_sspc, sspc)
