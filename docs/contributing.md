# Contributing Guide

See the full [Contributing Guide](https://github.com/forticheprod/py-aep/blob/main/CONTRIBUTING.md) on GitHub.

## Quick Start

1. **Fork and clone** the repository
2. **Install**:

    === "uv"

        ```bash
        uv sync --extra dev
        ```

    === "pip"

        ```bash
        pip install -e ".[dev]"
        ```

3. **Test**: `uv run pytest`
4. **Submit a pull request**

## Key Topics

The contributing guide covers:

- **Architecture** - Three-stage pipeline: Binary > Parsers > Models
- **ChunkField descriptors** - Write-through to binary, serialization roundtrips
- **CLI tools** - `aep-validate`, `aep-compare`, `aep-visualize`
- **Adding features** - New attributes, layer types, boolean flags, enum mappings
- **Testing** - Parse tests, roundtrip tests, creating samples
- **Code style** - Type hints, linting, documentation conventions

## Quick Links

- [GitHub Repository](https://github.com/forticheprod/py-aep)
- [Issue Tracker](https://github.com/forticheprod/py-aep/issues)
- [After Effects Scripting Guide](https://ae-scripting.docsforadobe.dev/)
