from __future__ import annotations

import json
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

    areas = pd.read_csv(path)
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
    for index, row in result.iterrows():
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (TypeError, ValueError):
            continue
        matched = _matched_areas(lon=lon, lat=lat, areas=areas)
        zoning = _first_area(matched, "zoning")
        city_planning = _first_area(matched, "city_planning_area")
        location_optimization = _first_area(matched, "location_optimization")
        if zoning is not None:
            zoning_type = _text(zoning.get("zoning_type") or zoning.get("area_name"))
            result.at[index, "zoning_type"] = zoning_type or "unknown"
            result.at[index, "is_commercial_zone"] = (
                1.0 if _is_commercial_zone(zoning_type) else 0.0
            )
            result.at[index, "is_residential_zone"] = (
                1.0 if _is_residential_zone(zoning_type) else 0.0
            )
            result.at[index, "floor_area_ratio"] = _float_or_zero(zoning.get("floor_area_ratio"))
            result.at[index, "building_coverage_ratio"] = _float_or_zero(
                zoning.get("building_coverage_ratio")
            )
            result.at[index, "has_zoning_data"] = 1.0
        if city_planning is not None:
            result.at[index, "city_planning_area_type"] = _text(
                city_planning.get("area_name")
            ) or "unknown"
        if location_optimization is not None:
            result.at[index, "location_optimization_area"] = _text(
                location_optimization.get("area_name")
            ) or "unknown"
    return _fill_missing_features(result)


def _prepare_areas(areas_df) -> list[dict[str, Any]]:
    rows = []
    for row in areas_df.to_dict(orient="records"):
        geometry = _parse_geometry(row.get("geometry_json"))
        if geometry is None:
            continue
        row["_geometry"] = geometry
        rows.append(row)
    return rows


def _matched_areas(*, lon: float, lat: float, areas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in areas if point_in_geometry(lon, lat, row["_geometry"])]


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
