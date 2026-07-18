from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .descriptors import ChunkField

if TYPE_CHECKING:
    from pathlib import Path

    from ..binary.item_chunks import HeadChunk
    from .preferences import Preferences
    from .project import Project
    from .viewer.viewer import Viewer

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)x(\d+)$")


def _validate_version(value: str, obj: HeadChunk) -> None:
    """Validate that the version string matches the expected format."""
    if not _VERSION_RE.match(value):
        raise ValueError(
            f"version must match '{{major}}.{{minor}}x{{build}}' "
            f"(e.g. '25.6x101'), got {value!r}"
        )


class Application:
    """
    The `Application` object represents the After Effects application. Attributes
    provide access to the project and application-level settings parsed from
    the binary file.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        print(app.version)
        ```

    See: https://ae-scripting.docsforadobe.dev/general/application/
    """

    build_number = ChunkField[str](
        "_head",
        "ae_build_number",
        reverse=int,
    )
    """The build number of After Effects that last saved the project.
    Read / Write.

    Warning:
        This attribute is read-only in ExtendScript. Modifying it could
        cause issues when opening the file in After Effects.
    """

    version = ChunkField[str](
        "_head",
        "version",
        validate=_validate_version,
        post_set=lambda obj: obj._head.sync_file_format_version(),
    )
    """The version of After Effects that last saved the project, formatted as
    "{major}.{minor}x{build}" (e.g., "25.6x101"). Read / Write.

    Setting it also updates the file-format compatibility marker (which
    determines the oldest AE that can open the file) to match the new major
    version, so the file claims to be openable by that AE.

    Warning:
        Setting the version does **not** migrate the project structure: the
        version-gated chunks and features are left unchanged, so relabeling
        to an older version may produce a file that the older AE opens but
        whose newer content it cannot represent. To create a project
        faithfully targeting a specific AE version use [py_aep.new][]; to
        convert an existing project, open and re-save it in the target AE.

        This attribute is read-only in ExtendScript. Modifying it could
        cause issues when opening the file in After Effects.
    """

    is_beta = ChunkField.bool(
        "_head",
        "ae_version_beta_flag",
    )
    """Indicates whether the After Effects version is a beta version. Read / Write.

    Warning:
        This attribute is read-only in ExtendScript. Modifying it could
        cause issues when opening the file in After Effects.
    """

    app_name: str = "After Effects"
    """The name of the application. Always "After Effects". Read-only."""

    def __init__(
        self,
        *,
        _head: HeadChunk,
        project: Project,
        active_viewer: Viewer | None = None,
    ) -> None:
        self._head = _head
        self._project = project
        self._active_viewer = active_viewer

    @classmethod
    def _new(cls, version: str, ae_preferences_dir: Path | None = None) -> Application:
        """Build a new, empty [Application][] (mirrors File > New Project).

        See `py_aep.new`.
        """
        from .project import Project

        project = Project._new(version, ae_preferences_dir=ae_preferences_dir)
        return cls(_head=project._head, project=project, active_viewer=None)

    def __repr__(self) -> str:
        return f"Application(version={self.version!r}, build_number={self.build_number!r}, app_name={self.app_name!r})"

    @property
    def project(self) -> Project:
        """The project that is currently loaded. Read-only."""
        return self._project

    @property
    def active_viewer(self) -> Viewer | None:
        """The Viewer object for the currently focused or active-focused viewer
        (Composition, Layer, or Footage) panel. Returns `None` if no viewers
        are open. Read-only."""
        return self._active_viewer

    @property
    def preferences(self) -> Preferences:
        """The [Preferences][] object, providing access to the After Effects
        preference files (requires `ae_preferences_dir` to read values from
        disk; overrides work without it). Read-only."""
        return self._project._preferences

    @property
    def build_name(self) -> str:
        """A string indicating the version and build of After Effects, formatted
        as "{major}.{minor}x{build}" (e.g., "25.6x101"). Read / Write.

        Alias for [version][py_aep.models.application.Application.version].

        Warning:
            This attribute is read-only in ExtendScript. Modifying it could
            cause issues when opening the file in After Effects.
        """
        return self.version

    @build_name.setter
    def build_name(self, value: str) -> None:
        self.version = value
