from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, cast

from ..binary.item_chunks import HeadChunk, NhedChunk, NnhdChunk
from ..binary.misc_chunks import DwgaChunk
from ..binary.scalar_chunks import F8Chunk, U1Chunk, Utf8Chunk
from ..binary.utils import (
    ChunkNotFoundError,
    filter_by_type,
    find_by_list_type,
    find_by_type,
)
from ..models.descriptors import _suppress_materialization
from ..models.project import Project
from .effect import parse_effect_definitions
from .item import parse_folder
from .render_queue import parse_render_queue

if TYPE_CHECKING:
    from pathlib import Path

    from ..binary.chunk import Chunk, ListChunk


def _color_profile_utf8(root_chunks: list[Chunk], marker: str) -> Utf8Chunk | None:
    """The color-profile `Utf8` AE writes immediately after `marker`.

    `marker` is `PwCs` (working space) or `pdvc` (display space). The slot is
    identified by its marker rather than by the order the envelopes appear in:
    an unset slot holds a literal `{}`, so keying on "first profile envelope
    wins" reads a display space as the working space whenever the working space
    is unset. Mirrors `Project._rewrite_color_profile`, which writes by this
    same rule.

    Returns:
        The `Utf8Chunk` holding the profile envelope, or `None` when the marker
        is absent or its slot is unset.
    """
    for i, chunk in enumerate(root_chunks):
        if chunk.chunk_type != marker or i + 1 >= len(root_chunks):
            continue
        following = root_chunks[i + 1]
        if following.chunk_type != "Utf8":
            continue
        utf8 = cast("Utf8Chunk", following)
        if "baseColorProfile" in utf8.value:
            return utf8
    return None


@_suppress_materialization()
def parse_project(
    rifx: ListChunk,
    xmp: str,
    file_path: str,
    ae_preferences_dir: Path | None = None,
) -> Project:
    """Parse an After Effects (.aep) project file into a Project.

    Args:
        rifx: The parsed binary RIFX root chunk.
        xmp: The XMP metadata string from the file trailer.
        file_path: Path to the `.aep` file (stored on the Project).
        ae_preferences_dir: Optional path to the AE preferences directory
            for template lookup.
    """
    root_chunks = rifx.chunks

    root_folder_chunk = find_by_list_type(chunks=root_chunks, list_type="Fold")
    head_chunk = cast("HeadChunk", find_by_type(chunks=root_chunks, chunk_type="head"))
    nhed_chunk = cast("NhedChunk", find_by_type(chunks=root_chunks, chunk_type="nhed"))
    nnhd_chunk = cast("NnhdChunk", find_by_type(chunks=root_chunks, chunk_type="nnhd"))
    acer_chunk = cast("U1Chunk", find_by_type(chunks=root_chunks, chunk_type="acer"))
    adfr_chunk = cast("F8Chunk", find_by_type(chunks=root_chunks, chunk_type="adfr"))
    dwga_chunk = cast("DwgaChunk", find_by_type(chunks=root_chunks, chunk_type="dwga"))
    gpug_chunk = find_by_list_type(chunks=root_chunks, list_type="gpuG")
    gpug_utf8 = cast(
        "Utf8Chunk", find_by_type(chunks=gpug_chunk.chunks, chunk_type="Utf8")
    )

    # Expression engine: LIST:ExEn > Utf8
    exen_utf8 = None
    with contextlib.suppress(ChunkNotFoundError):
        exen_chunk = find_by_list_type(chunks=root_chunks, list_type="ExEn")
        exen_utf8 = cast(
            "Utf8Chunk", find_by_type(chunks=exen_chunk.chunks, chunk_type="Utf8")
        )

    # CMS settings JSON
    cms_utf8: Utf8Chunk | None = None
    for c in cast(
        "list[Utf8Chunk]", filter_by_type(chunks=root_chunks, chunk_type="Utf8")
    ):
        content = c.value
        # The color-management settings JSON is fragmented across AE versions:
        # some files store `{"colorManagementSystem":..,"ocioConfigurationFile":..}`,
        # others `{"graphicsWhiteLuminance":..,"lutInterpolationMethod":..}`. Prefer
        # the `colorManagementSystem` chunk (so OCIO projects are detected), but
        # fall back to a `lutInterpolationMethod`-only chunk when there is none.
        if "colorManagementSystem" in content:
            cms_utf8 = c
        elif cms_utf8 is None and "lutInterpolationMethod" in content:
            cms_utf8 = c

    ws_utf8 = _color_profile_utf8(root_chunks, "PwCs")
    dcs_utf8 = _color_profile_utf8(root_chunks, "pdvc")

    project = Project(
        _nhed=nhed_chunk,
        _nnhd=nnhd_chunk,
        _head=head_chunk,
        _acer=acer_chunk,
        _adfr=adfr_chunk,
        _dwga=dwga_chunk,
        _gpug_utf8=gpug_utf8,
        _exen_utf8=exen_utf8,
        _cms_utf8=cms_utf8,
        _ws_utf8=ws_utf8,
        _dcs_utf8=dcs_utf8,
        _rifx=rifx,
        _xmp=xmp,
        file=file_path,
        items={},
        render_queue=None,
        ae_preferences_dir=ae_preferences_dir,
    )

    project._effect_param_defs = parse_effect_definitions(root_chunks)

    root_folder = parse_folder(
        is_root=True,
        child_chunks=root_folder_chunk.chunks,
        project=project,
        _idta=None,
        _name_utf8=None,
        _cmta=None,
        _item_list=root_folder_chunk,
        _gide=None,
        parent_folder=None,
    )
    project.items[0] = root_folder

    project._render_queue = parse_render_queue(root_chunks, project)

    with contextlib.suppress(ChunkNotFoundError):
        fcid_chunk = cast(
            "U1Chunk", find_by_type(chunks=root_chunks, chunk_type="fcid")
        )
        project._active_item = project.items[fcid_chunk.value]

    return project
