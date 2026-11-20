"""The baked built-in effect templates and their index."""

from __future__ import annotations

from py_aep.binary.utils import find_by_type
from py_aep.data.builtin_effects import BUILTIN_EFFECTS, EFFECTS_DIR, MIN_AE_VERSION
from py_aep.models.properties.property_group import _baked_effect_def


def test_index_matches_template_files() -> None:
    files = {path.stem for path in EFFECTS_DIR.glob("*.sspc")}
    assert files == {name.replace("/", "_") for name in BUILTIN_EFFECTS}
    assert set(MIN_AE_VERSION) <= set(BUILTIN_EFFECTS)


def test_template_holds_its_display_name() -> None:
    for match_name, display in BUILTIN_EFFECTS.items():
        sspc = _baked_effect_def(match_name)
        fnam = find_by_type(sspc.chunks, "fnam")
        assert fnam.chunks[0].value == display, match_name
