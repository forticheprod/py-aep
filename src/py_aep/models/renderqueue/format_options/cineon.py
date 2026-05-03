from __future__ import annotations

import typing

from ....enums import CineonFileFormat
from ...descriptors import ChunkField
from ...validators import validate_number, validate_one_of

if typing.TYPE_CHECKING:
    from ....binary.chunk import Chunk


class CineonFormatOptions:
    """Cineon/DPX format-specific render options.

    These settings correspond to the Cineon Settings dialog in After Effects,
    accessible when the output format is set to Cineon Sequence or DPX
    Sequence.

    Example:
        ```python
        from py_aep import CineonFormatOptions, parse

        app = parse("project.aep")
        om = app.project.render_queue.items[0].output_modules[0]
        if isinstance(om.format_options, CineonFormatOptions):
            print(om.format_options.file_format)
        ```
    """

    def __init__(self, *, _body: Chunk) -> None:
        self._body = _body

    ten_bit_black_point = ChunkField[int](
        "_body",
        "ten_bit_black_point",
        validate=validate_number(min=0, max=1023, integer=True),
    )
    """
    The 10-bit black point value (0-1023). Defines the code value that
    maps to the black point on a logarithmic scale. Read / Write.
    """

    ten_bit_white_point = ChunkField[int](
        "_body",
        "ten_bit_white_point",
        validate=validate_number(min=0, max=1023, integer=True),
    )
    """
    The 10-bit white point value (0-1023). Defines the code value that
    maps to the white point on a logarithmic scale. Read / Write.
    """

    converted_black_point = ChunkField[float](
        "_body",
        "converted_black_point",
    )
    """
    The converted black point value, normalized to the 0.0-1.0 range.
    This is the linear-light equivalent of the 10-bit black point. Read / Write.
    """

    converted_white_point = ChunkField[float](
        "_body",
        "converted_white_point",
    )
    """
    The converted white point value, normalized to the 0.0-1.0 range.
    This is the linear-light equivalent of the 10-bit white point. Read / Write.
    """

    current_gamma = ChunkField[float](
        "_body",
        "current_gamma",
    )
    """The gamma value applied during the Cineon/DPX conversion. Read / Write."""

    highlight_expansion = ChunkField[int](
        "_body",
        "highlight_expansion",
    )
    """The highlight expansion value. Read / Write."""

    logarithmic_conversion = ChunkField[bool](
        "_body",
        "logarithmic_conversion",
    )
    """Whether logarithmic conversion is enabled. Read / Write."""

    file_format = ChunkField.enum(
        CineonFileFormat,
        "_body",
        "file_format",
    )
    """
    The file format for the Cineon output. See [CineonFileFormat][] for
    possible values. Read / Write.
    """

    bit_depth = ChunkField[int](
        "_body",
        "bit_depth",
        validate=validate_one_of([8, 10, 12, 16]),
    )
    """The bit depth per channel (8, 10, 12, or 16). Read / Write."""
