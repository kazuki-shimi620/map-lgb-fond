from pathlib import Path

import pandas as pd
import pytest

from collect.future_population import (
    Tile,
    build_dry_run_summary,
    build_property_tiles,
    collect_tiles,
    lat_lon_to_tile,
    raw_tile_path,
    summarize_tile,
)


def test_lat_lon_to_tile_matches_xkt013_example() -> None:
    assert lat_lon_to_tile(41.77, 140.75) == Tile(15, 29195, 12192)


def test_build_property_tiles_deduplicates_coordinates_and_tiles(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    pd.DataFrame(
        [
            {"lat": 35.6812, "lon": 139.7671},
            {"lat": 35.6812, "lon": 139.7671},
            {"lat": None, "lon": None},
        ]
    ).to_parquet(processed_dir / "tokyo.parquet", index=False)

    tiles, coordinate_rows, unique_coordinates = build_property_tiles(
        processed_dir, ["tokyo"]
    )

    assert len(tiles) == 1
    assert coordinate_rows == 2
    assert unique_coordinates == 1


def test_dry_run_summary_excludes_cached_tiles(tmp_path: Path) -> None:
    tiles = [Tile(15, 1, 2), Tile(15, 3, 4)]
    cached = raw_tile_path(tmp_path, "latest", tiles[0])
    cached.parent.mkdir(parents=True)
    cached.write_text("{}", encoding="utf-8")

    summary = build_dry_run_summary(
        tiles,
        raw_dir=tmp_path,
        run_id="latest",
        coordinate_rows=10,
        unique_coordinates=2,
        request_interval_seconds=0.25,
    )

    assert summary["cachedCount"] == 1
    assert summary["requestCount"] == 1
    assert summary["minimumIntervalSeconds"] == pytest.approx(0.25)


def test_summarize_tile_reports_years_and_null_counts() -> None:
    payload = {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"PTN_2020": 100.0, "PTN_2030": 90.0}},
            {"properties": {"PTN_2020": 50.0, "PTN_2030": None}},
        ],
    }

    summary = summarize_tile(payload, byte_count=123)

    assert summary["years"] == [2020, 2030]
    assert summary["featureCount"] == 2
    assert summary["nullCounts"] == {"PTN_2020": 0, "PTN_2030": 1}


def test_collect_tiles_uses_cache_and_records_summary(tmp_path: Path) -> None:
    tiles = [Tile(15, 1, 2), Tile(15, 3, 4)]
    cached = raw_tile_path(tmp_path, "latest", tiles[0])
    cached.parent.mkdir(parents=True)
    cached.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")

    summary = collect_tiles(
        tiles,
        raw_dir=tmp_path,
        run_id="latest",
        api_key="test",
        timeout_seconds=1,
        max_retries=0,
        request_interval_seconds=0,
        continue_on_error=False,
        fetcher=lambda *_args, **_kwargs: {
            "type": "FeatureCollection",
            "features": [{"properties": {"PTN_2030": 1}}],
        },
    )

    assert summary == {
        "apiId": "XKT013",
        "runId": "latest",
        "tileCount": 2,
        "fetchedCount": 1,
        "cachedCount": 1,
        "failedCount": 0,
        "featureCountInFetchedTiles": 1,
    }
    assert raw_tile_path(tmp_path, "latest", tiles[1]).exists()
    assert (tmp_path / "latest" / "failed_tiles.json").read_text(encoding="utf-8") == "[]\n"


def test_collect_tiles_records_failure_and_continues(tmp_path: Path) -> None:
    def fail(*_args, **_kwargs):
        from collect.future_population import FuturePopulationCollectError

        raise FuturePopulationCollectError("request failed")

    summary = collect_tiles(
        [Tile(15, 1, 2)],
        raw_dir=tmp_path,
        run_id="latest",
        api_key="test",
        timeout_seconds=1,
        max_retries=0,
        request_interval_seconds=0,
        continue_on_error=True,
        fetcher=fail,
    )

    assert summary["failedCount"] == 1
    failures = (tmp_path / "latest" / "failed_tiles.json").read_text(encoding="utf-8")
    assert "request failed" in failures
