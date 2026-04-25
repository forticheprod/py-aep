# py_aep - AI Coding Agent Instructions

## Project Overview
A Python library for parsing Adobe After Effects project files (.aep). The binary RIFX format is decoded into typed Python classes representing the AE object model (Application > Project > Items > Layers > Properties). Two binary I/O layers coexist during migration:
- **`kaitai/`** (legacy) - Kaitai Struct-based, auto-generated from `aep.ksy`
- **`binary/`** (new) - attrs-based chunk classes with `fmt_field()` declarative fields

## Architecture

### Data Flow
```
.aep file > Binary I/O (binary/ or kaitai/) > Raw chunks > Parsers > Model classes
```
The `binary/` layer reads/writes typed `Chunk` subclasses directly.
The `kaitai/` layer uses auto-generated `Aep` classes from `aep.ksy`.
Parsers currently consume Kaitai chunks; migration to `binary/` chunks is in progress.

### Property Parsing Pipeline
Properties go through three stages. See [CONTRIBUTING.md](../CONTRIBUTING.md#property--effect-parsing-flow) for the full diagram.

1. **Binary parsing**: `parse_layer()` > `get_chunks_by_match_name()` > `parse_properties()` dispatches by chunk list_type (tdgp > PropertyGroup, tdbs > Property, sspc > Effect, etc.)
2. **Effect enrichment**: `parse_effect()` merges param defs from `LIST:parT` (layer-level, with project-level fallback from `LIST:EfdG`) into parsed properties via `_merge_param_def()`, and synthesizes missing params via `_synthesize_effect_property()`
3. **Post-processing**: `synthesize_layer_properties()` runs a single pass (in `parsers/synthesis.py`) handling transform defaults, top-level group ordering, recursive child synthesis via `_reorder_and_fill()`, and min/max bounds. Effect param synthesis remains a separate dynamic step inside `parse_effect()`. Synthesis uses `_PropSpec` (leaf Property) and `_GroupSpec` (empty PropertyGroup) with `ProxyBody` for chunk bodies.

### Key Directories
- **`src/py_aep/kaitai/`** - Binary parsing layer (legacy, being replaced by `binary/`)
  - `aep.ksy` - Kaitai schema defining RIFX chunk structure (auto-generates `aep.py`)
  - `utils.py` - Chunk filtering helpers (`find_by_type`, `filter_by_list_type`)
  - `patches.py` - Monkey-patches on auto-generated Kaitai body classes (e.g. `_recompute_size` for variable-size bodies)
  - `descriptors.py` - `ChunkField` descriptors for chunk-backed model fields (read/write through to Kaitai bodies)
  - `proxy.py` - `ProxyBody` for synthesized properties without backing chunks
  - `materializer.py` - Chunk builders for property materialization on first write
  - `transforms.py` / `reverses.py` - Transform and reverse functions for binary value conversion
- **`src/py_aep/binary/`** - New binary I/O layer (attrs-based, replacing Kaitai)
  - `chunk.py` - `Chunk` base, `ListChunk`, `ContainerChunk`, `read_aep()`/`write_aep()`
  - `fmt_field.py` - `fmt_field()` declarative field-format binding + `_struct_info()` introspection
  - `bitfield.py` - `BitField` descriptor for single-bit flag access
  - `registry.py` - `@register` decorator + `CHUNK_TYPES` dispatch table
  - `bin_utils.py` - `read_fmt()`, `write_fmt()`, `read_bytes()`, `write_bytes()`
  - Chunk modules: `scalar_chunks.py`, `property_chunks.py`, `item_chunks.py`, `composition_chunks.py`, `layer_chunks.py`, `misc_chunks.py`, `footage_chunks.py`, `render_chunks.py`
  - **Chunk subclass rules**: use `fmt_field()` for fixed-layout fields (generic `Chunk.read()`/`write()` handles I/O). Use `BitField` for single-bit flags. Chunks with no typed fields (raw bytes only) do NOT override `read()` - base `Chunk.read()` stores body as `data: bytes`. Only override `read()` when the chunk needs context parameters (e.g. `is_le`, `is_color`) or polymorphic dispatch.
- **`src/py_aep/__init__.py`** - Public API entry point: `parse()`
- **`src/py_aep/parsers/`** - Transform raw chunks into models
  - `application.py`, `project.py`, `layer.py`, `property.py`, `synthesis.py`, `effect.py`, ...
  - Pattern: Each parser receives chunks + context, returns a model instance
- **`src/py_aep/models/`** - Typed model classes mirroring AE's object model
  - `application.py`, `project.py`, `items/`, `layers/`, `properties/`, `sources/`, `renderqueue/`, `text/`, `viewer/`
  - `validators.py` - Validator factories for model field constraints
- **`src/py_aep/data/`** - Static data tables
  - `match_names.py` - Match name constants; `units.py` - Unit definitions for properties
- **`src/py_aep/enums/`** - Enumerations matching ExtendScript values (`general.py`, `property.py`, `mappings.py`, ...)
- **`src/py_aep/resolvers/`** - Business logic for computing derived values (`output.py` for render filenames, `interpolation.py` for keyframes)
- **`src/py_aep/cli/`** - `visualize.py`, `validate.py`, `compare.py`
- **`src/py_aep/cos/`** - COS (PDF) format parser for embedded text data
- **`scripts/`** - Dev/analysis scripts; `jsx/` has ExtendScript JSON exporters
- **`samples/`** - Test .aep files covering specific features

## Development Commands

```powershell
uv sync --extra dev --extra docs
uv run mypy src/py_aep
uv run ruff check src/ tests/  # Linting (excludes auto-generated kaitai/aep.py)
uv run ruff format src/ tests/
uv run zensical build --strict  # Build documentation
uv run pytest 2>&1 | Select-Object -Last 40
uv sync --python 3.7 --extra dev  # For Python 3.7
uv run --python 3.7 python -m pytest -o "addopts=" 2>&1 | Select-Object -Last 60
```

JSX scripts run in After Effects via VS Code debugger - see `.vscode/launch.json`.

## Code Conventions

### Style Guide
- All functions require type hints (`disallow_untyped_defs = true`)
- Use `from __future__ import annotations` and modern type hints (`list[int]` not `List[int]`)
- Conditional imports for TYPE_CHECKING to avoid circular imports
- Move imports used **only in annotations** (not at runtime) into `if TYPE_CHECKING:` blocks - with `from __future__ import annotations`, all annotations are strings at runtime so type-only imports (`IO`, `Any`, `Callable`, etc.) belong in TYPE_CHECKING
- PEP8 naming: snake_case for functions/variables, PascalCase for classes
- Use `pathlib` for file paths, f-strings for formatting
- No spaces on empty lines
- No em dashes (`—`) nor en-dashes (`–`); use regular dashes (`-`)
- In docstrings, use single backticks (`` ` ``) not double (` `` `)
- Use `>` or `->` instead of unicode arrow symbols (`→`)
- **No `struct` module in `kaitai/`** - binary decoding in the legacy layer must be in `kaitai/aep.ksy`. The new `binary/` layer uses `struct` via `fmt_field()` and `bin_utils`.
- **Constructor param ordering**: `__init__` parameters follow: private (`_`-prefixed chunk refs) -> back-references (`project`, `parent_folder`, `containing_comp`, `parent`, `comp`) -> public domain params. Call sites must match this order.
- **No backward compatibility** - when refactoring internal APIs (renaming functions, replacing classes with factory methods, etc.), update all call sites directly. Do not add shims, aliases, or deprecation wrappers for internal code.
- **Idempotent round-trip** - `parse()` then `save()` must produce byte-identical output. Parsers must not mutate Kaitai chunk data (use `__dict__["field"]` to modify without side effects when needed). Beware of `strz` for fixed-size string fields in `aep.ksy`.

### Avoiding Code Slop
- **No identity casts**: don't `int(x)` when x is already int, `str(x)` when x is already str, `bool(x == y)` when `==` already returns bool, etc.
- **No redundant exception tuples**: `except (SpecificError, Exception)` - `Exception` already catches everything. Use just `except Exception` or just `except SpecificError`.
- **Only catch what can be raised**: don't add `try/except` "just in case". Shield code only when you know it raises or when a caller explicitly documents exceptions.
- **No silent `except Exception: pass`** without a comment explaining why swallowing errors is correct.
- **No dead defaults**: `getattr(obj, "attr", 0)` when the attribute always exists is misleading. Access the attribute directly.
- **Comments explain WHY, not WHAT**: `# Convert None to 0 for pre-v23 files` is useful; `# Get the chunk` or `# Parse the layer` is not.
- **No docstrings that restate the function name or signature**. ExtendScript-sourced docstrings on model fields are fine.

### Adding New Parsed Data

**Via Kaitai (legacy path):**
1. Find/add chunk type in `kaitai/aep.ksy`
2. Create/update model class in `models/` with docstrings referencing AE equivalents
3. Add parser in `parsers/`:
   ```python
   def parse_thing(chunk: Aep.Chunk, context: ...) -> ThingModel:
       data_chunk = find_by_type(chunks=chunk.body.chunks, chunk_type="xxxx")
       return ThingModel(field=data_chunk.body.field)
   ```
4. Validate parsed values against ExtendScript using `aep-validate` (see [CLI Tools](#cli-tools))
5. Add test case in `tests/test_models_*.py` using sample .aep files

**Via binary/ (new path):**
1. Add chunk class in the appropriate `binary/*_chunks.py` module
2. Use `fmt_field()` for fixed-layout fields, `BitField` for flags, `optional=True` for version-dependent fields
3. Register with `@register("xxxx")`
4. Add round-trip test in `tests/test_binary_io.py`
5. Update model and parser to consume the new chunk type

### Binary Format Debugging
Use `aep-compare` to investigate unknown binary fields by diffing `.aep` files that differ in a single AE setting. For reverse-engineering bitflags in `aep.ksy`:
```yml
- id: preserve_nested_resolution
  type: b1
- type: b1
- id: frame_blending
  type: b1
- type: b2
- id: hide_shy_layers
  type: b1
```

### Chunk Navigation Pattern
```python
from py_aep.kaitai.utils import find_by_type, find_by_list_type, filter_by_type

ldta_chunk = find_by_type(chunks=child_chunks, chunk_type="ldta")
fold_chunk = find_by_list_type(chunks=root_chunks, list_type="Fold")
layer_chunks = filter_by_list_type(chunks=comp_chunks, list_type="Layr")
```

For debugging, `chunk_tree(chunks, depth)` prints the chunk hierarchy and `recursive_find(chunks, chunk_type, list_type)` searches the entire tree recursively.

### Typed LIST Instances
Some LIST types have children at **fixed positions**. For these, `list_body` in `aep.ksy` defines Kaitai instances that provide direct access by name instead of `find_by_type`:

```python
# LIST:list - keyframe/shape data
list_chunk.body.lhd3          # chunks[0] - header (count + item size)
list_chunk.body.ldat          # chunks[1] - data items (None if no keyframes)

# LIST:tdbs - leaf property container
tdbs_chunk.body.tdsb          # chunks[0] - property flags
tdbs_chunk.body.tdsn          # chunks[1] - property name
tdbs_chunk.body.tdb4          # chunks[2] - property metadata
```

Each instance has an `if` guard on `list_type`, so accessing e.g. `.lhd3` on a non-`list` LIST returns `None`. Use `find_by_type` when the LIST type is unknown or when a function handles multiple LIST types (e.g. `parse_layer` handles both `Layr` and `SecL`).

### Chunk Data Access

**Kaitai (legacy):** Chunk attributes live on `chunk.body`, not on the chunk itself:
```python
chunk.body.list_type     # the list_type of a LIST chunk
cdta_chunk.body.time_scale  # a typed body field
```

**binary/ (new):** Chunk attributes live directly on the chunk (no `.body` indirection):
```python
chunk.list_type          # ListChunk attribute
cdta_chunk.time_scale    # fmt_field attribute
chunk.data               # raw bytes for untyped chunks
```

### Value Mapping Pattern
Binary values often differ from ExtendScript values. Single-param mappings use a `from_binary` classmethod on the enum (`enums/general.py` or relevant module):
```python
blending_mode = BlendingMode.from_binary(raw_value)
```
Multi-param mappings (e.g. `map_alpha_mode(value, has_alpha)`) go in `enums/mappings.py`.

When adding new mappings:
1. Add enum to `enums/general.py` (matching ExtendScript values)
2. Single-param: add `from_binary(cls, value)` classmethod
3. Multi-param: create `map_<name>()` in `enums/mappings.py`
4. Use `.get(value, default)` for unknown values

## Testing
- Tests use sample `.aep` files from `samples/`; most have a matching `.json` from ExtendScript
- Add test cases in `tests/test_models_*.py`
- **Always validate** parsed output against ExtendScript ground truth using `aep-validate` after any parsing change (see [CLI Tools](#cli-tools))
- Use `aep-compare` to investigate unknown binary fields by diffing `.aep` files that differ in a single AE setting

## Regenerating Kaitai Parser
When modifying `aep.ksy`, regenerate:
```powershell
kaitai-struct-compiler --target python --outdir src/py_aep/kaitai src/py_aep/kaitai/aep.ksy --read-write --no-auto-read
```
**Integer division pitfall:** Kaitai's `/` on two integers compiles to `//` (floor division). Multiply one operand by `1.0` for true division: `value: 'dividend * 1.0 / divisor'`.

## Important Notes
- `kaitai/aep.py` is **auto-generated** - edit `aep.ksy` and regenerate
- Run python code through a temporary file, not `python.exe -c`
- Python 3.7+ compatibility (no walrus operator, no match/case, union types via annotations)
- Model docstrings should reference [AE Scripting Guide](https://ae-scripting.docsforadobe.dev/)
- DO NOT switch to plan agent prematurely - exhaust terminal-based investigation first

## CLI Tools
Installed via `uv sync --extra dev`. Also invocable as `uv run python -m py_aep.cli.{visualize,validate,compare}`.

- **`aep-visualize`** - Tree visualization of a parsed project
- **`aep-validate`** - Compare parsed output against ExtendScript JSON. **Use after any parsing change.**
- **`aep-compare`** - Binary chunk diff between `.aep` files. **Use to investigate unknown fields.**

```powershell
aep-visualize samples/models/composition/bgColor_custom.aep

aep-validate sample.aep sample.json
aep-validate sample.aep sample.json --verbose          # all fields
aep-validate sample.aep sample.json --category layers  # filter

aep-compare file1.aep file2.aep
aep-compare ref.aep v1.aep v2.aep v3.aep     # multi-file
aep-compare file.aep --list                  # list chunks
aep-compare file.aep --dump "LIST:Fold/ftts" # dump raw bytes
```

## Documentation
Zensical; auto-deployed to [GitHub Pages](https://forticheprod.github.io/py-aep/) on push to `main`. Build locally: `zensical serve --strict`.

### Docstring Conventions
- **Functions**: Google-style (Args, Returns, Raises sections)
- **Class attributes**: inline docstrings after each field (not `Attributes:` section):
  ```python
  class CompItem(AVItem):
      """Composition item containing layers."""

      frame_rate: float
      """The frame rate of the composition."""
  ```
- Copy AE ExtendScript descriptions
- Lines under 80 characters
- Use mkdocstrings [scoped cross-references](https://mkdocstrings.github.io/python/usage/configuration/docstrings/#scoped_crossrefs), **not** Sphinx `:class:`/`:func:`:
  ```python
  """The [CompItem][] that contains this layer."""                    # ✓ short
  """See [FileSource][py_aep.models.sources.file.FileSource]."""  # ✓ explicit
  """Returns a :class:`CompItem` instance."""                         # ✗ Sphinx
  ```

### Adding Documentation Pages
1. Create markdown file in `docs/api/`
2. Reference Python objects: `::: py_aep.models.my_module.MyClass`
3. Add to `nav:` in `zensical.toml`
4. Verify: `zensical serve --strict`
