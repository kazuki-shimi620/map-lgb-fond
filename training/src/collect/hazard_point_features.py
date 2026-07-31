from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.hazard_tiles import (  # noqa: E402
    API_CONFIG,
    ApiTile,
    find_cached_tile,
    raw_tile_path,
    read_json,
    write_json,
)
from collect.reinfolib import REINFOLIB_API_KEY_ENV  # noqa: E402
from collect.urban_planning import (  # noqa: E402
    Tile,
    build_tile_url,
    fetch_tile,
    lat_lon_to_tile,
)
from features.hazard_spatial import point_in_geometry  # noqa: E402

FIELDNAMES = [
    "lat",
    "lon",
    "flood_risk_level",
    "flood_source_available",
    "landslide_risk_level",
    "landslide_special_warning",
    "landslide_source_available",
]


def load_points(processed_dir: Path, regions: list[str]) -> list[tuple[float, float]]:
    import pandas as pd

    points = set()
    for region in regions:
        path = processed_dir / f"{region}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"processed dataset not found: {path}")
        frame = pd.read_parquet(path, columns=["lat", "lon"]).dropna()
        points.update(
            (float(row.lat), float(row.lon))
            for row in frame.itertuples(index=False)
            if -85.05112878 <= float(row.lat) <= 85.05112878
            and -180 <= float(row.lon) <= 180
        )
    return sorted(points)


def group_points_by_tile(
    points: list[tuple[float, float]], api_ids: list[str]
) -> dict[ApiTile, list[tuple[float, float]]]:
    grouped: dict[ApiTile, list[tuple[float, float]]] = defaultdict(list)
    for api_id in api_ids:
        zoom = int(API_CONFIG[api_id]["zoom"])
        for latitude, longitude in points:
            x, y = lat_lon_to_tile(latitude, longitude, zoom)
            grouped[ApiTile(api_id, Tile(zoom, x, y))].append((latitude, longitude))
    return dict(grouped)


def collect_point_features(
    *,
    grouped_points: dict[ApiTile, list[tuple[float, float]]],
    raw_dir: Path,
    output_dir: Path,
    api_key: str,
    run_id: str,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
    max_tiles: int = 0,
) -> dict[str, Any]:
    rows: dict[tuple[float, float], dict[str, Any]] = {}
    errors = []
    items = sorted(
        grouped_points.items(),
        key=lambda pair: (pair[0].api_id, pair[0].tile.z, pair[0].tile.x, pair[0].tile.y),
    )
    if max_tiles > 0:
        items = items[:max_tiles]
    for item, points in items:
        source_url = build_tile_url(api_id=item.api_id, tile=item.tile)
        try:
            cached_path = find_cached_tile(raw_dir, run_id, item)
            if cached_path is not None:
                payload = read_json(cached_path)
            else:
                payload = fetch_tile(
                    url=source_url,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                    request_interval_seconds=request_interval_seconds,
                )
                write_json(raw_tile_path(raw_dir, run_id, item), payload, compact=True)
            _apply_tile_features(rows, points, item.api_id, payload.get("features", []))
        except Exception as error:
            errors.append(
                {
                    "apiId": item.api_id,
                    "z": item.tile.z,
                    "x": item.tile.x,
                    "y": item.tile.y,
                    "error": f"{type(error).__name__}: {error}",
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / "hazard_point_features.csv"
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda row: (row["lat"], row["lon"])))
    metadata = {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "runId": run_id,
        "tileCount": len(items),
        "pointCount": len(rows),
        "errorCount": len(errors),
        "errors": errors,
    }
    write_json(output_dir / "metadata.json", metadata)
    return {"output": str(output_csv), **metadata}


def _apply_tile_features(
    rows: dict[tuple[float, float], dict[str, Any]],
    points: list[tuple[float, float]],
    api_id: str,
    features: list[dict[str, Any]],
) -> None:
    for latitude, longitude in points:
        row = rows.setdefault((latitude, longitude), _empty_row(latitude, longitude))
        if api_id == "XKT026":
            row["flood_source_available"] = 1
        else:
            row["landslide_source_available"] = 1
    for feature in features:
        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            continue
        for latitude, longitude in points:
            if not point_in_geometry(longitude, latitude, geometry):
                continue
            row = rows[(latitude, longitude)]
            if api_id == "XKT026":
                row["flood_risk_level"] = max(
                    row["flood_risk_level"], _number(properties.get("A31a_205"))
                )
            else:
                row["landslide_risk_level"] = max(
                    row["landslide_risk_level"], _number(properties.get("A33_002"))
                )
                row["landslide_special_warning"] = max(
                    row["landslide_special_warning"], _number(properties.get("A33_008"))
                )


def _empty_row(latitude: float, longitude: float) -> dict[str, Any]:
    return {
        "lat": latitude,
        "lon": longitude,
        "flood_risk_level": 0.0,
        "flood_source_available": 0,
        "landslide_risk_level": 0.0,
        "landslide_special_warning": 0.0,
        "landslide_source_available": 0,
    }


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect point-level numeric hazard features.")
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("data/processed/with_address_coordinates")
    )
    parser.add_argument(
        "--regions", nargs="+", default=["tokyo", "kanagawa", "saitama", "chiba"]
    )
    parser.add_argument(
        "--api-ids", nargs="+", choices=sorted(API_CONFIG), default=sorted(API_CONFIG)
    )
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/hazard_tiles"))
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/processed/hazard_point_features")
    )
    parser.add_argument("--run-id", default="capital-points")
    parser.add_argument("--max-tiles", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--request-interval-seconds", type=float, default=0.2)
    parser.add_argument("--api-key-env", default=REINFOLIB_API_KEY_ENV)
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        raise RuntimeError(f"{args.api_key_env} is required")
    points = load_points(args.processed_dir, args.regions)
    grouped = group_points_by_tile(points, args.api_ids)
    result = collect_point_features(
        grouped_points=grouped,
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        api_key=api_key,
        run_id=args.run_id,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        request_interval_seconds=args.request_interval_seconds,
        max_tiles=args.max_tiles,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
