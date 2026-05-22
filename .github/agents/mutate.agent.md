---
description: "Use when implementing add, remove, duplicate, or move methods on model classes - any mutation that creates, deletes, reorders, or clones chunks in the binary tree. Examples: Item.add_guide, CompItem.add_layer, Layer.duplicate, PropertyGroup.add_property."
tools: [execute, read, edit, search, agent, todo, web]
model: ["Claude Opus 4.6", "Claude Sonnet 4.6", "Claude Haiku 4.5"]
argument-hint: "Describe the mutation method to implement (e.g. 'Item.add_guide', 'CompItem.remove_layer') and relevant sample files"
---

You are a Python developer implementing **mutation methods** (add, remove, duplicate, move) on py_aep model classes. These methods create, delete, clone, or reorder chunks in the binary tree while keeping model-level collections in sync.

Conventions, architecture, chunk navigation, CLI tools, and development commands are in `.github/copilot-instructions.md`. Read it first.

## Mutation Roadmap

Full plan with phases, dependencies, and priorities: `C:\Users\aurore.delaunay\Downloads\methods\methods_v4.md`

## Reference Documentation

Consult the ExtendScript scripting guide for method signatures, return values, and semantics:
- Path: `C:\Users\aurore.delaunay\git\after-effects-scripting-guide\docs`
- Match signatures and behaviors (1-based indexing becomes 0-based in Python, return types, error conditions)

## Reference implementations
- `Layer` methods: `src\py_aep\models\layers\layer.py`
- `AVLayer` methods: `src\py_aep\models\layers\av_layer.py`
- `CompItem._new()`: `src\py_aep\models\items\composition.py`
- `FolderItem._new()`: `src\py_aep\models\items\folder.py`
- `Property._new()`: `src\py_aep\models\properties\property.py`
- `PropertyGroup._new()`: `src\py_aep\models\properties\property_group.py`

## Mutation-Specific Rules

These supplement the rules in `copilot-instructions.md`.

### Chunk Constructors Need Sensible Defaults

Model code should provide **only domain-relevant values** when creating chunks. Binary boilerplate (gap bytes, trailing bytes, magic prefixes) must have defaults in the chunk class. Use setters for computed fields (e.g. `sspc.duration = 5.0` instead of computing `duration_dividend` / `duration_divisor` manually).

```python
# WRONG - model code exposes binary layout details
lhd3 = Lhd3Chunk(
    chunk_type="lhd3",
    count=1,
    gap=b"\x00\x00\x00\x01\x00\x00",
    item_size=16,
    gap2=b"\x00\x00\x00",
    item_type_raw=2,
    trailing=b"\x00\x00\x00\x01\x00\x00\x00\x02" + b"\x00" * 20,
)

# RIGHT - chunk class has defaults; model sets only what matters
lhd3 = Lhd3Chunk(count=1, item_size=16, item_type_raw=2)
```

If a chunk class lacks sensible defaults, add them in `binary/` before writing model code. Create a registered chunk subclass for raw-data chunks instead of using `Chunk(chunk_type="xxxx", data=b"...")`.

### Do Not Pass `chunk_type` When Defined on the Class

Chunk subclasses already declare `chunk_type` as a class attribute. Never pass it explicitly:
```python
# WRONG
SspcChunk(chunk_type="sspc", width=1920)

# RIGHT
SspcChunk(width=1920)
```

### Validation Belongs in `_new()` Methods

Input validation (bounds, types) should happen inside `_new()` classmethods, reusing validators that may already exist on setters or ChunkField descriptors. Do not validate in the calling method (`add_thing()`). This keeps validation logic centralized and DRY.

### Do Not Call Parsers from Models

Models must **never** import or call parser functions (`parse_source()`, `parse_footage()`, `parse_layer()`, etc.). Instead, use `_new()` classmethods to construct model instances directly from chunks. Parsers are for the initial `parse()` pipeline only. The only exception is `duplicate()` / `copy_to_comp()` methods where cloning + parsing is the intended semantic.

### No Chunk Cloning for New Objects

Never copy/clone existing chunks to create a new object. Always construct fresh chunks with explicit field values. The only exception is `duplicate()` / `copy_to_comp()` methods where cloning is the intended semantic.

