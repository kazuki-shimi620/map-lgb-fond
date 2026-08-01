import json
from pathlib import Path

import pytest

from collect.future_population import lat_lon_to_tile, raw_tile_path
from preprocess.future_population import build_future_population_rows


def test_build_future_population_rows_matches_polygon_and_calculates_rates(
    tmp_path: Path,
) -> None:
    latitude, longitude = 35.0, 139.0
    tile = lat_lon_to_tile(latitude, longitude)
    path = raw_tile_path(tmp_path, "latest", tile)
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [138.9, 34.9],
                                    [139.1, 34.9],
                                    [139.1, 35.1],
                                    [138.9, 35.1],
                                    [138.9, 34.9],
                                ]
                            ],
                        },
                        "properties": {
                            "PTN_2020": 100,
                            "PTN_2030": 90,
                            "PTN_2040": 75,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rows, summary = build_future_population_rows(
        [(latitude, longitude)], raw_dir=tmp_path, run_id="latest"
    )

    assert rows[0]["future_population_change_2030_rate"] == pytest.approx(-10.0)
    assert rows[0]["future_population_change_2040_rate"] == pytest.approx(-25.0)
    assert rows[0]["has_future_population_data"] == 1.0
    assert summary["matchedCount"] == 1
    assert summary["missingTileCount"] == 0


def test_build_future_population_rows_records_missing_tile(tmp_path: Path) -> None:
    rows, summary = build_future_population_rows(
        [(35.0, 139.0)], raw_dir=tmp_path, run_id="latest"
    )

    assert rows[0]["has_future_population_data"] == 0.0
    assert summary["matchedCount"] == 0
    assert summary["missingTileCount"] == 1
