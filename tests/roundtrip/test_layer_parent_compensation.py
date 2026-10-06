"""`Layer.parent` must compensate the transform so nothing visibly moves.

That is the setter's whole contract - `set_parent_with_jump` exists for the
other case - and it had three holes: an oriented child, a child whose Position
is dimension-separated, and cameras / lights. Expectations below are AE 2026
measurements except where noted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import get_comp, parse_project_fresh

from py_aep import parse as parse_aep
from py_aep.resolvers.transform import build_world_matrix

LAYER_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "layer"
PROPERTY_DIR = Path(__file__).parent.parent.parent / "samples" / "models" / "property"


def _world_delta(before: object, after: object) -> float:
    return max(
        abs(before[row][col] - after[row][col])  # type: ignore[index]
        for row in range(4)
        for col in range(4)
    )


class TestParentOrientation:
    """A 3D layer is compensated through Orientation, a 2D one through
    Rotate Z.

    AE's rule for a 3D layer is `O_new = parent_rotation^-1 . O_old`, with
    Rotate X/Y/Z untouched - measured over ten AE 2026 cases. Under a
    pure-translation parent that delta is the identity, so Orientation comes
    out unchanged and only Position moves.
    """

    def test_oriented_child_does_not_move(self) -> None:
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [0.0, 0.0, 0.0]
        parent = comp.add_null()
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9

    def test_orientation_and_rotations_are_untouched(self) -> None:
        """AE rewrote only Position for this case: `[-150, 120, 0]`."""
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [0.0, 0.0, 0.0]
        parent = comp.add_null()
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]

        child.parent = parent

        assert child.transform["ADBE Position"].value == pytest.approx(
            [-150.0, 120.0, 0.0]
        )
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [0.0, 279.0, 0.0]
        )
        assert child.transform["ADBE Rotate Y"].value == pytest.approx(0.0)
        assert child.transform["ADBE Rotate Z"].value == pytest.approx(0.0)

    def test_zero_orientation_child_still_compensates(self) -> None:
        """The regression that the orientation fix must not break."""
        project = parse_project_fresh(PROPERTY_DIR / "property_2D_position.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [0.0, 0.0, 0.0]
        )
        parent = comp.add_null()
        parent.transform["ADBE Rotate Z"].value = 30.0
        parent.transform["ADBE Position"].value = [500.0, 400.0, 0.0]
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9


class TestParentSeparatedPosition:
    """A separated Position is driven by its followers, so that is where the
    compensation has to land - the leader's own value is dead."""

    def test_followers_receive_the_compensation(self, tmp_path: Path) -> None:
        """AE: a separated child at (150, 160) under a parent at (300, 40)
        becomes X = -150, Y = 120."""
        project = parse_project_fresh(PROPERTY_DIR / "transform_separated.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.transform["ADBE Anchor Point"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position_0"].value = 150.0
        child.transform["ADBE Position_1"].value = 160.0
        parent = comp.add_null()
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]

        child.parent = parent

        assert child.transform["ADBE Position_0"].value == pytest.approx(-150.0)
        assert child.transform["ADBE Position_1"].value == pytest.approx(120.0)
        assert child.transform["ADBE Position"].dimensions_separated is True

        out = tmp_path / "modified.aep"
        project.save(out)
        # add_null() inserts at index 0, so select the child by name.
        reloaded = next(
            layer
            for layer in parse_aep(out).project.compositions[0].layers
            if layer.name == child.name
        )
        assert reloaded.transform["ADBE Position_0"].value == pytest.approx(-150.0)
        assert reloaded.transform["ADBE Position_1"].value == pytest.approx(120.0)


