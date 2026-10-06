"""Regression tests for the v9 fuzz findings on footage import, reload,
replace and interpretation (area C). Each expectation is AE 2026 ground
truth from an AE import / reload / render of the same file (see the
comments), or an exact law."""

from __future__ import annotations

import os
import shutil
import struct
import warnings
import zlib
from pathlib import Path

import pytest
from helpers import parse_project_fresh, project_bytes

from py_aep import ImportAsType
from py_aep import parse as parse_aep
from py_aep.color.icc import (
    default_icc_directories,
    default_icc_library,
    icc_profile_id,
)
from py_aep.models.import_options import CURRENT_VALUE, ImportOptions
from py_aep.models.items.footage import FootageItem
from py_aep.models.sources.file import FileSource
from py_aep.resolvers.source_layers import list_layers

SAMPLES = Path(__file__).parent.parent.parent / "samples"
ASSETS = SAMPLES / "assets"
BASE = SAMPLES / "models" / "folder" / "folder.aep"
# An Adobe-CMS project (no working space), as AE's own imports were probed in.
ADOBE_BASE = SAMPLES / "models" / "import" / "windows_stills.aep"
_ICC_AVAILABLE = any(d.is_dir() for d in default_icc_directories())


def _project(base: Path = BASE) -> object:
    return parse_aep(base, platform="windows").project


def _import(project: object, path: Path, **options: object) -> object:
    opts = ImportOptions(path)
    for key, value in options.items():
        setattr(opts, key, value)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return project.import_file(opts)  # type: ignore[attr-defined]


def _layer_footage(project: object, file_name: str) -> list[FootageItem]:
    return [
        item
        for item in project.footages  # type: ignore[attr-defined]
        if isinstance(item.main_source, FileSource)
        and Path(item.main_source.file).name == file_name
        and item.main_source.layer_name
    ]


def _pin_bytes(source: FileSource) -> dict[str, bytes]:
    # Every Pin chunk but the random `pgui` id.
    return {
        f"{index}:{getattr(c, 'list_type', None) or c.chunk_type}": c.tobytes()
        for index, c in enumerate(source._pin.chunks)
        if c.chunk_type != "pgui"
    }


# --- synthetic files -----------------------------------------------------


def _psd_record(
    name: str,
    box: tuple[int, int, int, int],
    *,
    hidden: bool = False,
    lyid: int | None = None,
    lsct: int | None = None,
) -> tuple[bytes, bytes]:
    top, left, bottom, right = box
    size = max(right - left, 0) * max(bottom - top, 0)
    channels = (-1, 0, 1, 2)
    record = struct.pack(">iiiiH", top, left, bottom, right, len(channels))
    for channel in channels:
        record += struct.pack(">hI", channel, 2 + size)
    record += b"8BIMnorm" + bytes([255, 0, 0x02 if hidden else 0x00, 0])
    raw_name = name.encode("latin-1", "replace")[:255]
    pascal = bytes([len(raw_name)]) + raw_name
    pascal += b"\0" * (-len(pascal) % 4)
    unicode_name = struct.pack(">I", len(name)) + name.encode("utf-16-be")
    unicode_name += b"\0" * (-len(unicode_name) % 4)
    extra = struct.pack(">II", 0, 0) + pascal
    extra += b"8BIMluni" + struct.pack(">I", len(unicode_name)) + unicode_name
    if lyid is not None:
        extra += b"8BIMlyid" + struct.pack(">II", 4, lyid)
    if lsct is not None:  # 3 = group bounding divider, 1 = open group header
        extra += b"8BIMlsct" + struct.pack(">II", 4, lsct)
    record += struct.pack(">I", len(extra)) + extra
    data = b"".join(struct.pack(">H", 0) + bytes([200]) * size for _ in channels)
    return record, data


def _psd(path: Path, size: int, records: list[tuple[bytes, bytes]]) -> Path:
    """An 8-bit RGB PSD with raw-coded layer records."""
    layer_info = struct.pack(">h", -len(records))
    layer_info += b"".join(r for r, _ in records) + b"".join(d for _, d in records)
    layer_info += b"\0" * (len(layer_info) % 2)
    section = struct.pack(">I", len(layer_info)) + layer_info + struct.pack(">I", 0)
    header = b"8BPS" + struct.pack(">H", 1) + b"\0" * 6
    header += struct.pack(">HIIHH", 3, size, size, 8, 3)
    body = struct.pack(">II", 0, 0) + struct.pack(">I", len(section)) + section
    body += struct.pack(">H", 0) + bytes([128]) * (size * size * 3)
    path.write_bytes(header + body)
    return path


