from __future__ import annotations

import typing
from typing import List

from ...enums import (
    AlphaMode,
    FieldSeparationType,
    LinearLightMode,
    PulldownPhase,
)
from ...enums.mappings import map_media_color_space
from ...kaitai.descriptors import ChunkField
from ...kaitai.reverses import denormalize_values, reverse_fractional
from ...kaitai.transforms import normalize_values
from ...kaitai.utils import find_by_type, toggle_flag_chunk
from ..validators import validate_number, validate_sequence

if typing.TYPE_CHECKING:
    from ...kaitai import Aep


def _reverse_field_separation_type(
    value: FieldSeparationType,
    body: object,
) -> dict[str, int]:
    """Decompose a combined field-separation value back into seq fields."""
    if value == FieldSeparationType.OFF:
        return {"field_separation_type_raw": 0, "field_order": 0}
    return {
        "field_separation_type_raw": 1,
        "field_order": int(value == FieldSeparationType.LOWER_FIELD_FIRST),
    }


class FootageSource:
    """
    The `FootageSource` object holds information describing the source of some
    footage. It is used as the `main_source` of a `FootageItem` object, or the
    `proxy_source` of a `CompItem` object or `FootageItem`.

    See: https://ae-scripting.docsforadobe.dev/sources/footagesource/
    """

    alpha_mode = ChunkField.enum(
        AlphaMode,
        "_sspc",
        "alpha_mode_raw",
    )
    """Defines how the alpha information in the footage is interpreted.
    If `has_alpha` is `False`, this attribute has no relevant meaning.
    Read / Write."""

    field_separation_type = ChunkField.enum(
        FieldSeparationType,
        "_sspc",
        "field_separation_type",
        reverse_instance_field=_reverse_field_separation_type,
    )
    """How the fields are to be separated in non-still footage.
    Read / Write."""

    has_alpha = ChunkField.bool("_sspc", "has_alpha", read_only=True)
    """When `True`, the footage has an alpha component. In this case, the
    attributes `alpha_mode`, `invert_alpha`, and `premultiplied` have valid
    values. When `False`, those attributes have no relevant meaning for the
    footage. Read-only."""

    high_quality_field_separation = ChunkField[bool](
        "_sspc",
        "high_quality_field_separation",
        transform=lambda v: v % 2 != 0,
        reverse_seq_field=int,
    )
    """When `True`, After Effects uses special algorithms to determine how to
    perform high-quality field separation. Read / Write."""

    invert_alpha = ChunkField.bool("_sspc", "invert_alpha")
    """When `True`, an alpha channel in a footage clip or proxy should be
    inverted. This attribute is valid only if an alpha is present. If
    `has_alpha` is `False`, or if `alpha_mode` is
    [AlphaMode.IGNORE][py_aep.enums.AlphaMode], this attribute is
    ignored. Read / Write."""

    loop = ChunkField[int](
        "_sspc",
        "loop",
        validate=validate_number(min=1, max=9999, integer=True),
    )
    """The number of times that the footage is to be played consecutively
    when used in a composition. Read / Write."""

    premul_color = ChunkField[List[float]](
        "_sspc",
        "premul_color",
        transform=normalize_values,
        reverse_seq_field=denormalize_values,
        validate=validate_sequence(length=3, min=0.0, max=1.0),
    )
    """The color to be premultiplied. This attribute is valid only if
    the `alpha_mode` is
    [AlphaMode.PREMULTIPLIED][py_aep.enums.AlphaMode].
    Read / Write."""

    interpret_as_linear_light = ChunkField.enum(
        LinearLightMode,
        "_linl",
        "value",
        default=LinearLightMode.OFF,
    )
    """The Interpret As Linear Light setting from the Interpret Footage >
    Color Management tab. Read / Write.

    Note:
        Not exposed in ExtendScript."""

    conform_frame_rate = ChunkField[float](
        "_sspc",
        "conform_frame_rate",
        reverse_instance_field=reverse_fractional(
            "conform_frame_rate_integer", "conform_frame_rate_fractional"
        ),
        validate=validate_number(min=0.0, max=999.0),
    )
    """A frame rate to use instead of the `native_frame_rate` value. If
    set to 0, the `native_frame_rate` is used instead. Read / Write."""

    display_frame_rate = ChunkField[float](
        "_sspc", "display_frame_rate", read_only=True
    )
    """The effective frame rate as displayed and rendered in compositions.
    If `remove_pulldown` is active, the rate is multiplied by 0.8.
    Read-only."""

    remove_pulldown = ChunkField.enum(
        PulldownPhase,
        "_sspc",
        "remove_pulldown",
        invalidates=["display_frame_rate"],
    )
    """Controls which pulldown phase to remove from the source footage.
    [PulldownPhase.OFF][py_aep.enums.PulldownPhase] by default.
    Read / Write."""

    native_frame_rate = ChunkField[float]("_sspc", "native_frame_rate", read_only=True)
    """The native frame rate of the footage. Read-only."""

    def __init__(
        self,
        *,
        _sspc: Aep.SspcBody,
        _linl: Aep.LinlBody | None = None,
        _clrs: Aep.ListBody | None = None,
    ) -> None:
        self._sspc = _sspc
        self._linl = _linl
        self._clrs = _clrs

    @property
    def preserve_rgb(self) -> bool:
        """When `True`, the footage Preserve RGB setting is enabled.
        From the Interpret Footage > Color Management tab. Read / Write.

        Note:
            Not exposed in ExtendScript."""
        if self._clrs is None:
            return False
        return any(c.chunk_type == "prgb" for c in self._clrs.chunks)

    @preserve_rgb.setter
    def preserve_rgb(self, value: bool) -> None:
        if self._clrs is None:
            raise AttributeError("Cannot set preserve_rgb: no CLRS container")
        toggle_flag_chunk(self._clrs, "prgb", "PrgbBody", bool(value))

    @property
    def media_color_space(self) -> str:
        """The media color space from the Interpret Footage >
        Color Management tab.

        Returns `"Embedded"` (default), `"Working Color Space"`, or
        the name of the selected ICC profile (e.g. `"Apple RGB"`).
        Read-only.

        Note:
            Not exposed in ExtendScript."""
        if self._clrs is None:
            return "Embedded"
        ipws_chunk = find_by_type(chunks=self._clrs.chunks, chunk_type="ipws")
        apid_chunk = find_by_type(chunks=self._clrs.chunks, chunk_type="apid")
        return map_media_color_space(
            bool(ipws_chunk.body.enabled),
            bytes(apid_chunk.body.profile_id),
        )

    @property
    def is_still(self) -> bool:
        """When `True` the footage is still; When `False`, it has a
        time-based component. Read-only."""
        return bool(self._sspc.source_duration == 0)
