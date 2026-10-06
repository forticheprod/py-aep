"""Regression tests for the v9 round-trip / read-purity fixes.

- Fixed-size string fields keep the bytes After Effects leaves after the
  NUL terminator (a renamed solid's old name in its `opti`, the NUL-led
  `"\\0vsc"` code of CSV data footage) through parse -> save.
- tdb4 byte 0x4F is stored as the whole byte (AE writes 0x07 on Transform
  effect points of some projects), so reading a layer no longer rewrites it.
- `.csv` / `.txt` imports write the source code AE 2026 writes.
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from helpers import project_bytes

from py_aep import ImportOptions, parse
from py_aep.binary.footage_chunks import OptiChunk, SoliOptiChunk, SspcChunk
from py_aep.binary.property_chunks import Tdb4Chunk
from py_aep.models.project import Project

SAMPLES = Path(__file__).parent.parent.parent / "samples"
ASSETS = SAMPLES / "assets"


def _leaves(data: bytes, in_list: bytes = b"") -> list[tuple[str, int]]:
    """`(chunk type, body offset)` of every leaf chunk, by a raw RIFX walk
    (only those inside a `LIST:<in_list>` when given)."""
    out: list[tuple[str, int]] = []

    def walk(off: int, end: int, inside: bool) -> None:
        while off + 8 <= end:
            ctype = data[off : off + 4].decode("latin-1")
            (size,) = struct.unpack(">I", data[off + 4 : off + 8])
            body = off + 8
            if ctype in ("LIST", "RIFX"):
                list_type = data[body : body + 4]
                if list_type != b"btdk":
                    walk(body + 4, body + size, inside or list_type == in_list)
            elif inside:
                out.append((ctype, body))
            off = body + size + (size & 1)

    walk(0, len(data), not in_list)
    return out


def _read_every_layer(project: Project) -> None:
    """Iterate every property of every layer (parses the deferred layers)."""
    for comp in project.compositions:
        for layer in comp.layers:
            stack = [layer]
            while stack:
                group = stack.pop()
                for child in group:
                    if not hasattr(child, "keyframes"):
                        stack.append(child)


class TestFixedStringTail:
    def test_sspc_source_code_after_nul_round_trips(self) -> None:
        data = bytearray(SspcChunk().tobytes())
        data[0x16:0x1A] = b"\x00vsc"
        chunk = SspcChunk.frombytes(bytes(data))
        assert chunk.source_format_type == ""
        assert chunk.tobytes() == bytes(data)

    def test_assigned_code_with_nul_reads_back_as_reparsed(self) -> None:
        chunk = SspcChunk(source_format_type="\x00vsc")
        assert chunk.source_format_type == ""
        assert chunk.tobytes()[0x16:0x1A] == b"\x00vsc"

    def test_assigned_plain_string_drops_the_old_tail(self) -> None:
        data = bytearray(SspcChunk().tobytes())
        data[0x16:0x1A] = b"\x00vsc"
        chunk = SspcChunk.frombytes(bytes(data))
        chunk.source_format_type = "png!"
        assert chunk.tobytes()[0x16:0x1A] == b"png!"

    def test_solid_name_stale_tail_round_trips(self) -> None:
        data = bytearray(SoliOptiChunk(solid_name="Black Solid 3").tobytes())
        name_at = data.index(b"Black Solid 3")
        # AE keeps the end of a longer previous name after the terminator.
        stale = b"Black Solid 3\x00 1\x00id 1"
        data[name_at : name_at + len(stale)] = stale
        chunk = OptiChunk.frombytes(bytes(data))
        assert isinstance(chunk, SoliOptiChunk)
        assert chunk.solid_name == "Black Solid 3"
        assert chunk.tobytes() == bytes(data)

    def test_project_with_stale_tail_saves_byte_identical(self, tmp_path: Path) -> None:
        # The NUL-led CSV code in a real project, read and written whole.
        app = parse(SAMPLES / "models" / "folder" / "folder.aep")
        app.project.import_file(ImportOptions(ASSETS / "csv.csv"))
        first = tmp_path / "first.aep"
        app.project.save(first)
        reparsed = parse(first)
        _read_every_layer(reparsed.project)
        for item in reparsed.project.footages:
            assert item.main_source is not None
        second = tmp_path / "second.aep"
        reparsed.project.save(second)
        assert second.read_bytes() == first.read_bytes()


class TestTdb4KeyFlagsByte:
    def test_byte_0x4f_kept_whole(self) -> None:
        data = bytearray(Tdb4Chunk().tobytes())
        data[0x4F] = 0x07
        chunk = Tdb4Chunk.frombytes(bytes(data))
        assert chunk._spatial_marker == 0x07
        assert chunk._spatial_marker  # still reads as a spatial stream
        assert chunk.tobytes() == bytes(data)

    def test_reading_layers_keeps_the_byte(self, tmp_path: Path) -> None:
        source = SAMPLES / "models" / "property" / "effect_point_speed.aep"
        data = bytearray(source.read_bytes())
        target = next(
            body + 0x4F
            for ctype, body in _leaves(bytes(data), b"Layr")
            if ctype == "tdb4" and data[body + 0x4F] == 1
        )
        data[target] = 0x07
        patched = tmp_path / "patched.aep"
        patched.write_bytes(bytes(data))
        app = parse(patched)
        before = hashlib.sha1(project_bytes(app.project)).hexdigest()
        _read_every_layer(app.project)
        after = project_bytes(app.project)
        assert hashlib.sha1(after).hexdigest() == before
        assert after == bytes(data)


class TestDataFootageSourceCode:
    def test_csv_and_txt_codes_match_after_effects(self, tmp_path: Path) -> None:
        # AE 2026 imports a .csv / .txt with the comma- / tab-separated
        # values importer's NUL-led codes, in sspc and in the opti header.
        app = parse(SAMPLES / "models" / "folder" / "folder.aep")
        for name in ("csv.csv", "txt.txt"):
            app.project.import_file(ImportOptions(ASSETS / name))
        out = tmp_path / "data.aep"
        app.project.save(out)
        data = out.read_bytes()
        codes = {
            data[body + 0x16 : body + 0x1A]
            for ctype, body in _leaves(data)
            if ctype == "sspc"
        }
        assert {b"\x00vsc", b"\x00vst"} <= codes
        optis = {
            data[body : body + 4] for ctype, body in _leaves(data) if ctype == "opti"
        }
        assert {b"\x00vsc", b"\x00vst"} <= optis
        for item in parse(out).project.footages:
            if item.name in ("csv.csv", "txt.txt"):
                assert item.main_source._sspc.source_format_type == ""
