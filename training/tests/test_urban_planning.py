from __future__ import annotations

import csv

import pytest

from collect.urban_planning import (
    Tile,
    build_tile_url,
    collect_urban_planning,
    normalize_feature,
)


def test_build_tile_url_uses_geojson_xyz_parameters() -> None:
    url = build_tile_url(api_id="XKT002", tile=Tile(13, 7269, 3235))

    assert url.endswith("XKT002?response_format=geojson&z=13&x=7269&y=3235")


def test_normalize_feature_handles_zoning_values() -> None:
    record = normalize_feature(
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {
                "youto_id": 11,
                "prefecture": "東京都",
                "city_code": "13101",
                "city_name": "千代田区",
                "use_area_ja": "商業地域",
                "u_floor_area_ratio_ja": "600%",
                "u_building_coverage_ratio_ja": "80%",
                "decision_date": "2020-01-01",
            },
        },
        api_id="XKT002",
        source_url="https://example.test/xkt002",
    )

    assert record is not None
    assert record["area_type"] == "zoning"
    assert record["zoning_type"] == "商業地域"
    assert record["floor_area_ratio"] == pytest.approx(600.0)
    assert record["building_coverage_ratio"] == pytest.approx(80.0)


def test_normalize_feature_handles_city_planning_area() -> None:
    record = normalize_feature(
        {
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": []},
            "properties": {
                "prefecture": "東京都",
                "city_code": "13101",
                "city_name": "千代田区",
                "kubun_id": 21,
                "area_classification_ja": "市街化区域",
            },
        },
        api_id="XKT001",
        source_url="https://example.test/xkt001",
    )

    assert record is not None
    assert record["area_type"] == "city_planning_area"
    assert record["area_name"] == "市街化区域"
    assert record["geometry_type"] == "MultiPolygon"


def test_collect_urban_planning_writes_csv_from_cached_tiles(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    tile = Tile(13, 7269, 3235)
    cached_tile = raw_dir / "latest" / "XKT002" / "z13" / "7269" / "3235.geojson"
    cached_tile.parent.mkdir(parents=True)
    cached_tile.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {"type": "Polygon", "coordinates": []},
              "properties": {
                "youto_id": 11,
                "prefecture": "東京都",
                "city_code": "13101",
                "city_name": "千代田区",
                "use_area_ja": "商業地域",
                "u_floor_area_ratio_ja": "600%",
                "u_building_coverage_ratio_ja": "80%"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    outputs = collect_urban_planning(
        api_ids=["XKT002"],
        tiles=[tile],
        raw_dir=raw_dir,
        processed_dir=tmp_path / "processed",
        api_key="dummy",
        run_id="latest",
        cache=True,
        force=False,
        timeout_seconds=1,
        max_retries=0,
        request_interval_seconds=0,
    )

    with outputs["urban_planning_areas_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert outputs["area_count"] == 1
    assert rows[0]["zoning_type"] == "商業地域"
    assert rows[0]["floor_area_ratio"] == "600.0"
