# Quick Start

## Parse a project

```python
import py_aep

app = py_aep.parse("myproject.aep")
project = app.project

print(f"AE version: {app.version}")
print(f"Bits per channel: {project.bits_per_channel}")
```

## Iterate over items and layers

```python
for item in project:
    print(f"{item.name} ({type(item).__name__})")

for comp in project.compositions:
    print(f"Composition: {comp.name} ({comp.width}x{comp.height})")
    for layer in comp:
        print(f"  Layer: {layer.name}")
```

## Access layer properties

```python
layer = comp.layers[0]
transform = layer.property("ADBE Transform Group")  # By match name
opacity = transform.opacity  # Or using attributes
print(f"Opacity: {opacity.value}")

# Check for keyframes
if opacity.is_time_varying:
    for kf in opacity.keyframes:
        print(f"  Key at {kf.time}s: {kf.value}")
```

## Access footage sources

```python
for layer in comp.footage_layers:
    print(f"  File: {layer.source.file}")
```

## Inspect the render queue

```python
for rq_item in project.render_queue:
    print(f"Status: {rq_item.status}")
    print(f"Settings: {rq_item.settings}")
    for om in rq_item:
        print(f"  Format: {om.settings['Format']}")
```

## Modify and save

```python
app = py_aep.parse("myproject.aep")
project = app.project
comp = project.compositions[0]

# Change composition settings
comp.name = "Final Comp"
comp.frame_rate = 30

# Modify a layer property
layer = comp.layers[0]
opacity = layer.transform.opacity
opacity.value = 50

# Save to a new file (produces a byte-identical RIFX structure)
project.save("modified.aep")
```

## Add and remove keyframes

`add_key`, `set_value_at_time` and `remove_key` work on every property
kind - numeric, color, mask paths, source text, markers, orientation and
gradients. The first keyframe converts a static property to an animated
one; removing the last keyframe reverts it to a static value.

```python
opacity = layer.transform.opacity
opacity.set_value_at_time(0.0, 0)
opacity.set_value_at_time(1.0, 100)

# Source text keyframes
source_text = layer["ADBE Text Properties"]["ADBE Text Document"]
source_text.set_value_at_time(0.0, "Hello")
source_text.set_value_at_time(2.0, "World")

# Layer markers (a string is shorthand for a comment-only marker)
layer["ADBE Marker"].set_value_at_time(1.0, "first marker")

# Revert to static
opacity.remove_key(1)
opacity.remove_key(0)  # opacity is static again, holding value 0
```

## Create layers

```python
solid = comp.add_solid([1.0, 0.0, 0.0], "Red Solid", 1920, 1080, 1.0)
null = comp.add_null()
shape = comp.add_shape()
camera = comp.add_camera("Camera 1", [960.0, 540.0])
light = comp.add_light("Key Light", [960.0, 540.0])
text = comp.add_text("Hello World")
box = comp.add_box_text([400, 200], "Boxed text")
```

## Import footage

```python
from py_aep import ImportOptions

footage = project.import_file(ImportOptions("render.png"))
comp.add(footage)  # add it as a layer
```

## Add to the render queue

Adding render queue items needs the render/output templates from the
After Effects user preferences directory:

```python
app = py_aep.parse("myproject.aep", ae_preferences_dir=prefs_dir)
project = app.project

rq_item = project.render_queue.add(project.compositions[0])
rq_item.apply_template("Best Settings")
om = rq_item.output_modules[0]
om.apply_template("High Quality with Alpha")
om.file_template = "[compName]_[#####].tif"

project.save("queued.aep")
```
