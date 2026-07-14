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

    if _has_coordinate_columns(result) and _has_coordinate_columns(station_passengers_df):
        result = _join_by_station_name_and_coordinates(result, station_passengers_df)
    else:
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


def _join_by_station_name_and_coordinates(properties, stations):
    import pandas as pd

    scoped = stations.copy()
    scoped["normalized_station_name"] = scoped["normalized_station_name"].map(
        normalize_station_name
    )
    scoped = scoped[scoped["normalized_station_name"] != ""]
    candidates = {
        station_name: records for station_name, records in scoped.groupby("normalized_station_name")
    }

    passenger_rows = []
    for property_row in properties.to_dict(orient="records"):
        normalized_name = normalize_station_name(property_row.get("station"))
        selected = _select_nearest_station_candidate(
            candidates.get(normalized_name),
            property_row.get("lat"),
            property_row.get("lon"),
        )
        passenger_rows.append(selected or {})

    passenger_df = pd.DataFrame(passenger_rows)
    if passenger_df.empty:
        return properties.copy()
    columns = [
        "latest_passenger_count",
        "latest_passenger_year",
        "rank",
        "log_passenger_count",
        "line_count",
        "operator_count",
    ]
    existing_columns = [column for column in columns if column in passenger_df.columns]
    return properties.reset_index(drop=True).join(passenger_df[existing_columns])


def _select_nearest_station_candidate(candidates, lat, lon):
    if candidates is None or candidates.empty:
        return None
    try:
        property_lat = float(lat)
        property_lon = float(lon)
    except (TypeError, ValueError):
        return _largest_passenger_candidate(candidates)

    ranked = []
    for record in candidates.to_dict(orient="records"):
        try:
            station_lat = float(record["lat"])
            station_lon = float(record["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        ranked.append(
            (
                _haversine_km(property_lat, property_lon, station_lat, station_lon),
                -(record.get("latest_passenger_count") or 0),
                record,
            )
        )
    if not ranked:
        return _largest_passenger_candidate(candidates)
    return min(ranked, key=lambda item: (item[0], item[1]))[2]


def _largest_passenger_candidate(candidates):
    sorted_candidates = candidates.sort_values("latest_passenger_count", ascending=False)
    return sorted_candidates.iloc[0].to_dict()


def _has_coordinate_columns(df) -> bool:
    return "lat" in df.columns and "lon" in df.columns


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


def _fill_missing_features(result):
    for feature in STATION_PASSENGER_NUMERIC_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = result[feature].fillna(0.0)
    if "station_rank" not in result.columns:
        result["station_rank"] = "unknown"
    result["station_rank"] = result["station_rank"].fillna("unknown").astype(str)
    return result
