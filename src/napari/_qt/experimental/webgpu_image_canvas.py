"""Experimental Qt canvas that draws Image layers with WebGPU (pygfx / wgpu)."""

from __future__ import annotations

import contextlib
import weakref
from types import SimpleNamespace
from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import QPointF, Qt, Signal
from qtpy.QtGui import QImage
from qtpy.QtWidgets import QVBoxLayout, QWidget

from napari.utils.colormaps.standardize_color import transform_color
from napari.utils.events import disconnect_events
from napari.utils.theme import get_theme
from napari.utils.translations import trans

if TYPE_CHECKING:
    from napari._vispy.utils.qt_font import QtFontManager
    from napari.components.viewer_model import ViewerModel
    from napari.layers.image.image import Image
    from napari.utils.key_bindings import KeymapHandler


def webgpu_image_display_available() -> bool:
    """Return True if optional WebGPU (pygfx + wgpu + rendercanvas) dependencies import."""
    try:
        import pygfx  # noqa: F401
        import rendercanvas  # noqa: F401
        import wgpu  # noqa: F401
    except ImportError:
        return False
    return True


def _dispatch_qt_key(emitter, qtev) -> None:
    """Translate Qt key events like VisPy's Qt backend."""
    from vispy import keys
    from vispy.app.backends._qt import KEYMAP

    key = int(qtev.key())
    if key in KEYMAP:
        vkey = KEYMAP[key]
    elif 32 <= key <= 127:
        vkey = keys.Key(chr(key))
    else:
        vkey = None

    qt_keyboard_modifiers = Qt.KeyboardModifier
    mod = ()
    for q, v in (
        (qt_keyboard_modifiers.ShiftModifier, keys.SHIFT),
        (qt_keyboard_modifiers.ControlModifier, keys.CONTROL),
        (qt_keyboard_modifiers.AltModifier, keys.ALT),
        (qt_keyboard_modifiers.MetaModifier, keys.META),
    ):
        if qtev.modifiers() & q:
            mod += (v,)

    emitter(native=qtev, key=vkey, text=str(qtev.text()), modifiers=mod)


class _SceneBackendShim:
    """Provides ``_keyEvent`` for :class:`QtViewer` / main window forwarding."""

    def __init__(self, canvas: WebGPUImageCanvas) -> None:
        self._canvas = canvas

    def _keyEvent(self, func, ev) -> None:
        _dispatch_qt_key(func, ev)


class _KeyboardEventEmitter:
    """Stand-in for ``vispy.app.canvas.Canvas.events.key_*``."""

    def __init__(self) -> None:
        self._handlers: list = []

    def connect(self, handler, *args, **kwargs) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    def __call__(self, **kwargs) -> None:
        ev = SimpleNamespace(**kwargs)
        for h in self._handlers:
            h(ev)


class _SceneCanvasShim:
    def __init__(self, canvas: WebGPUImageCanvas) -> None:
        self._backend = _SceneBackendShim(canvas)
        self.events = SimpleNamespace(
            key_press=canvas._key_press_emitter,
            key_release=canvas._key_release_emitter,
        )


class _Stub3DCamera:
    depth_value = 1.0


class _WebGPUCameraStub:
    """Satisfies ``QtViewer._update_camera_depth`` (3D path mutates ``depth_value``)."""

    def __init__(self) -> None:
        self._3D_camera = _Stub3DCamera()


