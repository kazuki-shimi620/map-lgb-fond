from __future__ import annotations

import math

import pandas as pd

from features.station_passengers import (
    add_station_passenger_features,
    normalize_station_name,
)


def test_normalize_station_name_removes_spaces_and_suffix() -> None:
    assert normalize_station_name(" 新 宿 駅 ") == "新宿"
    assert normalize_station_name("渋谷停留場") == "渋谷"


def test_add_station_passenger_features_uses_largest_same_name_station() -> None:
    properties = pd.DataFrame(
        [
            {
                "station": "新宿",
                "station_distance": 10,
                "transaction_year": 2025,
            },
            {
                "station": "未収録",
                "station_distance": 5,
                "transaction_year": 2025,
            },
        ]
    )
    stations = pd.DataFrame(
        [
            {
                "station_name": "新宿",
                "normalized_station_name": "新宿",
                "latest_passenger_count": 100,
                "latest_passenger_year": 2023,
                "rank": "D",
                "log_passenger_count": math.log1p(100),
                "line_count": 1,
                "operator_count": 1,
            },
            {
                "station_name": "新宿",
                "normalized_station_name": "新宿",
                "latest_passenger_count": 1000,
                "latest_passenger_year": 2023,
                "rank": "C",
                "log_passenger_count": math.log1p(1000),
                "line_count": 2,
                "operator_count": 2,
            },
        ]
    )

    actual = add_station_passenger_features(properties, stations)

    assert actual.loc[0, "station_passenger_count"] == 1000
    assert actual.loc[0, "station_passenger_age"] == 2
    assert actual.loc[0, "station_rank"] == "C"
    assert actual.loc[0, "has_station_passenger_data"] == 1
    assert actual.loc[0, "effective_station_scale"] == math.log1p(1000) * math.exp(-0.6)
    assert actual.loc[1, "station_passenger_count"] == 0
    assert actual.loc[1, "station_rank"] == "unknown"


def test_add_station_passenger_features_scopes_same_name_by_prefecture() -> None:
    properties = pd.DataFrame(
        [
            {
                "prefecture": "静岡県",
                "station": "大森",
                "station_distance": 5,
                "transaction_year": 2025,
            }
        ]
    )
    stations = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "normalized_station_name": "大森",
                "latest_passenger_count": 10000,
                "latest_passenger_year": 2023,
                "rank": "D",
                "log_passenger_count": math.log1p(10000),
                "line_count": 1,
                "operator_count": 1,
            },
            {
                "prefecture": "静岡県",
                "normalized_station_name": "大森",
                "latest_passenger_count": 100,
                "latest_passenger_year": 2023,
                "rank": "E",
                "log_passenger_count": math.log1p(100),
                "line_count": 1,
                "operator_count": 1,
            },
        ]
    )

    actual = add_station_passenger_features(properties, stations)

    assert actual.loc[0, "station_passenger_count"] == 100


def test_add_station_passenger_features_uses_nearest_same_name_station_when_coordinates_exist() -> (
    None
):
    properties = pd.DataFrame(
        [
            {
                "station": "中央",
                "station_distance": 5,
                "transaction_year": 2025,
                "lat": 35.0,
                "lon": 139.0,
            }
        ]
    )
    stations = pd.DataFrame(
        [
            {
                "station_name": "中央",
                "normalized_station_name": "中央",
                "lat": 36.0,
                "lon": 140.0,
                "latest_passenger_count": 10000,
                "latest_passenger_year": 2023,
                "rank": "A",
                "log_passenger_count": math.log1p(10000),
                "line_count": 4,
                "operator_count": 3,
            },
            {
                "station_name": "中央",
                "normalized_station_name": "中央",
                "lat": 35.001,
                "lon": 139.001,
                "latest_passenger_count": 100,
                "latest_passenger_year": 2024,
                "rank": "D",
                "log_passenger_count": math.log1p(100),
                "line_count": 1,
                "operator_count": 1,
            },
        ]
    )

    actual = add_station_passenger_features(properties, stations)

    assert actual.loc[0, "station_passenger_count"] == 100
    assert actual.loc[0, "station_passenger_age"] == 1
    assert actual.loc[0, "station_rank"] == "D"
