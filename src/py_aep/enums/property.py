"""Property-related After Effects enumerations."""

from __future__ import annotations

from enum import IntEnum


class PropertyControlType(IntEnum):
    """The type of effect control for a property.

    Describes the UI control type exposed in the After Effects effect panel
    (scalar slider, color picker, angle dial, checkbox, dropdown, etc.).
    Values match the AE SDK `PF_ParamType` enum (SDK name in comments
    where it differs).
    """

    LAYER = 0
    INTEGER = 1  # PF_Param_SLIDER (obsolete integer slider)
    SCALAR = 2  # PF_Param_FIX_SLIDER (16.16 fixed-point slider)
    ANGLE = 3
    BOOLEAN = 4  # PF_Param_CHECKBOX
    COLOR = 5
    TWO_D = 6  # PF_Param_POINT
    ENUM = 7  # PF_Param_POPUP
    PAINT_GROUP = 9  # PF_Param_NO_DATA
    SLIDER = 10  # PF_Param_FLOAT_SLIDER
    CURVE = 11  # PF_Param_ARBITRARY_DATA
    MASK = 12  # PF_Param_PATH
    GROUP = 13  # PF_Param_GROUP_START
    UNKNOWN_14 = 14  # PF_Param_GROUP_END
    UNKNOWN = 15  # PF_Param_BUTTON
    THREE_D = 18  # PF_Param_POINT_3D


class PropertyValueType(IntEnum):
    """The type of value stored in a property.

    Each type of data is stored and retrieved in a different kind of
    structure.  For example, a 3-D spatial property (such as a layer's
    position) is stored as an array of three floating-point values.

    See: https://ae-scripting.docsforadobe.dev/property/property/#propertypropertyvaluetype
    """

    UNKNOWN = 0
    NO_VALUE = 6412
    ThreeD_SPATIAL = 6413
    ThreeD = 6414
    TwoD_SPATIAL = 6415
    TwoD = 6416
    OneD = 6417
    COLOR = 6418
    CUSTOM_VALUE = 6419
    MARKER = 6420
    LAYER_INDEX = 6421
    MASK_INDEX = 6422
    SHAPE = 6423
    TEXT_DOCUMENT = 6424
    LRDR = 6425
    LITM = 6426
    GIDE = 6427
    ORIENTATION = 6428
    VARIABLE_FONT_AXIS = 3145784


class KeyframeInterpolationType(IntEnum):
    """Interpolation type for keyframes.

    See: https://ae-scripting.docsforadobe.dev/property/property/#propertysetinterpolationtypeatkey
    """

    LINEAR = 6612
    BEZIER = 6613
    HOLD = 6614

    @classmethod
    def from_binary(cls, value: int) -> KeyframeInterpolationType:
        """Convert binary value to KeyframeInterpolationType."""
        try:
            return cls(value + 6611)
        except ValueError:
            return cls.LINEAR

    def to_binary(self) -> int:
        """Convert KeyframeInterpolationType to binary value."""
        return int(self) - 6611
