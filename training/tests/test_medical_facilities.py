from __future__ import annotations

import csv

from collect.medical_facilities import (
    Tile,
    build_tile_url,
    collect_medical_facilities,
    normalize_feature,
)


def test_normalize_feature_extracts_medical_facility_point() -> None:
    feature = {
        "type": "Feature",
        "properties": {
            "P04_001": "1",
            "P04_001_name_ja": "病院",
            "P04_002_ja": "東京テスト病院",
            "P04_003_ja": "東京都千代田区丸の内1-1-1",
            "P04_004": "内科",
            "P04_005": "外科",
            "P04_008": "120",
            "P04_009": "1",
            "P04_010": "0",
        },
        "geometry": {"type": "Point", "coordinates": [139.767125, 35.681236]},
    }

    row = normalize_feature(feature, source_url="https://example.test")

    assert row is not None
    assert row["source_api"] == "XKT010"
    assert row["facility_class_name"] == "病院"
    assert row["facility_name"] == "東京テスト病院"
    assert row["medical_subjects"] == "内科;外科"
    assert row["bed_count"] == 120
    assert row["lat"] == 35.681236
    assert row["lon"] == 139.767125


def test_collect_medical_facilities_writes_nearby_facility_csv_from_cache(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    tile = Tile(z=13, x=7272, y=3232)
    raw_path = raw_dir / "latest" / "XKT010" / "z13" / "7272" / "3232.geojson"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_text(
        """
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "properties": {
                "P04_001_name_ja": "病院",
                "P04_002_ja": "東京テスト病院",
                "P04_003_ja": "東京都千代田区丸の内1-1-1",
                "P04_008": "120"
              },
              "geometry": {"type": "Point", "coordinates": [139.767125, 35.681236]}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    outputs = collect_medical_facilities(
        tiles=[tile],
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        api_key="dummy",
        run_id="latest",
        cache=True,
        force=False,
        timeout_seconds=1,
        max_retries=0,
        request_interval_seconds=0,
    )

    assert outputs["facility_count"] == 1
    with outputs["nearby_facilities_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert rows[0]["category_id"] == "hospital"
    assert rows[0]["name"] == "東京テスト病院"
    assert rows[0]["source"] == "reinfolib_xkt010"


def test_build_tile_url_uses_xkt010() -> None:
    url = build_tile_url(tile=Tile(z=13, x=7272, y=3232))

    assert "/XKT010?" in url
    assert "response_format=geojson" in url
