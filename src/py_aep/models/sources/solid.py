from __future__ import annotations

import typing
from typing import List

from ..descriptors import ChunkField
from ..validators import validate_sequence
from .footage import FootageSource

if typing.TYPE_CHECKING:
    from ...binary.chunk import Chunk, ListChunk


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
        transform=list,
        validate=validate_sequence(length=3, min=0.0, max=1.0),
    )
    """The solid color, expressed as `[R, G, B]` values in the
    range `[0.0..1.0]`. Read / Write."""

    def __init__(
        self,
        *,
        _sspc: Chunk,
        _opti: Chunk,
        _linl: Chunk | None = None,
        _clrs: ListChunk | None = None,
    ) -> None:
        super().__init__(_sspc=_sspc, _linl=_linl, _clrs=_clrs)
        self._opti = _opti
