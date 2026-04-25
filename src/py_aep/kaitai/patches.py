"""Monkey-patches for auto-generated Kaitai body classes.

Variable-size body types gain a `_recompute_size` method so that
`propagate_check` can use duck typing instead of `isinstance` checks.
Import this module once at startup (done by `kaitai/__init__.py`).
"""

from __future__ import annotations

from .aep import Aep  # type: ignore[attr-defined]


def _utf8_recompute_size(self: Aep.Utf8Body) -> int:  # type: ignore[type-arg]
    return len(self.contents.encode("UTF-8"))


def _ropt_recompute_size(self: Aep.RoptGenericData) -> int:  # type: ignore[type-arg]
    # format_code (4 bytes) precedes the variable-size raw field.
    return 4 + len(self.raw)


def _list_body_recompute_size(self: Aep.ListBody) -> int:  # type: ignore[type-arg]
    if self.list_type == "btdk":
        # list_type (4 bytes) + variable-size binary_data.
        return 4 + len(self.binary_data)
    # Non-btdk LIST bodies are maintained incrementally by
    # _update_len_chain.  Return the current len_body so the delta is
    # zero, but guarantee at least 4 bytes for list_type so that newly
    # created (empty) LIST bodies propagate their base size correctly.
    return max(4, int(self._parent.len_body))


Aep.Utf8Body._recompute_size = _utf8_recompute_size  # type: ignore[attr-defined]
Aep.RoptGenericData._recompute_size = _ropt_recompute_size  # type: ignore[attr-defined]
Aep.ListBody._recompute_size = _list_body_recompute_size  # type: ignore[attr-defined]
