from __future__ import annotations

import csv

from collect.osm_nearby_facilities import (
    build_overpass_query,
    collect_osm_nearby_facilities,
    collect_osm_nearby_facilities_grid,
    normalize_overpass_element,
    normalize_overpass_elements,
    normalize_park_area_element,
    split_area,
)


def test_normalize_overpass_element_maps_supermarket_node() -> None:
    row = normalize_overpass_element(
        {
            "type": "node",
            "id": 123,
            "lat": 35.681236,
            "lon": 139.767125,
            "tags": {
                "shop": "supermarket",
                "name": "テストスーパー",
                "addr:province": "東京都",
                "addr:city": "千代田区",
            },
        }
    )

    assert row is not None
    assert row["id"] == "osm_node_123"
    assert row["category_id"] == "supermarket"
    assert row["name"] == "テストスーパー"
    assert row["prefecture"] == "東京都"


def test_normalize_overpass_element_uses_center_for_park_way() -> None:
    row = normalize_overpass_element(
        {
            "type": "way",
            "id": 456,
            "center": {"lat": 35.7, "lon": 139.8},
            "tags": {"leisure": "park", "name": "テスト公園"},
        }
    )

    assert row is not None
    assert row["category_id"] == "park"
    assert row["lat"] == 35.7
    assert row["lon"] == 139.8


