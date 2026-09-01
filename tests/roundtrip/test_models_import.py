"""Tests for media-file probing and file-source creation via import_file."""

from __future__ import annotations

import io
import struct
import warnings
from pathlib import Path

import pytest
from helpers import parse_project_fresh

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

    def test_sequence_sspc_necessary_fields(self, tmp_path: Path) -> None:
        # AE writes these three sspc fields for image sequences and does NOT
        # recompute them on open (proven necessary by an AE open+resave
        # diff, 2026-07-14): full_frame False, 0xC8 kind bytes 0x0000, and
        # byte 5 of the field-separation block 0x01. Verified byte-identical
        # to AE-native PNG/EXR/GIF sequence imports.
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "new_exr.0002.exr")
        opts.sequence = True
        item = project.import_file(opts)
        sspc = item.main_source._sspc
        assert sspc.full_frame is False
        assert sspc._reserved_c8 == b"\x00\x00"
        assert sspc._reserved_4a == b"\x00\x00\x00\x00\x00\x01\x00\x00\x00"


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

    # AE only writes the item-level Utf8 name chunk when the user renames the
    # item, so a replace leaves it alone: a default (source-derived) name
    # re-derives from the new source while a user-assigned one survives. A
    # solid or placeholder instead carries its name in the new opti chunk, so
    # the Utf8 goes back to empty and the new source's name always wins.
    # Every expectation below was taken from AE 2026 performing the same call.

    def test_replace_keeps_user_assigned_name(self) -> None:
        _, item = self._png_footage()
        item.name = "Custom Name"
        item.replace(ASSETS / "mov_480.mov")
        assert item.name == "Custom Name"
        assert item._name_utf8.value == "Custom Name"

    def test_replace_leaves_default_name_derived(self) -> None:
        _, item = self._png_footage()
        item.replace(ASSETS / "mov_480.mov")
        assert item.name == "mov_480.mov"
        # AE derives the name from the source rather than storing it.
        assert item._name_utf8.value == ""

    def test_replace_with_sequence_keeps_user_assigned_name(self) -> None:
        _, item = self._png_footage()
        item.name = "Custom Name"
        item.replace_with_sequence(ASSETS / "new_exr.0002.exr")
        assert item.name == "Custom Name"

    def test_replace_with_sequence_leaves_default_name_derived(self) -> None:
        _, item = self._png_footage()
        item.replace_with_sequence(ASSETS / "new_exr.0002.exr")
        assert item.name == "new_exr.[0002-0003].exr"
        assert item._name_utf8.value == ""

    def test_replace_with_solid_overrides_user_assigned_name(self) -> None:
        _, item = self._png_footage()
        item.name = "Custom Name"
        item.replace_with_solid([0.0, 1.0, 0.0], "Solid D", 50, 50)
        assert item.name == "Solid D"
        assert item._name_utf8.value == ""
        assert item.main_source._opti.solid_name == "Solid D"

    def test_replace_with_placeholder_overrides_user_assigned_name(self) -> None:
        _, item = self._png_footage()
        item.name = "Custom Name"
        item.replace_with_placeholder("PH C", 120, 120, 25.0, 5.0)
        assert item.name == "PH C"
        assert item._name_utf8.value == ""
        assert item.main_source._opti.placeholder_name == "PH C"

    def test_replace_naming_survives_roundtrip(self, tmp_path: Path) -> None:
        project, item = self._png_footage()
        item.name = "Custom Name"
        item.replace(ASSETS / "mov_480.mov")
        out = tmp_path / "r.aep"
        project.save(out)
        reparsed = next(f for f in parse_aep(out).project.footages if f.id == item.id)
        assert reparsed.name == "Custom Name"

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

    def test_grouped_cropped_matches_ae(self) -> None:
        # Every per-layer footage of a grouped cropped import matches AE
        # byte-for-byte (opti + sspc modulo noise). This pins the empty
        # ADJUSTMENT layer "hue/sat adj": full-canvas (80x60, not 1x1) with
        # opti channels 0 (no pixels), distinct from an empty raster.
        ae_project = parse_aep(IMPORT_DIR / "grouped_layers_cropped.aep").project
        project = parse_aep(BASE).project
        project.import_file(_cropped_opts(ASSETS / "grouped_layers.psd"))
        ae_foot = {
            i.name: i.main_source
            for i in ae_project.items.values()
            if isinstance(i, FootageItem) and isinstance(i.main_source, FileSource)
        }
        py_foot = {
            i.name: i.main_source
            for i in project.items.values()
            if isinstance(i, FootageItem) and isinstance(i.main_source, FileSource)
        }
        assert set(ae_foot) == set(py_foot)
        for name, ae_src in ae_foot.items():
            py_src = py_foot[name]
            assert py_src._opti.tobytes() == ae_src._opti.tobytes(), name
            _assert_sspc_matches(_sspc_bytes(ae_src), _sspc_bytes(py_src))
        adj = py_foot["hue/sat adj/grouped_layers.psd"]
        assert (adj._width, adj._height) == (80, 60)
        assert adj._opti.psd_layer_channels == 0


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
        # Name-matched byte parity of the necessary chunks: opti and the
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


