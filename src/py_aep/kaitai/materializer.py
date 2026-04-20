"""Chunk-tree builders for property materialization.

When a synthesized property (backed by `ProxyBody`) receives its first
end-user write, materialization creates the binary chunk subtree that
makes the property indistinguishable from one parsed from a .aep file.

Two public functions cover leaf properties and property groups:

- `materialize_property` builds tdmn + LIST:tdbs + tdsb + tdsn + tdb4
  + optional cdat + sentinel.
- `materialize_group` builds tdmn + LIST:tdgp + tdsb + tdsn + sentinel.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from .aep import Aep  # type: ignore[attr-defined]
from .proxy import ProxyBody
from .utils import create_chunk, create_tdsb_chunk

_TDSN_SENTINEL = "-_0_/-"


class MaterializedProperty(NamedTuple):
    """Chunk bodies produced by `materialize_property`."""

    tdsb: Aep.TdsbBody
    tdb4: Aep.Tdb4Body
    tdbs: Aep.ListBody
    name_utf8: Aep.Utf8Body
    cdat: Aep.CdatBody | None


class MaterializedGroup(NamedTuple):
    """Chunk bodies produced by `materialize_group`."""

    tdsb: Aep.TdsbBody
    tdgp: Aep.ListBody
    name_utf8: Aep.Utf8Body


def _build_tdb4_attrs(
    proxy_tdb4: ProxyBody | None,
) -> dict[str, Any]:
    """Build the attribute dict for a default tdb4 chunk body.

    Reads typed flags (dimensions, is_spatial, can_vary_over_time, etc.)
    from the proxy when available, falling back to safe defaults.
    """

    def _proxy(field: str, default: int) -> int:
        if proxy_tdb4 is not None:
            return getattr(proxy_tdb4, field, default)  # type: ignore[no-any-return]
        return default

    return {
        "magic": b"\xdb\x99",
        "dimensions": _proxy("dimensions", 1),
        "_unnamed2": b"\x00",
        "_unnamed3": 0,
        "is_spatial": _proxy("is_spatial", 0),
        "_unnamed5": 0,
        "static": 1,
        "_unnamed7": b"\x00" * 5,
        "_unnamed8": 0,
        "can_vary_over_time": _proxy("can_vary_over_time", 0),
        "_unnamed10": 0,
        "_unnamed11": b"\x00" * 4,
        "unknown_floats": [0.0001, 1.0, 1.0, 1.0, 1.0],
        "_unnamed13": b"\x00",
        "_unnamed14": 0,
        "no_value": _proxy("no_value", 0),
        "_unnamed16": b"\x00",
        "_unnamed17": 0,
        "vector": _proxy("vector", 0),
        "integer": _proxy("integer", 0),
        "_unnamed20": 0,
        "color": _proxy("color", 0),
        "_unnamed22": b"\x00" * 8,
        "animated": 0,
        "_unnamed24": b"\x00" * 15,
        "_unnamed25": b"\x00" * 32,
        "_unnamed26": b"\x00" * 3,
        "_unnamed27": 0,
        "expression_disabled": 1,
        "_unnamed29": b"\x00" * 4,
    }


def _create_property_container(
    parent_tdgp: Aep.ListBody,
    match_name: str,
    proxy_tdsb: ProxyBody,
    list_type: str,
) -> tuple[Aep.ListBody, Aep.TdsbBody]:
    """Create tdmn + LIST container + tdsb + sentinel in *parent_tdgp*.

    Returns the new container body and its tdsb body.
    """
    # 1. tdmn - match name identifier.
    create_chunk(parent_tdgp, "tdmn", "Utf8Body", contents=match_name + "\x00")

    # 2. LIST container (tdbs or tdgp).
    container_chunk = create_chunk(
        parent_tdgp, "LIST", "ListBody", list_type=list_type, chunks=[]
    )
    container_body = container_chunk.body

    # 3. tdsb - property flags.
    tdsb_chunk = create_tdsb_chunk(container_body, proxy_tdsb)

    # 4. "ADBE Group End" sentinel.
    create_chunk(parent_tdgp, "tdmn", "Utf8Body", contents="ADBE Group End\x00")

    return container_body, tdsb_chunk.body


def materialize_property(
    parent_tdgp: Aep.ListBody,
    match_name: str,
    proxy_tdsb: ProxyBody,
    proxy_tdb4: ProxyBody | None,
    value: Any,
    display_name: str | None = None,
) -> MaterializedProperty:
    """Build the full chunk subtree for a leaf property.

    Creates: tdmn + LIST:tdbs (tdsb + tdsn + tdb4 + optional cdat) +
    sentinel in *parent_tdgp*.
    """
    tdbs_body, tdsb_body = _create_property_container(
        parent_tdgp, match_name, proxy_tdsb, "tdbs"
    )

    # tdsn - property name. AE uses "-_0_/-" as the default display name
    # for properties whose name is derived from the match name at runtime.
    tdsn_contents = (display_name if display_name is not None else "-_0_/-") + "\x00"
    tdsn_chunk = create_chunk(tdbs_body, "tdsn", "Chunks", chunks=[])
    create_chunk(tdsn_chunk.body, "Utf8", "Utf8Body", contents=tdsn_contents)
    name_utf8: Aep.Utf8Body = tdsn_chunk.body.chunks[0].body

    # tdb4 - property metadata.
    tdb4_chunk = create_chunk(
        tdbs_body, "tdb4", "Tdb4Body", **_build_tdb4_attrs(proxy_tdb4)
    )

    # cdat - property value (only for numeric types).
    cdat_body: Aep.CdatBody | None = None
    if value is not None and isinstance(value, (int, float, list)):
        if isinstance(value, list):
            raw = [float(v) for v in value]
        else:
            raw = [float(value)]

        cdat_chunk = create_chunk(tdbs_body, "cdat", "CdatBody", False, value_be=raw)
        cdat_body = cdat_chunk.body

    return MaterializedProperty(
        tdsb=tdsb_body,
        tdb4=tdb4_chunk.body,
        tdbs=tdbs_body,
        name_utf8=name_utf8,
        cdat=cdat_body,
    )


def materialize_group(
    parent_tdgp: Aep.ListBody,
    match_name: str,
    proxy_tdsb: ProxyBody,
    display_name: str | None = None,
) -> MaterializedGroup:
    """Build the full chunk subtree for a property group.

    Creates: tdmn + LIST:tdgp (tdsb + tdsn) + sentinel in *parent_tdgp*.
    """
    tdgp_body, tdsb_body = _create_property_container(
        parent_tdgp, match_name, proxy_tdsb, "tdgp"
    )

    # tdsn - group name (sentinel when not explicitly set).
    tdsn_contents = (display_name if display_name is not None else "-_0_/-") + "\x00"
    tdsn_chunk = create_chunk(tdgp_body, "tdsn", "Chunks", chunks=[])
    create_chunk(tdsn_chunk.body, "Utf8", "Utf8Body", contents=tdsn_contents)
    name_utf8: Aep.Utf8Body = tdsn_chunk.body.chunks[0].body

    return MaterializedGroup(tdsb=tdsb_body, tdgp=tdgp_body, name_utf8=name_utf8)