def _tiff(path: Path, bits: list[int], photometric: int, extra: int | None) -> Path:
    """An uncompressed 8x8 little-endian TIFF (palette: a full colour map)."""
    width = height = 8
    row = (width * sum(bits) + 7) // 8
    pixels = bytes([0x40]) * (row * height)
    out = bytearray(b"II*\0\0\0\0\0") + pixels
    if len(out) % 2:
        out += b"\0"
    tags: list[tuple[int, int, int, bytes]] = [
        (256, 3, 1, struct.pack("<HH", width, 0)),
        (257, 3, 1, struct.pack("<HH", height, 0)),
        (259, 3, 1, struct.pack("<HH", 1, 0)),
        (262, 3, 1, struct.pack("<HH", photometric, 0)),
        (273, 4, 1, struct.pack("<I", 8)),
        (277, 3, 1, struct.pack("<HH", len(bits), 0)),
        (278, 4, 1, struct.pack("<I", height)),
        (279, 4, 1, struct.pack("<I", len(pixels))),
    ]
    bps = b"".join(struct.pack("<H", b) for b in bits)
    if len(bps) <= 4:
        tags.append((258, 3, len(bits), bps.ljust(4, b"\0")))
    else:
        tags.append((258, 3, len(bits), struct.pack("<I", len(out))))
        out += bps
    if extra is not None:
        tags.append((338, 3, 1, struct.pack("<HH", extra, 0)))
    if photometric == 3:
        entries = 1 << bits[0]
        color_map = b"".join(
            struct.pack("<H", i * 65535 // (entries - 1)) for i in range(entries)
        )
        tags.append((320, 3, 3 * entries, struct.pack("<I", len(out))))
        out += color_map * 3
    tags.sort()
    ifd = len(out)
    struct.pack_into("<I", out, 4, ifd)
    out += struct.pack("<H", len(tags))
    for tag, kind, count, value in tags:
        out += struct.pack("<HHI", tag, kind, count) + value
    out += b"\0\0\0\0"
    path.write_bytes(bytes(out))
    return path


def _png(path: Path, width: int, height: int) -> Path:
    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    return path


# --- C2: malformed .ai imports as footage --------------------------------


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.5\n1 0 obj\n<</OCProperties<</D<</Order 8 0 R/",
        b'%PDF-1.5\n1 0 obj\n<</OCProperties<</D "x>>>>\n',
    ],
)
def test_malformed_ai_still_imports_as_footage(tmp_path: Path, data: bytes) -> None:
    # A truncated or corrupt .ai hung (COS lexer EOF loop) or raised
    # SyntaxError since the import started counting its layers; it imports
    # as whole-document footage, as before.
    path = tmp_path / "bad.ai"
    path.write_bytes(data)
    item = _import(_project(), path)
    assert item.main_source._opti.text_document_layers == 0


# --- C1 / C12: reload --------------------------------------------------


@pytest.mark.parametrize(
    ("asset", "options"),
    [
        ("layer_bounds.psd", {"import_as": ImportAsType.COMP_CROPPED_LAYERS}),
        ("layer_bounds.psd", {"import_as": ImportAsType.COMP}),
        ("psd_layer_styles.psd", {"layer_index": 0, "layer_styles": "ignore"}),
        ("layer_bounds.psd", {"layer_index": 0, "layer_dimensions": "layer"}),
        ("ai.ai", {"import_as": ImportAsType.COMP}),
        ("ai.ai", {"layer_index": 0, "layer_dimensions": "layer"}),
    ],
)
def test_reload_keeps_the_layer_binding(
    tmp_path: Path, asset: str, options: dict[str, object]
) -> None:
    # AE 2026 reloads a layer-bound source as that same layer (a cropped
    # layer stays 10x12, the name stays "<layer>/<file>"); py_aep used to
    # rebuild it as the merged document.
    project = _project()
    _import(project, ASSETS / asset, **options)
    items = _layer_footage(project, asset)
    assert items
    before = {item.id: (item.name, _pin_bytes(item.main_source)) for item in items}
    for item in items:
        item.main_source.reload()
    for item in items:
        name, pin = before[item.id]
        assert item.name == name
        assert _pin_bytes(item.main_source) == pin
    out = tmp_path / "reloaded.aep"
    project.save(out)  # type: ignore[attr-defined]
    reparsed = parse_project_fresh(out)
    for item in items:
        assert reparsed.items[item.id].name == before[item.id][0]