class TestImportFileSequenceRange:
    """ImportOptions.range_start/range_end sequence imports.

    Semantics probed against AE 2026 (2026-07-14): the range is
    frame-NUMBER based and inclusive on both ends; the stored
    `start_frame`/`end_frame` are the range bounds even when files are
    missing inside or beyond the range (absent frames are implied
    placeholders); duration spans the bounds.
    """

    def _make_seq(
        self, tmp_path: Path, numbers: list[int], prefix: str = "range_"
    ) -> Path:
        data = (ASSETS / "8bits_compressed.png").read_bytes()
        for n in numbers:
            (tmp_path / f"{prefix}{n:04d}.png").write_bytes(data)
        return tmp_path / f"{prefix}{numbers[0]:04d}.png"

    def _import(self, first: Path, start: int = 0, end: int = 0) -> FootageItem:
        project = parse_aep(BASE).project
        opts = ImportOptions(first)
        opts.sequence = True
        opts.range_start = start
        opts.range_end = end
        item = project.import_file(opts)
        assert isinstance(item, FootageItem)
        return item

    def test_clip_range(self, tmp_path: Path) -> None:
        first = self._make_seq(tmp_path, list(range(1, 13)))
        item = self._import(first, 3, 8)
        sspc = item.main_source._sspc
        assert (sspc.start_frame, sspc.end_frame) == (3, 8)
        # AE probed duration: 0.2 s (6 frames at 30 fps).
        assert item.duration == pytest.approx(0.2, abs=1e-4)
        assert item.name == "range_[0003-0008].png"

    def test_over_range_keeps_bounds(self, tmp_path: Path) -> None:
        first = self._make_seq(tmp_path, list(range(1, 13)))
        item = self._import(first, 10, 20)
        sspc = item.main_source._sspc
        assert (sspc.start_frame, sspc.end_frame) == (10, 20)
        # AE probed duration: 11 frames at 30 fps even though only
        # frames 10-12 exist on disk.
        assert item.duration == pytest.approx(11 / 30, abs=1e-4)

    def test_interior_gap(self, tmp_path: Path) -> None:
        first = self._make_seq(tmp_path, [1, 2, 3, 4, 5, 8, 9, 10, 11, 12])
        item = self._import(first, 3, 8)
        sspc = item.main_source._sspc
        assert (sspc.start_frame, sspc.end_frame) == (3, 8)
        assert item.duration == pytest.approx(0.2, abs=1e-4)

    def test_gapped_full_import_spans_bounds(self, tmp_path: Path) -> None:
        # No range: AE's duration is the frame-number span, not the file
        # count (probed: 1-12 with 6-7 missing -> 0.4 s at 30 fps).
        first = self._make_seq(tmp_path, [1, 2, 3, 4, 5, 8, 9, 10, 11, 12])
        item = self._import(first)
        assert item.duration == pytest.approx(0.4, abs=1e-4)

    def test_start_without_end_raises(self, tmp_path: Path) -> None:
        first = self._make_seq(tmp_path, list(range(1, 13)))
        with pytest.raises(ValueError, match="range end"):
            self._import(first, 5, 0)

    def test_end_before_start_raises(self, tmp_path: Path) -> None:
        first = self._make_seq(tmp_path, list(range(1, 13)))
        with pytest.raises(ValueError, match="less than"):
            self._import(first, 9, 4)

    def test_range_outside_files_raises(self, tmp_path: Path) -> None:
        first = self._make_seq(tmp_path, list(range(1, 13)))
        with pytest.raises(ValueError, match="no sequence frames"):
            self._import(first, 20, 30)

    def test_range_ignored_for_non_sequence(self, tmp_path: Path) -> None:
        # AE parity: a range on a non-sequence import is silently ignored.
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "image_with_alpha.png")
        opts.range_start = 2
        opts.range_end = 5
        item = project.import_file(opts)
        assert isinstance(item, FootageItem)
        assert item.name == "image_with_alpha.png"

    def test_range_roundtrip(self, tmp_path: Path) -> None:
        first = self._make_seq(tmp_path, list(range(1, 13)))
        project = parse_aep(BASE).project
        opts = ImportOptions(first)
        opts.sequence = True
        opts.range_start = 3
        opts.range_end = 8
        project.import_file(opts)
        out = tmp_path / "ranged.aep"
        project.save(out)
        reparsed = parse_aep(out).project
        item = next(
            it for it in reparsed.items.values() if it.name == "range_[0003-0008].png"
        )
        sspc = item.main_source._sspc
        assert (sspc.start_frame, sspc.end_frame) == (3, 8)
        assert item.duration == pytest.approx(0.2, abs=1e-4)


