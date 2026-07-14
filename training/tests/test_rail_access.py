from __future__ import annotations

import csv

import pandas as pd
import pytest

from collect.rail_access import build_rail_access_rows, collect_rail_access
from features.rail_access import (
    MISSING_TRAVEL_TIME_MINUTES,
    add_rail_access_features,
)


def test_build_rail_access_rows_calculates_min_terminal_time() -> None:
    rows = build_rail_access_rows(
        terminal_rows=[
            {
                "station_name": "新宿",
                "is_terminal": "1",
                "terminal_group": "新宿",
                "source": "manual",
                "source_year": "2026",
            }
        ],
        travel_time_rows=[
            {
                "origin_station": "新宿",
                "destination_station": "東京",
                "travel_time_minutes": "14",
                "transfer_count": "0",
                "source": "manual",
                "source_year": "2026",
            },
            {
                "origin_station": "新宿",
                "destination_station": "渋谷",
                "travel_time_minutes": "5",
                "transfer_count": "0",
                "source": "manual",
                "source_year": "2026",
            },
        ],
    )

    assert rows[0]["station"] == "新宿"
    assert rows[0]["nearest_station_is_terminal"] == 1.0
    assert rows[0]["time_to_tokyo"] == 14.0
    assert rows[0]["major_terminal_min_time"] == 5.0
    assert rows[0]["closest_major_terminal"] == "shibuya"


def test_collect_rail_access_writes_csv(tmp_path) -> None:
    terminal_csv = tmp_path / "terminal_stations.csv"
    travel_csv = tmp_path / "major_station_travel_times.csv"
    terminal_csv.write_text(
        "station_name,is_terminal,terminal_group,source,source_year\n"
        "東京,1,東京,manual,2026\n",
        encoding="utf-8",
    )
    travel_csv.write_text(
        "origin_station,destination_station,travel_time_minutes,transfer_count,source,source_year\n"
        "東京,東京,0,0,manual,2026\n",
        encoding="utf-8",
    )

    outputs = collect_rail_access(
        terminal_stations_csv=terminal_csv,
        travel_times_csv=travel_csv,
        output_dir=tmp_path / "processed",
    )

    with outputs["rail_access_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert outputs["row_count"] == 1
    assert rows[0]["station"] == "東京"
    assert rows[0]["closest_major_terminal"] == "tokyo"


def test_add_rail_access_features_uses_station_name_and_missing_sentinel() -> None:
    properties = pd.DataFrame(
        [
            {"station": "新宿駅"},
            {"station": "未収録"},
        ]
    )
    rail_access = pd.DataFrame(
        [
            {
                "station": "新宿",
                "normalized_station_name": "新宿",
                "nearest_station_is_terminal": 1.0,
                "time_to_tokyo": 14.0,
                "time_to_shinjuku": 0.0,
                "time_to_shibuya": 5.0,
                "time_to_yokohama": 31.0,
                "major_terminal_min_time": 0.0,
                "major_terminal_min_transfer_count": 0.0,
                "closest_major_terminal": "shinjuku",
                "destination_count": 4,
            }
        ]
    )

    actual = add_rail_access_features(properties, rail_access)

    assert actual.loc[0, "station"] == "新宿駅"
    assert actual.loc[0, "nearest_station_is_terminal"] == 1.0
    assert actual.loc[0, "nearest_station_time_to_tokyo"] == pytest.approx(14.0)
    assert actual.loc[0, "closest_major_terminal"] == "shinjuku"
    assert actual.loc[0, "has_rail_access_data"] == 1.0
    assert actual.loc[1, "nearest_station_time_to_tokyo"] == MISSING_TRAVEL_TIME_MINUTES
    assert actual.loc[1, "closest_major_terminal"] == "unknown"
    assert actual.loc[1, "has_rail_access_data"] == 0.0
