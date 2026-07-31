"""Ray-traced 3D (`ADBE Picasso`) render options."""

from __future__ import annotations

from .render_options_base import RenderOptionsBase



class RayTracedRenderOptions(RenderOptionsBase):
    """Options for the Ray-traced 3D renderer.

    Deliberately empty. The renderer was removed in AE 2020 (17.0), so its
    Options dialog cannot be opened and its stored fields could never be
    matched to controls. Files using it parse and re-save byte-exact;
    there is nothing safe to expose. Read-only.
    """

    _SPEC = {}