def test_reload_restamps_the_source_mtime(tmp_path: Path) -> None:
    # AE 2026 writes the file's current mtime into the sspc stamp on reload.
    path = tmp_path / "frame.png"
    shutil.copy(ASSETS / "image_with_alpha.png", path)
    os.utime(path, (1_600_000_000, 1_600_000_000))
    item = _import(_project(), path)
    os.utime(path, (1_700_000_000, 1_700_000_000))
    item.main_source.reload()
    assert item.main_source._sspc.source_modified == 1_700_000_000


def test_sequence_reload_keeps_the_unreduced_duration() -> None:
    # A sequence's duration is frames over rate, unreduced (3/30), as the
    # import and every AE-authored sequence write it.
    item = _import(_project(), ASSETS / "dpx_seq.0001.dpx", sequence=True)
    sspc = item.main_source._sspc
    before = (sspc.duration_dividend, sspc.duration_divisor)
    item.main_source.reload()
    assert (sspc.duration_dividend, sspc.duration_divisor) == before == (3, 30)


# --- C4: conform rates AE cannot open ------------------------------------


@pytest.mark.parametrize("asset", ["mov_23_976.mov", "dpx_seq.0001.dpx"])
def test_tiny_conform_rate_is_rejected_unmodified(asset: str) -> None:
    # AE 2026 refused to open py's projects holding 0.0004 ("zero denominator
    # in ratio multiply") and opened 0.0005 on a movie and a sequence.
    project = _project()
    item = _import(project, ASSETS / asset, sequence=asset.endswith(".dpx"))
    before = project_bytes(project)
    with pytest.raises(ValueError, match="0.0005"):
        item.main_source.conform_frame_rate = 0.0004
    assert project_bytes(project) == before
    item.main_source.conform_frame_rate = 0.0005
    assert item.main_source.conform_frame_rate == pytest.approx(0.0005, abs=1e-5)


# --- C6: footage size ------------------------------------------------------


def test_footage_wider_than_32767_px_is_rejected_unmodified(tmp_path: Path) -> None:
    # AE reads the sspc size as signed 16-bit: 65535 px opened as -1, and
    # 65536 did not fit (save failed). Rejected before anything is added.
    project = _project()
    before = project_bytes(project)
    for path in (
        _png(tmp_path / "wide.png", 32768, 1),
        _psd(tmp_path / "wide.psd", 1, [_psd_record("a", (0, 0, 1, 1))]),
    ):
        if path.suffix == ".psd":
            data = bytearray(path.read_bytes())
            struct.pack_into(">I", data, 18, 40000)  # canvas width
            path.write_bytes(bytes(data))
        for how in (ImportAsType.FOOTAGE, ImportAsType.COMP):
            if how == ImportAsType.COMP and path.suffix != ".psd":
                continue
            with pytest.raises(ValueError, match="32767"):
                _import(project, path, import_as=how)
            assert project_bytes(project) == before
    assert _import(project, _png(tmp_path / "ok.png", 32767, 1)).width == 32767


# --- C7 / C10 / C13: synthetic Photoshop documents ------------------------


@pytest.mark.parametrize("how", [ImportAsType.COMP, ImportAsType.COMP_CROPPED_LAYERS])
def test_hidden_photoshop_layer_imports_disabled(
    tmp_path: Path, how: ImportAsType
) -> None:
    # AE 2026 turns the video switch off for a layer hidden in Photoshop
    # (synthetic hidden_layer.psd: frame 0 rendered without it).
    path = _psd(
        tmp_path / "hidden.psd",
        16,
        [
            _psd_record("visible", (0, 0, 8, 8), lyid=2),
            _psd_record("hidden", (4, 4, 12, 12), hidden=True, lyid=3),
        ],
    )
    comp = _import(_project(), path, import_as=how)
    enabled = {layer.name: layer.enabled for layer in comp.layers}
    assert enabled == {"hidden": False, "visible": True}


