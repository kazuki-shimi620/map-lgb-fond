from __future__ import annotations

from pathlib import Path

from features.station_passengers import normalize_station_name

MISSING_TRAVEL_TIME_MINUTES = 999.0
MISSING_TRANSFER_COUNT = 9.0
RAIL_ACCESS_NUMERIC_FEATURES = [
    "nearest_station_is_terminal",
    "nearest_station_time_to_tokyo",
    "nearest_station_time_to_shinjuku",
    "nearest_station_time_to_shibuya",
    "nearest_station_time_to_yokohama",
    "major_terminal_min_time",
    "major_terminal_min_transfer_count",
    "has_rail_access_data",
]
RAIL_ACCESS_CATEGORICAL_FEATURES = ["closest_major_terminal"]
RAIL_ACCESS_FEATURES = RAIL_ACCESS_NUMERIC_FEATURES + RAIL_ACCESS_CATEGORICAL_FEATURES
DESTINATION_COLUMNS = {
    "tokyo": "nearest_station_time_to_tokyo",
    "shinjuku": "nearest_station_time_to_shinjuku",
    "shibuya": "nearest_station_time_to_shibuya",
    "yokohama": "nearest_station_time_to_yokohama",
}


def load_rail_access_csv(path: str | Path):
    import pandas as pd

    rail_access = pd.read_csv(path)
    numeric_columns = [
        "nearest_station_is_terminal",
        "major_terminal_min_time",
        "major_terminal_min_transfer_count",
        "destination_count",
    ] + [
        column
        for destination in DESTINATION_COLUMNS
        for column in (f"time_to_{destination}", f"transfers_to_{destination}")
    ]
    for column in numeric_columns:
        if column in rail_access.columns:
            rail_access[column] = pd.to_numeric(rail_access[column], errors="coerce")
    if "normalized_station_name" not in rail_access.columns:
        rail_access["normalized_station_name"] = rail_access["station"].map(
            normalize_station_name
        )
    return rail_access


def add_rail_access_features(property_df, rail_access_df):
    result = property_df.copy()
    if rail_access_df.empty:
        return _fill_missing_features(result)

    access = rail_access_df.copy()
    access["normalized_station_name"] = access["normalized_station_name"].map(
        normalize_station_name
    )
    access = access[access["normalized_station_name"] != ""]
    access = access.drop(columns=["station"], errors="ignore")
    access = access.sort_values(["normalized_station_name", "destination_count"], ascending=False)
    access = access.drop_duplicates(subset=["normalized_station_name"], keep="first")
    result["_normalized_station_name"] = result["station"].map(normalize_station_name)
    result = result.merge(
        access,
        how="left",
        left_on="_normalized_station_name",
        right_on="normalized_station_name",
    ).drop(columns=["_normalized_station_name", "normalized_station_name"])

    result["has_rail_access_data"] = result["destination_count"].notna().astype(float)
    for destination, output_column in DESTINATION_COLUMNS.items():
        result[output_column] = result.get(f"time_to_{destination}")
    return _fill_missing_features(result)


def _fill_missing_features(result):
    for feature in RAIL_ACCESS_NUMERIC_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
    for feature in DESTINATION_COLUMNS.values():
        result[feature] = result[feature].fillna(MISSING_TRAVEL_TIME_MINUTES)
    result["major_terminal_min_time"] = result["major_terminal_min_time"].fillna(
        MISSING_TRAVEL_TIME_MINUTES
    )
    result["major_terminal_min_transfer_count"] = result[
        "major_terminal_min_transfer_count"
    ].fillna(MISSING_TRANSFER_COUNT)
    result["nearest_station_is_terminal"] = result["nearest_station_is_terminal"].fillna(0.0)
    result["has_rail_access_data"] = result["has_rail_access_data"].fillna(0.0)
    if "closest_major_terminal" not in result.columns:
        result["closest_major_terminal"] = "unknown"
    result["closest_major_terminal"] = result["closest_major_terminal"].fillna("unknown")
    result["closest_major_terminal"] = result["closest_major_terminal"].replace("", "unknown")
    return result