class TestParentCameraIsAlwaysThreeD:
    """Cameras and lights have no `three_d_layer` attribute because they are
    always 3D; reading it with a False default skipped their X / Y rotation
    compensation entirely.

    No AE ground truth here - `layers.addCamera` fails in a headless session -
    so this asserts world-matrix invariance rather than AE's exact tuple.
    """

    def test_camera_compensates_under_a_rotated_parent(self) -> None:
        project = parse_project_fresh(LAYER_DIR / "camera_rigs.aep")
        comp = get_comp(project, "CAM_ONE")
        camera = comp.layers[0]
        target = comp.layers[1]
        assert not hasattr(camera, "three_d_layer")
        target.transform["ADBE Rotate X"].value = 20.0
        target.transform["ADBE Rotate Z"].value = 30.0
        # A camera's world is its rig (position + rotations): its point of
        # interest sits in the Anchor Point slot and AE 2026 remaps it into
        # the new parent's space too, so it is no anchor to subtract.
        before = build_world_matrix(camera, as_parent=True)

        camera.parent = target

        assert _world_delta(before, build_world_matrix(camera, as_parent=True)) < 1e-9

    def test_camera_compensates_through_orientation(self) -> None:
        """A camera is 3D, so it takes the 3D path: the compensation lands in
        Orientation and Rotate X/Y/Z are left exactly as they were."""
        project = parse_project_fresh(LAYER_DIR / "camera_rigs.aep")
        comp = get_comp(project, "CAM_ONE")
        camera = comp.layers[0]
        target = comp.layers[1]
        rotations_before = [
            camera.transform[name].value
            for name in ("ADBE Rotate X", "ADBE Rotate Y", "ADBE Rotate Z")
        ]
        orientation_before = list(camera.transform["ADBE Orientation"].value)
        target.transform["ADBE Rotate X"].value = 20.0

        camera.parent = target

        assert [
            camera.transform[name].value
            for name in ("ADBE Rotate X", "ADBE Rotate Y", "ADBE Rotate Z")
        ] == rotations_before
        assert camera.transform["ADBE Orientation"].value != orientation_before


