"""The default camera zoom, against the distance After Effects stores.

After Effects places the three Custom View layers of a new composition from
its default camera distance Z, at `(W/2 - Z, H/2 - Z, -Z)`,
`(W/2, H/2 - Z, -Z)` and `(W/2 + Z, H/2 - Z, -Z)`. It is also the Zoom
ExtendScript reports for a camera whose Zoom the file leaves out.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import parse_project

from py_aep.binary.utils import filter_by_list_type, recursive_find
from py_aep.resolvers.transform import default_camera_zoom

SAMPLES_DIR = Path(__file__).parent.parent.parent / "samples"


def custom_view_positions(item_chunks: list) -> list[list[float]]:
    """The stored Position of each Custom View layer of a composition."""
    positions = []
    for view in filter_by_list_type(chunks=item_chunks, list_type="CLay"):
        for group in recursive_find(view.chunks, list_type="tdgp"):
            for index, chunk in enumerate(group.chunks):
                if chunk.chunk_type == "tdmn" and chunk.value == "ADBE Position":
                    stream = group.chunks[index + 1]
                    cdat = recursive_find(stream.chunks, chunk_type="cdat")[0]
                    positions.append(cdat.values[:3])
    return positions


class TestDefaultCameraZoom:
    @pytest.mark.parametrize(
        "sample",
        [
            "versions/ae2018/complete.aep",
            "versions/ae2026/complete.aep",
            "models/layer/camera_default_position.aep",
        ],
    )
    def test_places_the_custom_views(self, sample: str) -> None:
        project = parse_project(SAMPLES_DIR / sample)
        assert project.compositions
        for comp in project.compositions:
            zoom = default_camera_zoom(comp.width, comp.pixel_aspect)
            x = comp.width / 2.0
            y = comp.height / 2.0 - zoom
            assert custom_view_positions(comp._item_list.chunks) == [
                [x - zoom, y, -zoom],
                [x, y, -zoom],
                [x + zoom, y, -zoom],
            ], comp.name

    @pytest.mark.parametrize(
        "width, pixel_aspect, zoom",
        [
            # Stored by AE 2018 and AE 2026 in versions/*/complete.aep.
            (1920, 1.0, 2666.6666666),
            (320, 1.0, 444.44444443),
            (720, 1.0670000314712524, 1067.00003144),
            # Stored by AE 2026 in models/layer/camera_default_position.aep.
            (1440, 1.0, 1999.99999995),
            # The untouched camera of models/view/draft3d_false.aep, as
            # ExtendScript reports its Position Z.
            (1920, 10.0 / 11.0, 2424.24242418),
        ],
    )
    def test_known_values(self, width: int, pixel_aspect: float, zoom: float) -> None:
        assert default_camera_zoom(width, pixel_aspect) == zoom
