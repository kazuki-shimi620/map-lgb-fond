from __future__ import annotations

import csv

import pytest

from collect.land_prices import (
    BoundingBox,
    Tile,
    build_city_summary,
    collect_land_prices,
    enumerate_tiles,
    lat_lon_to_tile,
    normalize_land_price_feature,
)


def test_lat_lon_to_tile_and_enumerate_tiles() -> None:
    x, y = lat_lon_to_tile(35.681236, 139.767125, 14)

    assert isinstance(x, int)
    assert isinstance(y, int)
    assert enumerate_tiles(
        BoundingBox(north=35.7, south=35.6, east=139.8, west=139.7),
        14,
    )


def test_normalize_land_price_feature_extracts_numeric_values() -> None:
    feature = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [139.767125, 35.681236]},
        "properties": {
            "point_id": 3000032,
            "land_price_type": 1,
            "prefecture_code": "13",
            "prefecture_name_ja": "東京都",
            "city_code": "13101",
            "city_county_name_ja": "千代田区",
            "ward_town_village_name_ja": "",
            "use_category_name_ja": "00,住宅地",
            "standard_lot_number_ja": "千代田-1",
            "u_current_years_price_ja": "3,100,000(円/㎡)",
            "last_years_price": 2820000,
            "year_on_year_change_rate": "7.6",
            "u_cadastral_ja": "537(㎡)",
            "nearest_station_name_ja": "東京",
            "u_road_distance_to_nearest_station_name_ja": "150m",
            "area_division_name_ja": "市街化区域",
            "regulations_use_category_name_ja": "商業地域",
            "u_regulations_building_coverage_ratio_ja": "80(%)",
            "u_regulations_floor_area_ratio_ja": "800(%)",
        },
    }

    record = normalize_land_price_feature(
        feature,
        tile=Tile(14, 14547, 6462),
        year=2025,
        source_url="https://example.test/xpt002",
    )

    assert record is not None
    assert record["point_id"] == "3000032"
    assert record["municipality"] == "千代田区"
    assert record["use_category"] == "住宅地"
    assert record["current_price_yen_per_sqm"] == 3_100_000
    assert record["station_distance_m"] == 150
    assert record["building_coverage_ratio"] == 80
    assert record["floor_area_ratio"] == 800
    assert record["lat"] == pytest.approx(35.681236)
    assert record["lon"] == pytest.approx(139.767125)


def test_build_city_summary_groups_by_city_and_category() -> None:
    records = [
        {
            "year": 2025,
            "prefecture": "東京都",
            "municipality": "千代田区",
            "city_code": "13101",
            "use_category": "住宅地",
            "current_price_yen_per_sqm": 100.0,
            "year_on_year_change_rate": 1.0,
        },
        {
            "year": 2025,
            "prefecture": "東京都",
            "municipality": "千代田区",
            "city_code": "13101",
            "use_category": "住宅地",
            "current_price_yen_per_sqm": 300.0,
            "year_on_year_change_rate": 3.0,
        },
    ]

    summary = build_city_summary(records)

    assert len(summary) == 1
    assert summary[0]["point_count"] == 2
    assert summary[0]["avg_price_yen_per_sqm"] == pytest.approx(200.0)
    assert summary[0]["median_price_yen_per_sqm"] == pytest.approx(200.0)
    assert summary[0]["avg_yoy_rate"] == pytest.approx(2.0)


def test_collect_land_prices_writes_csv_from_cached_tile(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    cached_tile = raw_dir / "latest" / "2025" / "z14" / "14547" / "6462.geojson"
    cached_tile.parent.mkdir(parents=True)
    cached_tile.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {"type": "Point", "coordinates": [139.767125, 35.681236]},
              "properties": {
                "point_id": 1,
                "land_price_type": 1,
                "prefecture_name_ja": "東京都",
                "city_code": "13101",
                "city_county_name_ja": "千代田区",
                "ward_town_village_name_ja": "",
                "use_category_name_ja": "00,住宅地",
                "u_current_years_price_ja": "1000(円/㎡)",
                "year_on_year_change_rate": "1.0"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    outputs = collect_land_prices(
        tiles=[Tile(14, 14547, 6462)],
        years=[2025],
        raw_dir=raw_dir,
        processed_dir=tmp_path / "processed",
        cache_dir=tmp_path / "cache",
        api_key="dummy",
        run_id="latest",
        cache=True,
        force=False,
        use_category_codes=["00"],
        price_classification=None,
        timeout_seconds=1,
        max_retries=0,
        request_interval_seconds=0,
        progress_interval=0,
    )

    with outputs["points_csv"].open(encoding="utf-8", newline="") as file:
        points = list(csv.DictReader(file))
    with outputs["city_summary_csv"].open(encoding="utf-8", newline="") as file:
        summaries = list(csv.DictReader(file))

    assert outputs["point_count"] == 1
    assert points[0]["municipality"] == "千代田区"
    assert points[0]["current_price_yen_per_sqm"] == "1000.0"
    assert summaries[0]["point_count"] == "1"
