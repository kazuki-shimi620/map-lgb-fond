from __future__ import annotations

import csv

from collect.osm_nearby_facilities import (
    build_overpass_query,
    collect_osm_nearby_facilities,
    normalize_overpass_element,
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
