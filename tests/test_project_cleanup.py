"""Tests for project cleanup mutations: remove_unused_footage, reduce_project,
consolidate_footage.

Mutation tests use the uncached :func:`py_aep.parse` so each parse is fresh and
mutations never leak between tests.
"""

from __future__ import annotations

from pathlib import Path

from py_aep import parse as parse_aep
from py_aep.models.items.footage import FootageItem

SAMPLES_DIR = Path(__file__).parent.parent / "samples" / "models"
FOOTAGE_MISC = SAMPLES_DIR / "footage" / "footage_misc.aep"
SOLID_COLORS = SAMPLES_DIR / "footage" / "solid_colors.aep"


class TestRemoveUnusedFootage:
    def test_removes_all_unused(self):
        project = parse_aep(FOOTAGE_MISC).project
        assert len(project.footages) == 7
        assert all(not f.used_in for f in project.footages)

        removed = project.remove_unused_footage()

        assert removed == 7
        assert project.footages == []

    def test_keeps_used_footage(self):
        project = parse_aep(SOLID_COLORS).project
        used_count = len(project.footages)
        assert used_count > 0
        assert all(f.used_in for f in project.footages)

        removed = project.remove_unused_footage()

        assert removed == 0
        assert len(project.footages) == used_count

    def test_removes_only_unused(self):
        project = parse_aep(SOLID_COLORS).project
        used_ids = {f.id for f in project.footages}
        placeholder = project.import_placeholder("unused", 100, 100, 25.0, 5.0)

        removed = project.remove_unused_footage()

        assert removed == 1
        assert placeholder.id not in project.items
        assert {f.id for f in project.footages} == used_ids

    def test_roundtrip(self, tmp_path):
        project = parse_aep(SOLID_COLORS).project
        project.import_placeholder("unused", 100, 100, 25.0, 5.0)
        project.remove_unused_footage()

        out = tmp_path / "out.aep"
        project.save(out)
        reparsed = parse_aep(out).project

        assert all(f.used_in for f in reparsed.footages)


class TestReduceProject:
    def test_keeps_specified_comp_and_sources(self):
        project = parse_aep(SOLID_COLORS).project
        comps = project.compositions
        assert len(comps) == 4
        kept_comp = comps[0]
        kept_source_ids = kept_comp._source_ids_for_linking()

        before = set(project.items)
        removed = project.reduce_project([kept_comp])
        after = set(project.items)

        assert removed == len(before) - len(after)
        assert kept_comp.id in after
        for sid in kept_source_ids:
            assert sid in after
        # The other three comps are gone.
        assert len(project.compositions) == 1

    def test_count_matches_extendscript(self):
        # ExtendScript reduceProject keeping one comp on solid_colors removes 6
        # items (3 comps + 3 solids), keeping the comp, its solid and the
        # parent folder. Validated against AfterFX 2025.
        project = parse_aep(SOLID_COLORS).project
        kept_comp = project.compositions[0]

        removed = project.reduce_project([kept_comp])

        assert removed == 6

    def test_root_always_kept(self):
        project = parse_aep(SOLID_COLORS).project
        kept_comp = project.compositions[0]

        project.reduce_project([kept_comp])

        assert 0 in project.items

    def test_empty_keep_removes_all_but_root(self):
        project = parse_aep(SOLID_COLORS).project

        removed = project.reduce_project([])

        assert removed > 0
        assert set(project.items) == {0}

    def test_roundtrip(self, tmp_path):
        project = parse_aep(SOLID_COLORS).project
        kept_comp = project.compositions[0]
        kept_name = kept_comp.name
        project.reduce_project([kept_comp])

        out = tmp_path / "out.aep"
        project.save(out)
        reparsed = parse_aep(out).project

        assert [c.name for c in reparsed.compositions] == [kept_name]


class TestConsolidateFootage:
    def test_no_duplicates_is_noop(self):
        project = parse_aep(FOOTAGE_MISC).project
        before = len(project.footages)

        removed = project.consolidate_footage()

        assert removed == 0
        assert len(project.footages) == before

    def test_merges_identical_sources(self):
        project = parse_aep(FOOTAGE_MISC).project
        # footages 5 and 6 reference the same file and differ only by loop.
        first = project.items[5]
        second = project.items[6]
        assert isinstance(first, FootageItem)
        assert isinstance(second, FootageItem)
        first.main_source.loop = second.main_source.loop
        assert first._consolidation_key() == second._consolidation_key()
        before = len(project.footages)

        removed = project.consolidate_footage()

        assert removed == 1
        assert len(project.footages) == before - 1

    def test_retargets_layers(self):
        project = parse_aep(FOOTAGE_MISC).project
        first = project.items[5]
        second = project.items[6]
        assert isinstance(first, FootageItem)
        assert isinstance(second, FootageItem)
        first.main_source.loop = second.main_source.loop

        comp = project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        comp.add(first)
        comp.add(second)

        survivor_id = first.id
        removed = project.consolidate_footage()

        assert removed == 1
        assert {layer._source_id for layer in comp.av_layers} == {survivor_id}

    def test_retargets_cached_layer_source(self):
        project = parse_aep(FOOTAGE_MISC).project
        first = project.items[5]
        second = project.items[6]
        assert isinstance(first, FootageItem)
        assert isinstance(second, FootageItem)
        first.main_source.loop = second.main_source.loop

        comp = project.root_folder.add_comp("C", 100, 100, 1.0, 5.0, 25.0)
        comp.add(first)
        comp.add(second)
        dup_layer = next(ly for ly in comp.av_layers if ly._source_id == second.id)
        # Populate the layer's source cache before consolidating.
        assert dup_layer.source is second

        project.consolidate_footage()

        assert dup_layer.source is first

    def test_solids_not_consolidated(self):
        project = parse_aep(SOLID_COLORS).project

        removed = project.consolidate_footage()

        assert removed == 0

    def test_roundtrip(self, tmp_path):
        project = parse_aep(FOOTAGE_MISC).project
        first = project.items[5]
        second = project.items[6]
        assert isinstance(first, FootageItem)
        assert isinstance(second, FootageItem)
        first.main_source.loop = second.main_source.loop
        project.consolidate_footage()

        out = tmp_path / "out.aep"
        project.save(out)
        reparsed = parse_aep(out).project

        assert len(reparsed.footages) == 6
