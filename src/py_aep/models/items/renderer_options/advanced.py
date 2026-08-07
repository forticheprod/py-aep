"""Advanced 3D (`ADBE Calder`) render options."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....enums import EnvironmentLightShadowResolution
from ...descriptors import ChunkField
from ...validators import (
    validate_advanced_quality,
    validate_casting_box_center,
    validate_casting_box_size,
    validate_shadow_smoothness,
)
from .renderer_options_base import RendererOptionsBase

if TYPE_CHECKING:
    from ....binary.misc_chunks import AdvancedPrdaChunk


class AdvancedRendererOptions(RendererOptionsBase):
    """Options for the Advanced 3D renderer.

    Casting Box Size and Casting Box Center are stored as fractions of the
    composition's **raw pixel** dimensions - pixel aspect ratio is not
    applied - and are exposed here in the pixel values the Options dialog
    shows. Two things worth knowing:

    - Resizing a composition silently rescales these options in pixel
      terms, because the stored fraction does not move. That is After
      Effects' own behaviour.
    - Values that cross a save are stored as `float32`, so a pixel value
      read back after saving can differ from the one written by a tiny
      fraction of a pixel.
    """

    _body: AdvancedPrdaChunk

    _SPEC = {
        "Quality": ("quality", None),
        "Resolution": ("resolution", EnvironmentLightShadowResolution),
        "Smoothness": ("smoothness", None),
        "Casting Box Size": ("casting_box_size", None),
        "Casting Box Center": ("casting_box_center", None),
    }

    quality = ChunkField[int]("_body", "quality", validate=validate_advanced_quality)
    """Renderer quality, `1` to `125`. Read / Write."""

    resolution = ChunkField.enum(
        EnvironmentLightShadowResolution, "_body", "resolution"
    )
    """Environment light shadow resolution. Read / Write."""

    smoothness = ChunkField[int](
        "_body", "smoothness", validate=validate_shadow_smoothness
    )
    """Environment light shadow smoothness, `1` to `20`. Read / Write."""

    @property
    def casting_box_size(self) -> float:
        """
        Size of the shadow casting box, in pixels, as shown in the Options
        dialog. One dialog control drives all three stored axes, so reads
        report the X axis.
        Read / Write.
        """
        return self._body.casting_box_size_x * self._comp.width

    @casting_box_size.setter
    def casting_box_size(self, value: float) -> None:
        validate_casting_box_size(value)
        fraction = value / self._comp.width
        self._body.casting_box_size_x = fraction
        self._body.casting_box_size_y = fraction
        self._body.casting_box_size_z = fraction

    @property
    def casting_box_center(self) -> list[float]:
        """
        Centre of the shadow casting box as `[x, y, z]` in pixels, as shown
        in the Options dialog. X and Y are offsets from the composition
        centre; Z is measured from zero. Read / Write.
        """
        width, height = self._comp.width, self._comp.height
        return [
            self._body.casting_box_center_x * width + width / 2,
            self._body.casting_box_center_y * height + height / 2,
            self._body.casting_box_center_z * width,
        ]

    @casting_box_center.setter
    def casting_box_center(self, value: list[float]) -> None:
        validate_casting_box_center(value)
        width, height = self._comp.width, self._comp.height
        x, y, z = value
        self._body.casting_box_center_x = (x - width / 2) / width
        self._body.casting_box_center_y = (y - height / 2) / height
        self._body.casting_box_center_z = z / width
