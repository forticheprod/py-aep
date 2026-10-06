"""New items and layers carry the chunk set of the project's AE version.

Each AE release writes a slightly different chunk set for a new comp,
folder, footage item or layer. These tests build `py_aep.new(<version>)`
plus one item / layer of each kind and compare what py writes against the
`samples/versions/aeYYYY/complete.aep` project that same After Effects
release saved. AE 2022-2026 write the same structures for freshly created
items and layers (measured headlessly: `addComp`, `addFolder`, `addSolid`,
`addNull`, `addCamera`, `addLight`, `addText`, `addShape`, `importFile` +
`layers.add` on an opened `py_aep.new()` project). AE 15 (CC 2018) cannot
run scripts headless; its resave of a `py_aep.new("15.1x69")` composition
agrees with its sample on the item and layer chunk lists.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import py_aep
from py_aep import ImportOptions
from py_aep.binary.chunk import Chunk, ListChunk, read_aep

if TYPE_CHECKING:
    from typing import Iterator

    from py_aep.binary.layer_chunks import LdtaChunk

SAMPLES = Path(__file__).parent.parent.parent / "samples"
VERSIONS = SAMPLES / "versions"
PNG = SAMPLES / "assets" / "image_with_alpha.png"

# samples/versions folder -> the version its complete.aep was saved with.
RELEASES = {
    "ae2018": "15.1x69",
    "ae2022": "22.5x53",
    "ae2023": "23.6x62",
    "ae2024": "24.6x2",
    "ae2025": "25.6x101",
    "ae2026": "26.0x67",
}

_VIEW_LISTS = ("DLay", "SLay", "CLay", "SecL")
_VIEW_SEPTET = ("fvdv", "fiop", "ftts", "foac", "fiac", "fipc", "fifl")


def _tag(chunk: Chunk) -> str:
    if isinstance(chunk, ListChunk):
        return f"LIST:{chunk.list_type}"
    if chunk.chunk_type == "tdmn":
        return f"tdmn={chunk.value}"  # type: ignore[attr-defined]
    return chunk.chunk_type


def _signature(chunk: Chunk) -> list[str]:
    """Nested chunk tags with byte sizes (match names for `tdmn`)."""
    if isinstance(chunk, ListChunk):
        lines = [_tag(chunk)]
        for child in chunk.chunks:
            lines.extend("  " + line for line in _signature(child))
        return lines
    if chunk.chunk_type == "tdmn":
        return [_tag(chunk)]
    return [f"{chunk.chunk_type}({len(chunk.tobytes())})"]


def _walk(chunk: ListChunk) -> Iterator[tuple[ListChunk, int, Chunk]]:
    for i, child in enumerate(chunk.chunks):
        yield chunk, i, child
        if isinstance(child, ListChunk) and child.list_type != "btdk":
            yield from _walk(child)


class _Structure:
    """The version-sensitive structure of a saved project, by kind."""

    def __init__(self, rifx: ListChunk) -> None:
        self.items: dict[int, set[str]] = {}
        self.fee: set[str] = set()
        self.view_layers: dict[tuple[str, str], list[str]] = {}
        self.view_ldta_tails: set[tuple[str, bytes]] = set()
        self.shadow_colors: set[bytes] = set()
        self.layers: set[str] = set()
        self.groups: dict[int, set[str]] = {}
        self.source_options: set[str] = set()
        self.light_source_ids: set[int] = set()
        for parent, i, chunk in _walk(rifx):
            if not isinstance(chunk, ListChunk):
                continue
            if chunk.list_type == "Item":
                self._add_item(chunk)
            elif chunk.list_type == "FEE ":
                self.fee.add(" ".join(_tag(c) for c in chunk.chunks))
            elif chunk.list_type in _VIEW_LISTS:
                self._add_view_layer(chunk)
            elif chunk.list_type == "Layr":
                self._add_layer(chunk)
            elif chunk.list_type == "tdgp" and i > 0:
                previous = parent.chunks[i - 1]
                if _tag(previous) == "tdmn=ADBE Source Options Group":
                    self.source_options.add(" ".join(_tag(c) for c in chunk.chunks))
            elif chunk.list_type == "tdbs" and i > 0:
                if _tag(parent.chunks[i - 1]) == "tdmn=ADBE Shadow Color":
                    cdat = next(c for c in chunk.chunks if c.chunk_type == "cdat")
                    self.shadow_colors.add(cdat.tobytes())

    def _add_item(self, item: ListChunk) -> None:
        idta = next(c for c in item.chunks if c.chunk_type == "idta")
        tags: list[str] = []
        for child in item.chunks:
            tag = _tag(child)
            if tag in ("LIST:Layr", "LIST:Ewst") or tag in _VIEW_SEPTET:
                continue
            if not tags or tags[-1] != tag:
                tags.append(tag)
        item_type = idta.item_type  # type: ignore[attr-defined]
        self.items.setdefault(item_type, set()).add(" ".join(tags))

    def _add_view_layer(self, view: ListChunk) -> None:
        ldta = view.chunks[0]
        name = view.chunks[1].value  # type: ignore[attr-defined]
        self.view_layers[(view.list_type, name)] = _signature(view)
        self.view_ldta_tails.add((view.list_type, ldta.tobytes()[147:160]))

    def _add_layer(self, layer: ListChunk) -> None:
        ldta: LdtaChunk = layer.chunks[0]  # type: ignore[assignment]
        self.layers.add(
            " ".join(_tag(c) for c in layer.chunks if c.chunk_type != "cmta")
        )
        tdgp = next(c for c in layer.chunks if _tag(c) == "LIST:tdgp")
        groups = [
            _tag(c)
            for c in tdgp.chunks  # type: ignore[attr-defined]
            if c.chunk_type == "tdmn"
            # A new shape layer has no contents yet; AE's samples have some.
            and _tag(c) != "tdmn=ADBE Root Vectors Group"
        ]
        self.groups.setdefault(ldta.layer_type, set()).add(" ".join(groups))
        if ldta.layer_type == 1:  # light
            self.light_source_ids.add(ldta.source_id)


def _read(path: Path) -> ListChunk:
    with path.open("rb") as fp:
        rifx, _xmp = read_aep(fp)
    return rifx


@lru_cache(maxsize=None)
def _after_effects(year: str) -> _Structure:
    return _Structure(_read(VERSIONS / year / "complete.aep"))


def _new_project(version: str) -> py_aep.Application:
    """`new(version)` plus one new item / layer of each kind, as the AE
    probe built them."""
    app = py_aep.new(version)
    project = app.project
    comp = project.root_folder.add_comp("Comp 1", 320, 240, 1.0, 2.0, 25.0)
    project.root_folder.add_folder("Folder 1")
    comp.add_solid([1.0, 0.0, 0.0], "Red", 320, 240)
    comp.add_null()
    comp.add_camera("Camera 1", [160.0, 120.0])
    comp.add_light("Light 1", [160.0, 120.0])
    comp.add_text("Hello")
    comp.add_shape()
    comp.add(project.import_file(ImportOptions(PNG)))
    return app


@pytest.fixture(params=sorted(RELEASES), scope="module")
def year(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture(scope="module")
def written(year: str, tmp_path_factory: pytest.TempPathFactory) -> _Structure:
    path = tmp_path_factory.mktemp(year) / "new.aep"
    _new_project(RELEASES[year]).project.save(path)
    return _Structure(_read(path))


class TestNewItemsMatchTheRelease:
    @pytest.mark.parametrize(
        ("item_type", "kind"), [(1, "folder"), (4, "comp"), (7, "footage")]
    )
    def test_item_chunks(
        self, year: str, written: _Structure, item_type: int, kind: str
    ) -> None:
        # iide / idpc (all items) and comr, CIF3 and the Default view layer
        # (comps) are absent from AE 15 files.
        assert written.items[item_type] <= _after_effects(year).items[item_type], kind

    def test_comp_view_data(self, year: str, written: _Structure) -> None:
        # The FEE list after a comp item holds ppSn, except in AE 15.
        assert written.fee == _after_effects(year).fee

    def test_view_layers(self, year: str, written: _Structure) -> None:
        # Same viewer pseudo-layers, each with the chunk tree that release
        # writes (AE 15 adds a layer-level OvdG and lacks Layer Sets; AE 15-23
        # leave 11 Material Options properties out of the Markers layer).
        expected = _after_effects(year).view_layers
        assert written.view_layers.keys() == expected.keys()
        for key, signature in written.view_layers.items():
            assert signature == expected[key], key

    def test_view_layer_ldta_tail(self, year: str, written: _Structure) -> None:
        # Only AE 26 stamps 1 / 102.047... at 0x94 / 0x98 of the viewer
        # layers' records.
        assert written.view_ldta_tails == _after_effects(year).view_ldta_tails

    def test_markers_shadow_color(self, year: str, written: _Structure) -> None:
        # AE 24 writes the Markers layer's Shadow Color alpha as 0, AE 25+
        # as 255; earlier releases do not write the property.
        assert written.shadow_colors == _after_effects(year).shadow_colors

    def test_layer_chunks(self, year: str, written: _Structure) -> None:
        # AE 15 closes every layer with a LIST:OvdG.
        assert written.layers <= _after_effects(year).layers

    def test_layer_groups(self, year: str, written: _Structure) -> None:
        # AE 15 layers have no Layer Sets and no Source Options group.
        expected = _after_effects(year).groups
        for layer_type, groups in written.groups.items():
            assert groups <= expected[layer_type], layer_type

    def test_source_alternate(self, year: str, written: _Structure) -> None:
        # AE 22 writes the Layer Source Alternate match name and its
        # blsv/blsi pair but no value (tdbs); AE 23+ write the value.
        assert written.source_options <= _after_effects(year).source_options

    def test_light_source_id(self, year: str, written: _Structure) -> None:
        # AE 15-22 store 0 as a light layer's source id, AE 23+ 0xFFFFFFFF.
        assert written.light_source_ids == _after_effects(year).light_source_ids


@pytest.mark.parametrize("version", sorted(RELEASES.values()))
def test_gated_project_round_trips(version: str, tmp_path: Path) -> None:
    first = tmp_path / "first.aep"
    second = tmp_path / "second.aep"
    _new_project(version).project.save(first)
    py_aep.parse(first).project.save(second)
    assert first.read_bytes() == second.read_bytes()


def test_layer_comment_written_before_ovdg(tmp_path: Path) -> None:
    # AE 15 keeps a layer's comment ahead of the LIST:OvdG closing the layer.
    sample = _read(VERSIONS / "ae2018" / "complete.aep")
    commented = {
        " ".join(_tag(c) for c in chunk.chunks)
        for _parent, _i, chunk in _walk(sample)
        if isinstance(chunk, ListChunk)
        and chunk.list_type == "Layr"
        and any(c.chunk_type == "cmta" for c in chunk.chunks)
    }
    app = py_aep.new(RELEASES["ae2018"])
    comp = app.project.root_folder.add_comp("Comp 1", 320, 240, 1.0, 2.0, 25.0)
    comp.add_solid([1.0, 0.0, 0.0], "Red", 320, 240).comment = "note"
    path = tmp_path / "comment.aep"
    app.project.save(path)
    written = {
        " ".join(_tag(c) for c in chunk.chunks)
        for _parent, _i, chunk in _walk(_read(path))
        if isinstance(chunk, ListChunk) and chunk.list_type == "Layr"
    }
    assert written == commented
