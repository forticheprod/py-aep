from __future__ import annotations

import typing
from typing import List

from ...enums import MaskFeatherFalloff, MaskMode, MaskMotionBlur
from ...kaitai.descriptors import ChunkField
from ...kaitai.reverses import denormalize_values
from ...kaitai.transforms import normalize_values
from ..validators import validate_sequence
from .property_group import PropertyGroup

if typing.TYPE_CHECKING:
    from ...kaitai import Aep
    from .property import Property


class MaskPropertyGroup(PropertyGroup):
    """An individual mask applied to a layer.

    The `MaskPropertyGroup` object encapsulates mask attributes in a layer.

    Info:
        `MaskPropertyGroup` is a subclass of PropertyGroup object. All methods and
        attributes of [PropertyBase][py_aep.models.properties.property_base.PropertyBase]
        object and [PropertyGroup][], in addition to those listed below, are available
        when working with `MaskPropertyGroup`.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        comp = app.project.compositions[0]
        layer = comp.layers[0]
        mask = layer.masks[0]
        print(mask.inverted)
        ```

    See: https://ae-scripting.docsforadobe.dev/property/maskpropertygroup/
    """

    color = ChunkField[List[float]](
        "_mkif",
        "color",
        transform=normalize_values,
        reverse_seq_field=denormalize_values,
        validate=validate_sequence(length=3, min=0.0, max=1.0),
    )
    """The color used to draw the mask outline as it appears in the user
    interface (Composition panel, Layer panel, and Timeline panel).
    The three array values specify the red, green, and blue components
    of the color. Read / Write."""

    inverted = ChunkField.bool("_mkif", "inverted")
    """When `True`, the mask is inverted. Read / Write."""

    locked = ChunkField.bool("_mkif", "locked")
    """When `True`, the mask is locked and cannot be edited in the user
    interface. Read / Write."""

    mask_feather_falloff = ChunkField.enum(
        MaskFeatherFalloff, "_mkif", "mask_feather_falloff"
    )
    """The feather falloff mode for the mask. Applies to all feather
    values for the mask. Read / Write."""

    mask_mode = ChunkField.enum(MaskMode, "_mkif", "mode")
    """The blending mode for the mask. Controls how the mask interacts with
    other masks and with the layer below. Read / Write."""

    mask_motion_blur = ChunkField.enum(MaskMotionBlur, "_mkif", "mask_motion_blur")
    """How motion blur is applied to this mask. Read / Write."""

    roto_bezier = ChunkField.bool(
        "_mask_shape_tdsb",
        "roto_bezier",
        default=False,
    )
    """When `True`, the mask uses RotoBezier, enabling curved mask segments
    without direction handles. Read / Write."""

    def __init__(
        self,
        *,
        _tdgp: Aep.ListBody | None = None,
        _tdsb: Aep.TdsbBody | None,
        _mkif: Aep.MkifBody,
        _mask_shape_tdsb: Aep.TdsbBody | None,
        _name_utf8: Aep.Utf8Body | None = None,
        match_name: str,
        property_depth: int,
        auto_name: str | None = None,
        properties: list[Property | PropertyGroup],
    ) -> None:
        super().__init__(
            _tdgp=_tdgp,
            _tdsb=_tdsb,
            _name_utf8=_name_utf8,
            match_name=match_name,
            auto_name=auto_name,
            property_depth=property_depth,
            properties=properties,
        )
        self._mkif = _mkif
        self._mask_shape_tdsb = _mask_shape_tdsb