class TestFileSourceReload:
    """FileSource.reload() - AE 2026 semantics: re-probe the file at the
    stored path and update the cached sspc metadata in place (byte-validated
    against an AE reload fixture pair: width/height/data_size refresh, item
    identity and name unchanged)."""

    def _import_png(self, tmp_path: Path):
        target = tmp_path / "reload_src.png"
        target.write_bytes((ASSETS / "8bits_compressed.png").read_bytes())
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(target))
        return project, item, target

    def test_reload_updates_dimensions(self, tmp_path: Path) -> None:
        project, item, target = self._import_png(tmp_path)
        assert (item.width, item.height) == (25, 26)
        new_content = (ASSETS / "image_with_alpha.png").read_bytes()
        target.write_bytes(new_content)
        item.main_source.reload()
        # The AE fixture values for the same file swap.
        assert (item.width, item.height) == (640, 346)
        assert item.main_source._sspc.data_size == len(new_content)
        assert item.name == "reload_src.png"  # reload never renames

    def test_reload_survives_save_and_reparse(self, tmp_path: Path) -> None:
        project, item, target = self._import_png(tmp_path)
        target.write_bytes((ASSETS / "image_with_alpha.png").read_bytes())
        item.main_source.reload()
        out = tmp_path / "reloaded.aep"
        project.save(out)
        reparsed = parse_aep(out).project
        item2 = next(i for i in reparsed.footages if i.name == "reload_src.png")
        assert (item2.width, item2.height) == (640, 346)

    def test_reload_proxy_source(self, tmp_path: Path) -> None:
        # ExtendScript forbids this; py_aep allows it. Every chunk reload
        # touches lives in the source's own Pin, so it is self-contained.
        project, item, _ = self._import_png(tmp_path)
        proxy = tmp_path / "proxy.png"
        proxy.write_bytes((ASSETS / "8bits_compressed.png").read_bytes())
        item.set_proxy(proxy)
        assert isinstance(item.proxy_source, FileSource)
        assert (item.proxy_source._width, item.proxy_source._height) == (25, 26)

        # Swap the proxy file on disk for one with different dimensions.
        # (item.width is not asserted here: AE reports the MAIN source's
        # dimensions even while use_proxy is on - see proxy.json.)
        proxy.write_bytes((ASSETS / "image_with_alpha.png").read_bytes())
        item.proxy_source.reload()
        assert (item.proxy_source._width, item.proxy_source._height) == (640, 346)

        out = tmp_path / "proxy_reloaded.aep"
        project.save(out)
        reparsed = parse_aep(out).project
        item2 = next(i for i in reparsed.footages if i.name == "reload_src.png")
        assert isinstance(item2.proxy_source, FileSource)
        assert (item2.proxy_source._width, item2.proxy_source._height) == (640, 346)

    def test_reload_proxy_leaves_main_source_alone(self, tmp_path: Path) -> None:
        # The proxy and main sources own separate Pins: reloading one must
        # not disturb the other, nor the item's idta footage-kind flags.
        project, item, _ = self._import_png(tmp_path)
        proxy = tmp_path / "proxy.png"
        proxy.write_bytes((ASSETS / "8bits_compressed.png").read_bytes())
        item.set_proxy(proxy)
        main_dims = (item.main_source._width, item.main_source._height)
        flags_before = item._idta._flags_17

        proxy.write_bytes((ASSETS / "image_with_alpha.png").read_bytes())
        assert isinstance(item.proxy_source, FileSource)
        item.proxy_source.reload()

        assert (item.main_source._width, item.main_source._height) == main_dims
        assert item._idta._flags_17 == flags_before

    def test_reload_missing_file_raises(self, tmp_path: Path) -> None:
        project, item, target = self._import_png(tmp_path)
        target.unlink()
        with pytest.raises(ValueError):
            item.main_source.reload()

    def test_reload_path_replaced_by_directory_raises(self, tmp_path: Path) -> None:
        # A directory exists, so an existence check alone passes it through to
        # the format reader, which fails with an OS-specific error
        # (PermissionError on Windows, IsADirectoryError elsewhere) instead of
        # refusing cleanly at the API boundary.
        project, item, target = self._import_png(tmp_path)
        target.unlink()
        target.mkdir()
        with pytest.raises(ValueError, match="not a file"):
            item.main_source.reload()

    def test_import_a_directory_raises(self, tmp_path: Path) -> None:
        # Same class as the reload case, on the import path.
        folder = tmp_path / "looks_like.png"
        folder.mkdir()
        project = parse_aep(BASE).project
        with pytest.raises(ValueError, match="not a file"):
            project.import_file(ImportOptions(folder))

    def test_reload_sequence_rescans_frames(self, tmp_path: Path) -> None:
        data = (ASSETS / "8bits_compressed.png").read_bytes()
        for n in range(1, 4):
            (tmp_path / f"seq_{n:04d}.png").write_bytes(data)
        project = parse_aep(BASE).project
        opts = ImportOptions(tmp_path / "seq_0001.png")
        opts.sequence = True
        item = project.import_file(opts)
        sspc = item.main_source._sspc
        assert (sspc.start_frame, sspc.end_frame) == (1, 3)

        for n in range(4, 7):
            (tmp_path / f"seq_{n:04d}.png").write_bytes(data)
        item.main_source.reload()
        assert (sspc.start_frame, sspc.end_frame) == (1, 6)
        assert item.duration == pytest.approx(6 / 30, abs=1e-4)


# ---------------------------------------------------------------------------
# PSD layer styles (ImportOptions.layer_styles / FootageItem.replace)
# ---------------------------------------------------------------------------

STYLED_PSD = ASSETS / "psd_layer_styles.psd"
VARIANT_PSD = ASSETS / "psd_layer_styles_variant.psd"
SINGLE_PSD = ASSETS / "psd_layer_styles_8bits_single.psd"


def _serialize_tree(chunk: object) -> bytes:
    """Serialize a chunk subtree exactly as write_aep would (skip synthetic)."""
    from io import BytesIO

    from py_aep.binary.chunk import write_chunk

    buffer = BytesIO()
    write_chunk(buffer, chunk)  # type: ignore[arg-type]
    return buffer.getvalue()


def _styles_tdgp(project: object, comp_name: str, layer_name: str) -> object:
    comp = next(
        item
        for item in project.items.values()  # type: ignore[attr-defined]
        if isinstance(item, CompItem) and item.name == comp_name
    )
    layer = comp.layer(name=layer_name)
    return layer.property("ADBE Layer Styles")._tdgp


def _styles_import(
    psd: Path, import_as: ImportAsType, layer_styles: str | None = None
) -> tuple[object, object]:
    project = parse_aep(BASE).project
    opts = ImportOptions(psd)
    opts.import_as = import_as
    if layer_styles is not None:
        opts.layer_styles = layer_styles
    return project, project.import_file(opts)


