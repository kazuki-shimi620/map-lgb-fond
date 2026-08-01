from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ID = "XKT013"
ENDPOINT = f"https://www.reinfolib.mlit.go.jp/ex-api/external/{API_ID}"
API_KEY_ENV = "REINFOLIB_API_KEY"
ZOOM = 15
DEFAULT_RUN_ID = "latest"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class FuturePopulationCollectError(RuntimeError):
    pass


@dataclass(frozen=True, order=True)
class Tile:
    z: int
    x: int
    y: int


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def lat_lon_to_tile(latitude: float, longitude: float, zoom: int = ZOOM) -> Tile:
    if not -85.05112878 <= latitude <= 85.05112878:
        raise ValueError("latitude is outside Web Mercator range")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")
    scale = 2**zoom
    x = math.floor((longitude + 180.0) / 360.0 * scale)
    latitude_rad = math.radians(latitude)
    y = math.floor((1.0 - math.asinh(math.tan(latitude_rad)) / math.pi) / 2.0 * scale)
    return Tile(zoom, x, y)


def build_property_tiles(processed_dir: Path, regions: list[str]) -> tuple[list[Tile], int, int]:
    import pandas as pd

    coordinates: set[tuple[float, float]] = set()
    coordinate_rows = 0
    for region in regions:
        path = processed_dir / f"{region}.parquet"
        if not path.exists():
            raise FuturePopulationCollectError(f"processed dataset not found: {path}")
        frame = pd.read_parquet(path, columns=["lat", "lon"]).dropna()
        coordinate_rows += len(frame)
        coordinates.update(
            (float(row.lat), float(row.lon))
            for row in frame.itertuples(index=False)
            if -85.05112878 <= float(row.lat) <= 85.05112878
            and -180 <= float(row.lon) <= 180
        )
    tiles = sorted(lat_lon_to_tile(lat, lon) for lat, lon in coordinates)
    return sorted(set(tiles)), coordinate_rows, len(coordinates)


def raw_tile_path(raw_dir: Path, run_id: str, tile: Tile) -> Path:
    return raw_dir / run_id / API_ID.lower() / str(tile.z) / str(tile.x) / f"{tile.y}.geojson"


def fetch_tile(
    tile: Tile,
    *,
    api_key: str,
    timeout_seconds: int = 60,
    max_retries: int = 3,
) -> dict[str, Any]:
    query = urlencode(
        {"response_format": "geojson", "z": tile.z, "x": tile.x, "y": tile.y}
    )
    request = Request(f"{ENDPOINT}?{query}")
    request.add_header("Ocp-Apim-Subscription-Key", api_key)
    request.add_header("Accept", "application/json")
    request.add_header("Accept-Encoding", "gzip")
    request.add_header("User-Agent", "map-lgb-fond-future-population/0.1")
    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = response.read()
                if "gzip" in (response.headers.get("Content-Encoding") or "").lower():
                    payload = gzip.decompress(payload)
            data = json.loads(payload.decode("utf-8"))
            if data.get("type") != "FeatureCollection" or not isinstance(
                data.get("features"), list
            ):
                raise FuturePopulationCollectError(f"invalid {API_ID} GeoJSON response")
            return data
        except HTTPError as error:
            if error.code not in RETRY_STATUSES or attempt >= max_retries:
                raise FuturePopulationCollectError(
                    f"{API_ID} returned HTTP {error.code} for tile {tile}"
                ) from error
        except (URLError, TimeoutError, RemoteDisconnected) as error:
            if attempt >= max_retries:
                raise FuturePopulationCollectError(
                    f"{API_ID} request failed for tile {tile}: {error}"
                ) from error
        time.sleep(min(2**attempt, 8))
    raise FuturePopulationCollectError(f"{API_ID} request failed for tile {tile}")


def summarize_tile(payload: dict[str, Any], *, byte_count: int) -> dict[str, Any]:
    features = payload.get("features", [])
    properties = [feature.get("properties", {}) for feature in features]
    fields = sorted({key for row in properties for key in row})
    total_population_fields = [
        field for field in fields if field.startswith("PTN_") and field[4:].isdigit()
    ]
    years = sorted(int(field[4:]) for field in total_population_fields)
    null_counts = {
        field: sum(row.get(field) is None for row in properties)
        for field in total_population_fields
    }
    return {
        "bytes": byte_count,
        "featureCount": len(features),
        "fieldCount": len(fields),
        "years": years,
        "totalPopulationFields": total_population_fields,
        "nullCounts": null_counts,
    }


