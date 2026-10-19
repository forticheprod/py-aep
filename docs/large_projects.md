# Large Projects

## Read only what you need

py_aep decodes a project lazily, so a script pays for what it reads:

- `py_aep.parse()` reads the items, folders, render queue and composition
  settings.
- A composition's layers are built on first access (`comp.layers`), from each
  layer's own settings.
- A layer's properties (Transform, Effects, Masks, Text, ...) are decoded and
  built the first time one of them is read.

A script that reads layer attributes only (names, times, labels, switches,
sources) never builds a property. On a 29 MB production project with 726
layers, parsing and reading every layer's times, label and source takes 1.2 s
and 133 MB; reading every property value as well takes 8.6 s and 506 MB.

Reading an attribute a layer does not have, such as
`getattr(layer, "source", None)` on a camera, looks it up among the layer's
properties, which builds them. Test the layer's type instead
(`isinstance(layer, AVLayer)`).

## Garbage collection

Every property, keyframe and chunk is a Python object, and they reference
each other (each property knows its parent group), so a project is held in
reference cycles. CPython's cyclic garbage collector regularly walks every
tracked object, and while a large project is being read these passes grow with
it: reading every property of the 29 MB project above spends 28% of its time
in the collector, of a 133 MB one 38%, for nothing to free, since the project
is still in use.

A script that parses a project, reads it and exits can switch the collector
off:

```python
import gc

import py_aep

gc.disable()
app = py_aep.parse("show.aep")
...
```

A long-running process (a tool, a server, a farm job reading many projects)
can keep the collector but make its full passes rare while it reads, then free
the project once it holds none of its objects:

```python
import gc

import py_aep

previous = gc.get_threshold()
gc.set_threshold(100_000, 50, 1000)
try:
    app = py_aep.parse("show.aep")
    rows = read(app.project)  # plain values, no py_aep objects
finally:
    gc.set_threshold(*previous)
del app
gc.collect()  # the project's reference cycles are only freed by the collector
```

Loading and reading every property value, median of three runs:

| Project | Python | Default | `gc.disable()` | `gc.set_threshold(100_000, 50, 1000)` |
|---|---|---|---|---|
| 29 MB, 726 layers | 3.13 | 8.6 s | 6.0 s (-30%) | 6.3 s (-26%) |
| 29 MB, 726 layers | 3.7 | 13.3 s | 9.8 s (-26%) | 10.0 s (-25%) |
| 133 MB, 6993 layers | 3.13 | 60.8 s | 37.6 s (-38%) | 43.1 s (-29%) |

Peak memory was the same in every case: the collector finds nothing to free
while a project is being read. The 133 MB project was measured once.

A script that reads layer attributes only builds far fewer objects; the
collector then costs it 7% on the 29 MB project and 23% on the 133 MB one,
mostly during `parse()`.
