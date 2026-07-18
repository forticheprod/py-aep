"""Import options for importing files into an After Effects project."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ..data.file_formats import (
    COMP_CONVERSION_EXTENSIONS,
    get_file_format,
    get_import_as_types,
)
from ..enums import ImportAsType
from .validators import (
    validate_bool,
    validate_enum,
    validate_one_of,
    validate_path,
    validate_positive_int,
    validate_u4,
)

# Pattern to match trailing digits in a filename stem (e.g. "frame001").
_NUMBERED_RE = re.compile(r"(\d+)$")


class _CurrentValue:
    """Type of the `CURRENT_VALUE` sentinel."""

    def __repr__(self) -> str:
        return "CURRENT_VALUE"


CURRENT_VALUE = _CurrentValue()
"""Sentinel for `FootageItem.replace`: keep the current source's choice for the
argument it is passed to.

For `layer_index`, binds the new file at the layer whose stored binary index
(the `sspc` layer index: PSD record index / AI document index) matches the
current source's. For `layer_dimensions`, preserves the current single-layer
binding's Document/Layer Size choice.

Not valid for `ImportOptions.layer_index` - an import has no current binding."""


class ImportOptions:
    """Options for importing a file into an After Effects project.

    This is a parameter container used by `Project.import_file()`. It
    validates the import settings before the actual import operation.

    Unlike most py_aep classes, `ImportOptions` has no chunk backing -
    import settings are not stored in the `.aep` binary format.

    Example:
        ```python
        from pathlib import Path
        from py_aep import ImportOptions, ImportAsType

        opts = ImportOptions(Path("footage/shot_001.png"))
        opts.sequence = True
        opts.import_as = ImportAsType.FOOTAGE
        ```

    See: https://ae-scripting.docsforadobe.dev/other/importoptions/
    """

    def __init__(self, file: str | os.PathLike[str]) -> None:
        validate_path(file)
        self._file = Path(file)
        self._import_as = ImportAsType.FOOTAGE
        self._sequence = False
        self._force_alphabetical = False
        self._layer_index: int | None = None
        self._layer_dimensions: str | None = None
        self._layer_styles: str | None = None
        self._range_start = 0
        self._range_end = 0

    @property
    def layer_index(self) -> int | None:
        """The single layer to import from a layered file (`.psd`/`.psb`/
        `.ai`/`.pdf`), as its 0-based position in the list returned by
        `list_layers` (top layer first - the order of the "Choose Layer"
        dropdown of AE's import dialog). `None` (the default) imports the
        file like AE's "Merged Layers" / whole-document option. Only valid
        with `ImportAsType.FOOTAGE`. Read / Write.

        py_aep extension: ExtendScript exposes no layer-selection API. An
        index (not a name) selects the layer because layered files may
        contain several layers with the same name; AE's own dialog
        disambiguates duplicates by dropdown position.

        Raises:
            ValueError: On import, if the index is out of range for the
                file's selectable layers (see `list_layers`).
        """
        return self._layer_index

    @layer_index.setter
    def layer_index(self, value: int | None) -> None:
        if isinstance(value, _CurrentValue):
            raise ValueError(
                "CURRENT_VALUE is only valid for FootageItem.replace; an "
                "import has no current binding to keep"
            )
        if value is not None:
            validate_positive_int(value)
        self._layer_index = value

    @property
    def layer_dimensions(self) -> str | None:
        """Footage dimensions for a `layer_index` import: `"document"` (the
        full canvas) or `"layer"` (the layer's content box), matching the
        "Footage Dimensions" option of AE's import dialog. `None` (the
        default) follows the machine's sticky "Footage Dimensions" preference
        for a `.psd`/`.psb` import when the project was parsed with an
        `ae_preferences_dir`, and imports at document size otherwise (always,
        for `.ai`/`.pdf`). Read / Write.

        py_aep extension: ExtendScript exposes no layer-selection API.

        Note:
            `"layer"` is only supported for `.psd`/`.psb`. AE's own dialog
            defaults to Layer Size for `.ai`/`.pdf`, but computing an AI
            layer's artwork bounds requires rendering the PDF content, so
            py_aep raises `NotImplementedError` there.
        """
        return self._layer_dimensions

    @layer_dimensions.setter
    def layer_dimensions(self, value: str | None) -> None:
        if value is not None:
            validate_one_of(("document", "layer"))(value)
        self._layer_dimensions = value

    @property
    def layer_styles(self) -> str | None:
        """How a Photoshop (`.psd`/`.psb`) import treats the source layer
        styles, matching the "Layer Options" of AE's import dialog:
        `"editable"` (Editable Layer Styles), `"merge"` (Merge Layer Styles
        into Footage) or `"ignore"` (Ignore Layer Styles). `None` (the
        default) follows the machine's sticky "Layer Options" preference when
        the project was parsed with an `ae_preferences_dir`, falling back to
        AE's dialog default for the context: `"editable"` for a COMP /
        COMP_CROPPED_LAYERS import, `"merge"` for a FOOTAGE import of a single
        layer. Read / Write.

        py_aep extension: ExtendScript exposes no layer-styles API. AE's own
        `importFile` silently follows the sticky preference; py_aep mirrors
        that when a preferences directory is available. Pass an explicit value
        for behavior that does not depend on the machine.

        Valid combinations (checked at import time): a FOOTAGE import
        accepts `"merge"`/`"ignore"` and requires
        [layer_index][ImportOptions.layer_index] (AE's "Merged Layers"
        whole-document import - `layer_index=None` - always flattens the
        styles into the composite and offers no choice); a COMP import
        accepts `"editable"`/`"merge"`. Note the naming collision in AE's
        dialog: "Merged Layers" (flatten the whole document, expressed as
        `layer_index=None`) is unrelated to `"merge"` (bake the styles into
        one layer's raster).

        Raises:
            ValueError: On import, if the value is not offered for the
                import context (see above), or if the file is not
                `.psd`/`.psb`.
        """
        return self._layer_styles

    @layer_styles.setter
    def layer_styles(self, value: str | None) -> None:
        if isinstance(value, _CurrentValue):
            raise ValueError(
                "CURRENT_VALUE is only valid for FootageItem.replace; an "
                "import has no current binding to keep"
            )
        if value is not None:
            validate_one_of(("editable", "merge", "ignore"))(value)
        self._layer_styles = value

    @property
    def file(self) -> Path:
        """The file to be imported. If a file is set in the constructor, you can access
        it through this attribute. Read / Write."""
        return self._file

    @file.setter
    def file(self, value: str | os.PathLike[str]) -> None:
        validate_path(value)
        self._file = Path(value)

    @property
    def import_as(self) -> ImportAsType:
        """How to import the file. Read / Write."""
        return self._import_as

    @import_as.setter
    def import_as(self, value: ImportAsType) -> None:
        validate_enum(ImportAsType)(value)
        self._import_as = ImportAsType(value)

    @property
    def sequence(self) -> bool:
        """When `True`, import the file as part of a numbered image
        sequence. Read / Write."""
        return self._sequence

    @sequence.setter
    def sequence(self, value: bool) -> None:
        validate_bool(value)
        self._sequence = value

    @property
    def force_alphabetical(self) -> bool:
        """When `True` and `sequence` is also `True`, use alphabetical
        order for sequence frame numbering. Read / Write.

        Setting `True` resets [range_start][ImportOptions.range_start] and
        [range_end][ImportOptions.range_end] to 0 (matching After Effects:
        an alphabetical sequence cannot carry a frame range)."""
        return self._force_alphabetical

    @force_alphabetical.setter
    def force_alphabetical(self, value: bool) -> None:
        validate_bool(value)
        self._force_alphabetical = value
        if value:
            self._range_start = 0
            self._range_end = 0

    @property
    def range_start(self) -> int:
        """The first frame number of the clipping range for a numbered
        image sequence import, inclusive. 0 (with `range_end` 0) imports
        every frame. Read / Write.

        Frame numbers refer to the digits in the filenames, not ordinal
        positions. Has no effect unless [sequence][ImportOptions.sequence]
        is `True`. A `range_end` of 0 with a non-zero `range_start` is
        rejected at import time, as is `range_end < range_start` (both
        matching After Effects).

        Raises:
            ValueError: If set while `force_alphabetical` is `True`
                (After Effects: "You cannot set sequence range start for
                an alphabetical sequence"), or if the value does not fit
                the `sspc` `start_frame` field (a `u4`: 0..4294967295).
        """
        return self._range_start

    @range_start.setter
    def range_start(self, value: int) -> None:
        validate_u4(value)
        if self._force_alphabetical:
            raise ValueError(
                "cannot set a sequence range start for an alphabetical sequence"
            )
        self._range_start = value

    @property
    def range_end(self) -> int:
        """The last frame number of the clipping range for a numbered
        image sequence import, inclusive. 0 (with `range_start` 0) imports
        every frame. Read / Write.

        A `range_end` beyond the last existing frame keeps the range:
        After Effects treats the missing tail frames as implied (rendered
        as placeholder bars), and py_aep writes the same
        `start_frame`/`end_frame` bounds. The resulting footage duration is
        not clamped to After Effects' 3-hour ceiling - AE 2026 opens a
        longer ranged sequence without complaint.

        Raises:
            ValueError: If set while `force_alphabetical` is `True`, or if
                the value does not fit the `sspc` `end_frame` field (a
                `u4`: 0..4294967295).
        """
        return self._range_end

    @range_end.setter
    def range_end(self, value: int) -> None:
        validate_u4(value)
        if self._force_alphabetical:
            raise ValueError(
                "cannot set a sequence range end for an alphabetical sequence"
            )
        self._range_end = value

    def can_import_as(self, type: int | ImportAsType) -> bool:
        """Check whether the file can be imported as the given type.

        Gates on what py_aep can actually import: the per-extension
        capability table (`get_import_as_types`) reflects After Effects,
        while a file whose format py_aep does not implement (absent from
        `data.file_formats`, or marked unsupported) returns `False` for
        every type. `ImportAsType.PROJECT` is never importable (py_aep does
        not implement project import for any format), so it always returns
        `False` even though AE can import `.mov`/`.m4a`/`.aep`/`.aet` as a
        project.

        Args:
            type: The import type to check.

        Returns:
            `True` if the file can be imported as `type`.
        """
        validate_enum(ImportAsType)(type)
        type = ImportAsType(type)
        if type == ImportAsType.PROJECT:
            return False
        suffix = self._file.suffix.lower()
        if suffix in COMP_CONVERSION_EXTENSIONS:
            # Comp-conversion formats (e.g. SVG) have no media-format entry;
            # gate on the import-type table alone.
            return type in get_import_as_types(suffix)
        try:
            fmt = get_file_format(suffix)
        except ValueError:
            return False
        if fmt.opti == "unsupported":
            return False
        return type in get_import_as_types(suffix)

    def is_file_name_numbered(self) -> tuple[bool, int]:
        """Check whether the filename ends with a number.

        Returns:
            A tuple of `(is_numbered, first_number)` where
            `is_numbered` is `True` when the filename stem ends with
            digits and `first_number` is the parsed integer value (or
            `0` when not numbered).
        """
        stem = self._file.stem
        m = _NUMBERED_RE.search(stem)
        if m is not None:
            return True, int(m.group(1))
        return False, 0

    def __repr__(self) -> str:
        return (
            f"ImportOptions(file={self._file!r}, import_as={self._import_as.name}, "
            f"sequence={self._sequence})"
        )
