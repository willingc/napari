import numpy as np
import pint
import pytest
import zarr

from napari.components.layerlist import LayerList
from napari.layers import Image, Labels, Points, Shapes
from napari.layers._layer_actions import (
    _convert,
    _convert_dtype,
    _duplicate_layer,
    _hide_selected,
    _hide_unselected,
    _link_selected_layers,
    _merge_stack,
    _project,
    _show_selected,
    _show_unselected,
    _split_rgb,
    _split_stack,
    _toggle_visibility,
)

REG = pint.get_application_registry()


def test_split_stack():
    layer_list = LayerList()
    layer_list.append(Image(np.random.rand(8, 8, 8)))
    assert len(layer_list) == 1

    layer_list.selection.active = layer_list[0]
    _split_stack(layer_list)
    assert len(layer_list) == 8

    for idx in range(8):
        assert layer_list[idx].data.shape == (8, 8)


def test_split_rgb():
    layer_list = LayerList()
    layer_list.append(Image(np.random.random((48, 48, 3))))
    assert len(layer_list) == 1
    assert layer_list[0].rgb is True

    layer_list.selection.active = layer_list[0]
    _split_rgb(layer_list)
    assert len(layer_list) == 3

    for idx in range(3):
        assert layer_list[idx].data.shape == (48, 48)


def test_merge_stack():
    layer_list = LayerList()
    layer_list.append(Image(np.random.rand(8, 8)))
    layer_list.append(Image(np.random.rand(8, 8)))
    assert len(layer_list) == 2

    layer_list.selection.active = layer_list[0]
    layer_list.selection.add(layer_list[1])
    _merge_stack(layer_list)
    assert len(layer_list) == 1
    assert layer_list[0].data.shape == (2, 8, 8)


def test_merge_stack_rgb():
    layer_list = LayerList()
    layer_list.append(Image(np.random.rand(8, 8)))
    layer_list.append(Image(np.random.rand(8, 8)))
    layer_list.append(Image(np.random.rand(8, 8)))
    assert len(layer_list) == 3

    layer_list.selection.active = layer_list[0]
    layer_list.selection.add(layer_list[1])
    layer_list.selection.add(layer_list[2])

    # check that without R G B colormaps we warn
    with pytest.raises(ValueError, match='Missing colormap'):
        _merge_stack(layer_list, rgb=True)

    layer_list[0].colormap = 'red'
    layer_list[1].colormap = 'green'
    layer_list[2].colormap = 'blue'
    _merge_stack(layer_list, rgb=True)
    assert len(layer_list) == 1
    assert layer_list[0].data.shape == (8, 8, 3)
    assert layer_list[0].rgb is True


def test_toggle_visibility():
    """Test toggling visibility of a layer."""
    layer_list = LayerList()
    layer_list.append(Points([[0, 0]]))
    layer_list[0].visible = False

    layer_list.selection.active = layer_list[0]
    _toggle_visibility(layer_list)

    assert layer_list[0].visible is True


def test_toggle_visibility_with_linked_layers():
    """Test toggling visibility of a layer."""
    layer_list = LayerList()
    layer_list.append(Points([[0, 0]]))
    layer_list.append(Points([[0, 0]]))
    layer_list.append(Points([[0, 0]]))
    layer_list.append(Points([[0, 0]]))

    layer_list.selection.active = layer_list[0]
    layer_list.selection.add(layer_list[1])
    layer_list.selection.add(layer_list[2])

    _link_selected_layers(layer_list)

    layer_list[3].visible = False

    layer_list.selection.remove(layer_list[0])
    layer_list.selection.add(layer_list[3])

    _toggle_visibility(layer_list)

    assert layer_list[0].visible is False
    assert layer_list[1].visible is False
    assert layer_list[2].visible is False
    assert layer_list[3].visible is True


@pytest.mark.parametrize('layer_type', [Points, Shapes])
def test_duplicate_layers(layer_type):
    def _dummy():
        pass

    layer_list = LayerList()
    layer_list.append(layer_type([], name='test'))
    layer_list.selection.active = layer_list[0]
    layer_list[0].events.data.connect(_dummy)
    assert len(layer_list[0].events.data.callbacks) == 2
    assert len(layer_list) == 1
    _duplicate_layer(layer_list)
    assert len(layer_list) == 2
    assert layer_list[0].name == 'test'
    assert layer_list[1].name == 'test copy'
    assert layer_list[1].events.source is layer_list[1]
    assert (
        len(layer_list[1].events.data.callbacks) == 1
    )  # `events` Event Emitter
    assert layer_list[1].source.parent() is layer_list[0]


def test_hide_unselected_layers():
    layer_list = make_three_layer_layerlist()
    layer_list[0].visible = True
    layer_list[1].visible = True
    layer_list[2].visible = True

    layer_list.selection.active = layer_list[1]

    assert layer_list[0].visible is True
    assert layer_list[1].visible is True
    assert layer_list[2].visible is True

    _hide_unselected(layer_list)

    assert layer_list[0].visible is False
    assert layer_list[1].visible is True
    assert layer_list[2].visible is False