@pytest.mark.parametrize("how", [ImportAsType.COMP, ImportAsType.COMP_CROPPED_LAYERS])
def test_hidden_photoshop_group_imports_disabled(
    tmp_path: Path, how: ImportAsType
) -> None:
    # AE 2026 turns the group's nested-comp layer off and leaves the
    # children's switches alone (synthetic hidden_group.psd).
    path = _psd(
        tmp_path / "hidden_group.psd",
        16,
        [
            _psd_record("</Layer group>", (0, 0, 0, 0), lsct=3, lyid=10),
            _psd_record("in hidden group", (0, 0, 8, 8), lyid=11),
            _psd_record("hidden group", (0, 0, 0, 0), hidden=True, lsct=1, lyid=12),
            _psd_record("top visible", (8, 8, 16, 16), lyid=13),
        ],
    )
    comp = _import(_project(), path, import_as=how)
    layers = {layer.name: layer for layer in comp.layers}
    assert layers["top visible"].enabled is True
    group = layers["hidden group"]
    assert group.enabled is False
    assert [inner.enabled for inner in group.source.layers] == [True]


def test_layer_ids_without_lyid_number_from_two(tmp_path: Path) -> None:
    # AE 2026 numbers the layers of a PSD without `lyid` blocks from 2 in
    # record order (opti 0x154 and sspc layer_id).
    path = _psd(
        tmp_path / "no_ids.psd",
        16,
        [_psd_record("a", (0, 0, 8, 8)), _psd_record("b", (8, 8, 16, 16))],
    )
    project = _project()
    _import(project, path, import_as=ImportAsType.COMP)
    ids = {
        item.main_source.layer_name: item.main_source._sspc.layer_id
        for item in _layer_footage(project, path.name)
    }
    assert ids == {"a": 2, "b": 3}


def test_photoshop_layer_count_above_255(tmp_path: Path) -> None:
    # The opti layer count is 16-bit: AE 2026 writes 300 (`2c 01`) for a
    # 300-layer document, merged and per layer.
    path = _psd(
        tmp_path / "many.psd",
        40,
        [
            _psd_record(f"L{i:03d}", (i % 40, i % 39, i % 40 + 1, i % 39 + 1))
            for i in range(300)
        ],
    )
    project = _project()
    merged = _import(project, path)
    assert merged.main_source._opti.psd_layer_count == 300
    layer = _import(project, path, layer_index=0)
    assert layer.main_source._opti.psd_layer_count == 300


def test_long_photoshop_layer_name_is_cut_to_255_bytes(tmp_path: Path) -> None:
    # AE 2026 keeps the longest UTF-8 prefix of 255 bytes for the comp layer.
    name = "été 日本 " + "x" * 300
    path = _psd(tmp_path / "long.psd", 16, [_psd_record(name, (0, 0, 8, 8), lyid=2)])
    comp = _import(_project(), path, import_as=ImportAsType.COMP)
    layer_name = comp.layers[0].name
    assert len(layer_name.encode("utf-8")) == 255
    assert name.startswith(layer_name)


def test_background_layer_is_named_background() -> None:
    # AE 2026 names Photoshop's Background layer "Background" whatever the
    # file stores (a French Photoshop's "Arrière-plan"; footage_depth.aep).
    asset = ASSETS / "depth" / "psd_rgb8_bg_layer.psd"
    assert list_layers(asset)[-1] == "Background"
    comp = _import(_project(), asset, import_as=ImportAsType.COMP)
    assert [layer.name for layer in comp.layers] == ["Layer 1", "Background"]


# --- C9: empty content box at Layer Size -------------------------------


@pytest.mark.parametrize(
    ("asset", "layer_name", "size"),
    [
        ("grouped_layers.psd", "hue/sat adj", (80, 60)),
        ("psd_clipping_mask.psd", "Layer 1", (64, 64)),
    ],
)
def test_empty_layer_at_layer_size_spans_the_canvas(
    asset: str, layer_name: str, size: tuple[int, int]
) -> None:
    # As in AE's cropped-comp import of the same layer (fixtures
    # grouped_layers_cropped / psd_clipping_mask_cropped); 0x0 before.
    index = list_layers(ASSETS / asset).index(layer_name)
    item = _import(
        _project(), ASSETS / asset, layer_index=index, layer_dimensions="layer"
    )
    assert (item.width, item.height) == size
    assert item.main_source._sspc.full_frame is False