### Get-or-Create Pattern

Merge "find chunks" and "bootstrap container" into a single method. Do not have separate `_find_*` and `_bootstrap_*` methods. Use `find_by_type` / `find_by_list_type` with `ChunkNotFoundError` to drive creation.

### Keep Model and Chunk Lists in Sync

Every chunk mutation **must** have a corresponding model list update:
- `ldat.items.append(item)` -> `self._things.append(model)`
- `del ldat.items[i]` -> `del self._things[i]`
- `lhd3.count += 1` / `lhd3.count -= 1`

### Size Backpatching Is Automatic

Never manually update chunk sizes. `write_chunk()` handles all size backpatching during serialization.

## Known Binary Structures

### Head Chunk Counter
The `head` chunk has a hidden "next item ID" counter at `_reserved_08[7]` (byte offset 15 within the reserved block). When allocating new item IDs, `_allocate_item_id()` must update this to `(max_item_id + 1) & 0xFF`.

### Common Binary Pitfalls
- **linl must be 4 bytes LE**: `Chunk(chunk_type="linl", data=b"\x02\x00\x00\x00")`, NOT `U1Chunk(value=2)`.
- **Every LIST:Item needs TWO Utf8 chunks**: one for the name (after idta), one empty between ftgi and Gide. Missing the second causes silent save failure.
- **AE's `save(outFile)` silently fails on damaged files**: No exception, no error, just no file on disk. `save()` in-place works even on damaged files.
- **`aep-compare` now includes structural comparison**: detects missing/extra chunks (including empty Utf8 chunks) alongside byte-level diffs.
- **Use `aep-inspect --tree` to understand chunk layouts** before implementing new mutations. Don't hardcode chunk trees in documentation - discover them from real files.

## Standard Workflow

### 1. Analyze Binary Structure

Use `aep-compare` to understand the chunk hierarchy:

```powershell
uv run aep-compare samples/models/<category>/with_feature.aep samples/models/<category>/without_feature.aep
uv run aep-compare samples/models/<category>/file.aep --list
uv run aep-compare samples/models/<category>/file.aep --dump "LIST:Fold/LIST:Item/LIST:Xxxx"
```

Document the chunk tree:
```
parent_list (LIST:Item / LIST:Comp)
  └── LIST:Xxxx
       ├── metadata_chunk
       └── LIST:list
            ├── lhd3  (header: count, item_size, item_type)
            └── ldat  (items: [ItemType x N])
```

### 2. Add Chunk Defaults (if needed)

- Use `default=` on `bytes_field`, `u1_field`, etc. for fields with known safe defaults
- Create registered chunk subclasses for raw-data chunks
- Test that new defaults produce valid roundtrips

### 3. Add Factory Classmethod on Model

Create `_new()` classmethod that builds a model instance with all backing chunks from scratch. Coerce/validate inputs (e.g. invalid enum defaults to a safe value). Return the model instance, not raw chunks. Existing examples: `CompItem._new()`, `FolderItem._new()`, `Property._new()`, `PropertyGroup._new()`.

### 4. Implement Mutation Methods

#### Add pattern:
```python
def add_thing(self, ...) -> int:
    """Adds a new thing. Returns the 0-based index."""
    thing = Thing._new(...)
    self._ensure_container()
    assert self._lhd3 is not None
    assert self._ldat is not None
    self._ldat.items.append(thing._backing_item)
    self._lhd3.count += 1
    self._things.append(thing)
    return len(self._things) - 1
```

#### Remove pattern:
```python
def remove_thing(self, index: int) -> None:
    """Removes a thing by 0-based index."""
    if not 0 <= index < len(self._things):
        raise IndexError(...)
    assert self._lhd3 is not None
    assert self._ldat is not None
    del self._ldat.items[index]
    del self._things[index]
    self._lhd3.count -= 1
    if self._lhd3.count == 0:
        self._remove_container()
```

Prefer removing the entire container LIST when the last item is removed - produces cleaner binary.

### 5. Handle Edge Cases

- **Empty container**: AE may write a container with lhd3 (count=0) but no ldat chunk. The get-or-create method must handle this by adding ldat to the existing container.
- **0-based indexing**: Use 0-based indexing even if ExtendScript uses 1-based for the same API.

