from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.reinfolib import REINFOLIB_API_KEY_ENV  # noqa: E402
from collect.urban_planning import (  # noqa: E402
    AREAS,
    BoundingBox,
    Tile,
    build_tile_url,
    enumerate_tiles,
    fetch_tile,
    lat_lon_to_tile,
)

SCHEMA_VERSION = "1.0.0"
API_CONFIG = {
    "XKT026": {"hazard_type": "flood", "zoom": 14},
    "XKT029": {"hazard_type": "landslide", "zoom": 11},
}
FIELDNAMES = [
    "source_api",
    "hazard_type",
    "risk_level",
    "special_warning",
    "prefecture_code",
    "area_code",
    "area_name",
    "address",
    "geometry_type",
    "geometry_json",
    "source_url",
]


class HazardTileCollectError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiTile:
    api_id: str
    tile: Tile


def build_api_tiles(area: str = "capital") -> list[ApiTile]:
    if area not in AREAS:
        raise HazardTileCollectError(f"unsupported area: {area}")
    bbox = BoundingBox(**AREAS[area])
    return [
        ApiTile(api_id=api_id, tile=tile)
        for api_id, config in API_CONFIG.items()
        for tile in enumerate_tiles(bbox, int(config["zoom"]))
    ]


def build_property_api_tiles(processed_dir: Path, regions: list[str]) -> list[ApiTile]:
    import pandas as pd

    coordinates: set[tuple[float, float]] = set()
    for region in regions:
        path = processed_dir / f"{region}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"processed dataset not found: {path}")
        frame = pd.read_parquet(path, columns=["lat", "lon"]).dropna()
        coordinates.update(
            (float(row.lat), float(row.lon))
            for row in frame.itertuples(index=False)
            if -85.05112878 <= float(row.lat) <= 85.05112878
            and -180 <= float(row.lon) <= 180
        )
    return sorted(
        {
            ApiTile(
                api_id,
                Tile(int(config["zoom"]), *lat_lon_to_tile(lat, lon, int(config["zoom"]))),
            )
            for api_id, config in API_CONFIG.items()
            for lat, lon in coordinates
        },
        key=lambda item: (item.api_id, item.tile.z, item.tile.x, item.tile.y),
    )


def dry_run_summary(api_tiles: list[ApiTile], raw_dir: Path, run_id: str) -> dict[str, Any]:
    by_api = {}
    cached_count = 0
    for item in api_tiles:
        by_api[item.api_id] = by_api.get(item.api_id, 0) + 1
        if find_cached_tile(raw_dir, run_id, item) is not None:
            cached_count += 1
    return {
        "requestCount": len(api_tiles) - cached_count,
        "tileCount": len(api_tiles),
        "cachedCount": cached_count,
        "byApi": by_api,
        "runId": run_id,
    }


