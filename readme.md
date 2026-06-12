# py_aep
`py_aep` is a Python package for working with After Effects AEP files.

<center><strong><a href="https://forticheprod.github.io/py-aep/">Explore the docs »</a></strong></center>


## About

After Effects files (.aep) are mostly binary files, encoded in RIFX format. This package uses [struct](https://docs.python.org/3/library/struct.html) to parse .aep files and return an Application object containing a project, items, layers, effects and properties. The API is very close to the [ExtendScript API](https://ae-scripting.docsforadobe.dev/), with a few nice additions like iterators.


## Features
### Supported
* Reading .aep files
* Modifying most properties, including some that are not accessible through ExtendScript such as gradients, render settings, output module settings, etc. (<a href="https://forticheprod.github.io/py-aep/">Differences from ExtendScript</a> for more details)
* Adding and removing keyframes on any property - including mask paths, source text, markers, orientation and gradients - with static/animated transitions matching After Effects' own output
* Adding new compositions and folders, moving items between folders
* Creating layers: solids, nulls, shapes, cameras, lights, text (point, box and vertical text)
* Removing items and layers; moving and duplicating layers
* Importing footage files and image sequences, setting proxies
* Render queue management: adding compositions, removing and duplicating items, adding output modules, applying render/output templates from the AE preferences
* Saving to a new .aep file
* Interpolation between numeric keyframe values

### Limited support
* Essential graphics: controllers and override UUIDs are exposed but automatic resolution between them is not implemented
* Properties that are synthesized by After Effects at runtime and not stored in the binary are supported but some might be missing or inaccurate
* Some Text layers attributes are missing

### Not supported
* Expression evaluation
* Runtime things such as System information, preferences, available color spaces, UI state, etc.



## Installation

### uv (recommended)
```sh
uv add py-aep
```

### pip
```sh
pip install py-aep
```


## Getting started

```python
import py_aep

app = py_aep.parse("myproject.aep")
project = app.project
comp = project.compositions[0]

# Modify composition settings
comp.frame_rate = 24

# Modify a layer property
comp.layers[0].transform.opacity.value = 50

# Save to a new file
project.save("modified.aep")
```

_For more examples, see the [Quick Start guide](https://forticheprod.github.io/py-aep/quickstart/)._


## Roadmap

See the [open issues](https://github.com/forticheprod/py-aep/issues) for a list of proposed features and known issues.

If you encounter a bug, please submit an issue and attach a basic scene to reproduce your issue.


## Contributing

See the full [Contributing Guide](https://github.com/forticheprod/py-aep/blob/main/CONTRIBUTING.md) on GitHub.


## Contact

Aurore Delaunay - github.15@audel.ovh


## Acknowledgments

* [aftereffects-py-aep in Go](https://github.com/boltframe/aftereffects-py-aep)
* [The invaluable Lottie Docs](https://github.com/hunger-zh/lottie-docs/blob/main/docs/aep.md)
* [After Effects Scripting Guide](https://ae-scripting.docsforadobe.dev/)
* [AE version parsing](https://github.com/tinogithub/aftereffects-version-check)
