"""Enumerate and resolve the selectable layers of a layered source file.

Mirrors the "Choose Layer" dropdown in After Effects' import dialog for
layered files (`.psd`/`.psb` via the Photoshop layer records, `.ai`/`.pdf`
via PDF Optional Content Groups): leaf layers only (groups are not
selectable), listed top layer first, nested leaves shown without a group
prefix.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..data.file_formats import AI_COMP_EXTENSIONS, PSD_COMP_EXTENSIONS
from .ai_layers import read_ai_layers
from .psd_layers import PsdGroup, PsdLayer, read_psd_layers

if TYPE_CHECKING:
    import os


def psd_leaf_layers(file: str | os.PathLike[str]) -> list[PsdLayer]:
    """Return a PSD's leaf layers in document order (bottom layer first).

    Flattens the [read_psd_layers][] group tree to the layers AE's
    chooser offers (groups excluded).

    Raises:
        UnsupportedPsdLayersError: If the file is not a valid PSD/PSB.
        FlattenedPsdError: If the document has no layer records.
    """
    leaves: list[PsdLayer] = []

    def _walk(nodes: list[PsdLayer | PsdGroup]) -> None:
        for node in nodes:
            if isinstance(node, PsdGroup):
                _walk(node.children)
            else:
                leaves.append(node)

    _walk(read_psd_layers(file))
    leaves.sort(key=lambda leaf: leaf.record_index)
    return leaves


def list_layers(file: str | os.PathLike[str]) -> list[str]:
    """Return the selectable layer names of a layered file, top layer first.

    The order and contents match After Effects' "Choose Layer" import
    dropdown: leaf layers only, top-most first. Duplicate names are
    possible (Photoshop does not enforce unique layer names).

    Args:
        file: Path to a `.psd`, `.psb`, `.ai`, or `.pdf` file.

    Raises:
        ValueError: If the extension is not a layered format, or the file's
            layers cannot be enumerated (`UnsupportedPsdLayersError` /
            `UnsupportedAiLayersError`, both `ValueError` subclasses).
    """
    suffix = Path(file).suffix.lower()
    if suffix in PSD_COMP_EXTENSIONS:
        return [leaf.name for leaf in reversed(psd_leaf_layers(file))]
    if suffix in AI_COMP_EXTENSIONS:
        return list(reversed(read_ai_layers(file)))
    raise ValueError(
        f"list_layers supports layered .psd/.psb/.ai/.pdf files, got {suffix!r}"
    )


def layer_index_for_stored(
    file: str | os.PathLike[str],
    stored_index: int,
) -> int:
    """Map a stored binary layer index to its `list_layers` position in `file`.

    The stored index is the `sspc` layer index field of a single-layer
    binding: the PSD layer record index (which counts group divider
    records) or the AI/PDF document-order OCG index. Used by
    `FootageItem.replace(..., CURRENT_VALUE)` to rebind a new file at the
    same stored index.

    Raises:
        ValueError: If the extension is not a layered format, or no
            selectable layer of `file` has that stored index.
    """
    suffix = Path(file).suffix.lower()
    if suffix in PSD_COMP_EXTENSIONS:
        leaves = psd_leaf_layers(file)
        for i, leaf in enumerate(reversed(leaves)):
            if leaf.record_index == stored_index:
                return i
        raise ValueError(
            f"{Path(file).name}: no selectable layer has stored index "
            f"{stored_index} (leaf record indices: "
            f"{[leaf.record_index for leaf in leaves]!r})"
        )
    if suffix in AI_COMP_EXTENSIONS:
        names = read_ai_layers(file)
        if not 0 <= stored_index < len(names):
            raise ValueError(
                f"{Path(file).name}: no layer has stored (document) index "
                f"{stored_index}; the file has {len(names)} layers"
            )
        return len(names) - 1 - stored_index
    raise ValueError(
        f"layer_index_for_stored supports layered .psd/.psb/.ai/.pdf "
        f"files, got {suffix!r}"
    )


def _out_of_range(
    file: str | os.PathLike[str], layer_index: int, names: list[str]
) -> ValueError:
    return ValueError(
        f"{Path(file).name}: layer_index {layer_index} out of range; the "
        f"file has {len(names)} selectable layers (top first): {names!r}"
    )


def resolve_psd_layer(file: str | os.PathLike[str], layer_index: int) -> PsdLayer:
    """Return the PSD leaf layer at `layer_index` in `list_layers` order
    (top layer first).

    Raises:
        ValueError: If `layer_index` is out of range.
        UnsupportedPsdLayersError: If the file's layers cannot be read.
    """
    leaves = psd_leaf_layers(file)
    if not 0 <= layer_index < len(leaves):
        raise _out_of_range(file, layer_index, [leaf.name for leaf in reversed(leaves)])
    return leaves[len(leaves) - 1 - layer_index]


def resolve_ai_layer(
    file: str | os.PathLike[str],
    layer_index: int,
    data: bytes | None = None,
) -> tuple[int, str]:
    """Resolve an AI/PDF layer chosen by `list_layers` position.

    Args:
        file: Path to a `.ai` or `.pdf` file.
        layer_index: The layer's index in `list_layers` order (top first).
        data: The file's bytes, if the caller already read them.

    Returns:
        A `(document_index, name)` tuple, where `document_index` is the
        layer's document-order (bottom-first) position as stored in the
        binary.

    Raises:
        ValueError: If `layer_index` is out of range.
        UnsupportedAiLayersError: If the file's layers cannot be read.
    """
    names = read_ai_layers(file, data)
    if not 0 <= layer_index < len(names):
        raise _out_of_range(file, layer_index, list(reversed(names)))
    doc_index = len(names) - 1 - layer_index
    return doc_index, names[doc_index]
