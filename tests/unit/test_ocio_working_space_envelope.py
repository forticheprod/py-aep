"""The OCIO working-space envelope is per-selection-KIND, not per-AE-version.

Every expected string below is the exact `PwCs` `Utf8` value After Effects
itself stored in the matching sample - the same four selection kinds the
output color space uses (see the `color-management-write-rev-eng` notes).

The AE25/AE26 pair is the controlled experiment: the same scene, the same
pick, two AE versions, byte-identical envelopes. `aces_acescg_yo.aep` is AE
25.6 too, yet stores the OTHER shape - so the shape follows the SELECTION,
not the writer's version.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from py_aep.color.envelope import parse_envelope
from py_aep.color.ocio import ocio_color_profile_envelope, resolve_ocio_config

ROOT = Path(__file__).parent.parent.parent
CONFIG = ROOT / "samples/models/output_module/output_color_space_ocio/sergb.ocio"

# Verbatim AE output.
DIRECT_ACESCG = (
    '{"baseColorProfile":{"colorProfileData":"eyJjb2xvclNwYWNlMSI6IkFDRVNjZyB5byJ9",'
    '"colorProfileName":"ACES/ACEScg yo"},"baseProfileType":3}'
)
ROLE_MARI_INT16 = (
    '{"baseColorProfile":{"colorProfileData":'
    '"eyJjb2xvclNwYWNlMSI6InNSR0IgKG1hcmlfaW50MTYpIiwib2Npb0NvbG9yU3BhY2VUeXBlIjoyfQ==",'
    '"colorProfileName":"sRGB (mari_int16)"},"baseProfileType":3}'
)


class TestByteExactAgainstAE:
    def test_direct_colorspace(self) -> None:
        # family/name, and NO ocioColorSpaceType key.
        assert ocio_color_profile_envelope(CONFIG, "ACEScg yo") == DIRECT_ACESCG

    def test_role(self) -> None:
        # The role's TARGET name, with ocioColorSpaceType 2 and no family.
        assert ocio_color_profile_envelope(CONFIG, "mari_int16") == ROLE_MARI_INT16

    def test_direct_and_role_shapes_differ(self) -> None:
        # The bug this pins: the role/alias shape was applied to every kind.
        assert _decoded(DIRECT_ACESCG) == '{"colorSpace1":"ACEScg yo"}'
        assert _decoded(ROLE_MARI_INT16) == (
            '{"colorSpace1":"sRGB (mari_int16)","ocioColorSpaceType":2}'
        )


class TestQualifiedNameRoundTrips:
    def test_family_qualified_name_is_accepted(self) -> None:
        # `Project.working_space` reads back the qualified name, so assigning
        # it straight back must not raise.
        assert ocio_color_profile_envelope(CONFIG, "ACES/ACEScg yo") == DIRECT_ACESCG

    def test_display_view_pair(self) -> None:
        env = ocio_color_profile_envelope(CONFIG, "sRGB yo/Raw")
        assert '"colorProfileName":"sRGB yo/Raw"' in env
        assert '"ocioColorSpaceType":1' in _decoded(env)

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(ValueError, match="not a color space"):
            ocio_color_profile_envelope(CONFIG, "NotAColorSpace")

    def test_bogus_family_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="not a color space"):
            ocio_color_profile_envelope(CONFIG, "Nope/ACEScg yo")


class TestFamilyNamedLikeADisplay:
    """A family can share a display's name; `family/name` must still win.

    ACES 1.2's ONLY display is `ACES`, which is also the family of
    `ACES - ACEScg`. Matching a `display/view` on the display alone claimed
    the qualified `ACES/ACES - ACEScg` the getters return and silently wrote a
    display+view envelope (`ocioColorSpaceType: 1`) instead of a direct pick.
    `sergb.ocio` has no display called `ACES`, so this only shows up here.
    """

    ACES12 = resolve_ocio_config("ACES 1.2")

    @pytest.fixture(autouse=True)
    def _require_aces12(self) -> None:
        if self.ACES12 is None:
            pytest.skip("AE's bundled ACES 1.2 config is not installed")

    def test_family_qualified_name_is_a_direct_pick(self) -> None:
        env = ocio_color_profile_envelope(self.ACES12, "ACES/ACES - ACEScg")
        assert _decoded(env) == '{"colorSpace1":"ACES - ACEScg"}'
        assert '"colorProfileName":"ACES/ACES - ACEScg"' in env

    def test_bare_name_gives_the_same_envelope(self) -> None:
        assert ocio_color_profile_envelope(
            self.ACES12, "ACES - ACEScg"
        ) == ocio_color_profile_envelope(self.ACES12, "ACES/ACES - ACEScg")

    def test_real_display_view_pair_still_resolves(self) -> None:
        # `sRGB` IS a view of the `ACES` display - this must stay type 1.
        env = ocio_color_profile_envelope(self.ACES12, "ACES/sRGB")
        assert '"ocioColorSpaceType":1' in _decoded(env)
        assert '"colorSpace1":"ACES"' in _decoded(env)

    def test_display_prefix_with_a_non_view_raises(self) -> None:
        with pytest.raises(ValueError, match="not a color space"):
            ocio_color_profile_envelope(self.ACES12, "ACES/NotAView")


def _decoded(envelope: str) -> str:
    return parse_envelope(envelope).data.decode("utf-8")