def _psd_footage_source(project: object, name: str) -> FileSource:
    for item in project.items.values():  # type: ignore[attr-defined]
        if isinstance(item, FootageItem) and item.name == name:
            source = item.main_source
            assert isinstance(source, FileSource)
            return source
    raise AssertionError(f"footage {name!r} not found")


class TestLayerStylesEditableImport:
    """COMP + editable layer styles vs the AE 2026 dialog fixtures.

    The whole `ADBE Layer Styles` subtree must serialize byte-identically
    to AE for every layer of all three sample documents (values, enable
    bytes, tdb4 canon, bounds, gradient GCst containers).
    """

    _TWO_LAYERS = ("Layer 1", "Layer 1 copy")

    @pytest.mark.parametrize(
        "psd,fixture,fixture_comp,layers",
        [
            (
                STYLED_PSD,
                "psd_layer_styles.aep",
                "COMP Editable layer styles",
                _TWO_LAYERS,
            ),
            (VARIANT_PSD, "psd_layer_styles_variant.aep", None, _TWO_LAYERS),
            (SINGLE_PSD, "psd_layer_styles_single.aep", None, _TWO_LAYERS),
            # Noise-type gradients: the style imports without its gradient
            # leaf. The 32-bit sibling also exercises the Lr32 layer records.
            (
                ASSETS / "psd_noise_gradient.psd",
                "psd_noise_gradient.aep",
                None,
                _TWO_LAYERS,
            ),
            (
                ASSETS / "psd_noise_gradient_32bpc.psd",
                "psd_noise_gradient.aep",
                None,
                _TWO_LAYERS,
            ),
            # 2D point leaves: dragged Gradient Overlay offset + Pattern
            # Overlay phase (the only 2D-spatial style leaves).
            (
                ASSETS / "psd_styles_offset_phase.psd",
                "psd_styles_offset_phase.aep",
                None,
                _TWO_LAYERS,
            ),
            # Gradient smoothness: Intr 2048/1024 -> gradientSmoothness 50/25.
            (
                ASSETS / "psd_styles_smoothness.psd",
                "psd_styles_smoothness.aep",
                None,
                _TWO_LAYERS,
            ),
            # Blend options without styles (iOpa alone enables the chain)
            # and a present-but-disabled drop shadow (tdsb 0x00 + values).
            (
                ASSETS / "psd_fill_opacity.psd",
                "psd_fill_opacity.aep",
                None,
                ("fill only", "fill plus disabled shadow", "Layer 1"),
            ),
            # Legacy 4CC blend-mode enum spellings (spliced Mltp/SftL).
            (
                ASSETS / "psd_blend_4cc.psd",
                "psd_blend_4cc.aep",
                None,
                ("legacy modes", "Layer 1"),
            ),
            # The full 27-mode 4CC probe: AE resolves the 16 true-legacy
            # typeIDs and silently defaults the post-CS ones; py must
            # match both behaviors byte-for-byte on every layer.
            (
                ASSETS / "psd_blend_4cc_all.psd",
                "psd_blend_4cc_all.aep",
                None,
                (
                    "normal",
                    "dissolve",
                    "darken",
                    "multiply",
                    "colorBurn",
                    "linearBurn",
                    "darkerColor",
                    "lighten",
                    "screen",
                    "colorDodge",
                    "linearDodge",
                    "lighterColor",
                    "overlay",
                    "softLight",
                    "hardLight",
                    "vividLight",
                    "linearLight",
                    "pinLight",
                    "hardMix",
                    "difference",
                    "exclusion",
                    "hue",
                    "saturation",
                    "color",
                    "luminosity",
                    "blendSubtraction",
                    "blendDivide",
                    "Layer 1",
                ),
            ),
            # Styles on a layer GROUP: AE drops them (plain skeleton on the
            # precomp layer); the child's own style still imports.
            (
                ASSETS / "psd_group_styles.psd",
                "psd_group_styles.aep",
                None,
                ("styled group", "outside", "Layer 1"),
            ),
            (
                ASSETS / "psd_group_styles.psd",
                "psd_group_styles.aep",
                "styled group",
                ("inner bottom", "inner top"),
            ),
        ],
    )
    def test_styles_subtree_matches_ae(
        self,
        psd: Path,
        fixture: str,
        fixture_comp: str | None,
        layers: tuple[str, ...],
    ) -> None:
        ae_project = parse_aep(IMPORT_DIR / fixture).project
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            project, comp = _styles_import(psd, ImportAsType.COMP)
        # A named fixture_comp that exists in the py project too (the nested
        # group comp) targets that comp on both sides; otherwise the py side
        # is the freshly imported main comp.
        py_comp = comp.name
        if fixture_comp is not None and any(
            item.name == fixture_comp for item in project.items.values()
        ):
            py_comp = fixture_comp
        ae_comp = fixture_comp if fixture_comp is not None else comp.name
        for layer_name in layers:
            ae_tree = _serialize_tree(_styles_tdgp(ae_project, ae_comp, layer_name))
            py_tree = _serialize_tree(_styles_tdgp(project, py_comp, layer_name))
            assert py_tree == ae_tree, f"{psd.name} {layer_name}"

    def test_survives_disk_roundtrip(self, tmp_path: Path) -> None:
        # Enable/flag bytes are validated through a real save + re-parse:
        # a forgiving reader can mask a wrong written byte.
        ae_project = parse_aep(IMPORT_DIR / "psd_layer_styles_single.aep").project
        project, comp = _styles_import(SINGLE_PSD, ImportAsType.COMP)
        out = tmp_path / "editable.aep"
        project.save(out)
        reparsed = parse_project_fresh(out)
        ae_tree = _serialize_tree(_styles_tdgp(ae_project, comp.name, "Layer 1"))
        re_tree = _serialize_tree(_styles_tdgp(reparsed, comp.name, "Layer 1"))
        assert re_tree == ae_tree
        layer = next(
            item
            for item in reparsed.items.values()
            if isinstance(item, CompItem) and item.name == comp.name
        ).layer(name="Layer 1")
        styles = layer.property("ADBE Layer Styles")
        assert styles.enabled is True
        assert styles["dropShadow/enabled"].enabled is True
        assert styles["dropShadow/enabled"]["dropShadow/mode2"].value == 17.0

    def test_new_enable_states_survive_disk_roundtrip(self, tmp_path: Path) -> None:
        # The blend-only chain (tdsb 0x01 with zero styles), the
        # present-but-disabled 0x00 state, and the always-enabled Adv Blend
        # subgroup, re-read from an actual save (synthetic chunks flip real).
        ae_project = parse_aep(IMPORT_DIR / "psd_fill_opacity.aep").project
        project, comp = _styles_import(
            ASSETS / "psd_fill_opacity.psd", ImportAsType.COMP
        )
        out = tmp_path / "fill_opacity.aep"
        project.save(out)
        reparsed = parse_project_fresh(out)
        for layer_name in ("fill only", "fill plus disabled shadow", "Layer 1"):
            ae_tree = _serialize_tree(_styles_tdgp(ae_project, comp.name, layer_name))
            re_tree = _serialize_tree(_styles_tdgp(reparsed, comp.name, layer_name))
            assert re_tree == ae_tree, layer_name
        comp_item = next(
            item
            for item in reparsed.items.values()
            if isinstance(item, CompItem) and item.name == comp.name
        )
        styles = comp_item.layer(name="fill plus disabled shadow").property(
            "ADBE Layer Styles"
        )
        assert styles["dropShadow/enabled"].enabled is False
        assert styles["dropShadow/enabled"]._tdsb._enable_flags == 0
        adv = styles["ADBE Blend Options Group"]["ADBE Adv Blend Group"]
        assert adv["ADBE Layer Fill Opacity2"].value == 60.0

    def test_per_layer_footage_matches_ae(self) -> None:
        # sspc parity (modulo the documented still-import noise) + opti
        # byte-equality for the editable per-layer footage, including the
        # document pixel-aspect resource (4/3) and the mode byte 0x02.
        ae_project = parse_aep(IMPORT_DIR / "psd_layer_styles_single.aep").project
        project, _ = _styles_import(SINGLE_PSD, ImportAsType.COMP)
        for name in (
            "Layer 1/psd_layer_styles_8bits_single.psd",
            "Layer 1 copy/psd_layer_styles_8bits_single.psd",
        ):
            ae_source = _psd_footage_source(ae_project, name)
            py_source = _psd_footage_source(project, name)
            _assert_sspc_matches(_sspc_bytes(ae_source), _sspc_bytes(py_source))
            assert py_source._opti.tobytes() == ae_source._opti.tobytes()
            assert py_source.layer_styles == "editable"

    def test_multi_instance_styles_warn_and_disable(self) -> None:
        with pytest.warns(UserWarning, match="frameFX"):
            project, comp = _styles_import(STYLED_PSD, ImportAsType.COMP)
        layer = comp.layer(name="Layer 1")
        styles = layer.property("ADBE Layer Styles")
        assert styles["frameFX/enabled"].enabled is False
        assert styles["dropShadow/enabled"].enabled is True


