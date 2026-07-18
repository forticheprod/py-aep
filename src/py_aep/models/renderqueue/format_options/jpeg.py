from __future__ import annotations

from typing import TYPE_CHECKING

from ....enums import JpegFormatType
from ...descriptors import ChunkField
from ...validators import _validate_number, validate_one_of
from .base import FormatOptionsBase

if TYPE_CHECKING:
    from ....binary.render_chunks import RoptChunk


class JpegFormatOptions(FormatOptionsBase):
    """JPEG format-specific render options.

    These settings correspond to the JPEG Options dialog in After Effects,
    accessible when the output format is set to JPEG Sequence.

    Example:
        ```python
        from py_aep import JpegFormatOptions, parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        if isinstance(om.format_options, JpegFormatOptions):
            print(om.format_options.quality)
        ```
    """

    def __init__(self, *, _body: RoptChunk) -> None:
        self._body = _body

    quality = ChunkField[int](
        "_body",
        "quality",
        validate=_validate_number(min=0, max=10, integer=True),
    )
    """
    JPEG quality level, from 0 (Smaller File) to 10 (Bigger File). Read / Write.
    """

    format_type = ChunkField.enum(
        JpegFormatType,
        "_body",
        "format_type",
        allow_out_of_enum_values=True,
    )
    """
    JPEG format option type: Baseline (Standard), Baseline Optimized,
    or Progressive. An out-of-enum stored value reads back as a raw
    `int` (the binary is trusted). Read / Write.
    """

    scans = ChunkField[int](
        "_body",
        "scans",
        transform=lambda x: x + 2,
        reverse=lambda x: x - 2,
        validate=validate_one_of([3, 4, 5]),
    )
    """
    Number of progressive scans (3, 4, or 5). Only relevant when
    `format_type` is `JpegFormatType.PROGRESSIVE`. Read / Write.
    """
