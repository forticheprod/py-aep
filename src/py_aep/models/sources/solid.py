from __future__ import annotations

from typing import TYPE_CHECKING, List, cast

from ...binary.footage_chunks import SoliOptiChunk, SspcChunk
from ...resolvers.solid import solid_color_name
from ..descriptors import ChunkField
from ..validators import (
    validate_name,
    validate_pixel_aspect,
    validate_rgb_color,
    validate_solid_dimension,
)
from .footage import FootageSource

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import OptiChunk
    from ...binary.scalar_chunks import U1Chunk


class SolidSource(FootageSource):
    """
    The `SolidSource` object represents a solid-color footage source.

    Example:
        ```python
        from py_aep import SolidSource, parse

        app = parse("project.aep")
        footage = app.project.footages[0]
        if isinstance(footage.main_source, SolidSource):
            print(footage.main_source.color)
        ```

    Info:
        `SolidSource` is a subclass of [FootageSource][] object. All methods and
        attributes of [FootageSource][] are available when working with `SolidSource`.

    See: https://ae-scripting.docsforadobe.dev/sources/solidsource/
    """

    color = ChunkField[List[float]](
        "_opti",
        "color",
        validate=validate_rgb_color,
    )
    """The solid color, expressed as `[R, G, B]` values in the
    range `[0.0..1.0]`. Read / Write."""

    def __init__(
        self,
        *,
        _sspc: SspcChunk,
        _opti: OptiChunk,
        _linl: U1Chunk | None = None,
        _clrs: ListChunk | None = None,
    ) -> None:
        super().__init__(_sspc=_sspc, _linl=_linl, _clrs=_clrs)
        self._opti = _opti

    @staticmethod
    def _color_name(r: float, g: float, b: float) -> str:
        """Derive the base solid name from an RGB color.

        After Effects names solids by their perceived color category.
        Returns the base name (e.g. `"Red Solid"`) without a trailing
        number suffix; the caller is responsible for disambiguation.

        Args:
            r: Red channel in `[0.0, 1.0]`.
            g: Green channel in `[0.0, 1.0]`.
            b: Blue channel in `[0.0, 1.0]`.
        """
        return solid_color_name(r, g, b)

    @classmethod
    def _new(
        cls,
        name: str,
        color: list[float] | tuple[float, float, float] = (0.0, 0.0, 0.0),
        width: int = 100,
        height: int = 100,
        pixel_aspect: float = 1.0,
    ) -> SolidSource:
        """Create a new solid source with backing chunks.

        Args:
            color: Solid color as [R, G, B] in 0.0-1.0 range.
            name: The solid name.
            width: Width in pixels (1-30000).
            height: Height in pixels (1-30000).
            pixel_aspect: Pixel aspect ratio (0.01-100.0).
        """
        validate_name(name)
        validate_solid_dimension(width)
        validate_solid_dimension(height)
        validate_pixel_aspect(pixel_aspect)
        validate_rgb_color(color)

        sspc = SspcChunk(
            width=width,
            height=height,
            source_format_type="Soli",
            alpha_mode_raw=3,
            duration_dividend=0,
        )
        sspc.pixel_aspect = pixel_aspect

        opti = SoliOptiChunk(
            color_r=color[0],
            color_g=color[1],
            color_b=color[2],
            solid_name=name,
        )

        return cls(_sspc=sspc, _opti=opti)

    def _resolve_name(self, raw_name: str) -> str:
        return str(cast("SoliOptiChunk", self._opti).solid_name)
