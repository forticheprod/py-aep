from __future__ import annotations

from ..binary.ldat_chunks import GuideItem
from ..enums import GuideOrientationType
from .descriptors import ChunkField
from .validators import validate_positive_number


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
        "_guide_item", "position", validate=validate_positive_number
    )
    """The position of the guide in pixels from the top (horizontal) or
    left (vertical) edge of the composition. Read / Write."""

    position_type = ChunkField[int]("_guide_item", "position_type")
    """The position type of the guide. Always 0 (pixels). Read / Write."""

    def __init__(self, _guide_item: GuideItem) -> None:
        self._guide_item = _guide_item

    @classmethod
    def _new(cls, orientation_type: int, position: int) -> Guide:
        """Create a new guide with the given orientation and position.

        Any `orientation_type` value other than 0 or 1 defaults to
        horizontal (matching ExtendScript behavior).

        Args:
            orientation_type: 0 for horizontal, 1 for vertical.
            position: The pixel position of the guide.

        Returns:
            A new `Guide` instance backed by a freshly created `GuideItem`.
        """
        orientation = GuideOrientationType.from_binary(orientation_type)
        validate_positive_number(position)
        item = GuideItem(
            orientation_type=orientation.to_binary(),
            position_type=0,
            position=float(position),
        )
        return cls(_guide_item=item)

    def __repr__(self) -> str:
        orient = (
            "horizontal"
            if self.orientation_type == GuideOrientationType.HORIZONTAL
            else "vertical"
        )
        return f"Guide({orient}, position={self.position})"
