"""Regression tests for the v9 fuzz findings on media probing and the layered
file readers (area C): malformed input raises only the documented
exceptions, never allocates from a corrupt size field, and never hangs."""

from __future__ import annotations

import io
import struct
import threading
import tracemalloc
from pathlib import Path
from typing import Callable

import pytest

from py_aep.cos import CosParser
from py_aep.resolvers.ai_layers import UnsupportedAiLayersError, read_ai_layers
from py_aep.resolvers.media_probe import probe_media
from py_aep.resolvers.psd_layers import UnsupportedPsdLayersError, read_psd_layers

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"

_PSD_HEADER = (
    b"8BPS" + struct.pack(">H", 1) + b"\0" * 6 + struct.pack(">HIIHH", 3, 8, 8, 8, 3)
)


def _run(fn: Callable[[], object], timeout: float = 20.0) -> tuple[object, int]:
    """Run `fn` in a thread; return `(exception or result, peak bytes)`.
    Fails the test if it does not finish in `timeout` seconds."""
    box: dict[str, object] = {}

    def target() -> None:
        tracemalloc.start()
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - classified by the caller
            box["value"] = exc
        box["peak"] = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout)
    assert not thread.is_alive(), "call did not return (hang)"
    return box["value"], int(box["peak"])  # type: ignore[call-overload]


# Malformed files a few bytes long; each used to raise a raw struct.error or
# IndexError from inside a parser (v9 fuzz, area C).
_TRUNCATED = {
    "psd_header_only.psd": _PSD_HEADER,
    "png_trunc.png": (ASSETS / "image_with_alpha.png").read_bytes()[:24],
    "tif_ifd_past_eof.tif": b"II*\0" + struct.pack("<I", 1000),
    "bmp_short.bmp": b"BM" + b"\0" * 10,
    "gif_short.gif": b"GIF89a\x01",
    "jpg_short.jpg": b"\xff\xd8\xff\xc0",
    "crw_short.crw": (ASSETS / "crw.crw").read_bytes()[:16],
    "aif_short.aif": (ASSETS / "aif.aif").read_bytes()[:26],
    "tga_short.tga": b"\0\0\2",
    "exr_magic_only.exr": (ASSETS / "exr" / "rgb_full.exr").read_bytes()[:4],
}