def test_collect_osm_nearby_facilities_writes_csv_from_cache(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    (raw_dir / "latest.json").write_text(
        """
        {
          "elements": [
            {
              "type": "node",
              "id": 123,
              "lat": 35.681236,
              "lon": 139.767125,
              "tags": {"shop": "convenience", "name": "テストコンビニ"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    outputs = collect_osm_nearby_facilities(
        categories=["convenience_store"],
        area={"south": 35.0, "west": 139.0, "north": 36.0, "east": 140.0},
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        run_id="latest",
        endpoint="https://example.test",
        timeout_seconds=1,
        cache=True,
        force=False,
    )

    assert outputs["nearby_facility_count"] == 1
    with outputs["nearby_facilities_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["category_id"] == "convenience_store"
    assert rows[0]["source"] == "openstreetmap_odbl"


def test_collect_osm_nearby_facilities_writes_park_areas_from_geometry_cache(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    (raw_dir / "latest.json").write_text(
        """
        {
          "elements": [
            {
              "type": "way",
              "id": 456,
              "center": {"lat": 35.0005, "lon": 139.0005},
              "geometry": [
                {"lat": 35.0000, "lon": 139.0000},
                {"lat": 35.0000, "lon": 139.0010},
                {"lat": 35.0010, "lon": 139.0010},
                {"lat": 35.0010, "lon": 139.0000},
                {"lat": 35.0000, "lon": 139.0000}
              ],
              "tags": {"leisure": "park", "name": "テスト大公園"}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    outputs = collect_osm_nearby_facilities(
        categories=["park"],
        area={"south": 35.0, "west": 139.0, "north": 36.0, "east": 140.0},
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        run_id="latest",
        endpoint="https://example.test",
        timeout_seconds=1,
        cache=True,
        force=False,
        include_geometry=True,
    )

    assert outputs["park_area_count"] == 1
    with outputs["park_areas_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["id"] == "osm_way_456"
    assert rows[0]["area_source"] == "geometry"
    assert float(rows[0]["area_sqm"]) > 9_000


def test_collect_osm_nearby_facilities_grid_merges_split_cache(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()
    payload = """
        {
          "elements": [
            {
              "type": "way",
              "id": 456,
              "bounds": {
                "minlat": 35.0000,
                "minlon": 139.0000,
                "maxlat": 35.0010,
                "maxlon": 139.0010
              },
              "geometry": [
                {"lat": 35.0000, "lon": 139.0000},
                {"lat": 35.0000, "lon": 139.0010},
                {"lat": 35.0010, "lon": 139.0010},
                {"lat": 35.0010, "lon": 139.0000},
                {"lat": 35.0000, "lon": 139.0000}
              ],
              "tags": {"leisure": "park", "name": "分割公園"}
            }
          ]
        }
        """
    (raw_dir / "latest_r00_c00.json").write_text(payload, encoding="utf-8")
    (raw_dir / "latest_r00_c01.json").write_text(payload, encoding="utf-8")

    outputs = collect_osm_nearby_facilities_grid(
        categories=["park"],
        area={"south": 35.0, "west": 139.0, "north": 35.1, "east": 139.2},
        split_size_degrees=0.1,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        run_id="latest",
        endpoint="https://example.test",
        timeout_seconds=1,
        cache=True,
        force=False,
        include_geometry=True,
        request_interval_seconds=0,
    )

    assert outputs["element_count"] == 2
    assert outputs["nearby_facility_count"] == 1
    assert outputs["park_area_count"] == 1
    with outputs["park_areas_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["id"] == "osm_way_456"


def test_normalize_park_area_element_uses_bounds_for_relation() -> None:
    row = normalize_park_area_element(
        {
            "type": "relation",
            "id": 789,
            "center": {"lat": 35.0005, "lon": 139.0005},
            "bounds": {
                "minlat": 35.0000,
                "minlon": 139.0000,
                "maxlat": 35.0010,
                "maxlon": 139.0010,
            },
            "tags": {"leisure": "park", "name": "境界公園"},
        }
    )

    assert row is not None
    assert row["id"] == "osm_relation_789"
    assert row["area_source"] == "bounds"
    assert row["area_sqm"] > 9_000


def test_normalize_park_area_element_uses_bounds_center_when_center_is_missing() -> None:
    row = normalize_park_area_element(
        {
            "type": "way",
            "id": 890,
            "bounds": {
                "minlat": 35.0000,
                "minlon": 139.0000,
                "maxlat": 35.0010,
                "maxlon": 139.0010,
            },
            "geometry": [
                {"lat": 35.0000, "lon": 139.0000},
                {"lat": 35.0000, "lon": 139.0010},
                {"lat": 35.0010, "lon": 139.0010},
                {"lat": 35.0010, "lon": 139.0000},
                {"lat": 35.0000, "lon": 139.0000},
            ],
            "tags": {"leisure": "park", "name": "中心補完公園"},
        }
    )

    assert row is not None
    assert row["lat"] == 35.0005
    assert row["lon"] == 139.0005
    assert row["area_source"] == "geometry"


def test_build_overpass_query_contains_requested_categories() -> None:
    query = build_overpass_query(
        categories=["supermarket", "park"],
        south=35.0,
        west=139.0,
        north=36.0,
        east=140.0,
        timeout_seconds=180,
    )

    assert '["shop"="supermarket"]' in query
    assert '["leisure"="park"]' in query
    assert "out center tags" in query


def test_build_overpass_query_contains_cinema_and_hot_spring_filters() -> None:
    query = build_overpass_query(
        categories=["cinema", "hot_spring"],
        south=35.0,
        west=139.0,
        north=36.0,
        east=140.0,
        timeout_seconds=180,
    )

    assert '["amenity"="cinema"]' in query
    assert '["amenity"="public_bath"]' in query
    assert '["leisure"="spa"]' in query
    assert '["natural"="hot_spring"]' in query

    split_query = build_overpass_query(
        categories=["hot_spring_natural"],
        south=20.4,
        west=122.9,
        north=45.6,
        east=154.0,
        timeout_seconds=180,
    )
    assert '["natural"="hot_spring"]' in split_query
    assert '["amenity"="public_bath"]' not in split_query

    node_query = build_overpass_query(
        categories=["hot_spring_public_bath_node"],
        south=20.4,
        west=122.9,
        north=45.6,
        east=154.0,
        timeout_seconds=180,
    )
    assert 'node["amenity"="public_bath"]' in node_query
    assert 'way["amenity"="public_bath"]' not in node_query


def test_build_overpass_query_can_limit_to_japan_administrative_area() -> None:
    query = build_overpass_query(
        categories=["cinema"],
        south=20.4,
        west=122.9,
        north=45.6,
        east=154.0,
        timeout_seconds=180,
        area_filter="JP",
    )
    assert 'area["ISO3166-1"="JP"][admin_level=2]->.searchArea;' in query
    assert '["amenity"="cinema"](area.searchArea)' in query

    direct_query = build_overpass_query(
        categories=["cinema"],
        south=20.4,
        west=122.9,
        north=45.6,
        east=154.0,
        timeout_seconds=180,
        area_filter="JP",
        area_id="3600382313",
    )
    assert "area(3600382313)->.searchArea;" in direct_query
    assert 'ISO3166-1' not in direct_query


def test_normalize_overpass_elements_supports_cinema_and_hot_spring() -> None:
    rows = normalize_overpass_elements(
        [
            {
                "type": "node",
                "id": 1,
                "lat": 35.1,
                "lon": 139.1,
                "tags": {"amenity": "cinema", "name": "テストシネマ"},
            },
            {
                "type": "node",
                "id": 2,
                "lat": 35.2,
                "lon": 139.2,
                "tags": {"amenity": "public_bath", "name": "テスト温泉"},
            },
        ]
    )

    assert [row["category_id"] for row in rows] == ["cinema", "hot_spring"]


def test_hot_spring_tag_takes_priority_over_park_tag() -> None:
    rows = normalize_overpass_elements(
        [
            {
                "type": "way",
                "id": 1,
                "center": {"lat": 34.1, "lon": 131.4},
                "tags": {
                    "leisure": "park",
                    "natural": "hot_spring",
                    "name": "温泉公園",
                },
            }
        ]
    )
    assert rows[0]["category_id"] == "hot_spring"


def test_build_overpass_query_can_request_geometry() -> None:
    query = build_overpass_query(
        categories=["park"],
        south=35.0,
        west=139.0,
        north=36.0,
        east=140.0,
        timeout_seconds=180,
        include_geometry=True,
    )

    assert '["leisure"="park"]' in query
    assert "out center tags geom" in query


def test_split_area_returns_grid_cells() -> None:
    cells = split_area(
        {"south": 35.0, "west": 139.0, "north": 35.2, "east": 139.2},
        split_size_degrees=0.1,
    )

    assert len(cells) == 4
    assert cells[0]["row"] == 0
    assert cells[0]["col"] == 0
    assert cells[-1]["row"] == 1
    assert cells[-1]["col"] == 1
