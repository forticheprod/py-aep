from __future__ import annotations

import contextlib

from ..kaitai import Aep
from ..kaitai.utils import (
    ChunkNotFoundError,
    filter_by_type,
    find_by_list_type,
    find_by_type,
    str_contents,
)
from ..models.layers.av_layer import AVLayer
from ..models.layers.shape_layer import ShapeLayer
from ..models.layers.text_layer import TextLayer
from ..models.project import Project
from ..models.properties.property import Property
from .effect import parse_effect_definitions
from .item import parse_folder
from .render_queue import parse_render_queue


def parse_project(aep: Aep, file_path: str) -> Project:
    """Parse an After Effects (.aep) project file into a Project.

    Args:
        aep: The parsed Kaitai RIFX structure.
        file_path: Path to the `.aep` file (stored on the Project).
    """
    root_chunks: list[Aep.Chunk] = aep.body.chunks

    root_folder_chunk: Aep.Chunk = find_by_list_type(
        chunks=root_chunks, list_type="Fold"
    )
    head_chunk: Aep.HeadBody = find_by_type(chunks=root_chunks, chunk_type="head").body
    nnhd_chunk: Aep.NnhdBody = find_by_type(chunks=root_chunks, chunk_type="nnhd").body
    acer_chunk: Aep.AcerBody = find_by_type(chunks=root_chunks, chunk_type="acer").body
    adfr_chunk: Aep.AdfrBody = find_by_type(chunks=root_chunks, chunk_type="adfr").body
    dwga_chunk: Aep.DwgaBody = find_by_type(chunks=root_chunks, chunk_type="dwga").body
    gpug_chunk: Aep.Chunk = find_by_list_type(chunks=root_chunks, list_type="gpuG")
    gpug_utf8: Aep.Utf8Body = find_by_type(
        chunks=gpug_chunk.body.chunks, chunk_type="Utf8"
    ).body

    # Expression engine: LIST:ExEn > Utf8
    exen_utf8: Aep.Utf8Body | None = None
    with contextlib.suppress(ChunkNotFoundError):
        exen_chunk = find_by_list_type(chunks=root_chunks, list_type="ExEn")
        exen_utf8 = find_by_type(chunks=exen_chunk.body.chunks, chunk_type="Utf8").body

    # CMS settings JSON and baseColorProfile Utf8 chunks
    cms_utf8: Aep.Utf8Body | None = None
    ws_utf8: Aep.Utf8Body | None = None
    dcs_utf8: Aep.Utf8Body | None = None
    for c in filter_by_type(chunks=root_chunks, chunk_type="Utf8"):
        content = str_contents(c)
        if cms_utf8 is None and "lutInterpolationMethod" in content:
            cms_utf8 = c.body
        if "baseColorProfile" in content:
            if ws_utf8 is None:
                ws_utf8 = c.body
            elif dcs_utf8 is None:
                dcs_utf8 = c.body

    project = Project(
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
        _aep=aep,
        file=file_path,
        items={},
        render_queue=None,
    )

    project._effect_param_defs = parse_effect_definitions(root_chunks)

    root_folder = parse_folder(
        is_root=True,
        child_chunks=root_folder_chunk.body.chunks,
        project=project,
        _idta=None,
        _name_utf8=None,
        _cmta=None,
        _item_list=root_folder_chunk.body,
        parent_folder=None,
    )
    project.items[0] = root_folder

    _link_layers(project)

    project._render_queue = parse_render_queue(root_chunks, project)

    with contextlib.suppress(ChunkNotFoundError):
        fcid_chunk = find_by_type(chunks=root_chunks, chunk_type="fcid")
        project._active_item = project.items[fcid_chunk.body.active_item_id]

    return project


def _link_layers(project: Project) -> None:
    for composition in project.compositions:
        for layer in composition.layers:
            if isinstance(layer, AVLayer) and layer._source_id != 0:
                source = project.items.get(layer._source_id)
                if source is not None:
                    if hasattr(source, "_used_in"):
                        source._used_in.add(composition)
    _fix_anchor_defaults(project)


def _fix_anchor_defaults(project: Project) -> None:
    """Recompute Anchor Point defaults now that all sources are resolvable.

    During initial parsing, `synthesize_layer_properties` may run before the
    layer's source item is in `project.items`, causing the anchor default
    to fall back to composition center.  This pass corrects those defaults.
    """
    for composition in project.compositions:
        comp_w = composition.width
        comp_h = composition.height
        for layer in composition.layers:
            if not isinstance(layer, AVLayer):
                continue
            if isinstance(layer, (TextLayer, ShapeLayer)) or layer.null_layer:
                continue
            source = layer.source
            if source is None:
                continue
            s_w = getattr(source, "width", 0)
            s_h = getattr(source, "height", 0)
            if s_w == comp_w and s_h == comp_h:
                continue  # default is already correct
            anchor = layer.transform["ADBE Anchor Point"]
            if not isinstance(anchor, Property):
                continue
            # AE uses a minimum 1x1 source size for anchor defaults
            correct = [max(s_w, 1) / 2.0, max(s_h, 1) / 2.0, 0.0]
            anchor.default_value = correct
            # Update synthesized value (no cdat) to match
            if anchor._cdat is None and not anchor.keyframes:
                anchor._value = correct
