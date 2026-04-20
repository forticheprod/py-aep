from __future__ import annotations

import typing

from ....enums import JpegFormatType
from ....kaitai.descriptors import ChunkField
from ...validators import validate_number, validate_one_of

if typing.TYPE_CHECKING:
    from ....kaitai import Aep


class JpegFormatOptions:
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

    def __init__(self, *, _body: Aep.JpegRoptData) -> None:
        self._body = _body

    quality = ChunkField[int](
        "_body",
        "quality",
        validate=validate_number(min=0, max=10, integer=True),
    )
    """
    JPEG quality level, from 0 (Smaller File) to 10 (Bigger File). Read / Write.
    """

    format_type = ChunkField[JpegFormatType](
        "_body",
        "format_type",
        transform=JpegFormatType,
        reverse_seq_field=int,
    )
    """
    JPEG format option type: Baseline (Standard), Baseline Optimized,
    or Progressive. Read / Write.
    """

    scans = ChunkField[int](
        "_body",
        "scans",
        transform=lambda x: x + 2,
        reverse_seq_field=lambda x: x - 2,
        validate=validate_one_of([3, 4, 5]),
    )
    """
    Number of progressive scans (3, 4, or 5). Only relevant when
    `format_type` is `JpegFormatType.PROGRESSIVE`. Read / Write.
    """
