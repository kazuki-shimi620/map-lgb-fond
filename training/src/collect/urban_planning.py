from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.reinfolib import REINFOLIB_API_KEY_ENV, REINFOLIB_BASE_URL  # noqa: E402

SCHEMA_VERSION = "1.0.0"
DEFAULT_APIS = ["XKT001", "XKT002", "XKT003"]
DEFAULT_AREA = "capital"
DEFAULT_ZOOM = 13
RETRY_STATUSES = {429, 500, 502, 503, 504}
AREAS = {
    "capital": {
        "north": 36.3,
        "south": 34.9,
        "east": 140.9,
        "west": 138.6,
    }
}
API_LABELS = {
    "XKT001": "city_planning_area",
    "XKT002": "zoning",
    "XKT003": "location_optimization",
}
URBAN_PLANNING_FIELDNAMES = [
    "source_api",
    "area_type",
    "prefecture",
    "city_code",
    "city_name",
    "area_code",
    "area_name",
    "zoning_type",
    "floor_area_ratio",
    "building_coverage_ratio",
    "decision_date",
    "decision_classification",
    "decision_maker",
    "geometry_type",
    "geometry_json",
    "source_url",
]


class UrbanPlanningCollectError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundingBox:
    north: float
    south: float
    east: float
    west: float


@dataclass(frozen=True, order=True)
class Tile:
    z: int
    x: int
    y: int


def lat_lon_to_tile(latitude: float, longitude: float, zoom: int) -> tuple[int, int]:
    n = 2**zoom
    x = math.floor((longitude + 180.0) / 360.0 * n)
    latitude_rad = math.radians(latitude)
    y = math.floor((1.0 - math.asinh(math.tan(latitude_rad)) / math.pi) / 2.0 * n)
    return x, y


def enumerate_tiles(bbox: BoundingBox, zoom: int) -> list[Tile]:
    min_x, min_y = lat_lon_to_tile(bbox.north, bbox.west, zoom)
    max_x, max_y = lat_lon_to_tile(bbox.south, bbox.east, zoom)
    return [
        Tile(z=zoom, x=x, y=y) for x in range(min_x, max_x + 1) for y in range(min_y, max_y + 1)
    ]


def build_tile_url(*, api_id: str, tile: Tile) -> str:
    params = {
        "response_format": "geojson",
        "z": str(tile.z),
        "x": str(tile.x),
        "y": str(tile.y),
    }
    return f"{REINFOLIB_BASE_URL}/{api_id}?{urlencode(params)}"


def fetch_tile(
    *,
    url: str,
    api_key: str,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
) -> dict[str, Any]:
    request = Request(url)
    request.add_header("Ocp-Apim-Subscription-Key", api_key)
    request.add_header("Accept", "application/json")
    request.add_header("Accept-Encoding", "gzip")
    request.add_header("User-Agent", "map-lgb-fond-urban-planning/0.1")
    for attempt in range(max_retries + 1):
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                payload = response.read()
                if "gzip" in (response.headers.get("Content-Encoding") or "").lower():
                    payload = gzip.decompress(payload)
                data = json.loads(payload.decode("utf-8"))
                validate_geojson(data)
                if request_interval_seconds > 0:
                    time.sleep(request_interval_seconds)
                return data
        except HTTPError as error:
            if error.code not in RETRY_STATUSES or attempt >= max_retries:
                detail = error.read().decode("utf-8", errors="replace")[:300]
                raise UrbanPlanningCollectError(f"HTTP {error.code}: {detail}") from error
            time.sleep(min(60.0, 2.0 * (2**attempt)))
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            if attempt >= max_retries:
                raise UrbanPlanningCollectError(f"failed to fetch tile: {error}") from error
            time.sleep(2**attempt)
    raise UrbanPlanningCollectError("failed to fetch tile")


def validate_geojson(data: object) -> None:
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise UrbanPlanningCollectError("GeoJSON type must be FeatureCollection")
    if not isinstance(data.get("features"), list):
        raise UrbanPlanningCollectError("GeoJSON features must be a list")


def normalize_feature(
    feature: dict[str, Any],
    *,
    api_id: str,
    source_url: str,
) -> dict[str, Any] | None:
    if feature.get("type") != "Feature":
        return None
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None
    if api_id == "XKT001":
        area_name = _text(properties.get("area_classification_ja"))
        area_code = _text(properties.get("kubun_id"))
        zoning_type = ""
        floor_area_ratio = None
        building_coverage_ratio = None
    elif api_id == "XKT002":
        area_name = _text(properties.get("use_area_ja"))
        area_code = _text(properties.get("youto_id"))
        zoning_type = area_name
        floor_area_ratio = _extract_number(properties.get("u_floor_area_ratio_ja"))
        building_coverage_ratio = _extract_number(
            properties.get("u_building_coverage_ratio_ja")
        )
    elif api_id == "XKT003":
        area_name = _text(
            properties.get("kubun_name_ja") or properties.get("area_classification_ja")
        )
        area_code = _text(properties.get("kubun_id"))
        zoning_type = ""
        floor_area_ratio = None
        building_coverage_ratio = None
    else:
        return None

    return {
        "source_api": api_id,
        "area_type": API_LABELS[api_id],
        "prefecture": _text(properties.get("prefecture")),
        "city_code": _text(properties.get("city_code")),
        "city_name": _text(properties.get("city_name")),
        "area_code": area_code,
        "area_name": area_name,
        "zoning_type": zoning_type,
        "floor_area_ratio": floor_area_ratio,
        "building_coverage_ratio": building_coverage_ratio,
        "decision_date": _text(properties.get("decision_date")),
        "decision_classification": _text(properties.get("decision_classification")),
        "decision_maker": _text(properties.get("decision_maker")),
        "geometry_type": _text(geometry.get("type")),
        "geometry_json": json.dumps(geometry, ensure_ascii=False, separators=(",", ":")),
        "source_url": source_url,
    }


