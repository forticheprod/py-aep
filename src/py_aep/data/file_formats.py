"""Footage file-format table: extension -> AE source-format code and defaults.

Derived empirically by importing `samples/assets/` in AE 2026 and decoding the
resulting `sspc` chunks (see the `filesource-aep-format` notes). `source_format`
is the 4-char code stored in `SspcChunk.source_format_type`.
"""

from __future__ import annotations

from typing import NamedTuple

from ..enums import ImportAsType


class FileFormat(NamedTuple):
    """Static per-format defaults for footage import."""

    source_format: str
    """4-char `sspc.source_format_type` code (e.g. `png!`, `oEXR`)."""

    alpha_premultiplied: bool
    """When the footage has alpha, `True` selects PREMULTIPLIED, else STRAIGHT."""

    opti: str
    """`opti` asset-info strategy, verified against AE 2026:

    - `"empty"`: AE re-reads the located file (PNG, EXR); an empty `opti` works.
    - `"generic"`: AE's generic media importer needs the 58-byte `opti` header
      (JPEG, BMP, GIF, TGA, MOV, WAV).
    - `"tiff"`: AE needs the 602-byte TIFF-specific header (see
      `build_tiff_opti_data`).
    - `"psd"`: AE itself writes an empty opti for PSD (AE 2026 measured);
      py-aep generates a `PsdOptiChunk` with layer metadata, which AE
      accepts on re-open. The 602-byte body is produced by `build_psd_opti_data`.
    - `"unsupported"`: AE requires a format-specific `opti` not yet
      reverse-engineered; import is refused rather than crashing AE."""


#: `sspc.source_format_type` of a 3D model scene (`.fbx`).
FORMAT_3D_MODEL_SCENE = "LDOM"

_FILE_FORMATS: dict[str, FileFormat] = {
    ".exr": FileFormat("oEXR", True, "empty"),
    ".mov": FileFormat("MOoV", False, "generic"),
    ".m4v": FileFormat("MOoV", False, "generic"),
    ".aiff": FileFormat("AIFC", False, "generic"),
    ".wav": FileFormat("WAVE", False, "generic"),
    ".png": FileFormat("png!", False, "empty"),
    ".tif": FileFormat("TIF ", False, "tiff"),
    ".tiff": FileFormat("TIF ", False, "tiff"),
    ".jpg": FileFormat("ZPEG", False, "generic"),
    ".jpeg": FileFormat("ZPEG", False, "generic"),
    ".tga": FileFormat("TPIC", False, "generic"),
    ".bmp": FileFormat("STIL", False, "generic"),
    ".gif": FileFormat("STIL", False, "generic"),
    ".psd": FileFormat("8BPS", False, "psd"),
    ".psb": FileFormat("8BPS", False, "psd"),
    # Video/audio containers (generic opti; codec bytes re-derived by AE).
    ".m4a": FileFormat("MOoV", False, "generic"),
    ".mp3": FileFormat("MP3A", False, "generic"),
    # AAC in an ADTS stream (audio only); source code confirmed against an
    # AE 2026 import of samples/assets/aac.aac.
    ".aac": FileFormat("MPEG", False, "generic"),
    ".swf": FileFormat("SWF ", False, "generic"),
    ".mpeg": FileFormat("MPEO", False, "generic"),
    ".mpg": FileFormat("MPEO", False, "generic"),
    # Motion-graphics data stream (duration from the sampled time range).
    ".mgjson": FileFormat("sjgm", False, "generic"),
    # 3D scene - empty opti; AE re-reads the scene and uses default render dims.
    ".fbx": FileFormat(FORMAT_3D_MODEL_SCENE, False, "empty"),
    # Data footage - 0x0 items; empty source code for txt/csv, reversed-ext code
    # for json.
    ".txt": FileFormat("", False, "generic"),
    ".csv": FileFormat("", False, "generic"),
    ".json": FileFormat("nosj", False, "generic"),
    ".wmv": FileFormat("WMED", False, "generic"),
    # Radiance HDR - format-specific 30-byte opti.
    ".hdr": FileFormat("RHDR", False, "hdr"),
    # Vector / PostScript / PDF - shared 596-byte TEXT opti.
    ".ai": FileFormat("TEXT", False, "text"),
    ".eps": FileFormat("TEXT", False, "text"),
    ".pdf": FileFormat("TEXT", False, "text"),
}


# Formats AE imports as footage but py-aep does NOT support, with reasons:
#   .c4d  -> "C4DC" - opti is a ~357KB blob embedding the absolute file path and
#            Cineware render state; not reconstructable without Cineware
#   .crw / .nef -> "Craw" - opti embeds per-file Camera Raw XMP decode settings;
#            not reconstructable without Adobe Camera Raw
# AE refuses .avi (codec), .flv/.ps (invalid type) on import. .ma imports
# only as a cropped comp (not footage) - a separate comp-conversion feature.