def collect_tiles(
    tiles: list[Tile],
    *,
    raw_dir: Path,
    run_id: str,
    api_key: str,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
    continue_on_error: bool,
    fetcher: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fetch = fetcher or fetch_tile
    fetched_count = 0
    cached_count = 0
    feature_count = 0
    failed_tiles: list[dict[str, Any]] = []
    for tile in tiles:
        output_path = raw_tile_path(raw_dir, run_id, tile)
        if output_path.exists():
            cached_count += 1
            continue
        try:
            payload = fetch(
                tile,
                api_key=api_key,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            fetched_count += 1
            feature_count += len(payload.get("features", []))
            if request_interval_seconds > 0:
                time.sleep(request_interval_seconds)
        except FuturePopulationCollectError as error:
            failed_tiles.append(
                {"z": tile.z, "x": tile.x, "y": tile.y, "error": str(error)}
            )
            if not continue_on_error:
                _save_collection_records(raw_dir, run_id, failed_tiles, {})
                raise

    summary = {
        "apiId": API_ID,
        "runId": run_id,
        "tileCount": len(tiles),
        "fetchedCount": fetched_count,
        "cachedCount": cached_count,
        "failedCount": len(failed_tiles),
        "featureCountInFetchedTiles": feature_count,
    }
    _save_collection_records(raw_dir, run_id, failed_tiles, summary)
    return summary


def _save_collection_records(
    raw_dir: Path,
    run_id: str,
    failed_tiles: list[dict[str, Any]],
    summary: dict[str, Any],
) -> None:
    run_dir = raw_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "failed_tiles.json").write_text(
        json.dumps(failed_tiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if summary:
        (run_dir / "collection_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def build_dry_run_summary(
    tiles: list[Tile],
    *,
    raw_dir: Path,
    run_id: str,
    coordinate_rows: int,
    unique_coordinates: int,
    request_interval_seconds: float,
) -> dict[str, Any]:
    cached_count = sum(raw_tile_path(raw_dir, run_id, tile).exists() for tile in tiles)
    request_count = len(tiles) - cached_count
    return {
        "apiId": API_ID,
        "zoom": ZOOM,
        "runId": run_id,
        "coordinateRows": coordinate_rows,
        "uniqueCoordinates": unique_coordinates,
        "tileCount": len(tiles),
        "cachedCount": cached_count,
        "requestCount": request_count,
        "minimumIntervalSeconds": request_count * request_interval_seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan XKT013 future population collection")
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("data/processed/with_address_coordinates")
    )
    parser.add_argument("--regions", nargs="+", default=["tokyo", "kanagawa", "saitama", "chiba"])
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/future_population"))
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--request-interval-seconds", type=float, default=0.2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--tile", nargs=3, type=int, metavar=("Z", "X", "Y"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--max-tiles", type=int)
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    if args.tile:
        tile = Tile(*args.tile)
        if tile.z != ZOOM:
            raise FuturePopulationCollectError(f"{API_ID} requires z={ZOOM}")
        load_env_file(args.env_file)
        api_key = os.getenv(API_KEY_ENV, "")
        if not api_key:
            raise FuturePopulationCollectError(f"{API_KEY_ENV} is required")
        output_path = raw_tile_path(args.raw_dir, args.run_id, tile)
        if output_path.exists():
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        else:
            payload = fetch_tile(tile, api_key=api_key)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
        print(
            json.dumps(
                summarize_tile(payload, byte_count=output_path.stat().st_size),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.collect:
        load_env_file(args.env_file)
        api_key = os.getenv(API_KEY_ENV, "")
        if not api_key:
            raise FuturePopulationCollectError(f"{API_KEY_ENV} is required")
        tiles, _, _ = build_property_tiles(args.processed_dir, args.regions)
        if args.max_tiles is not None:
            if args.max_tiles < 1:
                raise FuturePopulationCollectError("--max-tiles must be positive")
            tiles = tiles[: args.max_tiles]
        summary = collect_tiles(
            tiles,
            raw_dir=args.raw_dir,
            run_id=args.run_id,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            request_interval_seconds=args.request_interval_seconds,
            continue_on_error=args.continue_on_error,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if not args.dry_run:
        raise FuturePopulationCollectError("specify --dry-run, --collect, or one --tile Z X Y")

    tiles, coordinate_rows, unique_coordinates = build_property_tiles(
        args.processed_dir, args.regions
    )
    summary = build_dry_run_summary(
        tiles,
        raw_dir=args.raw_dir,
        run_id=args.run_id,
        coordinate_rows=coordinate_rows,
        unique_coordinates=unique_coordinates,
        request_interval_seconds=args.request_interval_seconds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
