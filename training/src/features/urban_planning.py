from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

URBAN_PLANNING_NUMERIC_FEATURES = [
    "is_commercial_zone",
    "is_residential_zone",
    "floor_area_ratio",
    "building_coverage_ratio",
    "has_zoning_data",
]
URBAN_PLANNING_CATEGORICAL_FEATURES = [
    "city_planning_area_type",
    "zoning_type",
    "location_optimization_area",
]
URBAN_PLANNING_FEATURES = (
    URBAN_PLANNING_NUMERIC_FEATURES + URBAN_PLANNING_CATEGORICAL_FEATURES
)


def load_urban_planning_areas_csv(path: str | Path):
    import pandas as pd

    areas = pd.read_csv(path, low_memory=False)
    for column in ["floor_area_ratio", "building_coverage_ratio"]:
        if column in areas.columns:
            areas[column] = pd.to_numeric(areas[column], errors="coerce")
    return areas


def add_urban_planning_features(property_df, urban_planning_areas_df):
    result = property_df.copy()
    _initialize_features(result)
    if urban_planning_areas_df.empty or not {"lat", "lon"}.issubset(result.columns):
        return _fill_missing_features(result)

    areas = _prepare_areas(urban_planning_areas_df)
    area_grid = _build_area_grid(areas)
    coordinate_features = _build_coordinate_features(result, areas, area_grid)
    if coordinate_features.empty:
        return _fill_missing_features(result)

    import pandas as pd

    coordinate_keys = pd.DataFrame(
        {
            "_urban_lat": pd.to_numeric(result["lat"], errors="coerce"),
            "_urban_lon": pd.to_numeric(result["lon"], errors="coerce"),
        },
        index=result.index,
    )
    result = result.drop(columns=URBAN_PLANNING_FEATURES).join(coordinate_keys)
    result = result.merge(coordinate_features, how="left", on=["_urban_lat", "_urban_lon"])
    result = result.drop(columns=["_urban_lat", "_urban_lon"])
    return _fill_missing_features(result)


def _build_coordinate_features(result, areas, area_grid):
    import pandas as pd

    coordinates = pd.DataFrame(
        {
            "_urban_lat": pd.to_numeric(result["lat"], errors="coerce"),
            "_urban_lon": pd.to_numeric(result["lon"], errors="coerce"),
        }
    )
    coordinates = coordinates.dropna().drop_duplicates()
    records = []
    for lat_value, lon_value in coordinates.itertuples(index=False, name=None):
        lat = float(lat_value)
        lon = float(lon_value)
        matched = _matched_areas(lon=lon, lat=lat, areas=areas, area_grid=area_grid)
        records.append(
            {
                "_urban_lat": lat,
                "_urban_lon": lon,
                **_features_from_matched_areas(matched),
            }
        )
    return pd.DataFrame(records)


def _features_from_matched_areas(matched):
    features = _empty_feature_values()
    zoning = _first_area(matched, "zoning")
    city_planning = _first_area(matched, "city_planning_area")
    location_optimization = _first_area(matched, "location_optimization")
    if zoning is not None:
        zoning_type = _text(zoning.get("zoning_type") or zoning.get("area_name"))
        features["zoning_type"] = zoning_type or "unknown"
        features["is_commercial_zone"] = 1.0 if _is_commercial_zone(zoning_type) else 0.0
        features["is_residential_zone"] = 1.0 if _is_residential_zone(zoning_type) else 0.0
        features["floor_area_ratio"] = _float_or_zero(zoning.get("floor_area_ratio"))
        features["building_coverage_ratio"] = _float_or_zero(
            zoning.get("building_coverage_ratio")
        )
        features["has_zoning_data"] = 1.0
    if city_planning is not None:
        features["city_planning_area_type"] = _text(city_planning.get("area_name")) or "unknown"
    if location_optimization is not None:
        features["location_optimization_area"] = (
            _text(location_optimization.get("area_name")) or "unknown"
        )
    return features


def _empty_feature_values() -> dict[str, object]:
    values: dict[str, object] = {feature: 0.0 for feature in URBAN_PLANNING_NUMERIC_FEATURES}
    values.update({feature: "unknown" for feature in URBAN_PLANNING_CATEGORICAL_FEATURES})
    return values


def _prepare_areas(areas_df) -> list[dict[str, Any]]:
    rows = []
    for row in areas_df.to_dict(orient="records"):
        geometry = _parse_geometry(row.get("geometry_json"))
        if geometry is None:
            continue
        row["_geometry"] = geometry
        row["_bbox"] = _geometry_bbox(geometry)
        rows.append(row)
    return rows