def test_replace_current_value_keeps_an_empty_cropped_layer() -> None:
    project = _project()
    _import(
        project,
        ASSETS / "grouped_layers.psd",
        import_as=ImportAsType.COMP_CROPPED_LAYERS,
    )
    item = next(
        f for f in project.footages if f.name == "hue/sat adj/grouped_layers.psd"
    )
    item.replace(ASSETS / "grouped_layers.psd", layer_index=CURRENT_VALUE)
    assert (item.width, item.height) == (80, 60)


# --- C8: image sequences -----------------------------------------------


def _frames(folder: Path, names: list[str]) -> Path:
    folder.mkdir()
    for name in names:
        shutil.copy(ASSETS / "depth" / "png_g8.png", folder / name)
    return folder


@pytest.mark.parametrize(
    ("names", "pick", "expected"),
    [
        # AE 2026: at most the last 9 digits are the frame number.
        (
            ["f_99999999998.png", "f_99999999999.png"],
            1,
            "f_99[999999998-999999999].png",
        ),
        (["f_4294967294.png", "f_4294967295.png"], 1, "f_4[294967294-294967295].png"),
        # AE 2026 (Windows): prefixes compare case-insensitively, the name
        # takes the first frame's.
        (["F_001.png", "f_002.png"], 1, "F_[001-002].png"),
    ],
)
def test_sequence_frame_numbers_match_after_effects(
    tmp_path: Path, names: list[str], pick: int, expected: str
) -> None:
    folder = _frames(tmp_path / "seq", names)
    project = _project()
    item = _import(project, folder / names[pick], sequence=True)
    assert item.name == expected
    out = tmp_path / "seq.aep"
    project.save(out)
    assert parse_project_fresh(out).items[item.id].name == expected


def test_huge_frame_range_with_a_fractional_rate_saves(tmp_path: Path) -> None:
    # frames x 100 / 2997 overflowed the u4 duration dividend at save.
    project = _project()
    item = _import(
        project,
        ASSETS / "dpx_seq.0001.dpx",
        sequence=True,
        range_start=1,
        range_end=2**32 - 1,
    )
    item.main_source.conform_frame_rate = 29.97
    project.save(tmp_path / "range.aep")
    expected = (2**32 - 1) / 29.97
    assert item.duration == pytest.approx(expected, rel=1e-6)


def test_replace_with_sequence_validates_force_alphabetical() -> None:
    item = _import(_project(), ASSETS / "image_with_alpha.png")
    with pytest.raises(TypeError):
        item.replace_with_sequence(ASSETS / "dpx_seq.0001.dpx", force_alphabetical=1)


def test_invalid_default_sequence_fps_preference_is_rejected(tmp_path: Path) -> None:
    prefs = tmp_path / "prefs"
    prefs.mkdir()
    (prefs / "Adobe After Effects 26.0 Prefs-indep-general.txt").write_text(
        '["Import Options Preference Section"]\n'
        '\t"Import Options Default Sequence FPS" = "0.000000"\n',
        encoding="utf-8",
    )
    project = parse_aep(BASE, ae_preferences_dir=prefs).project
    with pytest.raises(ValueError, match="default sequence frame rate"):
        _import(project, ASSETS / "dpx_seq.0001.dpx", sequence=True)


# --- C13: TIFF bit depths below 8 ----------------------------------------


@pytest.mark.parametrize(
    ("bits", "photometric", "extra", "depth", "channels", "layers", "data_size"),
    [
        # AE 2026 reads 2/4-bit gray and palette TIFFs as 8 bits.
        ([2], 1, None, 40, 1, 0, 64),
        ([4], 1, None, 40, 1, 0, 64),
        ([4], 3, None, 8, 1, 0, 64),
        # A palette image's alpha sample is not counted in the opti.
        ([8, 8], 3, 2, 32, 1, 0, 64),
    ],
)
def test_tiff_depth_fields_match_after_effects(
    tmp_path: Path,
    bits: list[int],
    photometric: int,
    extra: int | None,
    depth: int,
    channels: int,
    layers: int,
    data_size: int,
) -> None:
    item = _import(_project(), _tiff(tmp_path / "t.tif", bits, photometric, extra))
    source = item.main_source
    opti = source._opti.tobytes()
    assert source._sspc.depth == depth
    assert opti[0x1E] == channels
    assert int.from_bytes(opti[0x28:0x2A], "little") == 8
    assert int.from_bytes(opti[0x30:0x32], "little") == layers
    assert source._sspc.data_size == data_size


