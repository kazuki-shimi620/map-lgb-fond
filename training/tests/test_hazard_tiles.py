from pathlib import Path

from collect.hazard_tiles import (
    ApiTile,
    build_api_tiles,
    build_property_api_tiles,
    dry_run_summary,
    normalize_feature,
)
from collect.urban_planning import Tile


def test_build_api_tiles_uses_minimum_supported_zooms() -> None:
    tiles = build_api_tiles("capital")
    by_api = {}
    for item in tiles:
        by_api[item.api_id] = by_api.get(item.api_id, 0) + 1

    assert by_api == {"XKT026": 8480, "XKT029": 140}


def test_dry_run_summary_counts_cached_tiles(tmp_path: Path) -> None:
    items = [
        ApiTile("XKT026", Tile(14, 1, 2)),
        ApiTile("XKT029", Tile(11, 3, 4)),
    ]
    cached = tmp_path / "run" / "XKT026" / "z14" / "1" / "2.geojson"
    cached.parent.mkdir(parents=True)
    cached.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")

    assert dry_run_summary(items, tmp_path, "run") == {
        "requestCount": 1,
        "tileCount": 2,
        "cachedCount": 1,
        "byApi": {"XKT026": 1, "XKT029": 1},
        "runId": "run",
    }


def test_build_property_api_tiles_deduplicates_coordinates(
    tmp_path: Path, monkeypatch
) -> None:
    import pandas as pd

    frame = pd.DataFrame({"lat": [35.68, 35.68], "lon": [139.76, 139.76]})
    (tmp_path / "tokyo.parquet").touch()
    monkeypatch.setattr(pd, "read_parquet", lambda *args, **kwargs: frame)

    tiles = build_property_api_tiles(tmp_path, ["tokyo"])

    assert len(tiles) == 2
    assert {item.api_id for item in tiles} == {"XKT026", "XKT029"}


def test_normalize_flood_and_landslide_features() -> None:
    geometry = {"type": "Polygon", "coordinates": []}
    flood = normalize_feature(
        {
            "properties": {"A31a_201": "river", "A31a_202": "川", "A31a_205": 3},
            "geometry": geometry,
        },
        "XKT026",
        "https://example.com/flood",
    )
    landslide = normalize_feature(
        {
            "properties": {
                "A33_002": 2,
                "A33_003": "13",
                "A33_004": "area",
                "A33_005": "区域",
                "A33_008": 1,
            },
            "geometry": geometry,
        },
        "XKT029",
        "https://example.com/landslide",
    )

    assert flood is not None and flood["risk_level"] == 3
    assert landslide is not None and landslide["special_warning"] == 1
