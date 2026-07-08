"""Variable-font design-axis reading via fontTools."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from fontTools.ttLib import TTFont

if TYPE_CHECKING:
    import os
    from typing import Union

    _PathLike = Union[str, "os.PathLike[str]"]


class FontDesignAxis(NamedTuple):
    """One design axis of a variable font (an `fvar` table entry)."""

    tag: str
    """The 4-character axis tag (e.g. `wght`)."""

    name: str
    """The axis display name from the font's name table (e.g. `Weight`)."""

    min_value: float
    default_value: float
    max_value: float


def read_design_axes(
    font_file: _PathLike, font_number: int = 0
) -> list[FontDesignAxis]:
    """Read the design axes of a variable font file.

    Args:
        font_file: Path to the variable font file (`.ttf` / `.otf` / `.ttc`).
        font_number: Face index within a TrueType Collection (0 for
            single-face files).

    Raises:
        ValueError: If the font has no `fvar` table (not a variable font).
    """
    font = TTFont(str(font_file), fontNumber=font_number, lazy=True)
    try:
        if "fvar" not in font:
            raise ValueError(
                f"{font_file} is not a variable font (it has no fvar table)."
            )
        name_table = font["name"] if "name" in font else None
        axes = []
        for axis in font["fvar"].axes:
            axis_name = None
            if name_table is not None:
                axis_name = name_table.getDebugName(axis.axisNameID)
            axes.append(
                FontDesignAxis(
                    tag=axis.axisTag,
                    name=axis_name or axis.axisTag,
                    min_value=float(axis.minValue),
                    default_value=float(axis.defaultValue),
                    max_value=float(axis.maxValue),
                )
            )
        return axes
    finally:
        font.close()