# --- C3: colour profiles (Adobe CMS project) -----------------------------


def _clrs(source: FileSource) -> dict[str, object]:
    chunks = source._clrs.chunks
    out: dict[str, object] = {}
    for index, chunk in enumerate(chunks):
        if chunk.chunk_type in ("epid", "apid"):
            out[chunk.chunk_type] = chunk.data
        elif chunk.chunk_type == "empd":
            out["empd"] = chunks[index + 1].value
        elif chunk.chunk_type == "ipws":
            out["ipws"] = chunk.value
        elif chunk.chunk_type in ("mcsp", "ocsp"):
            out[chunk.chunk_type] = chunks[index + 1].value
    return out


_UNSET = b"\xff" * 16


@pytest.mark.parametrize(
    ("asset", "name"),
    [
        ("depth/psd_cmyk8_flat.psd", "U.S. Web Coated (SWOP) v2"),
        ("depth/tif_cmyk8.tif", "U.S. Web Coated (SWOP) v2"),
        ("depth/psd_gray8_flat.psd", "Dot Gain 20%"),
        ("depth/tif_g8.tif", "Dot Gain 20%"),
        ("depth/tif_gf32.tif", "Linear Grayscale Profile"),
        ("depth/psd_lab8_flat.psd", "Lab D50"),
        ("depth/tif_lab8.tif", "Lab D50"),
        ("depth/psd_indexed8_flat.psd", "sRGB IEC61966-2.1"),
        ("depth/tif_pal8.tif", "sRGB IEC61966-2.1"),
        ("ai.ai", "Coated FOGRA39 (ISO 12647-2:2004)"),
    ],
)
def test_non_rgb_media_names_its_profile(asset: str, name: str) -> None:
    # AE 2026 records the profile by name only and interprets the footage in
    # the working space (Adobe CMS project, AE's import of the same file).
    clrs = _clrs(_import(_project(ADOBE_BASE), ASSETS / asset).main_source)
    assert clrs["empd"] == name
    assert clrs["ipws"] == 1
    assert clrs["epid"] == clrs["apid"] == _UNSET
    assert not clrs.get("mcsp") and not clrs.get("ocsp")


def test_dpx_and_cineon_carry_no_profile() -> None:
    for asset in ("dpx_10bit_be.dpx", "cin.cin"):
        clrs = _clrs(_import(_project(ADOBE_BASE), ASSETS / asset).main_source)
        assert clrs["epid"] == clrs["apid"] == _UNSET
        assert "empd" not in clrs
        assert clrs["ipws"] == 1
        assert not clrs.get("ocsp")


@pytest.mark.skipif(not _ICC_AVAILABLE, reason="Adobe ICC profiles not installed")
@pytest.mark.parametrize(
    ("asset", "slot", "profile"),
    [
        # Bitmap: sRGB assigned, not taken as carried.
        ("depth/psd_bitmap_flat.psd", "apid", "sRGB IEC61966-2.1"),
        ("depth/tif_bilevel.tif", "apid", "sRGB IEC61966-2.1"),
        # Camera Raw develops into ProPhoto RGB, which AE embeds.
        ("crw.crw", "epid", "ProPhoto RGB"),
        # An RGB-profiled .ai embeds the profile like a raster file.
        ("complex.ai", "epid", "sRGB IEC61966-2.1"),
        # An .ai without PDF content draws with no profile: sRGB assigned.
        ("ai_no_pdf.ai", "apid", "sRGB IEC61966-2.1"),
    ],
)
def test_profile_records_match_after_effects(
    asset: str, slot: str, profile: str
) -> None:
    clrs = _clrs(_import(_project(ADOBE_BASE), ASSETS / asset).main_source)
    other = "apid" if slot == "epid" else "epid"
    assert clrs[slot] == icc_profile_id(default_icc_library().bytes_for(profile))
    assert clrs[other] == _UNSET
    assert "empd" not in clrs
    assert clrs["ipws"] == 0