class TestLayerStylesModes:
    def test_comp_merge_writes_skeleton_and_mode_byte(self) -> None:
        project, comp = _styles_import(SINGLE_PSD, ImportAsType.COMP, "merge")
        source = _psd_footage_source(
            project, "Layer 1/psd_layer_styles_8bits_single.psd"
        )
        assert source._sspc._reserved_c8 == b"\x00\x01"
        assert source.layer_styles == "merge"
        layer = comp.layer(name="Layer 1")
        styles = layer.property("ADBE Layer Styles")
        assert styles.enabled is False
        assert all(
            not child.enabled
            for child in styles.properties
            if child.match_name.endswith("/enabled")
        )

    def test_cropped_merge_on_styled_layer_raises(self) -> None:
        with pytest.raises(NotImplementedError, match="layer styles"):
            _styles_import(SINGLE_PSD, ImportAsType.COMP_CROPPED_LAYERS, "merge")

    def test_cropped_merge_on_style_less_psd_works(self) -> None:
        _, comp = _styles_import(
            ASSETS / "choose_layer.psd", ImportAsType.COMP_CROPPED_LAYERS, "merge"
        )
        assert isinstance(comp, CompItem)

    def test_footage_ignore_matches_ae_fixture_item(self) -> None:
        ae_project = parse_aep(IMPORT_DIR / "psd_layer_styles.aep").project
        ae_item = next(
            item
            for item in ae_project.items.values()
            if isinstance(item, FootageItem)
            and item.name == "FOOTAGE Layer 1 Ignore layer styles"
        )
        project = parse_aep(BASE).project
        opts = ImportOptions(STYLED_PSD)
        opts.layer_index = 1  # "Layer 1" (bottom) in top-first dropdown order
        opts.layer_styles = "ignore"
        item = project.import_file(opts)
        ae_source, py_source = ae_item.main_source, item.main_source
        assert isinstance(py_source, FileSource)
        _assert_sspc_matches(_sspc_bytes(ae_source), _sspc_bytes(py_source))
        assert py_source._opti.tobytes() == ae_source._opti.tobytes()
        assert py_source.layer_styles == "ignore"

    def test_footage_merge_on_styled_layer_keeps_raw_bounds(self) -> None:
        # Documented divergence: AE stores the style-EXPANDED raster bounds
        # for merge mode; py writes the raw content box and AE restores the
        # expanded opti bbox on open (self-healing; data_size is a tolerated
        # stale cache). See docs/limitations.md.
        project = parse_aep(BASE).project
        opts = ImportOptions(STYLED_PSD)
        opts.layer_index = 1
        item = project.import_file(opts)  # merge is the FOOTAGE default
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source._sspc._reserved_c8 == b"\x00\x01"
        opti = source._opti
        assert (
            opti.psd_layer_left,
            opti.psd_layer_top,
            opti.psd_layer_right,
            opti.psd_layer_bottom,
        ) == (0, 0, 24, 25)

    def test_layer_size_merge_on_styled_layer_raises(self) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(STYLED_PSD)
        opts.layer_index = 1
        opts.layer_dimensions = "layer"
        with pytest.raises(NotImplementedError, match="layer styles"):
            project.import_file(opts)

    def test_layer_size_ignore_on_styled_layer_works(self) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(STYLED_PSD)
        opts.layer_index = 1
        opts.layer_dimensions = "layer"
        opts.layer_styles = "ignore"
        item = project.import_file(opts)
        assert (item.width, item.height) == (24, 25)


