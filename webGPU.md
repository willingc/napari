# WebGPU image display (experimental)

napari normally draws the canvas with **VisPy** and **OpenGL**. This optional path uses **pygfx** and **wgpu** (WebGPU-style APIs via [wgpu-native](https://github.com/gfx-rs/wgpu)) to render **2D `Image` layers** in the Qt viewer.

It is **experimental**: only a subset of features is supported, and behavior may change.

## Install

Install napari with the WebGPU extra (pulls in `pygfx`, `wgpu`, and transitive deps such as `rendercanvas`):

```bash
pip install "napari[webgpu]"
```

If you are developing from a clone of this repository:

```bash
pip install -e ".[pyqt,webgpu]"
```

Adjust the Qt extra (`pyqt`, `pyside6`, etc.) to match your environment.

### Check that dependencies resolve

```bash
python -c "from napari._qt.experimental.webgpu_image_canvas import webgpu_image_display_available; print(webgpu_image_display_available())"
```

You should see `True`. If you see `False`, the optional packages are missing or failed to import.

## Run

1. **Enable the setting** (a restart is required after changing it):
   - **GUI:** *File → Preferences → Experimental* (or *napari → Settings → Experimental* on macOS), then enable **“Use WebGPU for 2D image layers (experimental)”**.
   - **Config file:** In your napari settings YAML, under `experimental`, set:
     ```yaml
     experimental:
       webgpu_image_display: true
     ```
   - **Environment variable:** With napari’s default settings env prefix, you can try:
     ```bash
     export NAPARI_EXPERIMENTAL_WEBGPU_IMAGE_DISPLAY=true
     ```
     The field also accepts the alias `napari_webgpu_image_display` in config; exact env naming can depend on pydantic-settings version—if in doubt, use the YAML or the preferences UI.

2. **Restart napari** completely so a new `QtViewer` picks up the WebGPU canvas.

3. **Start the viewer** as usual, e.g.:

   ```bash
   napari
   ```

   or from Python:

   ```python
   import napari
   import numpy as np

   viewer = napari.Viewer()
   viewer.add_image(np.random.random((512, 512)))
   napari.run()
   ```

4. **Interaction:** With the WebGPU canvas, **left-drag** pans and the **mouse wheel** zooms, in line with the viewer camera’s mouse settings.

## Limitations

- **Layer type:** Only **`Image`** layers are supported. Adding other layer types (Points, Labels, Shapes, etc.) will raise `NotImplementedError` while WebGPU mode is on.
- **Dimensions:** **2D** viewing only (`ndisplay == 2`).
- **Multiscale:** Multiscale images are **not** supported yet.
- **Overlays:** VisPy-based canvas overlays (for example the welcome screen drawn on the GL canvas) are not replicated on the WebGPU widget; the rest of the Qt UI (layer list, dims, docks) still works.

To use the full layer set and 3D, turn **off** `webgpu_image_display` and restart.

## Test

There is no dedicated CI test file in-tree yet; you can still verify locally.

### Quick import / availability

```bash
python -c "
from napari._qt.experimental.webgpu_image_canvas import webgpu_image_display_available
assert webgpu_image_display_available(), 'Install napari[webgpu]'
print('WebGPU deps OK')
"
```

### Manual smoke test

1. Install `napari[webgpu]`, enable `webgpu_image_display`, restart.
2. Launch napari, add a 2D image (grayscale or RGB).
3. Confirm the image appears, pan/zoom works, and changing colormap / contrast updates the view.

### Optional pytest snippet

If you add a test module (for example under `src/napari/_qt/_tests/`), a minimal pattern is:

```python
import pytest

pytest.importorskip('pygfx')
pytest.importorskip('wgpu')

from napari._qt.experimental.webgpu_image_canvas import webgpu_image_display_available

def test_webgpu_optional_deps_import():
    assert webgpu_image_display_available()
```

GUI tests that construct a full `QtViewer` with WebGPU should use `pytest-qt` and will only pass when `pygfx`/`wgpu` and a working GPU stack are available; mark or skip them when those deps are absent.

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| Warning about WebGPU enabled but deps missing | Run `pip install "napari[webgpu]"` and restart. |
| `NotImplementedError` when adding a layer | WebGPU mode supports **Image** only; disable the experimental setting or use VisPy. |
| Blank or incorrect image | Confirm 2D mode, non-multiscale data; report issues with OS, GPU, and `pygfx`/`wgpu` versions. |

For implementation details, see:

- `src/napari/_qt/experimental/webgpu_image_canvas.py`
- `src/napari/_qt/experimental/webgpu_image_layer.py`
- `src/napari/_qt/qt_viewer.py` (canvas selection and layout embedding)