class TestParentCompensationConvention:
    """AE folds a 3D reparent into Orientation, a 2D one into Rotate Z.

    Every tuple below is what AE 2026 stored for the same setup: child at
    (150, 160, 0) on a 100x100 solid, parent null at (300, 40, 0).
    """

    @staticmethod
    def _setup(orientation: list[float], rotations: list[float]):  # type: ignore[no-untyped-def]
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Orientation"].value = list(orientation)
        for name, value in zip(
            ("ADBE Rotate X", "ADBE Rotate Y", "ADBE Rotate Z"), rotations
        ):
            child.transform[name].value = float(value)
        parent = comp.add_null()
        parent.three_d_layer = True
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Rotate X"].value = 20.0
        parent.transform["ADBE Rotate Y"].value = -35.0
        parent.transform["ADBE Rotate Z"].value = 30.0
        return child, parent

    def test_three_d_child_matches_the_ae_tuple(self) -> None:
        child, parent = self._setup([0.0, 279.0, 0.0], [0.0, 0.0, 0.0])

        child.parent = parent

        assert child.transform["ADBE Position"].value == pytest.approx(
            [-70.416, 170.863, 52.416], abs=0.001
        )
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [329.248, 323.066, 337.96], abs=0.001
        )
        for name in ("ADBE Rotate X", "ADBE Rotate Y", "ADBE Rotate Z"):
            assert child.transform[name].value == pytest.approx(0.0)

    def test_the_childs_own_rotations_are_preserved(self) -> None:
        """They cancel out of `O_new = parent^-1 . O_old`, so AE gets the
        same orientation whether or not the child carries rotations."""
        child, parent = self._setup([17.0, 279.0, 43.0], [11.0, -23.0, 47.0])

        child.parent = parent

        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [332.157, 321.758, 5.941], abs=0.001
        )
        assert child.transform["ADBE Rotate X"].value == pytest.approx(11.0)
        assert child.transform["ADBE Rotate Y"].value == pytest.approx(-23.0)
        assert child.transform["ADBE Rotate Z"].value == pytest.approx(47.0)

    def test_a_keyframed_rotation_no_longer_jumps(self) -> None:
        """Compensating through the rotations collided with the rule that
        keyframed properties are left alone: the layer kept its animated
        Rotate Z but lost the compensation, and jumped 362 px. AE never
        touches the rotations, so the animation and the compensation coexist.
        """
        child, parent = self._setup([0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        rotation = child.transform["ADBE Rotate Z"]
        rotation.add_key(0.0)
        rotation.keyframes[-1].value = 15.0
        rotation.add_key(2.0)
        rotation.keyframes[-1].value = 75.0
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9
        assert [(k.time, k.value) for k in rotation.keyframes] == [
            (0.0, 15.0),
            (2.0, 75.0),
        ]
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [358.013, 39.627, 337.08], abs=0.001
        )

    def test_keyframed_orientation_is_remapped_per_key(self) -> None:
        """AE rewrites every orientation keyframe, as it does for position."""
        child, parent = self._setup([0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        orientation = child.transform["ADBE Orientation"]
        orientation.add_key(0.0)
        orientation.keyframes[-1].value = [0.0, 30.0, 0.0]
        orientation.add_key(2.0)
        orientation.keyframes[-1].value = [0.0, 120.0, 0.0]

        child.parent = parent

        assert orientation.keyframes[0].value == pytest.approx(
            [25.56, 65.1, 314.569], abs=0.001
        )
        assert orientation.keyframes[1].value == pytest.approx(
            [157.34, 17.186, 198.299], abs=0.001
        )

    def test_two_d_child_uses_rotate_z(self) -> None:
        """A 2D layer has no Orientation to use, so AE puts it in Rotate Z."""
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = False
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        parent = comp.add_null()
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Rotate Z"].value = 30.0

        child.parent = parent

        assert child.transform["ADBE Rotate Z"].value == pytest.approx(-30.0)
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [0.0, 0.0, 0.0]
        )


class TestParentNonUniformParentScaleJumps:
    """A non-uniformly scaled parent shears the child's required local
    matrix, and `T . O . R . S . T(-anchor)` cannot represent shear.

    AE jumps here too - 68 to 95 px on the same setups - so mirroring the
    jump is the correct behaviour, not a defect. This test pins that down so
    nobody "fixes" it into a divergence from AE.
    """

    def test_jump_is_expected_and_matches_ae_in_kind(self) -> None:
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        parent = comp.add_null()
        parent.three_d_layer = True
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Rotate Z"].value = 30.0
        parent.transform["ADBE Scale"].value = [200.0, 50.0, 100.0]
        before = build_world_matrix(child)

        child.parent = parent

        # AE's own result for this setup is off by 68 px; ours is the same
        # order of magnitude. Asserting only that it does not silently claim
        # to be exact.
        assert _world_delta(before, build_world_matrix(child)) > 1.0


class TestParentScaledParentEdgeCases:
    """A non-uniformly scaled parent does not automatically mean a jump.

    The child's required local 3x3 is `S_parent^-1 . Q . D`, which only
    shears when `Q` - the combined rotation - is not axis-aligned. AE
    compensates the representable cases exactly, and so must we. All values
    are AE 2026 measurements.
    """

    @staticmethod
    def _pair(child_rotation: float = 0.0):  # type: ignore[no-untyped-def]
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        child.transform["ADBE Scale"].value = [100.0, 100.0, 100.0]
        child.transform["ADBE Rotate Z"].value = child_rotation
        parent = comp.add_null()
        parent.three_d_layer = True
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        return child, parent

    def test_non_uniform_scale_without_rotation_is_exact(self) -> None:
        """No rotation means no shear: AE inverts the scale per axis."""
        child, parent = self._pair()
        parent.transform["ADBE Scale"].value = [200.0, 50.0, 100.0]
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9
        assert child.transform["ADBE Scale"].value == pytest.approx(
            [50.0, 200.0, 100.0]
        )

    def test_non_uniform_scale_with_axis_aligned_rotation_is_exact(self) -> None:
        """A 90-degree parent only permutes the axes, so it stays exact."""
        child, parent = self._pair()
        parent.transform["ADBE Scale"].value = [200.0, 50.0, 100.0]
        parent.transform["ADBE Rotate Z"].value = 90.0
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9
        assert child.transform["ADBE Scale"].value == pytest.approx(
            [200.0, 50.0, 100.0]
        )
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [0.0, 0.0, 270.0]
        )

    def test_negative_uniform_scale_is_exact(self) -> None:
        child, parent = self._pair()
        parent.transform["ADBE Scale"].value = [-100.0, -100.0, -100.0]
        parent.transform["ADBE Rotate Z"].value = 30.0
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9
        assert child.transform["ADBE Scale"].value == pytest.approx(
            [-100.0, -100.0, -100.0]
        )
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [0.0, 0.0, 330.0]
        )

    def test_mirrored_parent_flips_all_three_scales(self) -> None:
        """AE keeps the rotation proper and spreads a mirror across all three
        scale axes: a parent at [-100, 100, 100] leaves the child at
        [-100, -100, -100] with Orientation [180, 0, 0], not at a mirrored
        rotation."""
        child, parent = self._pair()
        parent.transform["ADBE Scale"].value = [-100.0, 100.0, 100.0]
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9
        assert child.transform["ADBE Scale"].value == pytest.approx(
            [-100.0, -100.0, -100.0]
        )
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [180.0, 0.0, 0.0]
        )

    def test_genuine_shear_still_jumps(self) -> None:
        """A rotated child under a non-uniformly scaled parent needs a
        sheared local matrix, which `T . O . R . S . T(-anchor)` cannot hold.
        AE is off by 34.8 px here and we are off by 16.8 - neither is exact,
        so this pins the jump rather than pretending it can be removed.
        """
        child, parent = self._pair(child_rotation=30.0)
        parent.transform["ADBE Scale"].value = [200.0, 50.0, 100.0]
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) > 1.0


