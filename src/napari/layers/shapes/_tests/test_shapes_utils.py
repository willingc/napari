import os

import numpy as np
import pytest
from numpy import array, testing as npt

from napari.layers.shapes._accelerated_triangulate_python import (
    generate_2D_edge_meshes_py,
    is_convex_py,
    normalize_vertices_and_edges_py,
    reconstruct_polygons_from_edges_py,
)
from napari.layers.shapes._shapes_utils import (
    _save_failed_triangulation,
    get_default_shape_type,
    number_of_shapes,
    perpendicular_distance,
    rdp,
    reconstruct_and_triangulate_edge,
    triangulate_face_and_edges,
    triangulate_face_vispy,
)

W_DATA = [[0, 3], [1, 0], [2, 3], [5, 0], [2.5, 5]]

line_points = [
    (np.array([0, 0]), np.array([0, 3]), np.array([1, 0])),
    (np.array([0, 0, 0]), np.array([0, 0, 3]), np.array([1, 0, 0])),
    (
        np.array([0, 0, 0, 0]),
        np.array([0, 0, 3, 0]),
        np.array([1, 0, 0, 0]),
    ),
    (np.array([0, 0, 0]), np.array([0, 0, 0]), np.array([1, 0, 0])),
]


def _regen_testcases():
    """
    In case the below test cases need to be update here
    is a simple function you can run to regenerate the `cases` variable below.
    """
    exec(
        """
from napari.layers.shapes._tests.test_shapes_utils import (
    generate_2D_edge_meshes,
    W_DATA,
)


mesh_cases = [
    (W_DATA, False, 3, False),
    (W_DATA, True, 3, False),
    (W_DATA, False, 3, True),
    (W_DATA, True, 3, True),
]


s = '['
for args in mesh_cases:
    cot = generate_2D_edge_meshes(*args)
    s = s + str(['W_DATA', *args[1:], cot]) + ','
s += ']'
s = s.replace("'W_DATA'", 'W_DATA')
print(s)
"""
    )


