"""Essential Graphics controller model for After Effects compositions.

The Essential Graphics panel (EGP) allows properties to be exposed as
controllers in a Motion Graphics template (.mogrt). Each composition
can have an EGP definition stored in a `LIST:CIF3` chunk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .descriptors import ChunkField
from .validators import validate_string

if TYPE_CHECKING:
    from ..binary.scalar_chunks import U4Chunk, Utf8Chunk


class EssentialGraphicsController:
    """A single controller in the Essential Graphics panel.

    Each controller maps to a `LIST:CCtl` chunk inside `LIST:CIF3`.
    The controller name is stored in a `LIST:CpS2` localized string
    chunk and can be renamed via the `name` attribute.
    """

    name = ChunkField[str](
        "_name_utf8",
        "value",
        validate=validate_string(allow_empty=False),
    )
    """The display name of the controller. Read / Write."""

    controller_type = ChunkField[int]("_ctyp", "value", read_only=True)
    """The controller type ID. Read-only.

    Known values: 1=Checkbox, 2=Slider, 4=Color, 5=Point,
    6=Text, 8=Comment, 9=MultiDimensional, 10=Group, 13=Dropdown.
    """

    def __init__(
        self,
        *,
        _name_utf8: Utf8Chunk,
        _ctyp: U4Chunk,
        uuid: str,
    ) -> None:
        self._name_utf8 = _name_utf8
        self._ctyp = _ctyp
        self.uuid = uuid
        """The unique identifier for this controller."""

    def __repr__(self) -> str:
        return (
            f"EssentialGraphicsController(name={self.name!r},"
            f" type={self.controller_type},"
            f" uuid={self.uuid!r})"
        )