@pytest.mark.parametrize(
    ("fixture", "platform", "asset"),
    [
        (ADOBE_BASE, "windows", "heic_alpha.heic"),
        (SAMPLES / "models/format_options/heic/base.aep", "macos", "heic.heic"),
        (SAMPLES / "models/format_options/heic/base.aep", "macos", "heic_alpha.heic"),
    ],
)
def test_heic_imports_with_linear_light_off(
    fixture: Path, platform: str, asset: str
) -> None:
    # AE 2026 imports HEIC with Interpret As Linear Light off on both
    # platforms (these fixtures, and a scripted import on Windows).
    truth = {f.name: f.main_source for f in parse_aep(fixture).project.footages}
    project = parse_aep(fixture, platform=platform).project
    ours = _import(project, ASSETS / asset).main_source
    assert ours._linl.value == truth[asset]._linl.value == 0


_MAC_EPOCH = 2082844800


def _stamp(item: object) -> bytes:
    return item._idta.tobytes()[0x50:0x54]  # type: ignore[attr-defined]


def _mac(unix_time: int) -> bytes:
    return (unix_time + _MAC_EPOCH).to_bytes(4, "big")


def _stamped_copy(src: Path, dest: Path, mtime: int) -> Path:
    shutil.copy(src, dest)
    os.utime(dest, (mtime, mtime))
    return dest


def test_idta_stamp_follows_the_file_in_use(tmp_path: Path) -> None:
    # AE 2026 stamps a footage item's idta (0x50, big-endian Mac-epoch
    # seconds) with the mtime of the file in use: the main file on import,
    # replace and reload, the proxy's while a file proxy is in use, and the
    # main file's again after useProxy = false or setProxyToNone.
    png = ASSETS / "image_with_alpha.png"
    main = _stamped_copy(png, tmp_path / "main.png", 1_610_000_000)
    proxy = _stamped_copy(ASSETS / "bmp.bmp", tmp_path / "proxy.bmp", 1_610_002_000)
    other = _stamped_copy(png, tmp_path / "other.png", 1_610_003_000)
    project = _project()
    item = _import(project, main)
    assert _stamp(item) == _mac(1_610_000_000)
    item.set_proxy(proxy)
    assert _stamp(item) == _mac(1_610_002_000)
    item.use_proxy = False
    assert _stamp(item) == _mac(1_610_000_000)
    item.use_proxy = True
    assert _stamp(item) == _mac(1_610_002_000)
    item.set_proxy_to_none()
    assert _stamp(item) == _mac(1_610_000_000)
    item.replace(other)
    assert _stamp(item) == _mac(1_610_003_000)
    os.utime(other, (1_700_000_000, 1_700_000_000))
    item.main_source.reload()
    assert _stamp(item) == _mac(1_700_000_000)
    out = tmp_path / "out.aep"
    project.save(out)  # type: ignore[attr-defined]
    assert _stamp(parse_project_fresh(out).items[item.id]) == _mac(1_700_000_000)


def test_idta_stamp_of_sequences_placeholders_and_comps(tmp_path: Path) -> None:
    # AE 2026 stamps a sequence with its folder's mtime, leaves the stamp
    # alone when a placeholder becomes the proxy or the main source, and
    # keeps a comp's own (edit-time) stamp when it gets a file proxy
    # (sample proxy.aep).
    folder = tmp_path / "seq"
    folder.mkdir()
    for frame in ("s_001.png", "s_002.png"):
        _stamped_copy(ASSETS / "image_with_alpha.png", folder / frame, 1_610_000_000)
    os.utime(folder, (1_610_006_000, 1_610_006_000))
    project = _project()
    item = _import(project, folder / "s_001.png", sequence=True)
    assert _stamp(item) == _mac(1_610_006_000)
    item.set_proxy_with_placeholder("PP", 10, 10, 25.0, 1.0)
    item.replace_with_placeholder("RP", 10, 10, 25.0, 1.0)
    assert _stamp(item) == _mac(1_610_006_000)
    comp = project.root_folder.add_comp("C", 100, 100, 1.0, 1.0, 25.0)  # type: ignore[attr-defined]
    before = _stamp(comp)
    comp.set_proxy(folder / "s_001.png")
    assert _stamp(comp) == before
