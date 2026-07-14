from __future__ import annotations

import csv

import pytest

from collect.education_facilities import (
    Tile,
    build_tile_url,
    collect_education_facilities,
    normalize_feature,
)


def test_build_tile_url_adds_administrative_area_code_for_districts_only() -> None:
    tile = Tile(13, 7269, 3235)

    district_url = build_tile_url(
        api_id="XKT004",
        tile=tile,
        administrative_area_codes=["13101", "13102"],
    )
    facility_url = build_tile_url(
        api_id="XKT006",
        tile=tile,
        administrative_area_codes=["13101"],
    )

    assert "administrativeAreaCode=13101%2C13102" in district_url
    assert "administrativeAreaCode" not in facility_url


def test_normalize_feature_handles_district_and_facility() -> None:
    district = normalize_feature(
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "A27_001": "13101",
                "A27_002": "千代田区立",
                "A27_003": "B113210000001",
                "A27_004_ja": "千代田小学校",
                "A27_005": "東京都千代田区",
            },
        },
        api_id="XKT004",
        source_url="https://example.test/xkt004",
    )
    school = normalize_feature(
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [139.75, 35.68]},
            "properties": {
                "P29_001": "13101",
                "P29_002": "B113210000001",
                "P29_003": "16001",
                "P29_003_name_ja": "小学校",
                "P29_004_ja": "千代田小学校",
                "P29_005_ja": "東京都千代田区",
            },
        },
        api_id="XKT006",
        source_url="https://example.test/xkt006",
    )

    assert district is not None
    assert district["district_type"] == "elementary_school_district"
    assert district["school_name"] == "千代田小学校"
    assert school is not None
    assert school["facility_type"] == "小学校"
    assert school["lat"] == pytest.approx(35.68)
    assert school["lon"] == pytest.approx(139.75)


def test_collect_education_facilities_writes_csv_from_cached_tiles(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    tile = Tile(13, 7269, 3235)
    district_tile = raw_dir / "latest" / "XKT004" / "z13" / "7269" / "3235.geojson"
    facility_tile = raw_dir / "latest" / "XKT006" / "z13" / "7269" / "3235.geojson"
    district_tile.parent.mkdir(parents=True)
    facility_tile.parent.mkdir(parents=True)
    district_tile.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {"type": "Polygon", "coordinates": []},
              "properties": {
                "A27_001": "13101",
                "A27_002": "千代田区立",
                "A27_003": "B113210000001",
                "A27_004_ja": "千代田小学校",
                "A27_005": "東京都千代田区"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    facility_tile.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {"type": "Point", "coordinates": [139.75, 35.68]},
              "properties": {
                "P29_001": "13101",
                "P29_002": "B113210000001",
                "P29_003_name_ja": "小学校",
                "P29_004_ja": "千代田小学校",
                "P29_005_ja": "東京都千代田区"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    outputs = collect_education_facilities(
        api_ids=["XKT004", "XKT006"],
        tiles=[tile],
        raw_dir=raw_dir,
        processed_dir=tmp_path / "processed",
        api_key="dummy",
        run_id="latest",
        cache=True,
        force=False,
        administrative_area_codes=["13101"],
        timeout_seconds=1,
        max_retries=0,
        request_interval_seconds=0,
    )

    with outputs["school_districts_csv"].open(encoding="utf-8", newline="") as file:
        districts = list(csv.DictReader(file))
    with outputs["education_facilities_csv"].open(encoding="utf-8", newline="") as file:
        facilities = list(csv.DictReader(file))

    assert outputs["district_count"] == 1
    assert outputs["facility_count"] == 1
    assert districts[0]["school_name"] == "千代田小学校"
    assert facilities[0]["facility_name"] == "千代田小学校"
