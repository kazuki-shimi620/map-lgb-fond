from features.hazard_spatial import point_in_geometry


def test_point_in_polygon_respects_hole_and_boundary() -> None:
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
            [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
        ],
    }

    assert point_in_geometry(2, 2, geometry)
    assert point_in_geometry(0, 5, geometry)
    assert not point_in_geometry(5, 5, geometry)
    assert not point_in_geometry(11, 5, geometry)


def test_point_in_multipolygon() -> None:
    geometry = {
        "type": "MultiPolygon",
        "coordinates": [
            [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
            [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
        ],
    }

    assert point_in_geometry(2.5, 2.5, geometry)
