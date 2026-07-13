from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.reinfolib import REINFOLIB_API_KEY_ENV, REINFOLIB_BASE_URL  # noqa: E402

ENDPOINT = f"{REINFOLIB_BASE_URL}/XPT002"
SCHEMA_VERSION = "1.0.0"
RETRY_STATUSES = {429, 500, 502, 503, 504}
DEFAULT_YEARS = [2024, 2025]
DEFAULT_USE_CATEGORY_CODES = ["00", "05"]
AREAS = {
    "capital": [
        {
            "id": "capital",
            "north": 36.3,
            "south": 34.9,
            "east": 140.9,
            "west": 138.6,
        }
    ],
    "japan": [
        {
            "id": "main_japan",
            "north": 45.7,
            "south": 30.0,
            "east": 146.0,
            "west": 128.0,
        },
        {
            "id": "okinawa",
            "north": 28.0,
            "south": 24.0,
            "east": 131.5,
            "west": 122.5,
        },
        {
            "id": "ogasawara",
            "north": 28.0,
            "south": 20.0,
            "east": 154.0,
            "west": 136.0,
        },
    ],
}

LAND_PRICE_FIELDNAMES = [
    "source_api",
    "point_id",
    "year",
    "land_price_type",
    "prefecture",
    "prefecture_code",
    "municipality",
    "city_code",
    "use_category",
    "standard_lot_number",
    "lat",
    "lon",
    "current_price_yen_per_sqm",
    "last_year_price_yen_per_sqm",
    "year_on_year_change_rate",
    "land_area_sqm",
    "nearest_station",
    "station_distance_m",
    "area_division",
    "zoning",
    "building_coverage_ratio",
    "floor_area_ratio",
    "source_url",
]

CITY_SUMMARY_FIELDNAMES = [
    "year",
    "prefecture",
    "municipality",
    "city_code",
    "use_category",
    "point_count",
    "avg_price_yen_per_sqm",
    "median_price_yen_per_sqm",
    "avg_yoy_rate",
]

NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")


class LandPriceCollectError(RuntimeError):
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


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def lat_lon_to_tile(latitude: float, longitude: float, zoom: int) -> tuple[int, int]:
    if not -85.05112878 <= latitude <= 85.05112878:
        raise ValueError("latitude is outside Web Mercator range")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")
    if not 0 <= zoom <= 30:
        raise ValueError("zoom must be between 0 and 30")

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


def build_tiles(args: argparse.Namespace) -> list[Tile]:
    if args.tile:
        z, x, y = args.tile
        return [Tile(z=z, x=x, y=y)]
    if all(value is not None for value in [args.north, args.south, args.east, args.west]):
        return enumerate_tiles(
            BoundingBox(
                north=args.north,
                south=args.south,
                east=args.east,
                west=args.west,
            ),
            args.zoom,
        )
    if args.area not in AREAS:
        raise LandPriceCollectError(f"unsupported area: {args.area}")

    tiles: set[Tile] = set()
    for area in AREAS[args.area]:
        tiles.update(
            enumerate_tiles(
                BoundingBox(
                    north=area["north"],
                    south=area["south"],
                    east=area["east"],
                    west=area["west"],
                ),
                args.zoom,
            )
        )
    return sorted(tiles)


def build_tile_url(
    *,
    tile: Tile,
    year: int,
    use_category_codes: list[str],
    price_classification: str | None,
) -> str:
    params = {
        "response_format": "geojson",
        "z": str(tile.z),
        "x": str(tile.x),
        "y": str(tile.y),
        "year": str(year),
    }
    if price_classification:
        params["priceClassification"] = price_classification
    if use_category_codes:
        params["useCategoryCode"] = ",".join(use_category_codes)
    return f"{ENDPOINT}?{urlencode(params)}"