class TestParentKeyframedChild:
    """AE compensates once, using the parent at the current time, and rewrites
    the child's animated properties rather than skipping them."""

    def test_two_d_keyframed_rotation_is_offset_per_key(self) -> None:
        """Keys of 15 and 75 under a 30-degree parent became -15 and 45.
        Skipping them - which is what `write_compensation` does for a
        keyframed property - left the layer 35 px out of place."""
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = False
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        rotation = child.transform["ADBE Rotate Z"]
        rotation.add_key(0.0)
        rotation.keyframes[-1].value = 15.0
        rotation.add_key(2.0)
        rotation.keyframes[-1].value = 75.0
        parent = comp.add_null()
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Rotate Z"].value = 30.0
        before = build_world_matrix(child)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child)) < 1e-9
        assert [(k.time, k.value) for k in rotation.keyframes] == [
            (0.0, -15.0),
            (2.0, 45.0),
        ]

    def test_keyframed_scale_is_left_alone(self) -> None:
        """The parent carries no scale, so the child's animated Scale needs
        no compensation and AE leaves both keys untouched."""
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        scale = child.transform["ADBE Scale"]
        scale.add_key(0.0)
        scale.keyframes[-1].value = [100.0, 100.0, 100.0]
        scale.add_key(2.0)
        scale.keyframes[-1].value = [250.0, 60.0, 100.0]
        parent = comp.add_null()
        parent.three_d_layer = True
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Rotate Z"].value = 30.0
        before = {t: build_world_matrix(child, t) for t in (0.0, 2.0)}

        child.parent = parent

        for time in (0.0, 2.0):
            assert _world_delta(before[time], build_world_matrix(child, time)) < 1e-9
        assert [k.value for k in scale.keyframes] == [
            [100.0, 100.0, 100.0],
            [250.0, 60.0, 100.0],
        ]

    def test_animated_parent_is_compensated_at_time_zero_only(self) -> None:
        """The layer holds still at the moment of parenting; afterwards it
        follows the parent, which is the point of parenting rather than a
        jump. AE behaves the same - it writes one static compensation and
        adds no keyframes."""
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        parent = comp.add_null()
        parent.three_d_layer = True
        position = parent.transform["ADBE Position"]
        position.add_key(0.0)
        position.keyframes[-1].value = [300.0, 40.0, 0.0]
        position.add_key(2.0)
        position.keyframes[-1].value = [700.0, 300.0, 0.0]
        before = build_world_matrix(child, 0.0)

        child.parent = parent

        assert _world_delta(before, build_world_matrix(child, 0.0)) < 1e-9
        assert child.transform["ADBE Position"].value == pytest.approx(
            [-150.0, 120.0, 0.0]
        )
        assert child.transform["ADBE Position"].keyframes == []


class TestParentScaledParentKeyframes:
    """A scaled parent must move the child's animated Scale.

    The earlier test had an unscaled parent, so no scale compensation was
    needed and "AE leaves the keys alone" proved nothing. With a scaled
    parent AE divides every key per axis; skipping them left the layer 25 px
    out at one time and 62 px at another.
    """

    @staticmethod
    def _setup(parent_scale: list[float]):  # type: ignore[no-untyped-def]
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        scale = child.transform["ADBE Scale"]
        scale.add_key(0.0)
        scale.keyframes[-1].value = [100.0, 100.0, 100.0]
        scale.add_key(2.0)
        scale.keyframes[-1].value = [250.0, 60.0, 100.0]
        parent = comp.add_null()
        parent.three_d_layer = True
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Scale"].value = list(parent_scale)
        return child, parent, scale

    def test_uniform_scale_doubles_every_key(self) -> None:
        child, parent, scale = self._setup([50.0, 50.0, 50.0])
        before = {t: build_world_matrix(child, t) for t in (0.0, 2.0)}

        child.parent = parent

        assert [k.value for k in scale.keyframes] == [
            [200.0, 200.0, 200.0],
            [500.0, 120.0, 200.0],
        ]
        for time in (0.0, 2.0):
            assert _world_delta(before[time], build_world_matrix(child, time)) < 1e-9

    def test_non_uniform_scale_divides_per_axis(self) -> None:
        _, parent, scale = self._setup([200.0, 50.0, 100.0])
        child = scale._containing_layer

        child.parent = parent

        assert [k.value for k in scale.keyframes] == [
            [50.0, 200.0, 100.0],
            [125.0, 120.0, 100.0],
        ]

    def test_keyframed_position_remap_includes_the_parent_scale(self) -> None:
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        position = child.transform["ADBE Position"]
        position.add_key(0.0)
        position.keyframes[-1].value = [150.0, 160.0, 0.0]
        position.add_key(2.0)
        position.keyframes[-1].value = [400.0, 500.0, 0.0]
        parent = comp.add_null()
        parent.three_d_layer = True
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Scale"].value = [50.0, 50.0, 50.0]

        child.parent = parent

        assert [k.value for k in position.keyframes] == [
            [-300.0, 240.0, 0.0],
            [200.0, 920.0, 0.0],
        ]