def collect_urban_planning(
    *,
    api_ids: list[str],
    tiles: list[Tile],
    raw_dir: Path,
    processed_dir: Path,
    api_key: str,
    run_id: str,
    cache: bool,
    force: bool,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
) -> dict[str, Path | int]:
    records = []
    manifest = []
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    for api_id in api_ids:
        if api_id not in API_LABELS:
            raise UrbanPlanningCollectError(f"unsupported API: {api_id}")
        for tile in tiles:
            source_url = build_tile_url(api_id=api_id, tile=tile)
            path = raw_tile_path(raw_dir, run_id, api_id, tile)
            if cache and path.exists() and not force:
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                payload = fetch_tile(
                    url=source_url,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                    request_interval_seconds=request_interval_seconds,
                )
                save_json(path, payload, compact=True)
            features = payload.get("features", [])
            manifest.append(
                {
                    "apiId": api_id,
                    "z": tile.z,
                    "x": tile.x,
                    "y": tile.y,
                    "featureCount": len(features),
                }
            )
            for feature in features:
                record = normalize_feature(feature, api_id=api_id, source_url=source_url)
                if record:
                    records.append(record)

    rows = deduplicate(records)
    processed_dir.mkdir(parents=True, exist_ok=True)
    areas_path = processed_dir / "urban_planning_areas.csv"
    metadata_path = processed_dir / "metadata.json"
    write_csv(areas_path, rows, URBAN_PLANNING_FIELDNAMES)
    save_json(
        metadata_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": generated_at,
            "apiIds": api_ids,
            "tileCount": len(tiles),
            "requestCount": len(tiles) * len(api_ids),
            "areaCount": len(rows),
            "tiles": manifest,
        },
    )
    return {
        "urban_planning_areas_csv": areas_path,
        "metadata": metadata_path,
        "area_count": len(rows),
    }


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {}
    for row in rows:
        key = (
            row["source_api"],
            row["city_code"],
            row["area_code"],
            row["area_name"],
            row["geometry_json"],
        )
        by_key.setdefault(key, row)
    return sorted(
        by_key.values(),
        key=lambda row: (
            _text(row.get("source_api")),
            _text(row.get("city_code")),
            _text(row.get("area_code")),
            _text(row.get("area_name")),
        ),
    )


def raw_tile_path(raw_dir: Path, run_id: str, api_id: str, tile: Tile) -> Path:
    return raw_dir / run_id / api_id / f"z{tile.z}" / str(tile.x) / f"{tile.y}.geojson"


def save_json(path: Path, data: object, *, compact: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(
        data,
        ensure_ascii=False,
        separators=(",", ":") if compact else None,
        indent=None if compact else 2,
    )
    path.write_text(text + "\n", encoding="utf-8")
    return path


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def build_tiles(args: argparse.Namespace) -> list[Tile]:
    if args.tile:
        z, x, y = args.tile
        return [Tile(z=z, x=x, y=y)]
    if args.area not in AREAS:
        raise UrbanPlanningCollectError(f"unsupported area: {args.area}")
    area = AREAS[args.area]
    return enumerate_tiles(
        BoundingBox(
            north=area["north"],
            south=area["south"],
            east=area["east"],
            west=area["west"],
        ),
        args.zoom,
    )


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _extract_number(value: object) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).replace(",", "")
    number = ""
    for char in text:
        if char.isdigit() or char in ".-":
            number += char
        elif number:
            break
    if not number:
        return None
    try:
        return float(number)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect urban planning data.")
    parser.add_argument("--apis", default=",".join(DEFAULT_APIS))
    parser.add_argument("--area", default=DEFAULT_AREA)
    parser.add_argument("--zoom", type=int, default=DEFAULT_ZOOM)
    parser.add_argument("--tile", nargs=3, type=int)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/urban_planning"))
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/processed/urban_planning"),
    )
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--request-interval-seconds", type=float, default=1.0)
    parser.add_argument("--api-key", default=os.environ.get(REINFOLIB_API_KEY_ENV, ""))
    args = parser.parse_args()

    try:
        if not args.api_key:
            raise UrbanPlanningCollectError(f"{REINFOLIB_API_KEY_ENV} is required")
        outputs = collect_urban_planning(
            api_ids=[item.strip() for item in args.apis.split(",") if item.strip()],
            tiles=build_tiles(args),
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            api_key=args.api_key,
            run_id=args.run_id,
            cache=args.cache,
            force=args.force,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            request_interval_seconds=args.request_interval_seconds,
        )
    except UrbanPlanningCollectError as error:
        print(f"urban planning collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected urban planning: "
        f"areas={outputs['area_count']} "
        f"areas_csv={outputs['urban_planning_areas_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