class _CanvasHost(QWidget):
    """Hosts the render widget and matches VisPy ``native`` (``resized``, ``grabFramebuffer``)."""

    resized = Signal()

    def __init__(
        self, render_widget: QWidget, canvas_weak: weakref.ReferenceType
    ) -> None:
        super().__init__()
        self._canvas_ref = canvas_weak
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(render_widget, stretch=1)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def resizeEvent(self, event) -> None:
        self.resized.emit()
        super().resizeEvent(event)
        c = self._canvas_ref()
        if c is not None:
            c._on_host_resize()

    def grabFramebuffer(self) -> QImage:
        return self.grab()

    def wheelEvent(self, event) -> None:
        c = self._canvas_ref()
        if c is None:
            return super().wheelEvent(event)
        if not c.viewer.camera.mouse_zoom:
            return super().wheelEvent(event)
        delta = event.angleDelta().y()
        if delta == 0:
            return None
        factor = 1.1 if delta > 0 else 1 / 1.1
        c.viewer.camera.zoom = float(c.viewer.camera.zoom * factor)
        event.accept()
        c._renderer.request_draw()
        return None

    def mousePressEvent(self, event) -> None:
        self._press_pos = QPointF(event.position())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        c = self._canvas_ref()
        if (
            c is not None
            and c.viewer.camera.mouse_pan
            and event.buttons() & Qt.MouseButton.LeftButton
            and hasattr(self, '_press_pos')
        ):
            pos = QPointF(event.position())
            delta = pos - self._press_pos
            self._press_pos = pos
            h, w = c.size
            if w <= 0 or h <= 0:
                return super().mouseMoveEvent(event)
            zoom = float(c.viewer.camera.zoom)
            dz, cy, cx = c.viewer.camera.center
            cx -= float(delta.x()) / zoom
            cy -= float(delta.y()) / zoom
            c.viewer.camera.center = (dz, cy, cx)
            c._renderer.request_draw()
            event.accept()
            return None
        super().mouseMoveEvent(event)
        return None