cases = [
    [
        W_DATA,
        False,
        3,
        False,
        (
            array(
                [
                    [0.0, 3.0],
                    [0.0, 3.0],
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [2.0, 3.0],
                    [2.0, 3.0],
                    [5.0, 0.0],
                    [5.0, 0.0],
                    [2.5, 5.0],
                    [2.5, 5.0],
                    [1.0, 0.0],
                    [5.0, 0.0],
                ]
            ),
            array(
                [
                    [0.47434165, 0.15811388],
                    [-0.47434165, -0.15811388],
                    [-0.0, 0.5],
                    [-0.47434165, -0.15811388],
                    [-0.21850801, 0.92561479],
                    [0.21850801, -0.92561479],
                    [-0.29235514, 0.40562109],
                    [-0.35355339, -0.35355339],
                    [-0.4472136, -0.2236068],
                    [0.4472136, 0.2236068],
                    [0.47434165, -0.15811388],
                    [0.4472136, 0.2236068],
                ]
            ),
            array(
                [
                    [0, 1, 3],
                    [0, 3, 2],
                    [2, 10, 5],
                    [2, 5, 4],
                    [4, 5, 7],
                    [4, 7, 6],
                    [6, 11, 9],
                    [6, 9, 8],
                    [10, 2, 3],
                    [11, 6, 7],
                ]
            ),
        ),
    ],
    [
        W_DATA,
        True,
        3,
        False,
        (
            array(
                [
                    [0.0, 3.0],
                    [0.0, 3.0],
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [2.0, 3.0],
                    [2.0, 3.0],
                    [5.0, 0.0],
                    [5.0, 0.0],
                    [2.5, 5.0],
                    [2.5, 5.0],
                    [0.0, 3.0],
                    [0.0, 3.0],
                    [1.0, 0.0],
                    [5.0, 0.0],
                ]
            ),
            array(
                [
                    [0.58459244, -0.17263848],
                    [-0.58459244, 0.17263848],
                    [-0.0, 0.5],
                    [-0.47434165, -0.15811388],
                    [-0.21850801, 0.92561479],
                    [0.21850801, -0.92561479],
                    [-0.29235514, 0.40562109],
                    [-0.35355339, -0.35355339],
                    [-0.17061484, -0.7768043],
                    [0.17061484, 0.7768043],
                    [0.58459244, -0.17263848],
                    [-0.58459244, 0.17263848],
                    [0.47434165, -0.15811388],
                    [0.4472136, 0.2236068],
                ]
            ),
            array(
                [
                    [0, 1, 3],
                    [0, 3, 2],
                    [2, 12, 5],
                    [2, 5, 4],
                    [4, 5, 7],
                    [4, 7, 6],
                    [6, 13, 9],
                    [6, 9, 8],
                    [8, 9, 11],
                    [8, 11, 10],
                    [12, 2, 3],
                    [13, 6, 7],
                ]
            ),
        ),
    ],
    [
        W_DATA,
        False,
        3,
        True,
        (
            array(
                [
                    [0.0, 3.0],
                    [0.0, 3.0],
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [2.0, 3.0],
                    [2.0, 3.0],
                    [5.0, 0.0],
                    [5.0, 0.0],
                    [2.5, 5.0],
                    [2.5, 5.0],
                    [0.0, 3.0],
                    [1.0, 0.0],
                    [2.0, 3.0],
                    [5.0, 0.0],
                ]
            ),
            array(
                [
                    [0.47434165, 0.15811388],
                    [-0.47434165, -0.15811388],
                    [-0.0, 0.5],
                    [-0.47434165, -0.15811388],
                    [-0.47434165, 0.15811388],
                    [0.11487646, -0.48662449],
                    [-0.29235514, 0.40562109],
                    [-0.35355339, -0.35355339],
                    [-0.4472136, -0.2236068],
                    [0.4472136, 0.2236068],
                    [0.47434165, 0.15811388],
                    [0.47434165, -0.15811388],
                    [0.35355339, 0.35355339],
                    [0.4472136, 0.2236068],
                ]
            ),
            array(
                [
                    [10, 1, 3],
                    [10, 3, 2],
                    [2, 11, 5],
                    [2, 5, 4],
                    [12, 5, 7],
                    [12, 7, 6],
                    [6, 13, 9],
                    [6, 9, 8],
                    [0, 1, 10],
                    [11, 2, 3],
                    [4, 5, 12],
                    [13, 6, 7],
                ]
            ),
        ),
    ],
    [
        W_DATA,
        True,
        3,
        True,
        (
            array(
                [
                    [0.0, 3.0],
                    [0.0, 3.0],
                    [1.0, 0.0],
                    [1.0, 0.0],
                    [2.0, 3.0],
                    [2.0, 3.0],
                    [5.0, 0.0],
                    [5.0, 0.0],
                    [2.5, 5.0],
                    [2.5, 5.0],
                    [0.0, 3.0],
                    [0.0, 3.0],
                    [0.0, 3.0],
                    [1.0, 0.0],
                    [2.0, 3.0],
                    [5.0, 0.0],
                    [2.5, 5.0],
                ]
            ),
            array(
                [
                    [0.47952713, -0.14161119],
                    [-0.31234752, 0.3904344],
                    [-0.0, 0.5],
                    [-0.47434165, -0.15811388],
                    [-0.47434165, 0.15811388],
                    [0.11487646, -0.48662449],
                    [-0.29235514, 0.40562109],
                    [-0.35355339, -0.35355339],
                    [-0.10726172, -0.48835942],
                    [0.4472136, 0.2236068],
                    [0.47952713, -0.14161119],
                    [-0.31234752, 0.3904344],
                    [-0.47434165, -0.15811388],
                    [0.47434165, -0.15811388],
                    [0.35355339, 0.35355339],
                    [0.4472136, 0.2236068],
                    [-0.31234752, 0.3904344],
                ]
            ),
            array(
                [
                    [0, 12, 3],
                    [0, 3, 2],
                    [2, 13, 5],
                    [2, 5, 4],
                    [14, 5, 7],
                    [14, 7, 6],
                    [6, 15, 9],
                    [6, 9, 8],
                    [8, 16, 11],
                    [8, 11, 10],
                    [12, 0, 1],
                    [13, 2, 3],
                    [4, 5, 14],
                    [15, 6, 7],
                    [16, 8, 9],
                ]
            ),
        ),
    ],
]


@pytest.fixture
def create_complex_shape():
    shape = np.array(
        [
            [136.74888492, -279.3367529],
            [144.05664585, -286.64451383],
            [154.10481713, -295.77921499],
            [162.32604817, -303.08697591],
            [170.54727921, -307.65432649],
            [179.68198037, -306.74085638],
            [187.90321142, -300.34656557],
            [193.38403211, -291.21186441],
            [195.21097235, -282.07716325],
            [196.12444246, -272.94246209],
            [200.69179304, -264.72123104],
            [207.08608385, -255.58652988],
            [214.39384478, -246.45182872],
            [218.04772525, -237.31712756],
            [212.56690455, -229.09589652],
            [207.99955397, -220.87466548],
            [205.25914362, -209.91302409],
            [203.43220339, -200.77832293],
            [203.43220339, -189.81668153],
            [199.77832293, -179.76851026],
            [189.73015165, -171.54727921],
            [179.68198037, -166.97992864],
            [169.6338091, -164.23951829],
            [160.49910794, -166.06645852],
            [149.53746655, -169.72033898],
            [140.40276539, -176.11462979],
            [134.00847458, -185.24933095],
            [126.70071365, -195.29750223],
            [121.21989295, -204.43220339],
            [118.4794826, -213.56690455],
            [114.82560214, -222.70160571],
            [115.73907226, -232.74977698],
            [118.4794826, -241.88447814],
            [123.9603033, -251.0191793],
            [129.441124, -259.24041035],
        ]
    )
    return shape


