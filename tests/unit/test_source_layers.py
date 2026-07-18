"""Tests for the source-layer enumeration/resolution resolvers."""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep import list_layers
from py_aep.resolvers.psd_layers import FlattenedPsdError
from py_aep.resolvers.source_layers import (
    psd_leaf_layers,
    resolve_ai_layer,
    resolve_psd_layer,
)

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"


class TestListLayers:
    """list_layers mirrors AE's "Choose Layer" dropdown (top layer first)."""

    def test_psd_order_matches_ae_dropdown(self) -> None:
        # Verified against the AE 2026 dialog for choose_layer.psd: leaf
        # layers only (group `grp` is not listed), top-most first, the
        # nested `inner` shown without a group prefix.
        assert list_layers(ASSETS / "choose_layer.psd") == [
            "twin",
            "inner",
            "twin",
            "solo",
        ]

    def test_ai_order_is_top_first(self) -> None:
        # Document (OCG) order is bottom-first; the dropdown reverses it.
        assert list_layers(ASSETS / "ai.ai") == ["Calque 2", "Calque 1"]

    def test_non_layered_format_raises(self) -> None:
        with pytest.raises(ValueError, match="layered"):
            list_layers(ASSETS / "image_with_alpha.png")

    def test_flattened_psd_raises(self) -> None:
        with pytest.raises(FlattenedPsdError):
            list_layers(ASSETS / "flattened.psd")


class TestResolvePsdLayer:
    def test_resolves_leaf_fields(self) -> None:
        # `solo` is the bottom layer: last in the top-first dropdown.
        leaf = resolve_psd_layer(ASSETS / "choose_layer.psd", 3)
        assert leaf.name == "solo"
        assert leaf.record_index == 0
        assert leaf.layer_id == 2
        assert leaf.bounds == (4, 6, 24, 20)

    def test_nested_leaf_resolves(self) -> None:
        leaf = resolve_psd_layer(ASSETS / "choose_layer.psd", 1)
        # Record index counts the group divider records.
        assert leaf.name == "inner"
        assert leaf.record_index == 3
        assert leaf.layer_id == 6

    def test_duplicate_names_resolve_to_distinct_layers(self) -> None:
        top = resolve_psd_layer(ASSETS / "choose_layer.psd", 0)
        bottom = resolve_psd_layer(ASSETS / "choose_layer.psd", 2)
        assert top.name == bottom.name == "twin"
        assert top.layer_id == 4
        assert bottom.layer_id == 3

    @pytest.mark.parametrize("index", [-1, 4])
    def test_out_of_range_lists_available(self, index: int) -> None:
        with pytest.raises(ValueError, match=r"\['twin', 'inner', 'twin', 'solo'\]"):
            resolve_psd_layer(ASSETS / "choose_layer.psd", index)

    def test_leaves_are_document_order(self) -> None:
        leaves = psd_leaf_layers(ASSETS / "choose_layer.psd")
        assert [leaf.record_index for leaf in leaves] == [0, 1, 3, 5]


class TestPsd16BitLayers:
    """16/32-bit documents store their records in the global Lr16/Lr32 block.

    The classic Layer Info section is empty there; misreading it used to
    surface every 16-bit layered PSD as FlattenedPsdError.
    """

    @pytest.mark.parametrize(
        "name", ["psd_layer_styles.psd", "psd_layer_styles_variant.psd"]
    )
    def test_16bit_leaves_read_from_lr16(self, name: str) -> None:
        leaves = psd_leaf_layers(ASSETS / name)
        assert [(leaf.name, leaf.layer_id, leaf.record_index) for leaf in leaves] == [
            ("Layer 1", 2, 0),
            ("Layer 1 copy", 4, 1),
        ]
        assert all(leaf.bounds == (0, 0, 24, 25) for leaf in leaves)

    def test_32bit_leaves_read_from_lr32(self) -> None:
        # A 32-bit document keeps its records in the global Lr32 block.
        leaves = psd_leaf_layers(ASSETS / "psd_noise_gradient_32bpc.psd")
        assert {(leaf.name, leaf.layer_id) for leaf in leaves} == {
            ("Layer 1", 2),
            ("Layer 1 copy", 5),
        }
        assert {leaf.record_index for leaf in leaves} == {0, 1}

    def test_16bit_probe_layer_count(self) -> None:
        from py_aep.resolvers.media_probe import probe_media

        info = probe_media(ASSETS / "psd_layer_styles.psd")
        assert info.layer_count == 2
        assert info.has_alpha is True
        assert info.bit_depth == 16


class TestResolveAiLayer:
    def test_resolves_document_index_and_name(self) -> None:
        # Dropdown order is top-first; the document (OCG) order it maps to
        # is bottom-first.
        assert resolve_ai_layer(ASSETS / "ai.ai", 0) == (1, "Calque 2")
        assert resolve_ai_layer(ASSETS / "ai.ai", 1) == (0, "Calque 1")

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="layer_index 2 out of range"):
            resolve_ai_layer(ASSETS / "ai.ai", 2)