def _build_area_grid(areas: list[dict[str, Any]], cell_size: float = 0.02) -> dict:
    grid: dict[tuple[int, int], list[int]] = {}
    for index, area in enumerate(areas):
        bbox = area.get("_bbox")
        if bbox is None:
            continue
        min_lon, min_lat, max_lon, max_lat = bbox
        min_x = math.floor(min_lon / cell_size)
        max_x = math.floor(max_lon / cell_size)
        min_y = math.floor(min_lat / cell_size)
        max_y = math.floor(max_lat / cell_size)
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                grid.setdefault((x, y), []).append(index)
    return {"cellSize": cell_size, "cells": grid}


def _matched_areas(
    *,
    lon: float,
    lat: float,
    areas: list[dict[str, Any]],
    area_grid: dict | None = None,
) -> list[dict[str, Any]]:
    candidate_indexes = _candidate_area_indexes(lon=lon, lat=lat, area_grid=area_grid)
    candidates = [areas[index] for index in candidate_indexes] if candidate_indexes else areas
    return [
        row
        for row in candidates
        if _point_in_bbox(lon, lat, row.get("_bbox"))
        and point_in_geometry(lon, lat, row["_geometry"])
    ]


def _candidate_area_indexes(*, lon: float, lat: float, area_grid: dict | None) -> list[int]:
    if not area_grid:
        return []
    cell_size = area_grid["cellSize"]
    cell = (math.floor(lon / cell_size), math.floor(lat / cell_size))
    return area_grid["cells"].get(cell, [])


def _first_area(rows: list[dict[str, Any]], area_type: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("area_type") == area_type:
            return row
    return None


def point_in_geometry(lon: float, lat: float, geometry: dict[str, Any]) -> bool:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        return _point_in_polygon(lon, lat, coordinates)
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return any(_point_in_polygon(lon, lat, polygon) for polygon in coordinates)
    return False


def _geometry_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float] | None:
    points = list(_iter_geometry_points(geometry))
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return min(lons), min(lats), max(lons), max(lats)


def _iter_geometry_points(geometry: dict[str, Any]):
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        yield from _iter_polygon_points(coordinates)
    elif geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        for polygon in coordinates:
            yield from _iter_polygon_points(polygon)


def _iter_polygon_points(polygon: object):
    if not isinstance(polygon, list):
        return
    for ring in polygon:
        if not isinstance(ring, list):
            continue
        for coordinate in ring:
            if _is_coordinate(coordinate):
                yield float(coordinate[0]), float(coordinate[1])


def _point_in_bbox(
    lon: float,
    lat: float,
    bbox: tuple[float, float, float, float] | None,
) -> bool:
    if bbox is None:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _point_in_polygon(lon: float, lat: float, polygon: object) -> bool:
    if not isinstance(polygon, list) or not polygon:
        return False
    outer = polygon[0]
    if not _point_in_ring(lon, lat, outer):
        return False
    holes = polygon[1:]
    return not any(_point_in_ring(lon, lat, hole) for hole in holes)


def _point_in_ring(lon: float, lat: float, ring: object) -> bool:
    if not isinstance(ring, list) or len(ring) < 3:
        return False
    inside = False
    previous = ring[-1]
    for current in ring:
        if not _is_coordinate(current) or not _is_coordinate(previous):
            previous = current
            continue
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        intersects = (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (
            y2 - y1
        ) + x1
        if intersects:
            inside = not inside
        previous = current
    return inside


def _is_coordinate(value: object) -> bool:
    return isinstance(value, list | tuple) and len(value) >= 2


def _parse_geometry(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return None
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _initialize_features(result) -> None:
    for feature in URBAN_PLANNING_NUMERIC_FEATURES:
        result[feature] = 0.0
    for feature in URBAN_PLANNING_CATEGORICAL_FEATURES:
        result[feature] = "unknown"


def _fill_missing_features(result):
    for feature in URBAN_PLANNING_NUMERIC_FEATURES:
        result[feature] = result[feature].fillna(0.0)
    for feature in URBAN_PLANNING_CATEGORICAL_FEATURES:
        result[feature] = result[feature].fillna("unknown").replace("", "unknown")
    return result


def _is_commercial_zone(value: object) -> bool:
    return "商業" in _text(value)


def _is_residential_zone(value: object) -> bool:
    return "住居" in _text(value) or "住宅" in _text(value)


def _float_or_zero(value: object) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
