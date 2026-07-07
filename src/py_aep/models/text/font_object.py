"""Font object model for After Effects text layers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...cos.descriptors import CosField

if TYPE_CHECKING:
    from typing import Any


def _design_vector_from_cos(raw: list[int]) -> list[float]:
    """Decode the COS design vector (16.16 fixed-point ints) to floats."""
    return [v / 65536.0 for v in raw]


class FontObject:
    """Provides information about a specific font.

    The Font object provides information about a specific font, along with
    the font technology used, helping disambiguate when multiple fonts
    sharing the same PostScript name are installed on the system.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        font = comp.text_layers[0].text.source_text.value.font_object
        print(font.post_script_name)
        ```

    Note:
        This functionality was added in After Effects 24.0.

    See: https://ae-scripting.docsforadobe.dev/text/fontobject/
    """

    post_script_name = CosField[str]("_font_data", "0", transform=str, default="")
    """The PostScript name of the font. Read-only."""

    version = CosField[str]("_font_data", "5", transform=str, default=None)
    """The version number of the font. Read-only."""

    design_vector = CosField["list[float] | None"](
        "_font_data", "4", transform=_design_vector_from_cos, read_only=True
    )
    """For variable fonts, an ordered array with a length matching the
    number of design axes defined by the font. `None` for non-variable
    fonts. Read-only.

    Stored in the file as 16.16 fixed-point integers; exposed as floats
    (e.g. `[700.0, 87.5]`).
    """

    @property
    def has_design_axes(self) -> bool:
        """Returns `True` if the font is a variable font. Read-only."""
        return self.design_vector is not None

    @property
    def family_prefix(self) -> str | None:
        """The family prefix of the variable font. For example, the family
        of the PostScript name `SFPro-Bold` is `SFPro`. `None` for
        non-variable fonts. Read-only."""
        if not self.has_design_axes:
            return None
        return self.post_script_name.split("-", 1)[0]

    def __init__(
        self,
        *,
        _font_data: dict[str, Any],
        _font_entry: dict[str, Any] | None = None,
        post_script_name: str | None = None,
        version: str | None = None,
    ) -> None:
        self._font_data = _font_data
        self._font_entry = _font_entry
        if post_script_name is not None:
            self.__dict__["post_script_name"] = post_script_name
        if version is not None:
            self.__dict__["version"] = version
