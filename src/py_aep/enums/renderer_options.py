"""3D renderer option enumerations.

These options are not exposed in ExtendScript; the values are the indices
After Effects stores in the `prda` chunk, and the labels are the entries
its Render Options dialog shows.
"""

from __future__ import annotations

from enum import IntEnum


class ShadowMapResolution(IntEnum):
    """Classic 3D shadow map resolution.

    Used in Composition Settings > 3D Renderer > Classic 3D > Options.

    Not documented in the AE scripting reference.
    """

    COMP_SIZE = 0
    RES_250 = 1
    RES_500 = 2
    RES_750 = 3
    RES_1000 = 4
    RES_1500 = 5
    RES_2000 = 6
    RES_3000 = 7
    RES_4000 = 8

    @property
    def label(self) -> str:
        """The entry as the Options dialog spells it."""
        return _SHADOW_MAP_RESOLUTION_LABELS[self.value]


_SHADOW_MAP_RESOLUTION_LABELS: dict[int, str] = {
    0: "Comp Size",
    1: "250",
    2: "500",
    3: "750",
    4: "1000",
    5: "1500",
    6: "2000",
    7: "3000",
    8: "4000",
}


class EnvironmentLightShadowResolution(IntEnum):
    """Advanced 3D environment light shadow resolution.

    Used in Composition Settings > 3D Renderer > Advanced 3D > Options.

    Not documented in the AE scripting reference.
    """

    HALF = 0
    FULL = 1
    DOUBLE = 2

    @property
    def label(self) -> str:
        """The entry as the Options dialog spells it."""
        return _ENV_LIGHT_SHADOW_RESOLUTION_LABELS[self.value]


_ENV_LIGHT_SHADOW_RESOLUTION_LABELS: dict[int, str] = {
    0: "Half (2MB)",
    1: "Full (16MB)",
    2: "Double (128MB)",
}
