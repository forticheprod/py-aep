from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums import GuideOrientationType
from .descriptors import ChunkField
from .validators import validate_number

if TYPE_CHECKING:
    from ..binary.ldat_chunks import GuideItem


class Guide:
    """A ruler guide used for alignment in a composition.

    Guides are horizontal or vertical lines placed at specific pixel positions
    within a composition. They are visual aids and do not affect rendering.

    Note:
        Guide class has no ExtendScript equivalent.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        for guide in comp.guides:
            print(guide.orientation_type, guide.position)
        ```
    """

    orientation_type = ChunkField.enum(
        GuideOrientationType,
        "_guide_item",
        "orientation_type",
    )
    """The orientation of the guide. Read / Write."""

    position = ChunkField[float](
        "_guide_item", "position", validate=validate_number(min=0.0)
    )
    """The position of the guide in pixels from the top (horizontal) or
    left (vertical) edge of the composition. Read / Write."""

    position_type = ChunkField[int]("_guide_item", "position_type")
    """The position type of the guide. Always 0 (pixels). Read / Write."""

    def __init__(self, _guide_item: GuideItem) -> None:
        self._guide_item = _guide_item

    def __repr__(self) -> str:
        orient = (
            "horizontal"
            if self.orientation_type == GuideOrientationType.HORIZONTAL
            else "vertical"
        )
        return f"Guide({orient}, position={self.position})"
