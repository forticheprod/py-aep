"""Shared plumbing for the per-renderer option wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...renderqueue.settings import SettingsSpec, SettingsView

if TYPE_CHECKING:
    from ..composition import CompItem


class RendererOptionsBase(SettingsView):
    """
    A renderer's options, as both a mapping and a typed object.

    Subclasses [SettingsView][] with itself as the owner, so one object
    satisfies both idioms.

    Example:
        ```python
        comp.renderer_options["Quality"] = 61     # mapping
        comp.renderer_options.quality = 61        # typed, validated
        ```

    The [CompItem][] is held because Advanced 3D stores its Casting Box
    values as fractions of the composition's own pixel dimensions.
    """

    # ExtendScript-style key -> (attribute name, optional enum class)
    _SPEC: SettingsSpec = {}

    def __init__(self, *, body: Any, comp: CompItem) -> None:
        self._body = body
        self._comp = comp
        super().__init__(self, type(self)._SPEC)

    def __setattr__(self, name: str, value: Any) -> None:
        # A fresh wrapper is built on every `renderer_options` access, so a
        # write to a name with no backing descriptor would vanish with the
        # wrapper. Reject it instead of silently dropping it.
        if not name.startswith("_") and not hasattr(type(self), name):
            raise AttributeError(f"{type(self).__name__} has no option {name!r}")
        super().__setattr__(name, value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self.items())!r})"
