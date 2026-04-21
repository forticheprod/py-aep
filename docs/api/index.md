# API Reference

Welcome to the py_aep API reference. This section provides detailed documentation for all modules, classes, and functions in the library.

## Main Entry Point

The primary function you'll use is [`parse()`](parsers.md).

## Core Modules

### [Application](application.md)

The top-level `Application` representing the After Effects application.

### [Project](project.md)

The `Project` containing all project information.

### Items

Project items represent different types of content in the project panel:

- [Item](items/item.md) - Base class for all items
- [AV Item](items/av_item.md) - Base class for Audio/Video items
- [Composition](items/composition.md) - Composition items
- [Footage](items/footage.md) - Footage items
- [Folder](items/folder.md) - Folder items

### Layers

Layers are the building blocks of compositions:

- [Base Layer](layers/layer.md) - Base class for all layers
- [AV Layer](layers/av_layer.md) - Audio/Video layers
- [Text Layer](layers/text_layer.md) - Text layers
- [Shape Layer](layers/shape_layer.md) - Shape layers
- [Camera Layer](layers/camera_layer.md) - Camera layers
- [Light Layer](layers/light_layer.md) - Light layers
- [3D Model Layer](layers/three_d_model_layer.md) - 3D model layers

### Properties

Properties control layer appearance and behavior:

- [Property Base](properties/property_base.md) - Base class for properties
- [Property](properties/property.md) - Individual properties
- [Property Group](properties/property_group.md) - Property containers
- [Mask Property Group](properties/mask_property_group.md) - Mask property groups
- [Keyframe](properties/keyframe.md) - Animation keyframes
- [Keyframe Ease](properties/keyframe_ease.md) - Keyframe easing
- [MarkerValue](properties/marker.md) - Timeline markers
- [Shape](properties/shape.md) - Shape data

### Sources

Sources provide the content for footage items:

- [Footage Source](sources/footage_source.md) - Base class for sources
- [File Source](sources/file_source.md) - File-based sources
- [Solid Source](sources/solid_source.md) - Solid color sources
- [Placeholder Source](sources/placeholder_source.md) - Placeholder sources

### Text

Text-related classes:

- [Text Document](text/text_document.md) - Text layer content and styling
- [Font Object](text/font_object.md) - Font information

### Render Queue

Render queue management and output settings:

- [Render Queue](renderqueue/render_queue.md) - The render queue container
- [Render Queue Item](renderqueue/render_queue_item.md) - Individual render items
- [Render Settings](renderqueue/render_settings.md) - Render settings reference
- [Output Module](renderqueue/output_module.md) - Output module configuration
- [Output Module Settings](renderqueue/output_module_settings.md) - Output settings reference
- [Format Options](renderqueue/format_options.md) - Format-specific encoding options

### Viewer

Viewer panel state:

- [Viewer](viewer/viewer.md) - Viewer panel
- [View](viewer/view.md) - Individual view within a viewer
- [View Options](viewer/view_options.md) - View display options

### [Enums](other/enums.md)
Enumerations for various After Effects settings and modes.

## Quick Start

See the [Quick Start guide](../quickstart.md) for usage examples (parsing, iteration, modification, saving).
