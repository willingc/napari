import pytest

from napari._pydantic_compat import ValidationError
from napari.layers import Points
from napari.layers._source import Source, current_source, layer_source


def test_layer_source():
    """Test basic layer source assignment mechanism"""
    with layer_source(path='some_path', reader_plugin='napari'):
        points = Points()

    assert points.source == Source(path='some_path', reader_plugin='napari')


def test_cant_overwrite_source():
    """Test that we can't overwrite the source of a layer."""
    with layer_source(path='some_path', reader_plugin='napari'):
        points = Points()
    assert points.source == Source(path='some_path', reader_plugin='napari')
    with pytest.raises(ValueError, match='Tried to set source on layer'):
        points._set_source(
            Source(path='other_path', reader_plugin='other_plugin')
        )


def test_source_context():
    """Test nested contexts, overrides, and resets."""

    assert current_source() == Source()
    # everything created within this context will have this sample source
    with layer_source(sample=('samp', 'name')):
        assert current_source() == Source(sample=('samp', 'name'))
        # nested contexts override previous ones
        with layer_source(path='a', reader_plugin='plug'):
            assert current_source() == Source(
                path='a', reader_plugin='plug', sample=('samp', 'name')
            )
            # note the new path now...
            with layer_source(path='b'):
                assert current_source() == Source(
                    path='b', reader_plugin='plug', sample=('samp', 'name')
                )
                # as we exit the contexts, they should undo their assignments
            assert current_source() == Source(
                path='a', reader_plugin='plug', sample=('samp', 'name')
            )
        assert current_source() == Source(sample=('samp', 'name'))

        point = Points()
        with layer_source(parent=point):
            assert current_source() == Source(
                sample=('samp', 'name'), parent=point
            )
    assert current_source() == Source()


def test_source_assert_parent():
    assert current_source() == Source()
    with pytest.raises(ValidationError), layer_source(parent=''):
        current_source()
    assert current_source() == Source()
