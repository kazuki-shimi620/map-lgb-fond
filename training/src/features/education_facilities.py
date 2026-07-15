from __future__ import annotations

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

    coordinate_features = _build_coordinate_features(
        result,
        elementary=elementary,
        junior_high=junior_high,
        nursery=nursery,
        kindergarten=kindergarten,
    )
    if coordinate_features.empty:
        result["nearest_elementary_school_distance_km"] = MISSING_DISTANCE_KM
        result["nearest_junior_high_school_distance_km"] = MISSING_DISTANCE_KM
        return _fill_missing_features(result)

    import pandas as pd

    coordinate_keys = pd.DataFrame(
        {
            "_education_lat": pd.to_numeric(result["lat"], errors="coerce"),
            "_education_lon": pd.to_numeric(result["lon"], errors="coerce"),
        },
        index=result.index,
    )
    result = result.drop(columns=EDUCATION_FEATURES).join(coordinate_keys)
    result = result.merge(coordinate_features, how="left", on=["_education_lat", "_education_lon"])
    result = result.drop(columns=["_education_lat", "_education_lon"])
    return _fill_missing_features(result)


def _build_coordinate_features(result, *, elementary, junior_high, nursery, kindergarten):
    import numpy as np
    import pandas as pd
    from sklearn.neighbors import BallTree

    coordinates = pd.DataFrame(
        {
            "_education_lat": pd.to_numeric(result["lat"], errors="coerce"),
            "_education_lon": pd.to_numeric(result["lon"], errors="coerce"),
        }
    )
    coordinates = coordinates.dropna().drop_duplicates()
    if coordinates.empty:
        return pd.DataFrame()

    coordinate_values = coordinates[["_education_lat", "_education_lon"]].to_numpy(dtype=float)
    coordinate_values_rad = np.radians(coordinate_values)
    coordinate_features = coordinates.copy()
    coordinate_features["nearest_elementary_school_distance_km"] = _nearest_distances_km(
        coordinate_values_rad,
        elementary,
        BallTree,
    )
    coordinate_features["nearest_junior_high_school_distance_km"] = _nearest_distances_km(
        coordinate_values_rad,
        junior_high,
        BallTree,
    )
    coordinate_features["nursery_count_within_500m"] = _counts_within_km(
        coordinate_values_rad,
        nursery,
        0.5,
        BallTree,
    )
    coordinate_features["nursery_count_within_1km"] = _counts_within_km(
        coordinate_values_rad,
        nursery,
        1.0,
        BallTree,
    )
    coordinate_features["kindergarten_count_within_1km"] = _counts_within_km(
        coordinate_values_rad,
        kindergarten,
        1.0,
        BallTree,
    )
    coordinate_features["has_education_data"] = (
        (
            coordinate_features["nearest_elementary_school_distance_km"]
            < MISSING_DISTANCE_KM
        )
        | (
            coordinate_features["nearest_junior_high_school_distance_km"]
            < MISSING_DISTANCE_KM
        )
        | (coordinate_features["nursery_count_within_1km"] > 0)
        | (coordinate_features["kindergarten_count_within_1km"] > 0)
    ).astype(float)
    return coordinate_features


def _nearest_distances_km(coordinates_rad, facilities, ball_tree_class):
    import numpy as np

    tree = _facility_tree(facilities, ball_tree_class)
    if tree is None:
        return np.full(len(coordinates_rad), MISSING_DISTANCE_KM, dtype=float)
    distances_rad, _ = tree.query(coordinates_rad, k=1)
    return distances_rad[:, 0] * 6371.0088


def _counts_within_km(coordinates_rad, facilities, radius_km: float, ball_tree_class):
    import numpy as np

    tree = _facility_tree(facilities, ball_tree_class)
    if tree is None:
        return np.zeros(len(coordinates_rad), dtype=float)
    counts = tree.query_radius(
        coordinates_rad,
        r=radius_km / 6371.0088,
        count_only=True,
    )
    return counts.astype(float)


def _facility_tree(facilities, ball_tree_class):
    import numpy as np
    import pandas as pd

    if facilities.empty:
        return None
    coordinates = facilities[["lat", "lon"]].apply(pd.to_numeric, errors="coerce").dropna()
    if coordinates.empty:
        return None
    return ball_tree_class(np.radians(coordinates.to_numpy(dtype=float)), metric="haversine")


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


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
