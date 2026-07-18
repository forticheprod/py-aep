"""Tests for the Photoshop vector-mask path-record decoder."""

from __future__ import annotations

from pathlib import Path

from py_aep.resolvers.psd_layers import read_psd_layers
from py_aep.resolvers.psd_paths import parse_vector_mask

ASSETS = Path(__file__).parent.parent.parent / "samples" / "assets"


def _vector_mask(psd: str, layer: str) -> bytes:
    for node in read_psd_layers(ASSETS / psd):
        if node.name == layer:
            assert node.vector_mask is not None
            return node.vector_mask
    raise AssertionError(f"layer {layer!r} not found")


class TestParseVectorMask:
    def test_rectangle(self) -> None:
        # Corner knots: anchors in canvas pixels, zero tangents.
        shapes = parse_vector_mask(
            _vector_mask("psd_vector_mask.psd", "vector masked"), 64, 64
        )
        assert len(shapes) == 1
        shape = shapes[0]
        assert shape.closed is True
        assert shape.vertices == [
            [20.0, 12.0],
            [52.0, 12.0],
            [52.0, 44.0],
            [20.0, 44.0],
        ]
        assert shape.in_tangents == [[0.0, 0.0]] * 4

    def test_smooth_knots_match_ae_tangents(self) -> None:
        # The record's first point is the AE in-tangent handle (pinned by
        # the psd_vector_mask_curves fixture: identical values).
        shapes = parse_vector_mask(
            _vector_mask("psd_vector_mask_curves.psd", "curved"), 64, 64
        )
        shape = shapes[0]
        assert shape.vertices == [
            [32.0, 8.0],
            [56.0, 32.0],
            [32.0, 56.0],
            [8.0, 32.0],
        ]
        assert shape.in_tangents == [
            [12.0, 0.0],
            [0.0, 12.0],
            [-12.0, 0.0],
            [0.0, -12.0],
        ]
        assert shape.out_tangents == [
            [-12.0, 0.0],
            [0.0, -12.0],
            [12.0, 0.0],
            [0.0, 12.0],
        ]

    def test_multiple_subpaths(self) -> None:
        shapes = parse_vector_mask(
            _vector_mask("psd_vector_mask_multi.psd", "two rects"), 64, 64
        )
        assert len(shapes) == 2
        assert shapes[0].vertices[0] == [6.0, 6.0]
        assert shapes[1].vertices[0] == [38.0, 38.0]

    def test_truncated_block_returns_decoded_prefix(self) -> None:
        block = _vector_mask("psd_vector_mask.psd", "vector masked")
        shapes = parse_vector_mask(block[: 8 + 26 * 4], 64, 64)
        # Fill rule + initial fill + length record + one knot survive.
        assert len(shapes) == 1
        assert len(shapes[0].vertices) == 1
