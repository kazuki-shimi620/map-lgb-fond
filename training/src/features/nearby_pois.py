from __future__ import annotations

import json
from pathlib import Path

import numpy as np

EARTH_RADIUS_KM = 6371.0088
POI_CATEGORIES = ("commercial_facility", "cinema", "museum", "hot_spring")


def feature_names(category_id: str) -> list[str]:
    prefix = _feature_prefix(category_id)
    return [
        f"nearest_{prefix}_distance_km",
        f"{prefix}_count_within_1km",
        f"{prefix}_count_within_3km",
    ]


def load_nearby_pois_json(path: Path):
    import pandas as pd

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("facilities", [])
    frame = pd.DataFrame(rows)
    required = {"categoryId", "lat", "lon"}
    if frame.empty or not required.issubset(frame.columns):
        return pd.DataFrame(columns=["category_id", "lat", "lon"])
    result = frame.rename(columns={"categoryId": "category_id"})[
        ["category_id", "lat", "lon"]
    ].copy()
    result["lat"] = pd.to_numeric(result["lat"], errors="coerce")
    result["lon"] = pd.to_numeric(result["lon"], errors="coerce")
    return result.dropna(subset=["lat", "lon"])


def add_nearby_poi_features(properties, pois, categories: tuple[str, ...] = POI_CATEGORIES):
    from sklearn.neighbors import BallTree

    result = properties.copy()
    valid_property = result["lat"].notna() & result["lon"].notna()
    property_coordinates = np.radians(result.loc[valid_property, ["lat", "lon"]].to_numpy())

    for category_id in categories:
        names = feature_names(category_id)
        for name in names:
            result[name] = 0.0
        category_pois = pois[pois["category_id"] == category_id]
        if category_pois.empty or property_coordinates.size == 0:
            continue

        poi_coordinates = np.radians(category_pois[["lat", "lon"]].to_numpy())
        tree = BallTree(poi_coordinates, metric="haversine")
        nearest_radians, _ = tree.query(property_coordinates, k=1)
        within_1km = tree.query_radius(
            property_coordinates, r=1.0 / EARTH_RADIUS_KM, count_only=True
        )
        within_3km = tree.query_radius(
            property_coordinates, r=3.0 / EARTH_RADIUS_KM, count_only=True
        )
        result.loc[valid_property, names[0]] = nearest_radians[:, 0] * EARTH_RADIUS_KM
        result.loc[valid_property, names[1]] = within_1km.astype(float)
        result.loc[valid_property, names[2]] = within_3km.astype(float)
    return result


def _feature_prefix(category_id: str) -> str:
    return {
        "commercial_facility": "commercial",
        "cinema": "cinema",
        "museum": "museum",
        "hot_spring": "hot_spring",
    }.get(category_id, category_id)
