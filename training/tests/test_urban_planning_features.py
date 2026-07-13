from __future__ import annotations

import json

import pandas as pd
import pytest

from features.urban_planning import add_urban_planning_features, point_in_geometry


def test_point_in_geometry_handles_polygon_with_hole() -> None:
    geometry = {
        "type": "Polygon",
        "coordinates": [
            [[139.0, 35.0], [140.0, 35.0], [140.0, 36.0], [139.0, 36.0], [139.0, 35.0]],
            [[139.4, 35.4], [139.6, 35.4], [139.6, 35.6], [139.4, 35.6], [139.4, 35.4]],
        ],
    }

    assert point_in_geometry(139.2, 35.2, geometry)
    assert not point_in_geometry(139.5, 35.5, geometry)
    assert not point_in_geometry(138.9, 35.2, geometry)


def test_add_urban_planning_features_assigns_zoning_values() -> None:
    properties = pd.DataFrame([{"lat": 35.5, "lon": 139.5}])
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [[139.0, 35.0], [140.0, 35.0], [140.0, 36.0], [139.0, 36.0], [139.0, 35.0]]
        ],
    }
    areas = pd.DataFrame(
        [
            {
                "area_type": "zoning",
                "area_name": "商業地域",
                "zoning_type": "商業地域",
                "floor_area_ratio": 600.0,
                "building_coverage_ratio": 80.0,
                "geometry_json": json.dumps(polygon),
            },
            {
                "area_type": "city_planning_area",
                "area_name": "市街化区域",
                "geometry_json": json.dumps(polygon),
            },
            {
                "area_type": "location_optimization",
                "area_name": "都市機能誘導区域",
                "geometry_json": json.dumps(polygon),
            },
        ]
    )

    actual = add_urban_planning_features(properties, areas)

    assert actual.loc[0, "zoning_type"] == "商業地域"
    assert actual.loc[0, "is_commercial_zone"] == 1.0
    assert actual.loc[0, "is_residential_zone"] == 0.0
    assert actual.loc[0, "floor_area_ratio"] == pytest.approx(600.0)
    assert actual.loc[0, "building_coverage_ratio"] == pytest.approx(80.0)
    assert actual.loc[0, "city_planning_area_type"] == "市街化区域"
    assert actual.loc[0, "location_optimization_area"] == "都市機能誘導区域"
    assert actual.loc[0, "has_zoning_data"] == 1.0


def test_add_urban_planning_features_uses_unknown_without_coordinates() -> None:
    actual = add_urban_planning_features(
        pd.DataFrame([{"station": "東京"}]),
        pd.DataFrame([{"area_type": "zoning", "geometry_json": "{}"}]),
    )

    assert actual.loc[0, "zoning_type"] == "unknown"
    assert actual.loc[0, "floor_area_ratio"] == 0.0
    assert actual.loc[0, "has_zoning_data"] == 0.0