class WebGPUImageCanvas:
    """Canvas for 2D :class:`~napari.layers.Image` layers using WebGPU (experimental)."""

    embed_in_qt_layout = True

    def __init__(
        self,
        viewer: ViewerModel,
        key_map_handler: KeymapHandler,
        font_manager: QtFontManager,
        font_family: str,
        *args,
        parent=None,
        size=(600, 800),
        autoswap: bool = False,
        **kwargs,
    ) -> None:
        del font_manager, font_family, autoswap
        if not webgpu_image_display_available():
            raise RuntimeError(
                trans._(
                    'WebGPU image display requires optional dependencies. '
                    'Install with: pip install "napari[webgpu]"'
                )
            )

        import pygfx as gfx
        from pygfx.renderers import WgpuRenderer
        from rendercanvas.qt import QRenderWidget

        self.viewer = viewer
        self._key_map_handler = key_map_handler
        self._key_press_emitter = _KeyboardEventEmitter()
        self._key_release_emitter = _KeyboardEventEmitter()
        self._scene_canvas = _SceneCanvasShim(self)

        self._render_widget = QRenderWidget(parent=None)
        self._renderer = WgpuRenderer(self._render_widget)

        self._weak_self = weakref.ref(self)
        self.native = _CanvasHost(self._render_widget, self._weak_self)
        self.native.setParent(parent)

        self.destroyed = self._render_widget.destroyed

        self.camera = _WebGPUCameraStub()
        self.grid_cameras = []

        self.layer_to_visual = {}
        self._layer_gfx: dict = {}

        self._scene = gfx.Scene()
        self._gfx_camera = gfx.OrthographicCamera(1, 1, maintain_aspect=False)
        self._scene.add(self._gfx_camera)

        bg = transform_color(get_theme(viewer.theme).canvas.as_hex())[0]
        self._bg = gfx.Background.from_color(tuple(bg[:3]))
        self._scene.add(self._bg)

        viewer.events.theme.connect(self._on_theme_change)
        viewer.camera.events.zoom.connect(self._request_draw)
        viewer.camera.events.center.connect(self._request_draw)
        viewer.camera.events.angles.connect(self._request_draw)

        self._key_press_emitter.connect(key_map_handler.on_key_press)
        self._key_release_emitter.connect(key_map_handler.on_key_release)

        self._render_widget.add_event_handler(self._draw, 'before_draw')

        viewer.layers.events.removed.connect(self._on_layer_removed)
        viewer.layers.events.reordered.connect(self._sync_layer_draw_order)

        self.size = size
        self.max_texture_sizes = (8192, 2048)
        self._background_color_override = None
        self._last_theme_color = bg

    @property
    def bgcolor(self) -> str:
        return get_theme(self.viewer.theme).canvas.as_hex()

    @bgcolor.setter
    def bgcolor(self, value) -> None:
        self._last_theme_color = transform_color(value)[0]
        self._refresh_background_color()

    def _refresh_background_color(self) -> None:
        import pygfx as gfx

        c = self._background_color_override or self._last_theme_color
        rgb = tuple(np.asarray(c)[:3].astype(float))
        self._bg.material = gfx.BackgroundMaterial(rgb)
        self._renderer.request_draw()

    def _on_theme_change(self, event) -> None:
        self._set_theme_color_from_name(event.value)

    def _set_theme_color_from_name(self, theme: str) -> None:
        bg = transform_color(get_theme(theme).canvas.as_hex())[0]
        self._last_theme_color = bg
        if self._background_color_override is None:
            self._refresh_background_color()

    @property
    def background_color_override(self):
        return self._background_color_override

    @background_color_override.setter
    def background_color_override(self, value) -> None:
        self._background_color_override = value
        self._refresh_background_color()

    def _set_theme_change(self, theme: str) -> None:
        self._set_theme_color_from_name(theme)

    @property
    def size(self) -> tuple[int, int]:
        return (self.native.height(), self.native.width())

    @size.setter
    def size(self, value: tuple[int, int]) -> None:
        h, w = int(value[0]), int(value[1])
        self.native.resize(w, h)

    def screen_changed(self, *args) -> None:
        self._renderer.request_draw()

    def _request_draw(self, *args) -> None:
        self._renderer.request_draw()

    @property
    def view(self):
        class _V:
            interactive = True
            scene = self._scene
            children = ()

        return _V()

    def delete(self) -> None:
        disconnect_events(self.viewer.camera.events, self)
        disconnect_events(self.viewer.layers.events, self)
        disconnect_events(self.viewer.events, self)
        self.native.deleteLater()

    def on_draw(self, _event) -> None:
        self._renderer.request_draw()

    def _on_host_resize(self) -> None:
        self.viewer._canvas_size = self.size
        self._renderer.request_draw()

    def _sync_camera(self) -> None:
        h, w = self.size
        if w < 1 or h < 1:
            return
        zoom = float(self.viewer.camera.zoom)
        world_w = w / zoom
        world_h = h / zoom
        _, cy, cx = self.viewer.camera.center
        left = cx - world_w / 2
        right = cx + world_w / 2
        top = cy - world_h / 2
        bottom = cy + world_h / 2
        self._gfx_camera.show_rect(
            left, right, top, bottom, view_dir=(0, 0, -1), up=(0, -1, 0)
        )
        self._gfx_camera.maintain_aspect = False

    def _draw(self, *args) -> None:
        self._sync_camera()
        h, w = self.size
        if w < 1 or h < 1:
            return
        self._renderer.render(
            self._scene, self._gfx_camera, rect=(0, 0, w, h), flush=False
        )
        self._renderer.flush()

    def screenshot(self) -> QImage:
        self._draw()
        return self.native.grabFramebuffer()

    def _on_layer_removed(self, event) -> None:
        layer = event.value
        if layer not in self.layer_to_visual:
            return
        self.layer_to_visual[layer].close()

    def _sync_layer_draw_order(self, event=None) -> None:
        for i, layer in enumerate(self.viewer.layers):
            g = self._layer_gfx.get(layer)
            if g is not None:
                g.render_order = i
        self._renderer.request_draw()

    def add_layer_visual_mapping(self, napari_layer, visual) -> None:
        from napari.layers import Image

        if not isinstance(napari_layer, Image):
            raise NotImplementedError(
                trans._(
                    'WebGPU display supports Image layers only; got {layer_type}',
                    layer_type=type(napari_layer).__name__,
                )
            )
        self.layer_to_visual[napari_layer] = visual
        napari_layer.events.visible.connect(self._sync_layer_draw_order)
        self._sync_layer_draw_order()

    def remove_layer_visual(self, visual) -> None:
        layer = visual.layer
        with contextlib.suppress(TypeError, RuntimeError):
            layer.events.visible.disconnect(self._sync_layer_draw_order)
        if layer in self.layer_to_visual:
            del self.layer_to_visual[layer]
        g = self._layer_gfx.pop(layer, None)
        if g is not None:
            self._scene.remove(g)
        self._renderer.request_draw()

    def update_layer_image(
        self,
        layer: Image,
        data: np.ndarray,
        world_to_layer_units_scale: tuple[float, ...],
    ) -> None:
        import pygfx as gfx

        from napari._qt.experimental.webgpu_image_layer import (
            _layer_to_model_matrix,
        )

        is_rgb = layer.rgb
        if is_rgb:
            if data.dtype != np.uint8:
                d = np.clip(data, 0, 255).astype(np.uint8)
            else:
                d = np.ascontiguousarray(data)
            if d.shape[-1] == 3:
                rgba = np.concatenate(
                    [d, np.full(d.shape[:2] + (1,), 255, dtype=np.uint8)],
                    axis=-1,
                )
            else:
                rgba = d
            tex = gfx.Texture(rgba, dim=2, format='4xu8', colorspace='srgb')
            material = gfx.ImageBasicMaterial(interpolation='nearest')
        else:
            d = np.ascontiguousarray(data.astype(np.float32, copy=False))
            tex = gfx.Texture(d, dim=2, format='1xf4')
            lut = _colormap_texture(layer)
            material = gfx.ImageBasicMaterial(
                map=lut,
                maprange=(
                    float(layer.contrast_limits[0]),
                    float(layer.contrast_limits[1]),
                ),
                gamma=float(layer.gamma),
                interpolation='nearest',
            )

        geom = gfx.Geometry(grid=tex)
        img = gfx.Image(geom, material)
        img.local.matrix = _layer_to_model_matrix(
            layer, world_to_layer_units_scale
        )

        old = self._layer_gfx.pop(layer, None)
        if old is not None:
            self._scene.remove(old)
        self._layer_gfx[layer] = img
        self._scene.add(img)
        self._sync_layer_draw_order()
        self._renderer.request_draw()

    def update_layer_colormap(self, layer: Image) -> None:
        if layer.rgb or layer not in self._layer_gfx:
            return
        g = self._layer_gfx[layer]
        g.material.map = _colormap_texture(layer)
        self._renderer.request_draw()

    def update_layer_contrast_limits(self, layer: Image, clims) -> None:
        if layer.rgb or layer not in self._layer_gfx:
            return
        g = self._layer_gfx[layer]
        g.material.maprange = (float(clims[0]), float(clims[1]))
        self._renderer.request_draw()

    def update_layer_gamma(self, layer: Image, gamma: float) -> None:
        if layer.rgb or layer not in self._layer_gfx:
            return
        g = self._layer_gfx[layer]
        g.material.gamma = float(gamma)
        self._renderer.request_draw()

    def update_layer_transform(self, layer: Image, matrix: np.ndarray) -> None:
        if layer not in self._layer_gfx:
            return
        self._layer_gfx[layer].local.matrix = matrix.astype(
            np.float32, copy=False
        )
        self._renderer.request_draw()

    def set_layer_visible(self, layer: Image, visible: bool) -> None:
        if layer in self._layer_gfx:
            self._layer_gfx[layer].visible = visible
            self._renderer.request_draw()


def _colormap_texture(layer: Image):
    import pygfx as gfx

    cmap = layer.colormap
    colors = np.asarray(cmap.colors.data, dtype=np.float32)
    if colors.max() > 1.0:
        colors = colors / 255.0
    rgba = np.concatenate(
        [colors[:, :3], np.ones((len(colors), 1), dtype=np.float32)], axis=1
    )
    rgba = np.ascontiguousarray(rgba)
    return gfx.Texture(rgba, dim=1, format='4xf32', colorspace='srgb')