class TestParentAcrossTheTwoDThreeDBoundary:
    """A 2D layer cannot store an out-of-plane rotation, and AE does not try:
    it compensates as though every ancestor were 2D."""

    def test_two_d_child_ignores_a_three_d_parents_xy_rotation(self) -> None:
        """AE gives exactly the answer it would for a parent rotated 0/0/30,
        discarding the 20 and -35. Using the full 3D matrix put the layer
        8 px out and wrote a Z position onto a 2D layer."""
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = False
        child.transform["ADBE Orientation"].value = [0.0, 0.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        parent = comp.add_null()
        parent.three_d_layer = True
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Rotate X"].value = 20.0
        parent.transform["ADBE Rotate Y"].value = -35.0
        parent.transform["ADBE Rotate Z"].value = 30.0

        child.parent = parent

        assert child.transform["ADBE Position"].value == pytest.approx(
            [-69.9038, 178.923, 0.0], abs=0.001
        )
        assert child.transform["ADBE Rotate Z"].value == pytest.approx(-30.0)

    def test_three_d_child_under_a_two_d_parent(self) -> None:
        project = parse_project_fresh(LAYER_DIR / "orientation_0_279_0.aep")
        comp = project.compositions[0]
        child = comp.layers[0]
        child.three_d_layer = True
        child.transform["ADBE Orientation"].value = [0.0, 279.0, 0.0]
        child.transform["ADBE Position"].value = [150.0, 160.0, 0.0]
        child.transform["ADBE Anchor Point"].value = [50.0, 50.0, 0.0]
        parent = comp.add_null()
        parent.transform["ADBE Position"].value = [300.0, 40.0, 0.0]
        parent.transform["ADBE Rotate Z"].value = 30.0

        child.parent = parent

        assert child.transform["ADBE Position"].value == pytest.approx(
            [-69.9038, 178.923, 0.0], abs=0.001
        )
        assert child.transform["ADBE Orientation"].value == pytest.approx(
            [287.5766, 301.2001, 285.1604], abs=0.001
        )


TRANSFORM_FIXTURES = (
    Path(__file__).parent.parent.parent / "samples" / "unused" / "transforms"
)


@pytest.mark.skipif(
    not TRANSFORM_FIXTURES.is_dir(),
    reason="samples/unused is not committed",
)
class TestUnparentAgainstAeFixtures:
    """Replay AE 25.6's own un-parenting pairs.

    These fixtures were authored by a different AE build (25.6x101) than the
    2026 probes the compensation was measured against, so they double as a
    version check - and they cover removing a parent, which the probes did
    not. Each `_before` has ChildSolid parented; each `_after` has it free
    with its transform baked to hold it in place.
    """

    FIELDS = (
        "ADBE Anchor Point",
        "ADBE Position",
        "ADBE Scale",
        "ADBE Orientation",
        "ADBE Rotate X",
        "ADBE Rotate Y",
        "ADBE Rotate Z",
    )

    @staticmethod
    def _child(project):  # type: ignore[no-untyped-def]
        for comp in project.compositions:
            for layer in comp.layers:
                if layer.name == "ChildSolid":
                    return layer
        raise AssertionError("no ChildSolid in the fixture")

    def _snapshot(self, layer):  # type: ignore[no-untyped-def]
        return {
            name: (
                [round(v, 3) for v in layer.transform[name].value]
                if isinstance(layer.transform[name].value, list)
                else round(layer.transform[name].value, 3)
            )
            for name in self.FIELDS
        }

    @pytest.mark.parametrize(
        "stem",
        [
            "parent_test_3d",
            "parent_test_anchor",
            "parent_test_child_anchor",
            "parent_test_combined",
            "parent_test_position",
            "parent_test_rotation",
            "parent_test_scale",
        ],
    )
    def test_unparent_matches_after_effects(self, stem: str) -> None:
        expected = self._snapshot(
            self._child(parse_aep(TRANSFORM_FIXTURES / f"{stem}_after.aep").project)
        )
        project = parse_project_fresh(TRANSFORM_FIXTURES / f"{stem}_before.aep")
        child = self._child(project)

        child.parent = None

        assert self._snapshot(child) == expected