class TestLayerStylesValidation:
    def test_setter_rejects_bad_values(self) -> None:
        opts = ImportOptions(STYLED_PSD)
        with pytest.raises(ValueError):
            opts.layer_styles = "bake"
        with pytest.raises(ValueError, match="CURRENT_VALUE"):
            opts.layer_styles = CURRENT_VALUE

    @pytest.mark.parametrize(
        "import_as,layer_index,layer_styles,match",
        [
            (ImportAsType.FOOTAGE, 1, "editable", "COMP import"),
            (ImportAsType.FOOTAGE, None, "merge", "requires layer_index"),
            (ImportAsType.COMP, None, "ignore", "no Ignore option"),
        ],
    )
    def test_import_context_rules(
        self,
        import_as: ImportAsType,
        layer_index: int | None,
        layer_styles: str,
        match: str,
    ) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(STYLED_PSD)
        opts.import_as = import_as
        if layer_index is not None:
            opts.layer_index = layer_index
        opts.layer_styles = layer_styles
        with pytest.raises(ValueError, match=match):
            project.import_file(opts)

    def test_non_psd_rejected(self) -> None:
        project = parse_aep(BASE).project
        opts = ImportOptions(ASSETS / "ai.ai")
        opts.import_as = ImportAsType.COMP
        opts.layer_styles = "merge"
        with pytest.raises(ValueError, match="Photoshop"):
            project.import_file(opts)


class TestLayerStylesReplace:
    def _ignore_item(self) -> FootageItem:
        project = parse_aep(BASE).project
        opts = ImportOptions(STYLED_PSD)
        opts.layer_index = 1
        opts.layer_styles = "ignore"
        item = project.import_file(opts)
        assert isinstance(item, FootageItem)
        return item

    def test_current_value_preserves_recorded_choice(self) -> None:
        item = self._ignore_item()
        item.replace(VARIANT_PSD, CURRENT_VALUE)
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source.layer_styles == "ignore"

    def test_current_value_preserves_editable_byte(self) -> None:
        # Per-layer footage of an editable comp records mode 0x02; replace
        # keeps the byte verbatim (editable state lives on comp layers).
        project, _ = _styles_import(SINGLE_PSD, ImportAsType.COMP)
        for item in project.items.values():
            if (
                isinstance(item, FootageItem)
                and item.name == "Layer 1/psd_layer_styles_8bits_single.psd"
            ):
                break
        else:
            raise AssertionError("per-layer footage not found")
        item.replace(VARIANT_PSD, CURRENT_VALUE)
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source.layer_styles == "editable"
        assert source._sspc._reserved_c8 == b"\x00\x02"

    def test_explicit_values_and_rejections(self) -> None:
        item = self._ignore_item()
        item.replace(STYLED_PSD, CURRENT_VALUE, layer_styles="merge")
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source.layer_styles == "merge"
        with pytest.raises(ValueError):
            item.replace(STYLED_PSD, CURRENT_VALUE, layer_styles="editable")
        with pytest.raises(ValueError, match="Photoshop"):
            item.replace(ASSETS / "ai.ai", 0, layer_styles="ignore")

    def test_merged_current_falls_back_to_merge(self) -> None:
        project = parse_aep(BASE).project
        item = project.import_file(ImportOptions(STYLED_PSD))
        assert isinstance(item, FootageItem)
        item.replace(STYLED_PSD, 1)
        source = item.main_source
        assert isinstance(source, FileSource)
        assert source.layer_styles == "merge"


# ---------------------------------------------------------------------------
# PSD vector masks / shape layers (imported as AE masks)
# ---------------------------------------------------------------------------


def _mask_parade_bytes(project: object, comp_name: str, layer_name: str) -> bytes:
    """Serialize a layer's Mask Parade with the per-machine mkif noise
    normalized: `_reserved_0c` carries an app-global counter + timestamp
    fingerprint, and the outline color follows AE's non-reproducible
    global mask-color cycle (see MaskPropertyGroup._MASK_COLOR_CYCLE)."""
    comp = next(
        item
        for item in project.items.values()  # type: ignore[attr-defined]
        if isinstance(item, CompItem) and item.name == comp_name
    )
    parade = comp.layer(name=layer_name).property("ADBE Mask Parade")
    for mask in parade.properties:
        mkif = mask._mkif
        if mkif is not None and not mkif.synthetic:
            mkif._reserved_0c = bytes(33)
            mkif.color_r = mkif.color_g = mkif.color_b = 0
    return _serialize_tree(parade._tdgp)


