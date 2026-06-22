"""Tests for ViewOptions model parsing using samples from models/view/.

These tests verify that py_aep correctly reads viewer panel settings
(channels, exposure, zoom, fast preview, toggle flags, etc.) from the
`fips` chunks in the binary AEP format.

The viewer panel data is accessed via `project.active_viewer`, which
represents the focused Composition/Layer/Footage panel. Each panel has
one or more `View` objects containing `ViewOptions`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from py_aep import (
    FastPreviewType,
    ViewOptions,
)
from py_aep.binary.misc_chunks import FipsChunk

if TYPE_CHECKING:
    pass
SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "view"


class TestViewOptionsWithoutItem:
    """Version-gated fields work when the viewer's item is no AVItem.

    parsers/view.py creates `ViewOptions(_item=None)` for such viewers;
    the `min_version` gate must be skipped (write allowed) when no AE
    version can be determined, instead of raising TypeError.
    """

    def test_set_and_read_gated_fields_with_item_none(self) -> None:
        opts = ViewOptions(_fips=FipsChunk(), _item=None)

        opts.rulers = True
        assert opts.rulers is True
        opts.guides_locked = True
        assert opts.guides_locked is True
        opts.guides_snap = True
        assert opts.guides_snap is True
        opts.guides_visibility = True
        assert opts.guides_visibility is True

    def test_gated_enum_field_with_item_none(self) -> None:
        opts = ViewOptions(_fips=FipsChunk(), _item=None)

        opts.fast_preview = FastPreviewType.FP_WIREFRAME
        assert opts.fast_preview == FastPreviewType.FP_WIREFRAME
