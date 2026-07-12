from __future__ import annotations

import pytest

from collect.station_passengers import (
    BoundingBox,
    Tile,
    aggregate_passenger_counts,
    aggregate_station_groups,
    calculate_log_passenger_count,
    calculate_station_rank,
    enumerate_tiles,
    lat_lon_to_tile,
    normalize_feature,
    normalize_station_name,
    passenger_year_fields,
)


def test_lat_lon_to_tile_and_enumerate_tiles() -> None:
    x, y = lat_lon_to_tile(35.681236, 139.767125, 11)

    assert isinstance(x, int)
    assert isinstance(y, int)
    assert enumerate_tiles(
        BoundingBox(north=35.7, south=35.6, east=139.8, west=139.7),
        11,
    )


def test_normalize_station_name_removes_suffix() -> None:
    assert normalize_station_name(" 大宮駅 ") == "大宮"
    assert normalize_station_name("大宮（埼玉）") == "大宮(埼玉)"


def test_passenger_year_fields_preserve_expected_codes() -> None:
    fields = passenger_year_fields()

    assert fields[2011]["passengers"] == "S12_009"
    assert fields[2023]["passengers"] == "S12_057"


def test_normalize_feature_preserves_station_code_and_latest_count() -> None:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [139.654321, 35.487654]},
        "properties": {
            "S12_001_ja": "新子安駅",
            "S12_001c": "004562",
            "S12_001g": "004562",
            "S12_002_ja": "東日本旅客鉄道",
            "S12_003_ja": "東海道線",
            "S12_004": "11",
            "S12_005": "2",
            "S12_006": "1",
            "S12_007": "1",
            "S12_008": "",
            "S12_009": "42174",
            "S12_054": "1",
            "S12_055": "1",
            "S12_056": "",
            "S12_057": "40962",
        },
    }

    record = normalize_feature(feature, Tile(14, 14547, 6462), "2026-07-10T00:00:00Z")

    assert record is not None
    assert record["stationCode"] == "004562"
    assert record["normalizedStationName"] == "新子安"
    assert record["normalizedOperatorName"] == "JR東日本"
    assert record["latestPassengerCount"] == 40962
    assert record["latestPassengerYear"] == 2023


def test_normalize_feature_accepts_linestring_geometry() -> None:
    feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[139.0, 35.0], [139.2, 35.2]],
        },
        "properties": {
            "S12_001_ja": "新子安",
            "S12_001c": "004562",
            "S12_001g": "004562",
            "S12_002_ja": "東日本旅客鉄道",
            "S12_003_ja": "東海道線",
            "S12_004": "11",
            "S12_005": "2",
            "S12_054": "1",
            "S12_055": "1",
            "S12_056": "",
            "S12_057": "40962",
        },
    }

    record = normalize_feature(feature, Tile(14, 14547, 6462), "2026-07-10T00:00:00Z")

    assert record is not None
    assert record["location"]["longitude"] == pytest.approx(139.1)
    assert record["location"]["latitude"] == pytest.approx(35.1)


def test_aggregate_station_groups_uses_max_fallback_for_different_counts() -> None:
    base_record = {
        "stationCode": "001",
        "groupCode": "grp001",
        "stationName": "テスト",
        "normalizedStationName": "テスト",
        "operatorName": "A",
        "normalizedOperatorName": "A",
        "lineName": "L1",
        "normalizedLineName": "L1",
        "location": {"latitude": 35.0, "longitude": 139.0},
        "passengerHistory": [
            {"year": year, "passengerCount": 100 if year == 2023 else None}
            for year in range(2011, 2024)
        ],
    }
    other_record = {
        **base_record,
        "stationCode": "002",
        "normalizedOperatorName": "B",
        "normalizedLineName": "L2",
        "passengerHistory": [
            {"year": year, "passengerCount": 200 if year == 2023 else None}
            for year in range(2011, 2024)
        ],
    }

    groups = aggregate_station_groups([base_record, other_record])

    assert len(groups) == 1
    assert groups[0]["latestPassengerCount"] == 200
    assert groups[0]["passengerHistory"][-1]["aggregationMethod"] == "max_fallback"
    assert groups[0]["lineCount"] == 2


@pytest.mark.parametrize(
    ("count", "rank"),
    [
        (500_000, "S"),
        (100_000, "A"),
        (50_000, "B"),
        (20_000, "C"),
        (5_000, "D"),
        (1, "E"),
        (None, None),
    ],
)
def test_calculate_station_rank(count: int | None, rank: str | None) -> None:
    assert calculate_station_rank(count) == rank


def test_aggregate_passenger_counts_and_log() -> None:
    assert aggregate_passenger_counts([None, -1]) == (None, "unavailable")
    assert aggregate_passenger_counts([100, 100]) == (100, "deduplicated")
    assert aggregate_passenger_counts([100, 200]) == (200, "max_fallback")
    assert calculate_log_passenger_count(0) == pytest.approx(0.0)