def collect_hazard_tiles(
    *,
    api_tiles: list[ApiTile],
    raw_dir: Path,
    processed_dir: Path,
    api_key: str,
    run_id: str,
    cache: bool,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
    continue_on_error: bool,
) -> dict[str, Any]:
    records = []
    manifest = []
    errors = []
    for item in api_tiles:
        path = raw_tile_path(raw_dir, run_id, item)
        source_url = build_tile_url(api_id=item.api_id, tile=item.tile)
        try:
            cached_path = find_cached_tile(raw_dir, run_id, item) if cache else None
            if cached_path is not None:
                payload = read_json(cached_path)
                cache_hit = True
            else:
                payload = fetch_tile(
                    url=source_url,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                    request_interval_seconds=request_interval_seconds,
                )
                write_json(path, payload, compact=True)
                cache_hit = False
            features = payload.get("features", [])
            manifest.append(_manifest_row(item, len(features), cache_hit))
            records.extend(
                row
                for feature in features
                if (row := normalize_feature(feature, item.api_id, source_url)) is not None
            )
        except Exception as error:
            errors.append(
                {
                    **_manifest_row(item, 0, False),
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            if not continue_on_error:
                raise

    rows = deduplicate(records)
    processed_dir.mkdir(parents=True, exist_ok=True)
    areas_csv = processed_dir / "hazard_areas.csv"
    metadata_json = processed_dir / "metadata.json"
    write_csv(areas_csv, rows)
    write_json(
        metadata_json,
        {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "runId": run_id,
            "tileCount": len(api_tiles),
            "successCount": len(manifest),
            "errorCount": len(errors),
            "areaCount": len(rows),
            "tiles": manifest,
            "errors": errors,
        },
    )
    return {
        "hazard_areas_csv": areas_csv,
        "metadata": metadata_json,
        "area_count": len(rows),
        "error_count": len(errors),
    }


def normalize_feature(
    feature: dict[str, Any], api_id: str, source_url: str
) -> dict[str, Any] | None:
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None
    if api_id == "XKT026":
        risk_level = _number(properties.get("A31a_205"))
        special_warning = 0
        prefecture_code = ""
        area_code = _text(properties.get("A31a_201"))
        area_name = _text(properties.get("A31a_202"))
        address = ""
    elif api_id == "XKT029":
        risk_level = _number(properties.get("A33_002"))
        special_warning = _number(properties.get("A33_008"))
        prefecture_code = _text(properties.get("A33_003"))
        area_code = _text(properties.get("A33_004"))
        area_name = _text(properties.get("A33_005"))
        address = _text(properties.get("A33_006"))
    else:
        return None
    return {
        "source_api": api_id,
        "hazard_type": API_CONFIG[api_id]["hazard_type"],
        "risk_level": risk_level,
        "special_warning": special_warning,
        "prefecture_code": prefecture_code,
        "area_code": area_code,
        "area_name": area_name,
        "address": address,
        "geometry_type": _text(geometry.get("type")),
        "geometry_json": json.dumps(geometry, ensure_ascii=False, separators=(",", ":")),
        "source_url": source_url,
    }


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = {}
    for row in rows:
        key = (row["source_api"], row["area_code"], row["geometry_json"])
        result.setdefault(key, row)
    return sorted(
        result.values(),
        key=lambda row: (row["source_api"], row["area_code"], row["area_name"]),
    )


def raw_tile_path(raw_dir: Path, run_id: str, item: ApiTile) -> Path:
    tile = item.tile
    return raw_dir / run_id / item.api_id / f"z{tile.z}" / str(tile.x) / f"{tile.y}.geojson.gz"


def find_cached_tile(raw_dir: Path, run_id: str, item: ApiTile) -> Path | None:
    path = raw_tile_path(raw_dir, run_id, item)
    if path.exists():
        return path
    legacy_path = path.with_suffix("")
    return legacy_path if legacy_path.exists() else None


def _manifest_row(item: ApiTile, feature_count: int, cache_hit: bool) -> dict[str, Any]:
    return {
        "apiId": item.api_id,
        "z": item.tile.z,
        "x": item.tile.x,
        "y": item.tile.y,
        "featureCount": feature_count,
        "cacheHit": cache_hit,
    }


def write_json(path: Path, payload: object, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
            payload,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        )
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as file:
            file.write(serialized + "\n")
    else:
        path.write_text(serialized + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as file:
            return json.load(file)
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect numeric hazard polygon tiles.")
    parser.add_argument("--area", default="capital")
    parser.add_argument("--property-tiles", action="store_true")
    parser.add_argument(
        "--regions", nargs="+", default=["tokyo", "kanagawa", "saitama", "chiba"]
    )
    parser.add_argument(
        "--property-dir", type=Path, default=Path("data/processed/with_address_coordinates")
    )
    parser.add_argument("--tile", nargs=4, metavar=("API", "Z", "X", "Y"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id", default="capital")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/hazard_tiles"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/hazard_tiles"))
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--request-interval-seconds", type=float, default=0.2)
    parser.add_argument("--api-key-env", default=REINFOLIB_API_KEY_ENV)
    args = parser.parse_args()

    if args.tile:
        api_id, z, x, y = args.tile
        if api_id not in API_CONFIG:
            raise HazardTileCollectError(f"unsupported API: {api_id}")
        api_tiles = [ApiTile(api_id, Tile(int(z), int(x), int(y)))]
    elif args.property_tiles:
        api_tiles = build_property_api_tiles(args.property_dir, args.regions)
    else:
        api_tiles = build_api_tiles(args.area)
    if args.dry_run:
        print(json.dumps(dry_run_summary(api_tiles, args.raw_dir, args.run_id), ensure_ascii=False))
        return 0

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        raise HazardTileCollectError(f"{args.api_key_env} is required")
    result = collect_hazard_tiles(
        api_tiles=api_tiles,
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
        api_key=api_key,
        run_id=args.run_id,
        cache=not args.no_cache,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        request_interval_seconds=args.request_interval_seconds,
        continue_on_error=args.continue_on_error,
    )
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
