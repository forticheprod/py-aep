from __future__ import annotations

from typing import TYPE_CHECKING

from ....enums import CineonFileFormat
from ...descriptors import ChunkField
from ...validators import _validate_number, validate_one_of, validate_u2
from .base import FormatOptionsBase

if TYPE_CHECKING:
    from ....binary.render_chunks import RoptChunk


class CineonFormatOptions(FormatOptionsBase):
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

    def __init__(self, *, _body: RoptChunk) -> None:
        self._body = _body

    ten_bit_black_point = ChunkField[int](
        "_body",
        "ten_bit_black_point",
        validate=_validate_number(min=0, max=1023, integer=True),
    )
    """
    The 10-bit black point value (0-1023). Defines the code value that
    maps to the black point on a logarithmic scale. Read / Write.
    """

    ten_bit_white_point = ChunkField[int](
        "_body",
        "ten_bit_white_point",
        validate=_validate_number(min=0, max=1023, integer=True),
    )
    """
    The 10-bit white point value (0-1023). Defines the code value that
    maps to the white point on a logarithmic scale. Read / Write.
    """

    converted_black_point = ChunkField[float](
        "_body",
        "converted_black_point",
        validate=_validate_number(),
    )
    """
    The converted black point value, normalized to the 0.0-1.0 range.
    This is the linear-light equivalent of the 10-bit black point. Read / Write.
    """

    converted_white_point = ChunkField[float](
        "_body",
        "converted_white_point",
        validate=_validate_number(),
    )
    """
    The converted white point value, normalized to the 0.0-1.0 range.
    This is the linear-light equivalent of the 10-bit white point. Read / Write.
    """

    current_gamma = ChunkField[float](
        "_body",
        "current_gamma",
        validate=_validate_number(),
    )
    """The gamma value applied during the Cineon/DPX conversion. Read / Write."""

    highlight_expansion = ChunkField[int](
        "_body",
        "highlight_expansion",
        # Backed by a u2 field: an out-of-range value overflows `struct`
        # and crashes save() mid-write, leaving a partial .aep on disk.
        validate=validate_u2,
    )
    """The highlight expansion value. Read / Write."""

    logarithmic_conversion = ChunkField.bool(
        "_body",
        "logarithmic_conversion",
    )
    """Whether logarithmic conversion is enabled. Read / Write."""

    file_format = ChunkField.enum(
        CineonFileFormat,
        "_body",
        "file_format",
        allow_out_of_enum_values=True,
    )
    """
    The file format for the Cineon output. See [CineonFileFormat][] for
    possible values. An out-of-enum stored value reads back as a raw
    `int` (the binary is trusted). Read / Write.
    """

    bit_depth = ChunkField[int](
        "_body",
        "bit_depth",
        validate=validate_one_of([8, 10, 12, 16]),
    )
    """The bit depth per channel (8, 10, 12, or 16). Read / Write.

    Only meaningful when `file_format` is `CineonFileFormat.DPX`. For
    FIDO/Cineon 4.5 the output is always 10-bit and AE hides the Bit
    Depth dropdown; the stored byte is inert and keeps whatever the last
    DPX selection was (AE-observed), so reads may return a stale value.
    """
