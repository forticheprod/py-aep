"""Output module settings must decode on every AE-written sample.

Real files can hold values outside our enums (garbage `Rouu.depth` bytes
observed in `dpx_fido.aep` and `frame_rate.aep`, unknown format ids from
third-party plugins). The binary is trusted: every read falls back to the
raw value instead of raising.
"""

from __future__ import annotations

import pytest
from helpers import SAMPLES_DIR, parse_app

from py_aep.enums import GetSettingsFormat
from py_aep.models.renderqueue.format_options import (
    CineonFormatOptions,
    JpegFormatOptions,
    OpenExrFormatOptions,
    PngFormatOptions,
)

_CORPUS_ROOTS = [
    SAMPLES_DIR / "models" / "format_options",
    SAMPLES_DIR / "models" / "renderqueue",
    SAMPLES_DIR / "unused" / "output_module",
    SAMPLES_DIR / "unused" / "output_module_settings",
]

_CORPUS = sorted(
    path for root in _CORPUS_ROOTS if root.is_dir() for path in root.rglob("*.aep")
)


@pytest.mark.parametrize(
    "aep_path",
    _CORPUS,
    ids=[str(p.relative_to(SAMPLES_DIR)) for p in _CORPUS],
)
def test_settings_and_format_options_reads_never_raise(aep_path) -> None:
    app = parse_app(aep_path)
    for rqi in app.project.render_queue.items:
        for om in rqi.output_modules:
            om.get_settings(GetSettingsFormat.STRING)
            om.get_settings(GetSettingsFormat.NUMBER)
            fo = om.format_options
            if isinstance(fo, CineonFormatOptions):
                _ = fo.file_format
            elif isinstance(fo, JpegFormatOptions):
                _ = fo.format_type
            elif isinstance(fo, OpenExrFormatOptions):
                _ = (fo.compression, fo.dwa_compression_level)
            elif isinstance(fo, PngFormatOptions):
                _ = (fo.compression, fo.color_primaries)