@pytest.mark.parametrize(
    ('path', 'closed', 'limit', 'bevel', 'expected'),
    cases,
)
def test_generate_2D_edge_meshes(
    path,
    closed,
    limit,
    bevel,
    expected,
):
    c, o, t = generate_2D_edge_meshes_py(path, closed, limit, bevel)
    expected_center, expected_offsets, expected_triangles = expected
    assert np.allclose(c, expected_center)
    assert np.allclose(o, expected_offsets)
    assert (t == expected_triangles).all()


def test_no_shapes():
    """Test no shapes."""
    assert number_of_shapes([]) == 0
    assert number_of_shapes(np.empty((0, 4, 2))) == 0


def test_one_shape():
    """Test one shape."""
    assert number_of_shapes(np.random.random((4, 2))) == 1


def test_many_shapes():
    """Test many shapes."""
    assert number_of_shapes(np.random.random((8, 4, 2))) == 8


def test_get_default_shape_type():
    """Test getting default shape type"""
    shape_type = ['polygon', 'polygon']
    assert get_default_shape_type(shape_type) == 'polygon'

    shape_type = []
    assert get_default_shape_type(shape_type) == 'polygon'

    shape_type = ['ellipse', 'rectangle']
    assert get_default_shape_type(shape_type) == 'polygon'

    shape_type = ['rectangle', 'rectangle']
    assert get_default_shape_type(shape_type) == 'rectangle'

    shape_type = ['ellipse', 'ellipse']
    assert get_default_shape_type(shape_type) == 'ellipse'

    shape_type = ['polygon']
    assert get_default_shape_type(shape_type) == 'polygon'


def test_rdp(create_complex_shape):
    # Rational of test is more vertices should be removed as epsilon gets higher.
    shape = create_complex_shape

    rdp_shape = rdp(shape, 0)
    assert len(shape) == len(rdp_shape)

    rdp_shape = rdp(shape, 1)
    assert len(rdp_shape) < len(shape)

    rdp_shape_lt = rdp(shape, 2)
    assert len(rdp_shape_lt) < len(rdp_shape)


@pytest.mark.parametrize(('start', 'end', 'point'), line_points)
def test_perpendicular_distance(start, end, point):
    # check whether math is correct and works higher than 2D / 3d
    distance = perpendicular_distance(point, start, end)

    assert distance == 1


def pentagram(reverse):
    radius = 10
    n = 5
    angles = np.linspace(0, 4 * np.pi, n, endpoint=False)
    if reverse:
        angles = angles[::-1]
    return np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))


def generate_regular_polygon(n, reverse, radius=1):
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    if reverse:
        angles = angles[::-1]
    return np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))


def rotation_matrix(angle):
    return np.array(
        [
            [np.cos(np.radians(angle)), -np.sin(np.radians(angle))],
            [np.sin(np.radians(angle)), np.cos(np.radians(angle))],
        ]
    )


ANGLES = [0, 5, 75, 95, 355]


def test_is_convex_self_intersection(self_intersecting_polygon):
    assert not is_convex_py(self_intersecting_polygon)


def test_is_convex_regular_polygon(regular_polygon):
    assert is_convex_py(regular_polygon)


def test_is_convex_non_convex(non_convex_poly):
    assert not is_convex_py(non_convex_poly)


def test_line_non_convex(line):
    assert not is_convex_py(line)


def test_line_two_point_non_convex(line_two_point):
    assert not is_convex_py(line_two_point)


def test_normalize_vertices_and_edges(poly_hole):
    points, edges = normalize_vertices_and_edges_py(poly_hole, close=True)
    assert points.shape == (8, 2)
    assert edges.shape == (8, 2)


def test_reconstruct_and_triangulate_edge(poly_hole):
    points, edges = normalize_vertices_and_edges_py(poly_hole, close=True)
    centers, offsets, triangles = reconstruct_and_triangulate_edge(
        points, edges
    )
    assert len(triangles) == 16
    assert len(offsets) == 20
    assert len(centers) == 20


def test_reconstruct_polygon_edges(poly_hole):
    points, edges = normalize_vertices_and_edges_py(poly_hole, close=True)
    polygon_list = reconstruct_polygons_from_edges_py(points, edges)
    assert len(polygon_list) == 2
    assert len(polygon_list[0]) == 4
    assert len(polygon_list[1]) == 4


def test_triangulate_face_and_edges(poly_hole):
    faces, edges = triangulate_face_and_edges(
        poly_hole, triangulate_face_vispy
    )


def test_save_failed_triangulation(tmp_path):
    data = np.empty((10, 10), dtype=np.uint16)
    bin_path, text_path = _save_failed_triangulation(
        data, target_dir=str(tmp_path)
    )
    assert os.path.exists(bin_path)
    assert os.path.exists(text_path)
    assert bin_path.endswith('.npz')
    assert text_path.endswith('.txt')
    assert bin_path.startswith(str(tmp_path))
    assert text_path.startswith(str(tmp_path))

    d1 = np.loadtxt(text_path)
    npt.assert_array_equal(d1, data)

    d2 = np.load(bin_path)['data']
    npt.assert_array_equal(d2, data)
