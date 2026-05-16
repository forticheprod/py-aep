# py_aep Documentation

Welcome to the py_aep documentation! This library provides a Python interface for parsing Adobe After Effects project files (.aep).

## About

py_aep is a Python library that parses Adobe After Effects project files (.aep), which are binary files encoded in RIFX format. The library uses [struct](https://docs.python.org/3/library/struct.html) to parse the binary format and provides a clean, typed Python API to access project data.

## Installation

=== "uv"

    ```bash
    uv add py-aep
    ```

=== "pip"

    ```bash
    pip install py-aep
    ```

## Quick Start

```python
import py_aep

app = py_aep.parse("myproject.aep")
project = app.project
comp = project.compositions[0]

# Modify composition settings
comp.frame_rate = 30

# Modify a layer property
opacity = comp.layers[0].transform.opacity
opacity.value = 50

# Save to a new file
project.save("modified.aep")
```

See the [Quick Start guide](quickstart.md) for examples.

## Key Concepts

### Project Structure

An After Effects project has a hierarchical structure:

```
Application
└── Project
    ├── FolderItem
    │   ├── CompItem
    │   │   ├── AVLayer ──────────┐
    │   │   ├── TextLayer ────────┤
    │   │   ├── ShapeLayer ───────┤
    │   │   ├── ThreeDModelLayer ─┤
    │   │   ├── CameraLayer ──────┤
    │   │   ├── LightLayer ───────┘──▶ PropertyGroup
    │   │   ├── Guide                  ├── Property
    │   │   └── Viewer                 │   ├── Keyframe
    │   │       └── View               │   │   └── KeyframeEase
    │   │           └── ViewOptions    │   ├── MarkerValue
    │   └── FootageItem                │   └── Shape
    │       ├── Viewer                 │       └── FeatherPoint
    │       │   └── View               ├── MaskPropertyGroup
    │       │       └── ViewOptions    └── PropertyGroup (nested)
    │       ├── FileSource                 └── ...
    │       ├── SolidSource
    │       └── PlaceholderSource
    ├── TextDocument
    │   └── FontObject
    │
    └── RenderQueue
        └── RenderQueueItem
            └── OutputModule
```

### Data Model

The library provides classes that mirror After Effects' object model:

- `Application`: Application-level object (version, build number, active viewer)
- `Viewer`, `View`, `ViewOptions`: Viewer panels and view settings
- `Project`: Root project object
- `Item`, `AVItem`, `FolderItem`, `CompItem`, `FootageItem`: Project items
- `AVLayer`, `TextLayer`, `ShapeLayer`, `ThreeDModelLayer`, `CameraLayer`, `LightLayer`: Layer types
- `PropertyBase`, `Property`, `PropertyGroup`, `MaskPropertyGroup`: Layer properties
- `Keyframe`, `KeyframeEase`, `MarkerValue`, `Shape`, `FeatherPoint`, `Gradient`: Animation and property value data
- `Guide`: Composition ruler guide
- `FootageSource`, `FileSource`, `SolidSource`, `PlaceholderSource`: Footage sources
- `TextDocument`, `FontObject`: Text layer data
- `RenderQueue`, `RenderQueueItem`, `OutputModule`: Render queue

## API Reference

Browse the [API Reference](api/index.md) for detailed documentation of all classes and methods.

## Contributing

Contributions are welcome! See the [Contributing Guide](contributing.md) to get started, or visit the [GitHub repository](https://github.com/forticheprod/py-aep) for more information.

## License

This project is licensed under the MIT License.
