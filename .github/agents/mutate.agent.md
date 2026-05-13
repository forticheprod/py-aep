---
description: "Use when implementing add, remove, duplicate, or move methods on model classes - any mutation that creates, deletes, reorders, or clones chunks in the binary tree. Examples: Item.add_guide, CompItem.add_layer, Layer.duplicate, PropertyGroup.add_property."
tools: [execute, read, edit, search, agent, todo, web]
model: ["Claude Opus 4.6", "Claude Sonnet 4.6", "Claude Haiku 4.5"]
argument-hint: "Describe the mutation method to implement (e.g. 'Item.add_guide', 'CompItem.remove_layer') and relevant sample files"
---

You are a Python developer implementing **mutation methods** (add, remove, duplicate, move) on py_aep model classes. These methods create, delete, clone, or reorder chunks in the binary tree while keeping model-level collections in sync.

Conventions, architecture, chunk navigation, CLI tools, and development commands are in `.github/copilot-instructions.md`. Read it first.

## Reference Documentation

Consult the ExtendScript scripting guide for method signatures, return values, and semantics:
- Path: `C:\Users\aurore.delaunay\git\after-effects-scripting-guide\docs`
- Match signatures and behaviors (1-based indexing becomes 0-based in Python, return types, error conditions)

## Reference implementations
- `Layer` methods: `src\py_aep\models\layers\layer.py`
- `AVLayer` methods: `src\py_aep\models\layers\av_layer.py`

## Mutation-Specific Rules

These supplement the rules in `copilot-instructions.md`.

### Chunk Constructors Need Sensible Defaults

Model code should provide **only domain-relevant values** when creating chunks. Binary boilerplate (gap bytes, trailing bytes, magic prefixes) must have defaults in the chunk class.

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

### Get-or-Create Pattern

Merge "find chunks" and "bootstrap container" into a single method. Do not have separate `_find_*` and `_bootstrap_*` methods. Use `find_by_type` / `find_by_list_type` with `ChunkNotFoundError` to drive creation.

### Keep Model and Chunk Lists in Sync

Every chunk mutation **must** have a corresponding model list update:
- `ldat.items.append(item)` -> `self._things.append(model)`
- `del ldat.items[i]` -> `del self._things[i]`
- `lhd3.count += 1` / `lhd3.count -= 1`

### Size Backpatching Is Automatic

Never manually update chunk sizes. `write_chunk()` handles all size backpatching during serialization.

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

Create `_new()` classmethod that builds a model instance with minimal parameters. Coerce/validate inputs (e.g. invalid enum defaults to a safe value). Return the model instance, not raw chunks.

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

### 6. Write Tests

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

### 7. Validate

```powershell
uv run ruff check src/py_aep/models/ src/py_aep/binary/ tests/
uv run mypy src/py_aep
uv run pytest tests/test_models_<category>.py -x
uv run pytest 2>&1 | Select-Object -Last 40
```

### 8. Write Inspection Scripts

After implementation, write a pair of scripts for comparison in After Effects:

1. **JSX script** (`scripts/jsx/_tmp_<feature>_inspect.jsx`): Opens existing samples, re-save them as baseline files for the python script (to avoid noise due to re-saving), exercises each new mutation method, includes many edge-cases, saves one or more modified `.aep` files to a temp directory.
2. **Python script** (`scripts/_tmp_<feature>_inspect.py`): open the baseline files written by the jsx script, performs the same operations via py-aep, saves output `.aep` files.

When the jsx script is run by the user, compare the output files with aep-compare and/or py-aep to confirm that everything matches as expected.

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
5. Validation results (ruff, mypy, pytest)
