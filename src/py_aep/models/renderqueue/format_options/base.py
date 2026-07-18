from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..output_module import OutputModule


class FormatOptionsBase:
    """Shared plumbing for the format-specific render-option wrappers.

    Every wrapper holds an `Ropt` chunk that lives inside its output
    module's block. `OutputModule.apply_template()` and a rolled-back
    `batch_edit()` REPLACE that chunk (the new one may even be a different
    format, and so a different wrapper class), rebinding
    `OutputModule._format_options` to a freshly parsed object. A reference
    the caller took before that point still wraps the old chunk, which is
    no longer in the tree - so its writes would land in an orphaned body
    and be silently dropped from the saved file, while reading back as if
    they had succeeded.

    Those call sites mark the outgoing wrapper detached, and every write
    is gated on it here.
    """

    #: Back-reference to the owning output module. `None` while the parser
    #: is building the wrapper, before `OutputModule` wires it up - which
    #: is why detachment needs its own flag rather than reusing `is None`.
    _parent_om: OutputModule | None = None

    #: Set when the owning module has replaced this wrapper's chunk.
    _detached: bool = False

    def _check_attached(self) -> None:
        if self._detached:
            raise RuntimeError(
                "format options are detached from their output module: the "
                "module replaced them (apply_template, or a rolled-back "
                "batch_edit). Re-fetch `output_module.format_options`."
            )

    def __setattr__(self, name: str, value: Any) -> None:
        # Public fields only: `__init__` assigns `_body` (and friends), and
        # the detach itself writes `_detached`, both before/while there is
        # anything to guard.
        if not name.startswith("_"):
            self._check_attached()
        super().__setattr__(name, value)