# Which `ImportAsType` values `ImportOptions.can_import_as()` accepts per
# extension. Values for the asset extensions present in `samples/assets/` were
# measured empirically in AE 2026 via `scripts/jsx/can_import_as_matrix.jsx`
# (the matrix lives at `scripts/jsx/can_import_as_matrix.json`). Note the
# non-obvious cases that the empirical run surfaced:
#   - FOOTAGE is NOT universal: `.svg` and `.aep` reject it.
#   - COMP and COMP_CROPPED_LAYERS differ: `.exr`/`.svg` allow the cropped
#     variant but not plain COMP.
#   - `.mov` accepts PROJECT (a QuickTime file may carry an AE project).
# Extensions not in `samples/assets/` (`.ai`, `.pdf`, `.aet`, `.jpeg`, `.tiff`)
# follow documented AE behavior / format aliases and are marked below.
_FOOTAGE = ImportAsType.FOOTAGE
_COMP = ImportAsType.COMP
_CROPPED = ImportAsType.COMP_CROPPED_LAYERS
_PROJECT = ImportAsType.PROJECT

_IMPORT_AS_TYPES: dict[str, frozenset[ImportAsType]] = {
    # Layered Photoshop - footage, comp, or comp-cropped.
    ".psd": frozenset({_FOOTAGE, _COMP, _CROPPED}),
    ".psb": frozenset({_FOOTAGE, _COMP, _CROPPED}),
    # Vector / PostScript / PDF - footage, comp, or comp-cropped (AE-measured).
    ".ai": frozenset({_FOOTAGE, _COMP, _CROPPED}),
    ".eps": frozenset({_FOOTAGE, _COMP, _CROPPED}),
    ".pdf": frozenset({_FOOTAGE, _COMP, _CROPPED}),
    # Multi-channel EXR - footage or comp-cropped, but not plain comp.
    ".exr": frozenset({_FOOTAGE, _CROPPED}),
    # SVG - comp-cropped only; cannot import as plain footage.
    ".svg": frozenset({_CROPPED}),
    # Still images - footage only.
    ".png": frozenset({_FOOTAGE}),
    ".jpg": frozenset({_FOOTAGE}),
    ".jpeg": frozenset({_FOOTAGE}),  # alias of .jpg
    ".tif": frozenset({_FOOTAGE}),
    ".tiff": frozenset({_FOOTAGE}),  # alias of .tif
    ".tga": frozenset({_FOOTAGE}),
    ".bmp": frozenset({_FOOTAGE}),
    ".gif": frozenset({_FOOTAGE}),
    ".hdr": frozenset({_FOOTAGE}),
    # Video - footage or project.
    ".mov": frozenset({_FOOTAGE, _PROJECT}),
    ".m4v": frozenset({_FOOTAGE}),
    ".wmv": frozenset({_FOOTAGE}),
    # Audio - footage only (m4a may also carry an AE project).
    ".aiff": frozenset({_FOOTAGE}),
    ".wav": frozenset({_FOOTAGE}),
    ".m4a": frozenset({_FOOTAGE, _PROJECT}),
    # AE still reports these importable as footage.
    ".fbx": frozenset({_FOOTAGE}),
    ".txt": frozenset({_FOOTAGE}),
    ".csv": frozenset({_FOOTAGE}),
    ".json": frozenset({_FOOTAGE}),
    ".mgjson": frozenset({_FOOTAGE}),
    ".mp3": frozenset({_FOOTAGE}),
    ".aac": frozenset({_FOOTAGE}),
    ".swf": frozenset({_FOOTAGE}),
    ".mpeg": frozenset({_FOOTAGE}),
    ".mpg": frozenset({_FOOTAGE}),
    # Project / template - project only (.aet not in samples/assets).
    ".aep": frozenset({_PROJECT}),
    ".aet": frozenset({_PROJECT}),
}


# Extensions imported by converting the file directly into a composition
# (no FileSource/footage item), so they are absent from `_FILE_FORMATS` yet
# are still importable. `can_import_as` gates these on `_IMPORT_AS_TYPES`
# alone (no media-format lookup).
COMP_CONVERSION_EXTENSIONS: frozenset[str] = frozenset({".svg"})

# Layered formats AE imports as a composition of per-layer footage. Illustrator
# /PDF layers are PDF Optional Content Groups (see resolvers.ai_layers);
# Photoshop layers come from the file's layer records (see resolvers.psd_layers).
AI_COMP_EXTENSIONS: frozenset[str] = frozenset({".ai", ".pdf"})
PSD_COMP_EXTENSIONS: frozenset[str] = frozenset({".psd", ".psb"})
# EPS is single-stream PostScript with no layer structure, so AE rasterizes it
# to a one-layer composition (verified: AE 2026 imports eps.eps as a 1-layer
# comp). Handled separately from AI_COMP_EXTENSIONS, which needs PDF OCGs.
EPS_COMP_EXTENSIONS: frozenset[str] = frozenset({".eps"})


def get_import_as_types(suffix: str) -> frozenset[ImportAsType]:
    """Return the `ImportAsType` values valid for a file extension.

    Args:
        suffix: The file extension including the leading dot (e.g. `.psd`).

    Returns:
        The set of accepted import types, or an empty set for an extension
        with no recorded import support.
    """
    return _IMPORT_AS_TYPES.get(suffix.lower(), frozenset())


def get_file_format(suffix: str) -> FileFormat:
    """Return the `FileFormat` for a file extension (e.g. `.png`).

    Args:
        suffix: The file extension including the leading dot.

    Raises:
        ValueError: If the extension is not a supported footage format.
    """
    fmt = _FILE_FORMATS.get(suffix.lower())
    if fmt is None:
        raise ValueError(f"Unsupported footage format: {suffix!r}")
    return fmt
