from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...binary.chunk import Chunk, ListChunk
from ...binary.comp_skeleton import build_item_view_chunks
from ...binary.item_chunks import IdpcChunk, IdtaChunk, IideChunk
from ...binary.misc_chunks import FtgiChunk
from ...binary.scalar_chunks import Utf8Chunk
from ...data.file_formats import AI_COMP_EXTENSIONS, PSD_COMP_EXTENSIONS
from ...resolvers.source_layers import layer_index_for_stored
from ..import_options import CURRENT_VALUE, _CurrentValue
from ..naming import auto_name
from ..preferences import default_sequence_fps, label_index
from ..sources.file import FileSource
from ..sources.placeholder import PlaceholderSource
from ..sources.solid import SolidSource
from ..validators import validate_one_of, validate_positive_int
from .av_item import AVItem

if TYPE_CHECKING:
    import os

    from ...binary.item_chunks import CmtaChunk
    from ..project import Project
    from .folder import FolderItem


class FootageItem(AVItem):
    """
    The `FootageItem` object represents a footage item imported into a project,
    which appears in the Project panel.

    Example:
        ```python
        from py_aep import parse

        app = parse("project.aep")
        footage = app.project.footages[0]
        print(footage.main_source)
        ```

    Info:
        `FootageItem` is a subclass of [AVItem][] object, which is a subclass of
        [Item][] object. All methods and attributes of [AVItem][] and [Item][] are
        available when working with `FootageItem`.

    See: https://ae-scripting.docsforadobe.dev/item/footageitem/
    """

    @property
    def width(self) -> int:  # type: ignore[override]
        """The width of the item in pixels. Read-only."""
        return self._main_source._width

    @property
    def height(self) -> int:  # type: ignore[override]
        """The height of the item in pixels. Read-only."""
        return self._main_source._height

    @property
    def duration(self) -> float:  # type: ignore[override]
        """The duration of the item in seconds. Still footages have a duration
        of 0. Read-only."""
        return self._main_source._duration

    @property
    def frame_rate(self) -> float:  # type: ignore[override]
        """The frame rate of the item in frames-per-second. Read-only."""
        return self._main_source.display_frame_rate

    @property
    def frame_duration(self) -> int:  # type: ignore[override]
        """The duration of the item in frames. Still footages have a duration
        of 0. Read-only."""
        return self._main_source._frame_duration

    @property
    def pixel_aspect(self) -> float:  # type: ignore[override]
        """The pixel aspect ratio of the item (1.0 is square). Read-only."""
        return self._main_source._pixel_aspect

    @property
    def footage_missing(self) -> bool:
        """When `True`, the AVItem is a placeholder, or represents footage with a
        source file that could not be found when the project was last saved.

        In this case, the path of the missing source file is in the
        `missing_footage_path` attribute of the footage item's source-file object.
        See [FootageItem.main_source][] and
        [FileSource.missing_footage_path][py_aep.models.sources.file.FileSource.missing_footage_path].
        Read-only."""
        return self._main_source._footage_missing

    @property
    def has_audio(self) -> bool:
        """When `True`, the footage has an audio component.

        When [use_proxy][py_aep.models.items.av_item.AVItem.use_proxy] is
        `True`, reflects the proxy source rather than the main source.
        Read-only.
        """
        if self.use_proxy and self._proxy_source is not None:
            return self._proxy_source._has_audio
        return self._main_source._has_audio

    @property
    def is_media_replacement_compatible(self) -> bool:
        """`True` if the footage can be used as an alternate source when setting
        [Property.alternate_source][py_aep.models.properties.property.Property.alternate_source].
        Read-only.

        `False` for solids, for footage without a video component (audio-only
        or data files), and for 3D model scenes (AE 2026 reports an imported
        `.fbx` as incompatible even though it has video).
        """
        source = self._main_source
        if isinstance(source, SolidSource):
            return False
        if isinstance(source, FileSource) and source._is_3d_model_scene:
            return False
        return self.has_video

    @property
    def start_frame(self) -> int:
        """The footage start frame. Read-only."""
        return self._main_source._start_frame

    @property
    def end_frame(self) -> int:
        """The footage end frame. Read-only."""
        return self._main_source._end_frame

    def __init__(
        self,
        *,
        _idta: IdtaChunk,
        _name_utf8: Utf8Chunk,
        _cmta: CmtaChunk | None,
        _item_list: ListChunk,
        _gide: ListChunk | None,
        _pin_chunks: list[ListChunk],
        project: Project,
        parent_folder: FolderItem,
        main_source: FileSource | SolidSource | PlaceholderSource,
        proxy_source: FileSource | SolidSource | PlaceholderSource | None,
    ) -> None:
        super().__init__(
            _idta=_idta,
            _name_utf8=_name_utf8,
            _cmta=_cmta,
            _item_list=_item_list,
            _gide=_gide,
            _pin_chunks=_pin_chunks,
            project=project,
            parent_folder=parent_folder,
            type_name="Footage",
            proxy_source=proxy_source,
        )
        self._main_source = main_source
        main_source._project = project
        self._view_data: list[Chunk] = []
        # Store resolved display name in __dict__ so the ChunkField
        # getter returns it without mutating the binary Utf8 chunk.
        self.__dict__["name"] = main_source._resolve_name(_name_utf8.value)

    @property
    def main_source(self) -> FileSource | SolidSource | PlaceholderSource:
        """The footage source. Read-only."""
        return self._main_source

    @property
    def asset_type(self) -> str:
        """The footage type (placeholder, solid, file). Read-only."""
        if isinstance(self._main_source, SolidSource):
            return "solid"
        elif isinstance(self._main_source, FileSource):
            return "file"
        elif isinstance(self._main_source, PlaceholderSource):
            return "placeholder"
        else:
            raise TypeError(
                f"Unexpected source type for {self.name}: {type(self._main_source)}"
            )

    @property
    def file(self) -> str | None:
        """The footage file path if its source is a [FileSource][], else `None`."""
        if hasattr(self._main_source, "file"):
            return self._main_source.file
        return None

    def _consolidation_key(self) -> tuple[object, ...] | None:
        """Identity used by [Project.consolidate_footage][].

        Returns a hashable key for footage that can be merged with other
        footage sharing the same source file and interpretation, or `None`
        for sources that are always unique (solids, placeholders).
        """
        source = self._main_source
        if not isinstance(source, FileSource):
            return None
        attrs = source.file_attributes
        return (
            source.file,
            tuple(source.file_names),
            source.alpha_mode,
            source.invert_alpha,
            tuple(source.premul_color),
            source.field_separation_type,
            source.remove_pulldown,
            source.loop,
            source.conform_frame_rate,
            source.high_quality_field_separation,
            source.interpret_as_linear_light,
            source.is_still,
            source.native_frame_rate,
            source.media_color_space,
            tuple(sorted(attrs.items())) if attrs else (),
        )

    @classmethod
    def _new(
        cls,
        source: FileSource | PlaceholderSource | SolidSource,
        *,
        project: Project,
        parent_folder: FolderItem,
    ) -> FootageItem:
        """Create a new FootageItem with backing chunks.

        The item name resolves from the source; like AE, the item-level
        Utf8 chunk stays empty until the user renames the item.

        Args:
            source: The footage source (file, placeholder, or solid).
            project: The project that owns this item.
            parent_folder: The folder that will contain this item.
        """
        item_id = project._allocate_id()

        # AE labels footage items by kind (probed in AE 2026): solids use
        # "Solid Label Index 2" (factory 1), audio-only files "Audio Label
        # Index 2" (7), stills "Still Label Index 2" (5), and video files,
        # sequences, and placeholders "Video Label Index 2" (3).
        if isinstance(source, SolidSource):
            label = label_index(project._preferences, "Solid Label Index 2", 1)
        elif (
            isinstance(source, FileSource) and source._has_audio and source._width == 0
        ):
            label = label_index(project._preferences, "Audio Label Index 2", 7)
        elif isinstance(source, FileSource) and source.is_still:
            label = label_index(project._preferences, "Still Label Index 2", 5)
        else:
            label = label_index(project._preferences, "Video Label Index 2", 3)

        iide = IideChunk(value=item_id)
        idpc = IdpcChunk()
        idta = IdtaChunk(
            item_type=7,
            item_id=item_id,
            label=label,
        )
        idta.is_footage = True
        idta.is_solid = isinstance(source, SolidSource)
        # A file source carries the footage-kind flags; solid/placeholder
        # sources keep the chunk default.
        if isinstance(source, FileSource):
            idta._flags_17 = source._idta_flags17()
        # AE leaves the item-level Utf8 empty; the display name resolves
        # from the source (solid / placeholder / file name).
        name_utf8 = Utf8Chunk()

        pin_list = AVItem._pin_for_source(source)

        ftgi = FtgiChunk()

        item_list = ListChunk(
            list_type="Item",
            chunks=[iide, idpc, idta, name_utf8, pin_list, ftgi, Utf8Chunk()],
        )

        # View data chunks AE expects after LIST:Item in the parent folder
        view_data: list[Chunk] = build_item_view_chunks()

        item = cls(
            _idta=idta,
            _name_utf8=name_utf8,
            _cmta=None,
            _item_list=item_list,
            _gide=None,
            _pin_chunks=[pin_list],
            project=project,
            parent_folder=parent_folder,
            main_source=source,
            proxy_source=None,
        )
        source._project = project
        item._ensure_guides_container()
        item._view_data = view_data
        return item

    def replace_with_placeholder(
        self,
        name: str | None,
        width: int,
        height: int,
        frame_rate: float,
        duration: float,
    ) -> None:
        """Replace the footage source with a placeholder.

        Args:
            name: The placeholder name. Pass `None` to use
                `Missing Name`. An empty string becomes `Placeholder`.
            width: Width in pixels (4-30000).
            height: Height in pixels (4-30000).
            frame_rate: Frame rate in fps (1.0-99.0).
            duration: Duration in seconds (> 0, <= 10800).
        """
        if name is None:
            name = "Missing Name"
        elif name == "":
            name = "Placeholder"

        source = PlaceholderSource._new(name, width, height, frame_rate, duration)
        self._replace_main_source(source)

    def replace_with_solid(
        self,
        color: list[float],
        name: str | None,
        width: int,
        height: int,
        pixel_aspect: float = 1.0,
    ) -> None:
        """Replace the footage source with a solid.

        Args:
            color: Solid color as [R, G, B] in 0.0-1.0 range.
            name: The solid name. Pass `None` to auto-generate
                a name from the color (e.g. `Red Solid 1`).
                An empty string becomes `????`.
            width: Width in pixels (1-30000).
            height: Height in pixels (1-30000).
            pixel_aspect: Pixel aspect ratio (0.01-100.0).
        """
        if name is None:
            existing = {item.name for item in self._project.items.values()}
            solid_name = SolidSource._color_name(color[0], color[1], color[2])
            name = auto_name(solid_name, existing)
        elif name == "":
            name = "????"

        source = SolidSource._new(
            name=name,
            color=color,
            width=width,
            height=height,
            pixel_aspect=pixel_aspect,
        )
        self._replace_main_source(source)

    def replace(
        self,
        file: str | os.PathLike[str],
        layer_index: int | _CurrentValue | None = None,
        layer_dimensions: str | _CurrentValue = CURRENT_VALUE,
        layer_styles: str | _CurrentValue = CURRENT_VALUE,
    ) -> None:
        """Replace the footage source with a file on disk.

        Changes the source of this `FootageItem` to the specified file.

        In addition to loading the file, the method creates a new `FileSource` object
        for the file and sets `main_source` to that object. In the new source object, it
        sets the name, width, height, `frame_duration`, and duration attributes (see
        `AVItem` object) based on the contents of the file.

        The method preserves interpretation parameters from the previous `main_source`
        object.

        py_aep extension: `layer_index` binds the new source to a single
        layer of a layered file, by `list_layers` position (see
        `ImportOptions.layer_index`). `None` (the default) always replaces
        with the merged/whole document, even when the current source
        references a single layer - consistent with `import_file`, where
        `layer_index=None` imports merged. Pass `CURRENT_VALUE` to rebind at
        the current source's stored layer index (the `sspc` layer index:
        PSD record index / AI document index) in the new file.

        `layer_dimensions` chooses the footage dimensions when a layer is
        selected (see `ImportOptions.layer_dimensions`): `"document"` (the
        full canvas) or `"layer"` (the layer's content box). `CURRENT_VALUE`
        (the default) preserves the current single-layer binding's choice.
        Layer Size is only representable for PSD targets - AI/PDF always use
        Document size, and `"layer"` on an AI/PDF file raises
        `NotImplementedError`. `layer_dimensions` is ignored when
        `layer_index` is `None` (a merged document is always document-sized).

        `layer_styles` chooses how a PSD layer's styles are treated (see
        `ImportOptions.layer_styles`): `"merge"` (bake them into the raster,
        AE's dialog default) or `"ignore"`. `CURRENT_VALUE` (the default)
        preserves the current binding's recorded choice verbatim - including
        the `"editable"` marker of an editable-comp per-layer footage item,
        which is not accepted as an explicit argument (AE's footage dialog
        offers merge/ignore only) - and falls back to `"merge"` when the
        current source has no PSD layer binding. Like `layer_dimensions`, it
        is ignored when `layer_index` is `None`.

        Note:
            Unlike ExtendScript, if the specified file has an unlabeled alpha channel,
            this method does not estimate the alpha interpretation.

        Args:
            file: Path to the new source file.
            layer_index: Layer of the new file to reference, as its 0-based
                `list_layers` position, or `CURRENT_VALUE` (layered files
                only); `None` replaces with the merged/whole document.
            layer_dimensions: `"document"`, `"layer"`, or `CURRENT_VALUE` to
                keep the current binding's choice (the default).
            layer_styles: `"merge"`, `"ignore"`, or `CURRENT_VALUE` to keep
                the current binding's choice (the default). PSD targets only.

        Raises:
            ValueError: If the extension is not a supported footage format,
                if `layer_index` is passed for a non-layered file, if
                `layer_index` is out of range for the new file, if
                `layer_dimensions` is not `"document"`/`"layer"`/`CURRENT_VALUE`,
                if `layer_styles` is not `"merge"`/`"ignore"`/`CURRENT_VALUE`
                or is passed explicitly for an AI/PDF target, or if
                `CURRENT_VALUE` is passed while the current source does
                not reference a single layer (or the new file has no layer at
                the stored index).
            NotImplementedError: If After Effects requires a format-specific
                `opti` header not implemented for this format, if
                `layer_dimensions="layer"` is requested for an AI/PDF file,
                or if `layer_dimensions="layer"` is combined with merge-mode
                styles on a PSD layer that has styles (the style-expanded
                bounds are not derivable).
        """
        if layer_index is None:
            self._replace_main_source(FileSource._from_file(file))
            return
        if not isinstance(layer_index, _CurrentValue):
            validate_positive_int(layer_index)
        if not isinstance(layer_dimensions, _CurrentValue):
            validate_one_of(("document", "layer"))(layer_dimensions)
        if not isinstance(layer_styles, _CurrentValue):
            validate_one_of(("merge", "ignore"))(layer_styles)
        suffix = Path(file).suffix.lower()
        if suffix not in PSD_COMP_EXTENSIONS and suffix not in AI_COMP_EXTENSIONS:
            raise ValueError(
                f"layer_index requires a layered .psd/.psb/.ai/.pdf "
                f"file, got {suffix!r}"
            )
        if suffix not in PSD_COMP_EXTENSIONS and not isinstance(
            layer_styles, _CurrentValue
        ):
            raise ValueError(
                "layer_styles applies to Photoshop (.psd/.psb) targets only"
            )
        if isinstance(layer_index, _CurrentValue):
            current = self._main_source
            if not (isinstance(current, FileSource) and current.layer_name):
                raise ValueError(
                    "CURRENT_VALUE requires the current source to reference "
                    "a single layer of a layered file"
                )
            layer_index = layer_index_for_stored(file, current._sspc.layer_index)
        if isinstance(layer_dimensions, _CurrentValue):
            # Preserve the Document/Layer Size choice of the current binding.
            # Layer Size is only representable for PSD targets (_from_layer
            # raises NotImplementedError for .ai/.pdf), so fall back to
            # Document size when switching to a format that cannot keep it.
            dimensions = None
            current = self._main_source
            if (
                suffix in PSD_COMP_EXTENSIONS
                and isinstance(current, FileSource)
                and current.layer_name
                and not current._sspc.full_frame
            ):
                dimensions = "layer"
        else:
            dimensions = layer_dimensions
        if isinstance(layer_styles, _CurrentValue):
            # Preserve the recorded choice verbatim (00/01/02); "merge" is
            # AE's dialog default when the current source has no binding.
            current = self._main_source
            styles = current.layer_styles if isinstance(current, FileSource) else None
            resolved_styles = styles if styles is not None else "merge"
        else:
            resolved_styles = layer_styles
        self._replace_main_source(
            FileSource._from_layer(
                file, layer_index, dimensions=dimensions, layer_styles=resolved_styles
            )
        )

    def replace_with_sequence(
        self, file: str | os.PathLike[str], force_alphabetical: bool = False
    ) -> None:
        """Changes the source of this `FootageItem` to the specified image sequence.

        In addition to loading the file, the method creates a new `FileSource` object
        for the file and sets `main_source` to that object. In the new source object, it
        sets the name, width, height, `frame_duration`, and duration attributes (see
        `AVItem` object) based on the contents of the file.

        The method preserves interpretation parameters from the previous `main_source`
        object.

        Note:
            Unlike ExtendScript, if the specified file has an unlabeled alpha channel,
            this method does not estimate the alpha interpretation.

        Args:
            file: Path to a representative frame; sibling frames in the same
                folder are gathered into the sequence.
            force_alphabetical: Order frames alphabetically rather than
                numerically.

        Raises:
            ValueError: If the extension is not a supported footage format.
            NotImplementedError: If After Effects requires a format-specific
                `opti` header not implemented for this format.
        """
        self._replace_main_source(
            FileSource._from_file(
                file,
                sequence=True,
                force_alphabetical=force_alphabetical,
                default_sequence_fps=default_sequence_fps(self._project._preferences),
            )
        )

    def _replace_main_source(
        self, source: FileSource | PlaceholderSource | SolidSource
    ) -> None:
        """Replace the first LIST:Pin in _item_list with a new source."""
        is_solid = isinstance(source, SolidSource)
        self._replace_pin(0, AVItem._pin_for_source(source))

        self._main_source = source
        source._project = self._project

        assert self._idta is not None
        self._idta.is_footage = True
        self._idta.is_solid = is_solid
        if isinstance(source, FileSource):
            self._idta._flags_17 = source._idta_flags17()

        # AE updates item-level Utf8 with new source name
        self.name = source._resolve_name("")