def fetch_tile(
    *,
    tile: Tile,
    year: int,
    api_key: str,
    use_category_codes: list[str],
    price_classification: str | None,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
) -> dict[str, Any]:
    url = build_tile_url(
        tile=tile,
        year=year,
        use_category_codes=use_category_codes,
        price_classification=price_classification,
    )
    request = Request(url)
    request.add_header("Ocp-Apim-Subscription-Key", api_key)
    request.add_header("Accept", "application/json")
    request.add_header("Accept-Encoding", "gzip")
    request.add_header("User-Agent", "map-lgb-fond-land-prices/0.1")

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
                raise LandPriceCollectError(
                    f"XPT002 returned HTTP {error.code} for tile {tile}: {detail}"
                ) from error
            time.sleep(_retry_wait_seconds(error, attempt))
        except (
            URLError,
            TimeoutError,
            RemoteDisconnected,
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as error:
            if attempt >= max_retries:
                raise LandPriceCollectError(
                    f"failed to fetch XPT002 tile {tile}: {error}"
                ) from error
            time.sleep(2**attempt)
    raise LandPriceCollectError(f"failed to fetch XPT002 tile {tile}")


def _retry_wait_seconds(error: HTTPError, attempt: int) -> float:
    retry_after = error.headers.get("Retry-After")
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return min(60.0, 2.0 * (2**attempt))


def validate_geojson(data: object) -> None:
    if not isinstance(data, dict):
        raise LandPriceCollectError("GeoJSON response must be an object")
    if data.get("type") != "FeatureCollection":
        raise LandPriceCollectError("GeoJSON type must be FeatureCollection")
    if not isinstance(data.get("features"), list):
        raise LandPriceCollectError("GeoJSON features must be a list")


def normalize_land_price_feature(
    feature: dict[str, Any],
    *,
    tile: Tile,
    year: int,
    source_url: str,
) -> dict[str, Any] | None:
    if feature.get("type") != "Feature":
        return None
    geometry = feature.get("geometry")
    properties = feature.get("properties")
    if not isinstance(geometry, dict) or not isinstance(properties, dict):
        return None
    lon, lat = extract_point_coordinate(geometry)
    if lon is None or lat is None:
        return None
    point_id = _to_text(properties.get("point_id"))
    if not point_id:
        return None

    municipality = "".join(
        value
        for value in [
            _to_text(properties.get("city_county_name_ja")),
            _to_text(properties.get("ward_town_village_name_ja")),
        ]
        if value
    )
    return {
        "source_api": "XPT002",
        "point_id": point_id,
        "year": year,
        "land_price_type": _to_int(properties.get("land_price_type")),
        "prefecture": _to_text(properties.get("prefecture_name_ja")),
        "prefecture_code": _to_text(properties.get("prefecture_code")),
        "municipality": municipality,
        "city_code": _to_text(properties.get("city_code")),
        "use_category": _normalize_use_category(properties.get("use_category_name_ja")),
        "standard_lot_number": _to_text(properties.get("standard_lot_number_ja")),
        "lat": lat,
        "lon": lon,
        "current_price_yen_per_sqm": _extract_number(properties.get("u_current_years_price_ja")),
        "last_year_price_yen_per_sqm": _to_int(properties.get("last_years_price")),
        "year_on_year_change_rate": _to_float(properties.get("year_on_year_change_rate")),
        "land_area_sqm": _extract_number(properties.get("u_cadastral_ja")),
        "nearest_station": _to_text(properties.get("nearest_station_name_ja")),
        "station_distance_m": _extract_number(
            properties.get("u_road_distance_to_nearest_station_name_ja")
        ),
        "area_division": _to_text(properties.get("area_division_name_ja")),
        "zoning": _to_text(properties.get("regulations_use_category_name_ja")),
        "building_coverage_ratio": _extract_number(
            properties.get("u_regulations_building_coverage_ratio_ja")
        ),
        "floor_area_ratio": _extract_number(properties.get("u_regulations_floor_area_ratio_ja")),
        "source_url": source_url,
        "_tile_z": tile.z,
        "_tile_x": tile.x,
        "_tile_y": tile.y,
    }


def extract_point_coordinate(geometry: dict[str, Any]) -> tuple[float | None, float | None]:
    coordinates = geometry.get("coordinates")
    if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, None
    lon = _to_float(coordinates[0])
    lat = _to_float(coordinates[1])
    if lon is None or lat is None:
        return None, None
    if not -180 <= lon <= 180 or not -90 <= lat <= 90:
        return None, None
    return lon, lat


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[object, ...], dict[str, Any]] = {}
    for record in records:
        key = (
            record["point_id"],
            record["year"],
            record["land_price_type"],
            record["use_category"],
        )
        by_key.setdefault(key, record)
    return sorted(
        by_key.values(),
        key=lambda row: (
            str(row["year"]),
            row["prefecture"],
            row["municipality"],
            row["point_id"],
        ),
    )