class TestVectorMaskImport:
    """PSD vector masks and shape-layer paths become AE masks, one per
    subpath, byte-matched (modulo the documented mkif noise) against the
    AE 2026 fixtures."""

    @pytest.mark.parametrize(
        "name,layer_name,mask_count",
        [
            ("psd_vector_mask", "vector masked", 1),
            ("psd_shape_layer", "rect shape", 1),
            # Smooth knots: tangent decode fidelity.
            ("psd_vector_mask_curves", "curved", 1),
            # Two subpaths: AE creates Mask 1 + Mask 2.
            ("psd_vector_mask_multi", "two rects", 2),
        ],
    )
    def test_mask_parade_matches_ae(
        self, name: str, layer_name: str, mask_count: int
    ) -> None:
        ae_project = parse_aep(IMPORT_DIR / f"{name}.aep").project
        project, comp = _styles_import(ASSETS / f"{name}.psd", ImportAsType.COMP)
        py_parade = (
            next(
                item
                for item in project.items.values()
                if isinstance(item, CompItem) and item.name == comp.name
            )
            .layer(name=layer_name)
            .property("ADBE Mask Parade")
        )
        assert len(py_parade.properties) == mask_count
        assert all(m.roto_bezier is False for m in py_parade.properties)
        ae_tree = _mask_parade_bytes(ae_project, name, layer_name)
        py_tree = _mask_parade_bytes(project, comp.name, layer_name)
        assert py_tree == ae_tree

    def test_cropped_import_offsets_mask_to_content_box(self) -> None:
        # Mask vertices are canvas coordinates; a COMP_CROPPED_LAYERS layer
        # is cropped to its content box, so AE shifts the mask by the crop
        # origin ((20,12)-(52,44) minus origin (4,4), AE 2026 fixture).
        ae_project = parse_aep(IMPORT_DIR / "psd_vector_mask_cropped.aep").project
        project, comp = _styles_import(
            ASSETS / "psd_vector_mask.psd", ImportAsType.COMP_CROPPED_LAYERS
        )
        py_comp = next(
            item
            for item in project.items.values()
            if isinstance(item, CompItem) and item.name == comp.name
        )
        parade = py_comp.layer(name="vector masked").property("ADBE Mask Parade")
        shape = parade.properties[0].property("ADBE Mask Shape").value
        assert shape.vertices == [[16.0, 8.0], [48.0, 8.0], [48.0, 40.0], [16.0, 40.0]]
        ae_tree = _mask_parade_bytes(ae_project, "psd_vector_mask", "vector masked")
        py_tree = _mask_parade_bytes(project, comp.name, "vector masked")
        assert py_tree == ae_tree

    def test_cropped_mask_vertices_survive_reparse(self, tmp_path: Path) -> None:
        # Mask space is LAYER space: after save + reparse, the cached parse
        # Shape must still denormalize by the (56px cropped) layer size, not
        # the 64px comp - reading vertices must return the same layer-space
        # coordinates as before the round-trip.
        project, comp = _styles_import(
            ASSETS / "psd_vector_mask.psd", ImportAsType.COMP_CROPPED_LAYERS
        )
        out = tmp_path / "cropped_mask.aep"
        project.save(out)
        reparsed = parse_project_fresh(out)
        layer = next(
            item
            for item in reparsed.items.values()
            if isinstance(item, CompItem) and item.name == comp.name
        ).layer(name="vector masked")
        assert (layer.width, layer.height) == (56, 56)
        shape = (
            layer.property("ADBE Mask Parade")
            .properties[0]
            .property("ADBE Mask Shape")
            .value
        )
        # f4 shph precision loss on the round-trip; the scale basis is what
        # matters (layer 56, not comp 64 which would give ~18.3/9.1).
        flat = [coord for vertex in shape.vertices for coord in vertex]
        assert flat == pytest.approx(
            [16.0, 8.0, 48.0, 8.0, 48.0, 40.0, 16.0, 40.0], abs=1e-3
        )

    def test_clipping_run_auto_precomposes(self, tmp_path: Path) -> None:
        """A PSD clipping pair (base + clipped-to-base layer) imports like
        AE: a nested comp named "<stem> (1)", the base's name baked on the
        uncollapsed parent layer with name_set off, and preserve
        transparency on the clipped member (psd_clipping_mask fixture) -
        verified through a disk round-trip."""
        project, comp = _styles_import(
            ASSETS / "psd_clipping_mask.psd", ImportAsType.COMP
        )
        out = tmp_path / "clipping.aep"
        project.save(out)
        reparsed = parse_project_fresh(out)
        main = next(
            item
            for item in reparsed.items.values()
            if isinstance(item, CompItem) and item.name == comp.name
        )
        base_layer = main.layer(name="base")
        assert isinstance(base_layer.source, CompItem)
        assert base_layer.source.name == f"{comp.name} (1)"
        assert base_layer._ldta.name_set is False
        assert base_layer.label == 15
        assert base_layer.collapse_transformation is False
        nested = base_layer.source
        assert [layer.name for layer in nested.layers] == ["clipped", "base"]
        assert nested.layer(name="clipped").preserve_transparency is True
        assert nested.layer(name="base").preserve_transparency is False
        assert nested.parent_folder.name == f"{comp.name} Layers"

    def test_cropped_clipping_matches_ae(self) -> None:
        # COMP_CROPPED_LAYERS + a clipping run: AE still auto-precomposes,
        # the base crops to its content box (40x40), the clipped layer keeps
        # its full-canvas content box, and every per-layer footage matches
        # AE byte-for-byte (opti + sspc modulo the still-import noise).
        ae_project = parse_aep(IMPORT_DIR / "psd_clipping_mask_cropped.aep").project
        project = parse_aep(BASE).project
        project.import_file(_cropped_opts(ASSETS / "psd_clipping_mask.psd"))
        ae_foot = {
            i.name: i.main_source
            for i in ae_project.items.values()
            if isinstance(i, FootageItem) and isinstance(i.main_source, FileSource)
        }
        py_foot = {
            i.name: i.main_source
            for i in project.items.values()
            if isinstance(i, FootageItem) and isinstance(i.main_source, FileSource)
        }
        assert set(ae_foot) == set(py_foot)
        for name, ae_src in ae_foot.items():
            py_src = py_foot[name]
            assert py_src._opti.tobytes() == ae_src._opti.tobytes(), name
            _assert_sspc_matches(_sspc_bytes(ae_src), _sspc_bytes(py_src))
        # The empty background "Layer 1" is full-canvas (64x64), not 1x1, and
        # keeps its raster channel count (4) despite the empty content box.
        empty = py_foot["Layer 1/psd_clipping_mask.psd"]
        assert (empty._width, empty._height) == (64, 64)
        assert empty._sspc.data_size == 0
        assert empty._opti.psd_layer_channels == 4

    def test_layers_without_vector_masks_get_none(self, tmp_path: Path) -> None:
        # Raster layer masks are baked into the footage by AE (masks=0);
        # the disk round-trip also re-reads the created mask chunks.
        project, comp = _styles_import(
            ASSETS / "psd_raster_mask.psd", ImportAsType.COMP
        )
        comp_item = next(
            item
            for item in project.items.values()
            if isinstance(item, CompItem) and item.name == comp.name
        )
        parade = comp_item.layer(name="masked").property("ADBE Mask Parade")
        assert len(parade.properties) == 0

        project2, comp2 = _styles_import(
            ASSETS / "psd_vector_mask.psd", ImportAsType.COMP
        )
        out = tmp_path / "vector_mask.aep"
        project2.save(out)
        reparsed = parse_project_fresh(out)
        ae_project = parse_aep(IMPORT_DIR / "psd_vector_mask.aep").project
        ae_tree = _mask_parade_bytes(ae_project, "psd_vector_mask", "vector masked")
        re_tree = _mask_parade_bytes(reparsed, comp2.name, "vector masked")
        assert re_tree == ae_tree


