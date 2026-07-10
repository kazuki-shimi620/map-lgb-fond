from __future__ import annotations

import math
import re
from pathlib import Path

STATION_PASSENGER_NUMERIC_FEATURES = [
    "station_passenger_count",
    "station_passenger_log",
    "station_passenger_year",
    "station_passenger_age",
    "station_line_count",
    "station_operator_count",
    "effective_station_scale",
    "has_station_passenger_data",
]
STATION_PASSENGER_CATEGORICAL_FEATURES = ["station_rank"]
STATION_PASSENGER_FEATURES = (
    STATION_PASSENGER_NUMERIC_FEATURES + STATION_PASSENGER_CATEGORICAL_FEATURES
)

_SPACE_RE = re.compile(r"[\s\u3000]+")
_SUFFIX_RE = re.compile(r"(駅|停留場)$")


def load_station_passengers_csv(path: str | Path):
    import pandas as pd

    stations = pd.read_csv(path)
    numeric_columns = [
        "latest_passenger_count",
        "latest_passenger_year",
        "log_passenger_count",
        "line_count",
        "operator_count",
    ]
    for column in numeric_columns:
        if column in stations.columns:
            stations[column] = pd.to_numeric(stations[column], errors="coerce")
    if "normalized_station_name" not in stations.columns:
        stations["normalized_station_name"] = stations["station_name"].map(normalize_station_name)
    return stations


def add_station_passenger_features(property_df, station_passengers_df):
    import pandas as pd

    result = property_df.copy()
    if station_passengers_df.empty:
        return _fill_missing_features(result)

    stations = _aggregate_by_station_name(station_passengers_df)
    result["_normalized_station_name"] = result["station"].map(normalize_station_name)
    result = result.merge(
        stations,
        how="left",
        left_on="_normalized_station_name",
        right_on="normalized_station_name",
    ).drop(columns=["_normalized_station_name", "normalized_station_name"])

    result = result.rename(
        columns={
            "latest_passenger_count": "station_passenger_count",
            "latest_passenger_year": "station_passenger_year",
            "log_passenger_count": "station_passenger_log",
            "rank": "station_rank",
            "line_count": "station_line_count",
            "operator_count": "station_operator_count",
        }
    )
    result["has_station_passenger_data"] = result["station_passenger_count"].notna().astype(float)
    result["station_passenger_age"] = (
        result["transaction_year"] - result["station_passenger_year"]
    ).clip(lower=0)
    walking_meters = pd.to_numeric(result["station_distance"], errors="coerce").fillna(0.0) * 60.0
    result["effective_station_scale"] = result["station_passenger_log"] * walking_meters.map(
        lambda meters: math.exp(-meters / 1000.0)
    )
    return _fill_missing_features(result)


def normalize_station_name(value: object) -> str:
    if value is None:
        return ""
    text = _SPACE_RE.sub("", str(value).strip())
    return _SUFFIX_RE.sub("", text)


def _aggregate_by_station_name(stations):
    import pandas as pd

    scoped = stations.copy()
    scoped["normalized_station_name"] = scoped["normalized_station_name"].map(
        normalize_station_name
    )
    scoped = scoped[scoped["normalized_station_name"] != ""]
    scoped = scoped.sort_values(
        ["normalized_station_name", "latest_passenger_count"],
        ascending=[True, False],
    )
    selected = scoped.drop_duplicates(subset=["normalized_station_name"], keep="first")
    columns = [
        "normalized_station_name",
        "latest_passenger_count",
        "latest_passenger_year",
        "rank",
        "log_passenger_count",
        "line_count",
        "operator_count",
    ]
    existing_columns = [column for column in columns if column in selected.columns]
    return pd.DataFrame(selected[existing_columns])


def _fill_missing_features(result):
    for feature in STATION_PASSENGER_NUMERIC_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = result[feature].fillna(0.0)
    if "station_rank" not in result.columns:
        result["station_rank"] = "unknown"
    result["station_rank"] = result["station_rank"].fillna("unknown").astype(str)
    return result