def test_show_unselected_layers():
    layer_list = make_three_layer_layerlist()
    layer_list[0].visible = False
    layer_list[1].visible = True
    layer_list[2].visible = True

    layer_list.selection.active = layer_list[1]

    assert layer_list[0].visible is False
    assert layer_list[1].visible is True
    assert layer_list[2].visible is True

    _show_unselected(layer_list)

    assert layer_list[0].visible is True
    assert layer_list[1].visible is True
    assert layer_list[2].visible is True


def test_hide_selected_layers():
    layer_list = make_three_layer_layerlist()
    layer_list[0].visible = False
    layer_list[1].visible = True
    layer_list[2].visible = True

    layer_list.selection.active = layer_list[0]
    layer_list.selection.add(layer_list[1])

    assert layer_list[0].visible is False
    assert layer_list[1].visible is True
    assert layer_list[2].visible is True

    _hide_selected(layer_list)

    assert layer_list[0].visible is False
    assert layer_list[1].visible is False
    assert layer_list[2].visible is True


def test_show_selected_layers():
    layer_list = make_three_layer_layerlist()
    layer_list[0].visible = False
    layer_list[1].visible = True
    layer_list[2].visible = True

    layer_list.selection.active = layer_list[0]
    layer_list.selection.add(layer_list[1])

    assert layer_list[0].visible is False
    assert layer_list[1].visible is True
    assert layer_list[2].visible is True

    _show_selected(layer_list)

    assert layer_list[0].visible is True
    assert layer_list[1].visible is True
    assert layer_list[2].visible is True


@pytest.mark.parametrize(
    'mode', ['max', 'min', 'std', 'sum', 'mean', 'median']
)
def test_projections(mode):
    ll = LayerList()
    ll.append(
        Image(
            np.random.rand(7, 8, 8),
            scale=(3, 2, 2),
            translate=(10, 5, 5),
            units=('nm', 'um', 'um'),
            axis_labels=('z', 'y', 'x'),
        )
    )
    assert len(ll) == 1
    assert ll[-1].data.ndim == 3
    _project(ll, mode=mode)
    assert len(ll) == 2
    # because keepdims = False
    assert ll[-1].data.shape == (8, 8)
    assert tuple(ll[-1].scale) == (2, 2)
    assert tuple(ll[-1].translate) == (5, 5)
    assert ll[-1].units == (REG.um, REG.um)
    assert ll[-1].axis_labels == ('y', 'x')


@pytest.mark.parametrize(
    'mode',
    ['int8', 'int16', 'int32', 'int64', 'uint8', 'uint16', 'uint32', 'uint64'],
)
def test_convert_dtype(mode):
    ll = LayerList()
    data = np.zeros((10, 10), dtype=np.int16)
    ll.append(Labels(data))
    assert ll[-1].data.dtype == np.int16

    data[5, 5] = 1000
    assert data[5, 5] == 1000
    if mode == 'int8' or mode == 'uint8':
        # label value 1000 is outside of the target data type range.
        with pytest.raises(AssertionError):
            _convert_dtype(ll, mode=mode)
        assert ll[-1].data.dtype == np.int16
    else:
        _convert_dtype(ll, mode=mode)
        assert ll[-1].data.dtype == np.dtype(mode)

    assert ll[-1].data[5, 5] == 1000
    assert ll[-1].data.flatten().sum() == 1000


@pytest.mark.filterwarnings('ignore:projection mode :UserWarning')
@pytest.mark.parametrize(
    ('layer', 'type_'),
    [
        (Image(np.random.rand(10, 10)), 'labels'),
        (Image(np.array([[1.5, 2.5], [3.5, 4.5]])), 'labels'),
        (Image(np.array([[1, 2], [3, 4]], dtype=(int))), 'labels'),
        (
            Image(zarr.array([[1, 2], [3, 4]], dtype=(int), chunks=(1, 2))),
            'labels',
        ),
        (Labels(np.ones((10, 10), dtype=int)), 'image'),
        (Shapes([np.array([[0, 0], [0, 10], [10, 0], [10, 10]])]), 'labels'),
    ],
)
def test_convert_layer(layer, type_):
    ll = LayerList()
    layer.scale *= 1.5
    original_scale = layer.scale.copy()
    ll.append(layer)
    assert ll[0]._type_string != type_
    _convert(ll, 'labels')
    if isinstance(layer, Shapes) or (
        type_ == 'labels'
        and isinstance(layer, Image)
        and np.issubdtype(layer.data.dtype, float)
    ):
        assert ll[1]._type_string == type_
        assert np.array_equal(ll[1].scale, original_scale)
    else:
        assert (
            layer.data is ll[0].data
        )  # check array data not copied unnecessarily


def test_convert_warns_with_projecton_mode():
    # inplace
    ll = LayerList(
        [Image(np.random.rand(10, 10).astype(int), projection_mode='mean')]
    )
    with pytest.warns(UserWarning, match='projection mode'):
        _convert(ll, 'labels')
    assert isinstance(ll['Image'], Labels)
    # not inplace
    ll = LayerList([Image(np.random.rand(10, 10), projection_mode='mean')])
    with pytest.warns(UserWarning, match='projection mode'):
        _convert(ll, 'labels')
    assert isinstance(ll['Image [1]'], Labels)


def make_three_layer_layerlist():
    layer_list = LayerList()
    layer_list.append(Points([[0, 0]], name='test'))
    layer_list.append(Image(np.random.rand(8, 8, 8)))
    layer_list.append(Image(np.random.rand(8, 8, 8)))

    return layer_list
