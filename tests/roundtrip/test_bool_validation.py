"""Strict-bool validation across the model layer.

Writable boolean attributes reject non-bool values (the binary layer would
otherwise silently coerce truthy values - `"no"` -> `True`); real booleans
are accepted and round-trip. Covers a representative writable bool on each
major model. The render-queue package has its own coverage in
`test_rq_validation.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pytest
from helpers import parse_app_fresh, parse_project_fresh

from py_aep.models.import_options import ImportOptions

if TYPE_CHECKING:
    from py_aep.models.properties.mask_property_group import MaskPropertyGroup
    from py_aep.models.sources.footage import FootageSource

SAMPLES = Path(__file__).parent.parent.parent / "samples"
LAYER = SAMPLES / "models" / "layer" / "enabled_false.aep"
FOOTAGE = SAMPLES / "models" / "essential_graphics" / "media_replacement.aep"
MASK = SAMPLES / "models" / "essential_graphics" / "indexed_group_controllers.aep"
VIEW = SAMPLES / "models" / "view" / "grid_on.aep"


def _file_source() -> FootageSource:
    project = parse_project_fresh(FOOTAGE)
    footage = next(
        f
        for f in project.footages
        if type(getattr(f, "main_source", None)).__name__ == "FileSource"
    )
    return footage.main_source


def _first_mask() -> MaskPropertyGroup:
    project = parse_project_fresh(MASK)
    for comp in project.compositions:
        for layer in comp.layers:
            masks = getattr(layer, "masks", None)
            if masks and len(masks) > 0:
                return masks[0]
    raise AssertionError("no mask found in sample")


# (id, factory returning a fresh mutable object, bool attribute name)
CASES: list[tuple[str, Callable[[], object], str]] = [
    (
        "comp.motion_blur",
        lambda: parse_project_fresh(LAYER).compositions[0],
        "motion_blur",
    ),
    (
        "comp.frame_blending",
        lambda: parse_project_fresh(LAYER).compositions[0],
        "frame_blending",
    ),
    (
        "layer.enabled",
        lambda: parse_project_fresh(LAYER).compositions[0].layers[0],
        "enabled",
    ),
    (
        "layer.solo",
        lambda: parse_project_fresh(LAYER).compositions[0].layers[0],
        "solo",
    ),
    ("layer.shy", lambda: parse_project_fresh(LAYER).compositions[0].layers[0], "shy"),
    (
        "project.frames_use_feet_frames",
        lambda: parse_project_fresh(LAYER),
        "frames_use_feet_frames",
    ),
    ("footage.invert_alpha", _file_source, "invert_alpha"),
    ("mask.inverted", _first_mask, "inverted"),
    ("view.grid", lambda: parse_app_fresh(VIEW).active_viewer.views[0].options, "grid"),
    ("import.sequence", lambda: ImportOptions(str(LAYER)), "sequence"),
    (
        "import.force_alphabetical",
        lambda: ImportOptions(str(LAYER)),
        "force_alphabetical",
    ),
]

_IDS = [c[0] for c in CASES]
_PARAMS = [(c[1], c[2]) for c in CASES]


@pytest.mark.parametrize("factory,attr", _PARAMS, ids=_IDS)
class TestStrictBool:
    def test_rejects_non_bool_string(
        self, factory: Callable[[], object], attr: str
    ) -> None:
        obj = factory()
        with pytest.raises(TypeError):
            setattr(obj, attr, "no")

    def test_rejects_bare_int(self, factory: Callable[[], object], attr: str) -> None:
        obj = factory()
        with pytest.raises(TypeError):
            setattr(obj, attr, 1)

    def test_accepts_true_and_false(
        self, factory: Callable[[], object], attr: str
    ) -> None:
        obj = factory()
        setattr(obj, attr, True)
        assert getattr(obj, attr) is True
        setattr(obj, attr, False)
        assert getattr(obj, attr) is False


class TestBoolPersists:
    """A validated bool still serializes through a disk round-trip."""

    def test_comp_and_layer_flags_roundtrip(self, tmp_path: Path) -> None:
        project = parse_project_fresh(LAYER)
        comp = project.compositions[0]
        layer = comp.layers[0]
        comp.motion_blur = True
        layer.solo = True
        out = tmp_path / "bools.aep"
        project.save(out)

        project2 = parse_project_fresh(out)
        comp2 = project2.compositions[0]
        assert comp2.motion_blur is True
        assert comp2.layers[0].solo is True
