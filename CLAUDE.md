# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

napari is a fast, interactive, multi-dimensional image viewer for Python. Built on Qt (via qtpy for multi-backend support), VisPy (GPU-accelerated rendering), and the scientific Python stack. Source lives in `src/napari/`.

## Architecture

### Model-View Separation

The core architectural pattern is strict model-view separation with three layers:

1. **Model Layer** (`layers/`, `components/`) - Pure Python data models with no UI dependencies
2. **Qt View** (`_qt/`) - GUI widgets and controls, accessed via `qtpy` for PyQt5/6 and PySide2/6 compatibility
3. **VisPy View** (`_vispy/`) - GPU-accelerated rendering visuals

The `Viewer` class (`viewer.py`) extends `ViewerModel` (`components/viewer_model.py`) and creates the Qt window on instantiation. Qt and VisPy are lazily imported only when a Viewer is created.

### Event System

Two event systems coexist:
- **psygnal Signals** (`from psygnal import Signal`) - Used in Layer base class and transforms for typed, field-level change notifications
- **Custom EventedModel** (`utils/events/`) - Extends pydantic BaseModel with automatic signal emission on field changes. Also provides `EventedList`, `EventedDict`, `EventedSet` containers

Event flow: Model emits events → VisPy visuals subscribe to update rendering → Qt controls subscribe to update UI

### Layer Hierarchy

Base class: `Layer` (`layers/base/base.py`) inherits `KeymapProvider`, `MousemapProvider`, `ABC`.

Concrete types: `Image`, `Labels`, `Points`, `Shapes`, `Surface`, `Tracks`, `Vectors`

Key mixins:
- `IntensityVisualizationMixin` - Colormap and contrast limit controls (used by Image, Labels)
- `ScalarFieldBase` - Base for intensity-based raster layers

Each layer type has three parallel implementations:
- `layers/<type>/` - Model (data, properties, state)
- `_vispy/layers/<type>.py` - VisPy visual (inherits `VispyBaseLayer`, connects to layer events)
- `_qt/layer_controls/qt_<type>_controls.py` - Qt controls (inherits `QtLayerControls`)

### Plugin System

Uses npe2 (napari plugin engine v2) with manifest-based plugin discovery. Plugins declare readers, writers, widgets, and sample data in YAML manifests. Integration point: `plugins/_npe2.py`.

## Development Commands

### Testing
```bash
# Run single test
pytest src/napari/layers/_tests/test_image.py::test_function_name

# Run a test file
pytest src/napari/layers/_tests/test_image.py

# Run full suite via tox (respects platform/backend matrix)
tox -e py312-macos-pyqt6-no_cov

# Run with coverage
tox -e py312-macos-pyqt6-cov
```

Tests live in `_tests/` directories alongside source code. pytest-qt is used for GUI testing. Tests use `--import-mode=importlib`.

### Code Quality
```bash
# Run all pre-commit hooks (linting + formatting)
make pre

# Run ruff only
tox -e ruff

# Type checking
make typecheck   # or: tox -e mypy
```

### Code Style
- Line length: 79 characters
- Quote style: single quotes
- Import sorting: isort via ruff with `known-first-party = ['napari']`, `combine-as-imports = true`
- Formatter: ruff-format

### Running napari
```bash
python -m napari
```

## Key Dependencies

- **qtpy** - Qt backend abstraction (supports PyQt5/6, PySide2/6)
- **vispy** - OpenGL-based scientific visualization (pinned to >=0.16.1,<0.17)
- **psygnal** - Typed signals/events
- **pydantic** - Data validation and settings (v2)
- **app-model** - Application model framework (pinned <0.6.0)
- **npe2** - Plugin engine

## Testing Notes

- Python versions: 3.10-3.14
- Qt backends tested: PyQt5, PyQt6, PySide6
- Headless test environment excludes `_vispy/`, `_qt/`, and `_tests/` directories
- mypy configured with `plugins = "pydantic.mypy"`, checks against PyQt6 stubs (`always_true = ['PYQT6']`)
- Strict warning filters: napari warnings are treated as errors in tests
