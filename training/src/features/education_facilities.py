from __future__ import annotations

import math
from pathlib import Path

EDUCATION_FEATURES = [
    "nearest_elementary_school_distance_km",
    "nearest_junior_high_school_distance_km",
    "nursery_count_within_500m",
    "nursery_count_within_1km",
    "kindergarten_count_within_1km",
    "has_education_data",
]
MISSING_DISTANCE_KM = 99.0


def load_education_facilities_csv(path: str | Path):
    import pandas as pd

    facilities = pd.read_csv(path)
    for column in ["lat", "lon"]:
        if column in facilities.columns:
            facilities[column] = pd.to_numeric(facilities[column], errors="coerce")
    return facilities


def add_education_features(property_df, facilities_df):
    result = property_df.copy()
    for feature in EDUCATION_FEATURES:
        result[feature] = 0.0
    if facilities_df.empty or not {"lat", "lon"}.issubset(result.columns):
        result["nearest_elementary_school_distance_km"] = MISSING_DISTANCE_KM
        result["nearest_junior_high_school_distance_km"] = MISSING_DISTANCE_KM
        return _fill_missing_features(result)

    facilities = facilities_df.dropna(subset=["lat", "lon"]).copy()
    if facilities.empty:
        return _fill_missing_features(result)

    elementary = facilities[facilities["facility_type"].map(_is_elementary_school)]
    junior_high = facilities[facilities["facility_type"].map(_is_junior_high_school)]
    nursery = facilities[facilities["facility_type"].map(_is_nursery)]
    kindergarten = facilities[facilities["facility_type"].map(_is_kindergarten)]

    nearest_elementary = []
    nearest_junior_high = []
    nursery_500m_counts = []
    nursery_1km_counts = []
    kindergarten_1km_counts = []
    has_data = []

    for row in result.to_dict(orient="records"):
        try:
            lat = float(row["lat"])
            lon = float(row["lon"])
        except (KeyError, TypeError, ValueError):
            nearest_elementary.append(MISSING_DISTANCE_KM)
            nearest_junior_high.append(MISSING_DISTANCE_KM)
            nursery_500m_counts.append(0.0)
            nursery_1km_counts.append(0.0)
            kindergarten_1km_counts.append(0.0)
            has_data.append(0.0)
            continue

        elementary_distance = _nearest_distance_km(lat, lon, elementary)
        junior_high_distance = _nearest_distance_km(lat, lon, junior_high)
        nursery_500m = _count_within_km(lat, lon, nursery, 0.5)
        nursery_1km = _count_within_km(lat, lon, nursery, 1.0)
        kindergarten_1km = _count_within_km(lat, lon, kindergarten, 1.0)
        nearest_elementary.append(elementary_distance)
        nearest_junior_high.append(junior_high_distance)
        nursery_500m_counts.append(nursery_500m)
        nursery_1km_counts.append(nursery_1km)
        kindergarten_1km_counts.append(kindergarten_1km)
        has_data.append(
            1.0
            if (
                elementary_distance < MISSING_DISTANCE_KM
                or junior_high_distance < MISSING_DISTANCE_KM
                or nursery_1km > 0
                or kindergarten_1km > 0
            )
            else 0.0
        )

    result["nearest_elementary_school_distance_km"] = nearest_elementary
    result["nearest_junior_high_school_distance_km"] = nearest_junior_high
    result["nursery_count_within_500m"] = nursery_500m_counts
    result["nursery_count_within_1km"] = nursery_1km_counts
    result["kindergarten_count_within_1km"] = kindergarten_1km_counts
    result["has_education_data"] = has_data
    return _fill_missing_features(result)


def _nearest_distance_km(lat: float, lon: float, facilities) -> float:
    distances = _distances_km(lat, lon, facilities)
    return min(distances) if distances else MISSING_DISTANCE_KM


def _count_within_km(lat: float, lon: float, facilities, radius_km: float) -> float:
    count = sum(
        1 for distance in _distances_km(lat, lon, facilities) if distance <= radius_km
    )
    return float(count)


def _distances_km(lat: float, lon: float, facilities) -> list[float]:
    return [
        _haversine_km(lat, lon, float(row["lat"]), float(row["lon"]))
        for row in facilities.to_dict(orient="records")
    ]


def _is_elementary_school(value: object) -> bool:
    return "小学校" in _text(value)


def _is_junior_high_school(value: object) -> bool:
    text = _text(value)
    return "中学校" in text and "小中" not in text


def _is_nursery(value: object) -> bool:
    text = _text(value)
    return "保育" in text or "050401" in text


def _is_kindergarten(value: object) -> bool:
    text = _text(value)
    return "幼稚園" in text or "こども園" in text


def _fill_missing_features(result):
    result["nearest_elementary_school_distance_km"] = result[
        "nearest_elementary_school_distance_km"
    ].fillna(MISSING_DISTANCE_KM)
    result["nearest_junior_high_school_distance_km"] = result[
        "nearest_junior_high_school_distance_km"
    ].fillna(MISSING_DISTANCE_KM)
    for feature in [
        "nursery_count_within_500m",
        "nursery_count_within_1km",
        "kindergarten_count_within_1km",
        "has_education_data",
    ]:
        result[feature] = result[feature].fillna(0.0)
    return result


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