def build_city_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[object, ...], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            record["year"],
            record["prefecture"],
            record["municipality"],
            record["city_code"],
            record["use_category"],
        )
        grouped.setdefault(key, []).append(record)

    rows = []
    for key, values in grouped.items():
        prices = [
            float(record["current_price_yen_per_sqm"])
            for record in values
            if record["current_price_yen_per_sqm"] is not None
        ]
        yoy_rates = [
            float(record["year_on_year_change_rate"])
            for record in values
            if record["year_on_year_change_rate"] is not None
        ]
        rows.append(
            {
                "year": key[0],
                "prefecture": key[1],
                "municipality": key[2],
                "city_code": key[3],
                "use_category": key[4],
                "point_count": len(values),
                "avg_price_yen_per_sqm": _mean(prices),
                "median_price_yen_per_sqm": _median(prices),
                "avg_yoy_rate": _mean(yoy_rates),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["year"]),
            str(row["prefecture"]),
            str(row["municipality"]),
            str(row["use_category"]),
        ),
    )


def raw_tile_path(raw_dir: Path, run_id: str, year: int, tile: Tile) -> Path:
    return raw_dir / run_id / str(year) / f"z{tile.z}" / str(tile.x) / f"{tile.y}.geojson"


def save_json(path: Path, data: object, *, compact: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def collect_land_prices(
    *,
    tiles: list[Tile],
    years: list[int],
    raw_dir: Path,
    processed_dir: Path,
    cache_dir: Path,
    api_key: str,
    run_id: str,
    cache: bool,
    force: bool,
    use_category_codes: list[str],
    price_classification: str | None,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
    progress_interval: int,
) -> dict[str, Path | int]:
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    raw_records = []
    invalid_features = []
    failed_tiles = []
    manifest_tiles = []

    total = len(tiles) * len(years)
    current = 0
    for year in years:
        for tile in tiles:
            current += 1
            if progress_interval > 0 and (current == 1 or current % progress_interval == 0):
                print(f"land price tiles: {current}/{total}", file=sys.stderr)
            source_url = build_tile_url(
                tile=tile,
                year=year,
                use_category_codes=use_category_codes,
                price_classification=price_classification,
            )
            path = raw_tile_path(raw_dir, run_id, year, tile)
            try:
                if cache and path.exists() and not force:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                else:
                    payload = fetch_tile(
                        tile=tile,
                        year=year,
                        api_key=api_key,
                        use_category_codes=use_category_codes,
                        price_classification=price_classification,
                        timeout_seconds=timeout_seconds,
                        max_retries=max_retries,
                        request_interval_seconds=request_interval_seconds,
                    )
                    save_json(path, payload, compact=True)
                features = payload.get("features", [])
                manifest_tiles.append(_tile_manifest(tile, year, "completed", len(features)))
                for index, feature in enumerate(features):
                    record = normalize_land_price_feature(
                        feature,
                        tile=tile,
                        year=year,
                        source_url=source_url,
                    )
                    if record is None:
                        invalid_features.append(
                            {"tile": tile.__dict__, "year": year, "index": index}
                        )
                    else:
                        raw_records.append(record)
            except (OSError, LandPriceCollectError, json.JSONDecodeError) as error:
                failed_tiles.append({"tile": tile.__dict__, "year": year, "error": str(error)})
                manifest_tiles.append(_tile_manifest(tile, year, "failed", 0, str(error)))

    records = deduplicate_records(raw_records)
    city_summary = build_city_summary(records)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "provider": "国土交通省",
            "service": "不動産情報ライブラリ",
            "apiId": "XPT002",
            "dataset": "地価公示・地価調査のポイント",
        },
        "generatedAt": fetched_at,
        "years": years,
        "tileCount": len(tiles),
        "requestCount": total,
        "completedRequestCount": sum(1 for tile in manifest_tiles if tile["status"] == "completed"),
        "failedRequestCount": len(failed_tiles),
        "pointCount": len(records),
        "citySummaryCount": len(city_summary),
        "useCategoryCodes": use_category_codes,
        "priceClassification": price_classification,
    }

    manifest_path = raw_dir / run_id / "manifest.json"
    points_path = processed_dir / "land_price_points.csv"
    city_summary_path = processed_dir / "land_price_city_summary.csv"
    metadata_path = processed_dir / "metadata.json"
    failed_path = cache_dir / "failed_tiles.json"
    invalid_path = cache_dir / "invalid_features.json"

    save_json(manifest_path, {"tiles": manifest_tiles, **metadata})
    write_csv(points_path, records, LAND_PRICE_FIELDNAMES)
    write_csv(city_summary_path, city_summary, CITY_SUMMARY_FIELDNAMES)
    save_json(metadata_path, metadata)
    save_json(failed_path, failed_tiles)
    save_json(invalid_path, invalid_features)

    return {
        "manifest": manifest_path,
        "points_csv": points_path,
        "city_summary_csv": city_summary_path,
        "metadata": metadata_path,
        "failed_tiles": len(failed_tiles),
        "invalid_features": len(invalid_features),
        "point_count": len(records),
        "city_summary_count": len(city_summary),
    }


