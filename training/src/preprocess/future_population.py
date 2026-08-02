from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.future_population import Tile, lat_lon_to_tile, raw_tile_path  # noqa: E402
from features.hazard_spatial import point_in_geometry  # noqa: E402

OUTPUT_FIELDS = (
    "lat",
    "lon",
    "future_population_2020",
    "future_population_2030",
    "future_population_2040",
    "future_population_change_2030_rate",
    "future_population_change_2040_rate",
    "has_future_population_data",
)


def load_unique_coordinates(processed_dir: Path, regions: list[str]) -> list[tuple[float, float]]:
    import pandas as pd

    coordinates: set[tuple[float, float]] = set()
    for region in regions:
        path = processed_dir / f"{region}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"processed dataset not found: {path}")
        frame = pd.read_parquet(path, columns=["lat", "lon"]).dropna()
        coordinates.update(
            (float(row.lat), float(row.lon)) for row in frame.itertuples(index=False)
        )
    return sorted(coordinates)


def build_future_population_rows(
    coordinates: list[tuple[float, float]], *, raw_dir: Path, run_id: str
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    tile_payloads: dict[Tile, dict[str, Any] | None] = {}
    rows = []
    missing_tile_count = 0
    matched_count = 0
    for latitude, longitude in coordinates:
        tile = lat_lon_to_tile(latitude, longitude)
        if tile not in tile_payloads:
            path = raw_tile_path(raw_dir, run_id, tile)
            if path.exists():
                tile_payloads[tile] = json.loads(path.read_text(encoding="utf-8"))
            else:
                tile_payloads[tile] = None
                missing_tile_count += 1
        feature = _find_feature(tile_payloads[tile], latitude, longitude)
        row = _build_row(latitude, longitude, feature)
        matched_count += int(row["has_future_population_data"])
        rows.append(row)
    return rows, {
        "coordinateCount": len(coordinates),
        "tileCount": len(tile_payloads),
        "missingTileCount": missing_tile_count,
        "matchedCount": matched_count,
        "unmatchedCount": len(coordinates) - matched_count,
    }


def _find_feature(
    payload: dict[str, Any] | None, latitude: float, longitude: float
) -> dict[str, Any] | None:
    if not payload:
        return None
    for feature in payload.get("features", []):
        geometry = feature.get("geometry")
        if isinstance(geometry, dict) and point_in_geometry(longitude, latitude, geometry):
            return feature
    return None


def _build_row(
    latitude: float, longitude: float, feature: dict[str, Any] | None
) -> dict[str, Any]:
    properties = feature.get("properties", {}) if feature else {}
    population_2020 = _number(properties.get("PTN_2020"))
    population_2030 = _number(properties.get("PTN_2030"))
    population_2040 = _number(properties.get("PTN_2040"))
    has_data = population_2020 is not None and population_2020 > 0
    return {
        "lat": latitude,
        "lon": longitude,
        "future_population_2020": population_2020 or 0.0,
        "future_population_2030": population_2030 or 0.0,
        "future_population_2040": population_2040 or 0.0,
        "future_population_change_2030_rate": _change_rate(
            population_2020, population_2030
        ),
        "future_population_change_2040_rate": _change_rate(
            population_2020, population_2040
        ),
        "has_future_population_data": float(has_data),
    }


def _number(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number


def _change_rate(baseline: float | None, future: float | None) -> float:
    if baseline is None or baseline <= 0 or future is None:
        return 0.0
    return (future - baseline) / baseline * 100.0


def write_rows(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build point-level future population features")
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("data/processed/with_address_coordinates")
    )
    parser.add_argument("--regions", nargs="+", default=["tokyo", "kanagawa", "saitama", "chiba"])
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/future_population"))
    parser.add_argument("--run-id", default="latest")
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/future_population/features.csv")
    )
    args = parser.parse_args()

    coordinates = load_unique_coordinates(args.processed_dir, args.regions)
    rows, summary = build_future_population_rows(
        coordinates, raw_dir=args.raw_dir, run_id=args.run_id
    )
    write_rows(rows, args.output)
    summary_path = args.output.with_name("summary.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