@pytest.mark.parametrize("name", sorted(_TRUNCATED))
def test_truncated_media_raises_value_error(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    path.write_bytes(_TRUNCATED[name])
    for data in (None, _TRUNCATED[name]):
        with pytest.raises(ValueError):
            probe_media(path, data)


def test_corrupt_exr_attribute_size_does_not_allocate(tmp_path: Path) -> None:
    # An attribute declaring 0xFFFFFFF0 bytes in a 36-byte file used to make
    # read(size) allocate 4 GB before reading.
    exr = (ASSETS / "exr" / "rgb_full.exr").read_bytes()[:8]
    path = tmp_path / "huge_attr.exr"
    path.write_bytes(exr + b"channels\0chlist\0" + struct.pack("<I", 0xFFFFFFF0))
    _, peak = _run(lambda: probe_media(path))
    assert peak < 50_000_000


def test_corrupt_psd_resource_length_does_not_allocate(tmp_path: Path) -> None:
    path = tmp_path / "huge_resources.psd"
    path.write_bytes(_PSD_HEADER + struct.pack(">II", 0, 0xFFFFFFF0) + b"8BIM")
    _, peak = _run(lambda: probe_media(path))
    assert peak < 50_000_000


def test_psd_header_fields_are_validated(tmp_path: Path) -> None:
    # A bit depth outside 1/8/16/32 used to import and then fail at save
    # (it did not fit the opti byte recording it).
    header = bytearray(_PSD_HEADER)
    struct.pack_into(">H", header, 22, 300)
    path = tmp_path / "bad_depth.psd"
    path.write_bytes(bytes(header) + struct.pack(">III", 0, 0, 0))
    with pytest.raises(ValueError, match="Not a valid PSD/PSB file"):
        probe_media(path)


def test_tiff_bits_per_sample_is_validated(tmp_path: Path) -> None:
    entries = [(256, 3, 1, 8), (257, 3, 1, 8), (258, 3, 1, 9000), (262, 3, 1, 1)]
    ifd = struct.pack("<H", len(entries))
    for tag, typ, count, value in entries:
        ifd += struct.pack("<HHIHH", tag, typ, count, value, 0)
    path = tmp_path / "bad_bits.tif"
    path.write_bytes(b"II*\0" + struct.pack("<I", 8) + ifd + b"\0\0\0\0")
    with pytest.raises(ValueError, match="bits per sample"):
        probe_media(path)


def test_read_psd_layers_truncated_records_raise_documented_error(
    tmp_path: Path,
) -> None:
    # Cut inside the layer records: an IndexError escaped before.
    path = tmp_path / "cut.psd"
    path.write_bytes((ASSETS / "choose_layer.psd").read_bytes()[:200])
    result, _ = _run(lambda: read_psd_layers(path))
    assert isinstance(result, UnsupportedPsdLayersError)


def test_read_psd_layers_huge_canvas_is_rejected(tmp_path: Path) -> None:
    header = bytearray((ASSETS / "layer_bounds.psd").read_bytes())
    struct.pack_into(">II", header, 14, 0xFFFFFFF0, 0xFFFFFFF0)
    path = tmp_path / "huge_canvas.psd"
    path.write_bytes(bytes(header))
    result, peak = _run(lambda: read_psd_layers(path))
    assert isinstance(result, UnsupportedPsdLayersError)
    assert peak < 50_000_000


def test_cos_lexer_stops_at_end_of_data() -> None:
    # `read(1)` returns b"" at the end of the data; the lexer treated it as
    # a character and looped forever on a truncated name.
    parser = CosParser(io.BytesIO(b"<</Order 8 0 R/"))
    result, _ = _run(lambda: (parser.lex(), parser.parse_value()))
    assert isinstance(result, (tuple, SyntaxError))


@pytest.mark.parametrize("max_pos", [None, 10_000_100])
def test_cos_stream_is_read_in_blocks(max_pos: int | None) -> None:
    # A 0.5 MB embedded ICC profile took seconds to lex byte by byte, which
    # the import's colour-profile lookup now does for every .ai/.pdf.
    body = b"x" * 3_000_000 + b"endstrea" + b"y" * 1000
    data = b"<</Length 1>>stream\n" + body + b"endstream\nendobj 7"
    parser = CosParser(io.BytesIO(data), max_pos)
    result, _ = _run(lambda: (parser.lex(), parser.parse_value()), timeout=5.0)
    assert not isinstance(result, BaseException)
    stream = result[1]  # type: ignore[index]
    assert stream.data == body
    assert parser.lookahead.type.name == "IndirectObjectEnd"


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.5\n1 0 obj\n<</OCProperties<</D<</Order 8 0 R/",
        b'%PDF-1.5\n1 0 obj\n<</OCProperties<</D "x>>>>\n',
    ],
)
def test_malformed_ai_layers_raise_documented_error(
    tmp_path: Path, data: bytes
) -> None:
    path = tmp_path / "bad.ai"
    path.write_bytes(data)
    result, _ = _run(lambda: read_ai_layers(path))
    assert isinstance(result, UnsupportedAiLayersError)


def test_luminance_only_exr_reads_as_float_gray() -> None:
    # AE 2026 caches depth -32 for a Y-only EXR (exr/y.exr); Y + A stays
    # RGBA float.
    assert probe_media(ASSETS / "exr" / "y.exr").depth == -32
    assert probe_media(ASSETS / "exr" / "ya.exr").depth == 128
    assert probe_media(ASSETS / "exr" / "r_only.exr").depth == 96