def _tile_manifest(
    tile: Tile,
    year: int,
    status: str,
    feature_count: int,
    error: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "z": tile.z,
        "x": tile.x,
        "y": tile.y,
        "year": year,
        "status": "empty" if status == "completed" and feature_count == 0 else status,
        "featureCount": feature_count,
    }
    if error:
        row["error"] = error
    return row


def _to_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _extract_number(value: object) -> float | None:
    if value in (None, ""):
        return None
    match = NUMBER_PATTERN.search(str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _normalize_use_category(value: object) -> str:
    text = _to_text(value)
    if "," in text:
        return text.split(",", 1)[1].strip()
    return text


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[midpoint]
    return (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2


def _parse_years(value: str) -> list[int]:
    years = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        years.append(int(item))
    return years


def _parse_codes(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect MLIT XPT002 land price data.")
    parser.add_argument("--area", choices=sorted(AREAS), default="capital")
    parser.add_argument("--zoom", type=int, default=14)
    parser.add_argument("--tile", nargs=3, type=int, metavar=("Z", "X", "Y"))
    parser.add_argument("--north", type=float)
    parser.add_argument("--south", type=float)
    parser.add_argument("--east", type=float)
    parser.add_argument("--west", type=float)
    parser.add_argument("--years", default=",".join(str(year) for year in DEFAULT_YEARS))
    parser.add_argument(
        "--use-category-codes",
        default=",".join(DEFAULT_USE_CATEGORY_CODES),
        help="Comma-separated XPT002 useCategoryCode values. Empty string means all categories.",
    )
    parser.add_argument("--price-classification")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/land_prices"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/land_prices"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/land_prices"))
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--request-interval-seconds", type=float, default=1.0)
    parser.add_argument("--progress-interval", type=int, default=100)
    args = parser.parse_args()

    load_env_file(Path(__file__).resolve().parents[2] / ".env")
    api_key = os.getenv(REINFOLIB_API_KEY_ENV)
    if not api_key:
        print(f"land price collect failed: {REINFOLIB_API_KEY_ENV} is not set", file=sys.stderr)
        return 1

    try:
        tiles = build_tiles(args)
        outputs = collect_land_prices(
            tiles=tiles,
            years=_parse_years(args.years),
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            cache_dir=args.cache_dir,
            api_key=api_key,
            run_id=args.run_id,
            cache=args.cache,
            force=args.force,
            use_category_codes=_parse_codes(args.use_category_codes),
            price_classification=args.price_classification,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            request_interval_seconds=args.request_interval_seconds,
            progress_interval=args.progress_interval,
        )
    except (ValueError, LandPriceCollectError) as error:
        print(f"land price collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected land prices: "
        f"points={outputs['point_count']} "
        f"city_summary={outputs['city_summary_count']} "
        f"failed_tiles={outputs['failed_tiles']} "
        f"invalid_features={outputs['invalid_features']} "
        f"csv={outputs['points_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