class TestImportChoicePrefsWiring:
    """import_file fills an unset layer_styles/layer_dimensions from the
    machine's sticky PSD import-dialog preferences (AE's own importFile does
    the same). Factory fallbacks are covered by the merge/editable tests
    above; these cover the pref-driven path and its PSD-only gating."""

    _SECTION = "Choose Layer Dialog"

    def test_footage_layer_styles_from_pref(self) -> None:
        project = parse_aep(BASE).project
        # PSD Footage Layer Styles Option: 1 = ignore.
        project._preferences.set_pref_as_number(
            self._SECTION, "PSD Footage Layer Styles Option", 1
        )
        source = project.import_file(_layer_opts(STYLED_PSD, 1)).main_source
        assert isinstance(source, FileSource)
        assert source.layer_styles == "ignore"

    def test_explicit_layer_styles_overrides_pref(self) -> None:
        project = parse_aep(BASE).project
        project._preferences.set_pref_as_number(
            self._SECTION,
            "PSD Footage Layer Styles Option",
            1,  # ignore
        )
        opts = _layer_opts(STYLED_PSD, 1)
        opts.layer_styles = "merge"
        source = project.import_file(opts).main_source
        assert isinstance(source, FileSource)
        assert source.layer_styles == "merge"

    def test_footage_dimensions_from_pref(self) -> None:
        project = parse_aep(BASE).project
        # PSD Dimensions Popup: 0 = layer (style-less solo layer, no expansion).
        project._preferences.set_pref_as_number(
            self._SECTION, "PSD Dimensions Popup", 0
        )
        source = project.import_file(
            _layer_opts(ASSETS / "choose_layer.psd", 3)
        ).main_source
        assert isinstance(source, FileSource)
        assert source._sspc.full_frame is False

    def test_comp_layer_styles_from_pref(self) -> None:
        project = parse_aep(BASE).project
        # PSD Comp Layer Styles Option v2: 1 = merge (bakes the styles in).
        project._preferences.set_pref_as_number(
            self._SECTION, "PSD Comp Layer Styles Option v2", 1
        )
        opts = ImportOptions(SINGLE_PSD)
        opts.import_as = ImportAsType.COMP
        project.import_file(opts)
        source = _psd_footage_source(
            project, "Layer 1/psd_layer_styles_8bits_single.psd"
        )
        assert source.layer_styles == "merge"

    def test_ai_layer_import_ignores_psd_dimensions_pref(self) -> None:
        # The dimensions pref is PSD-only. An AI/PDF layer import must keep
        # its document-size default: a PSD "layer" pref leaking through would
        # trip _from_layer's Layer-Size NotImplementedError for AI.
        project = parse_aep(BASE).project
        project._preferences.set_pref_as_number(
            self._SECTION,
            "PSD Dimensions Popup",
            0,  # layer
        )
        source = project.import_file(_layer_opts(ASSETS / "ai.ai", 0)).main_source
        assert isinstance(source, FileSource)
        assert source._sspc.full_frame is True
