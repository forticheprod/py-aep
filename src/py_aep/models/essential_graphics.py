"""Essential Graphics controller model for After Effects compositions.

The Essential Graphics panel (EGP) allows properties to be exposed as
controllers in a Motion Graphics template (.mogrt). Each composition
can have an EGP definition stored in a `LIST:CIF3` chunk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from .descriptors import ChunkField
from .validators import validate_name

if TYPE_CHECKING:
    from ..binary.scalar_chunks import U4Chunk, Utf8Chunk


class SourcePropertyRef(NamedTuple):
    """One node in a controller's source-property path, from root to leaf.

    `prop_index` is After Effects' raw 0-based position of the node within its
    parent property group's full (AE-internal) child list, or `None` to match
    by name (AE stores `0xFFFFFFFF` for by-name). It does NOT correspond to
    py_aep's `property(n)`/`properties[n]` index - e.g. the Fill effect's
    `ADBE Fill-0002` leaf has `prop_index=3` but is py_aep child position 1.
    (Named `prop_index`, not `index`, to avoid shadowing `tuple.index`.)
    """

    match_name: str
    prop_index: int | None


class EssentialGraphicsController:
    """A single controller in the Essential Graphics panel.

    Each controller maps to a `LIST:CCtl` chunk inside `LIST:CIF3`.
    The controller name is stored in a `LIST:CpS2` localized string
    chunk and can be renamed via the `name` attribute.
    """

    name = ChunkField[str](
        "_name_utf8",
        "value",
        validate=validate_name,
    )
    """The display name of the controller. Read / Write."""

    controller_type = ChunkField[int]("_ctyp", "value", read_only=True)
    """The controller type ID. Read-only.

    Known values: 1=Checkbox, 2=Slider, 4=Color, 5=Point,
    6=Text, 8=Comment, 9=MultiDimensional, 10=Group, 13=Dropdown,
    14=Media Replacement.
    """

    def __init__(
        self,
        *,
        _name_utf8: Utf8Chunk,
        _ctyp: U4Chunk,
        uuid: str,
        source_property_path: list[SourcePropertyRef],
        source_comp_id: int | None = None,
        source_layer_id: int | None = None,
    ) -> None:
        self._name_utf8 = _name_utf8
        self._ctyp = _ctyp
        self.uuid = uuid
        """The unique identifier for this controller."""
        self.source_property_path = source_property_path
        """The path (root to leaf) to the source-composition property this
        controller exposes, as `SourcePropertyRef` nodes. Empty when the
        path is not stored. Read-only."""
        self.source_comp_id = source_comp_id
        """The item id of the source composition that owns the controlled
        property (the `CCId` chunk), or `None` when not stored. Read-only."""
        self.source_layer_id = source_layer_id
        """The `layer_id` of the source layer that owns the controlled
        property (the `CLId` chunk), or `None` when not stored. Read-only."""

    def __repr__(self) -> str:
        return (
            f"EssentialGraphicsController(name={self.name!r},"
            f" type={self.controller_type},"
            f" uuid={self.uuid!r})"
        )
