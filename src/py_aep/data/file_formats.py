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
}


# Additional formats imported into AE 2026 and decoded but not yet supported
# (their `source_format` codes are recorded here for the follow-up work):
#   .aac  -> "MPEG" (generic opti) - measured on an M4A container renamed to
#            .aac (AE picks the importer from the extension); re-measure with
#            a real ADTS stream, then add an ADTS frame-scan duration probe
#   .m4a  -> "MOoV" (generic opti) - _probe_mov reads it, but AAC encoder
#            padding makes the duration ~0.05s long; needs `elst` edit-list
#   .mp3  -> "MP3A" (generic opti) - needs an MP3 frame-header duration probe
#   .mpeg -> "MPEO" (generic opti) - needs an MPEG program-stream probe
#   .wmv  -> "WMED" (generic opti) - needs an ASF-header probe
#   .hdr  -> "RHDR" - uses a 30-byte format-specific opti (not generic)
# AE refused .avi (codec) and .flv (unsupported) on import.


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
    # Layered vector (not in samples/assets) - documented to behave like PSD.
    ".ai": frozenset({_FOOTAGE, _COMP, _CROPPED}),
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
    # Video - footage or project.
    ".mov": frozenset({_FOOTAGE, _PROJECT}),
    ".m4v": frozenset({_FOOTAGE}),
    # Audio - footage only.
    ".aiff": frozenset({_FOOTAGE}),
    ".wav": frozenset({_FOOTAGE}),
    # AE still reports these importable as footage.
    ".fbx": frozenset({_FOOTAGE}),
    ".txt": frozenset({_FOOTAGE}),
    # Project / template - project only (.aet not in samples/assets).
    ".aep": frozenset({_PROJECT}),
    ".aet": frozenset({_PROJECT}),
}


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
