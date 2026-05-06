from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, cast

from ..descriptors import ComputedField
from ..reverses import unpack_values
from ..transforms import pack_values
from ..validators import validate_sequence
from .footage import FootageSource

if TYPE_CHECKING:
    from ...binary.chunk import ListChunk
    from ...binary.footage_chunks import OptiChunk, SspcChunk
    from ...binary.scalar_chunks import U1Chunk


def _compute_color(body: OptiChunk) -> list[float]:
    return cast("list[float]", pack_values(body, "color_r", "color_g", "color_b"))


def _reverse_color(value: list[float], _body: OptiChunk) -> dict[str, Any]:
    return unpack_values("color_r", "color_g", "color_b")(value, _body)


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

    color = ComputedField[List[float]](
        "_opti",
        compute=_compute_color,
        reverse=_reverse_color,
        validate=validate_sequence(length=3, min=0.0, max=1.0),
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
