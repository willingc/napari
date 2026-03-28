"""Image layer visual backed by pygfx (WebGPU via wgpu-native)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pint
from psygnal import Signal

from napari._vispy.utils.gl import fix_data_dtype
from napari.layers.image.image import Image
from napari.utils.colormaps.colormap_utils import _coerce_contrast_limits
from napari.utils.events import disconnect_events
from napari.utils.translations import trans

if TYPE_CHECKING:
    from napari._qt.experimental.webgpu_image_canvas import WebGPUImageCanvas


class _WebGPUImageLayerEvents:
    loaded = Signal()


class WebGPUImageLayerVisual:
    """Bridges a napari Image layer to a pygfx Image in :class:`WebGPUImageCanvas`."""

    def __init__(self, layer: Image, canvas: WebGPUImageCanvas) -> None:
        self.events = _WebGPUImageLayerEvents()
        self.layer = layer
        self._canvas = canvas
        self._order = 0
        self.first_visible = True
        self._world_units = layer.units
        self._world_to_layer_units_scale = (1.0,) * layer.ndim

        self.layer.events.set_data.connect(self._on_data_or_display_change)
        self.layer.events.colormap.connect(self._on_colormap_change)
        self.layer.events.contrast_limits.connect(
            self._on_contrast_limits_change
        )
        self.layer.events.gamma.connect(self._on_gamma_change)
        self.layer.events.visible.connect(self._on_visible_change)
        self.layer.events.scale.connect(self._on_matrix_change)
        self.layer.events.translate.connect(self._on_matrix_change)
        self.layer.events.rotate.connect(self._on_matrix_change)
        self.layer.events.shear.connect(self._on_matrix_change)
        self.layer.events.affine.connect(self._on_matrix_change)
        self.layer.events.depiction.connect(self._on_display_change)
        self.layer.events.rendering.connect(self._on_display_change)
        self.layer.events.units.connect(self._recalculate_units_scale)
        canvas.viewer.layers.events.units.connect(
            self._recalculate_units_scale
        )

        self._recalculate_units_scale()
        self._on_display_change()
        self._on_data_or_display_change()
        self._on_colormap_change()
        self._on_contrast_limits_change()
        self._on_gamma_change()
        self._on_visible_change()
        self._on_matrix_change()

    @property
    def order(self) -> int:
        return self._order

    @order.setter
    def order(self, value: int) -> None:
        self._order = int(value)

    @property
    def world_units(self):
        return self._world_units

    @world_units.setter
    def world_units(self, value) -> None:
        if value is None:
            self._world_units = self.layer.units
            self._world_to_layer_units_scale = (1.0,) * self.layer.ndim
        else:
            self._world_units = value[-self.layer.ndim :]
            self._recalculate_units_scale()
        self._on_matrix_change()

    @property
    def node(self):
        """VisPy-compatible attribute; layer overlays are not supported for WebGPU."""

        class _Node:
            parent = None
            children = ()

        return _Node()

    def _recalculate_units_scale(self, _event=None) -> None:
        reg = pint.get_application_registry()
        extent_units = self._canvas.viewer.layers.extent.units
        if extent_units is None:
            self._world_to_layer_units_scale = (1.0,) * self.layer.ndim
            return
        wu = extent_units[-self.layer.ndim :]
        self._world_to_layer_units_scale = tuple(
            float(reg.get_base_units(y)[0] / reg.get_base_units(x)[0])
            for x, y in zip(wu, self.layer.units, strict=False)
        )

    def _on_poll(self) -> None:
        return

    def close(self) -> None:
        disconnect_events(self.layer.events, self)
        disconnect_events(self._canvas.viewer.layers.events, self)
        self._canvas.remove_layer_visual(self)

    def _on_visible_change(self, _event=None) -> None:
        self._canvas.set_layer_visible(self.layer, self.layer.visible)

    def _on_display_change(self, _event=None) -> None:
        if self.layer._slice_input.ndisplay != 2:
            raise NotImplementedError(
                trans._(
                    'WebGPU image display is only implemented for 2D (ndisplay=2).'
                )
            )
        if self.layer.multiscale:
            raise NotImplementedError(
                trans._(
                    'WebGPU image display does not yet support multiscale images.'
                )
            )

    def _on_data_or_display_change(self, _event=None) -> None:
        self._on_display_change()
        data = fix_data_dtype(self.layer._data_view)
        if self.layer.rgb:
            if data.ndim != 3 or data.shape[-1] not in (3, 4):
                return
        elif data.ndim != 2:
            return
        self._canvas.update_layer_image(
            self.layer, data, self._world_to_layer_units_scale
        )
        self._on_matrix_change()
        self.events.loaded.emit()

    def _on_colormap_change(self, _event=None) -> None:
        self._canvas.update_layer_colormap(self.layer)

    def _on_contrast_limits_change(self, _event=None) -> None:
        cl = _coerce_contrast_limits(
            self.layer.contrast_limits
        ).contrast_limits
        self._canvas.update_layer_contrast_limits(self.layer, cl)

    def _on_gamma_change(self, _event=None) -> None:
        self._canvas.update_layer_gamma(self.layer, self.layer.gamma)

    def _on_matrix_change(self, _event=None) -> None:
        matrix = _layer_to_model_matrix(
            self.layer, self._world_to_layer_units_scale
        )
        self._canvas.update_layer_transform(self.layer, matrix)

    def _on_blending_change(self, _event=None) -> None:
        return

    def _on_camera_move(self, _event=None) -> None:
        return


def _layer_to_model_matrix(
    layer: Image, world_to_layer_units_scale: tuple[float, ...]
) -> np.ndarray:
    """Match VisPy placement (see VispyBaseLayer._on_matrix_change)."""
    dims_displayed = layer._slice_input.displayed
    transform = layer._transforms.simplified.set_slice(dims_displayed)
    units_scale = [world_to_layer_units_scale[x] for x in dims_displayed][::-1]
    translate = transform.translate[::-1] * units_scale
    matrix = transform.linear_matrix[::-1, ::-1].T * units_scale

    affine_matrix = np.eye(4, dtype=np.float32)
    affine_matrix[: matrix.shape[0], : matrix.shape[1]] = matrix
    affine_matrix[-1, : len(translate)] = translate

    if layer._slice_input.ndisplay == 2:
        offset_matrix = layer._data_to_world.set_slice(
            dims_displayed
        ).linear_matrix
        offset = -offset_matrix @ np.ones(offset_matrix.shape[1]) / 2
        affine_offset = np.eye(4, dtype=np.float32)
        affine_offset[-1, : len(offset)] = offset[::-1] * units_scale
        affine_matrix = affine_matrix @ affine_offset

    return affine_matrix