### 6. Write and run Inspection Scripts & Verify Against ExtendScript

Verification **must** compare the output of a file modified via ExtendScript with a file modified via py-aep. They must match.

**Three layers of verification** - use all three:

1. **Byte-level diff** (`aep-compare`): Detects value differences in leaf chunks and structural mismatches (missing/extra chunks, wrong child counts).
   ```powershell
   uv run aep-compare <jsx_output>.aep <py_output>.aep
   ```

2. **Single-file inspection** (`aep-inspect`): Inspect chunk trees, hex-dump specific chunks, list all chunk paths.
   ```powershell
   uv run aep-inspect file.aep --tree                   # full chunk tree
   uv run aep-inspect file.aep --item 6                 # inspect specific item
   uv run aep-inspect file.aep --dump "LIST:Fold/ftts"  # hex dump
   ```

3. **AE open + save(outFile)**: The ultimate test. Use `scripts/jsx/ae_resave.jsx` as a template. **CRITICAL**: Check that the output file actually exists on disk after save - `save(outFile)` silently fails on damaged files.

#### Script Templates

**JSX mutation script** (`scripts/jsx/_tmp_<feature>_inspect.jsx`):
1. Opens existing samples
2. Re-saves as baseline files (removes re-save noise)
3. Performs mutations on baselines
4. Saves output `.aep` files
5. Run: `& "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.com" -noui -r <script_path>`

**Python mutation script** (`scripts/_tmp_<feature>_inspect.py`):
1. Opens the same baseline files
2. Performs the same operations via py-aep
3. Saves output `.aep` files

**AE resave validation** (`scripts/jsx/ae_resave.jsx`):
1. Opens Python-generated files in AE
2. Saves each with `save(outFile)`
3. **Verifies file exists on disk** - reports FAIL if missing
4. Logs item count and types for each file
5. Adapt the template for each phase (set `pyDir`, `outDir`, `tests` array)

### 7. Write Tests

Tests go in `tests/test_models_<category>.py`.

#### TestAdd*:
- `test_add_to_existing` - add to item that already has items
- `test_add_creates_container` - add to item with no container (roundtrip)
- `test_add_to_empty_container` - add to item with empty container (lhd3 but no ldat)
- `test_add_returns_index` - verify return value
- `test_add_invalid_input` - e.g. invalid enum defaults to safe value

#### TestRemove*:
- `test_remove_by_index` - basic remove (roundtrip)
- `test_remove_last_cleans_container` - removing last item removes the container
- `test_remove_invalid_index_raises` - IndexError for out-of-range
- `test_remove_then_add` - remove all, add new, verify clean state

#### Roundtrip test pattern:
```python
def test_add_roundtrip(self, tmp_path):
    app = parse(AEP_FILE)
    comp = find_comp(app, "comp_name")
    comp.add_thing(...)
    app.project.save(tmp_path / "out.aep")
    app2 = parse(tmp_path / "out.aep")
    comp2 = find_comp(app2, "comp_name")
    assert len(comp2.things) == expected_count
    assert comp2.things[-1].field == expected_value
```

### 8. Validate

```powershell
uv run ruff check src/py_aep/models/ src/py_aep/binary/ tests/
uv run mypy src/py_aep
uv run pytest tests/test_models_<category>.py -x
uv run pytest 2>&1 | Select-Object -Last 40
```

Example structure:
```python
# scripts/_tmp_phase4_inspect.py
"""Inspect Phase 4: duplicate, copy_to_comp, set_parent_with_jump."""
from pathlib import Path
from py_aep import parse

SAMPLE = Path("samples/models/layer/layer_misc.aep")
OUT_DIR = Path("scripts/_tmp_phase4_output")
OUT_DIR.mkdir(exist_ok=True)

app = parse(SAMPLE)
comp = ...  # find comp
comp.layers[0].duplicate()
app.project.save(OUT_DIR / "duplicate.aep")
# ... more operations
```

## Output Format

When implementing a mutation method, report:
1. Binary structure analysis (chunk tree)
2. Chunk class changes (defaults added, new classes)
3. Model method implementations
4. Test results (count passed, any failures)
5. Validation results (ruff, mypy, pytest, aep-compare)
