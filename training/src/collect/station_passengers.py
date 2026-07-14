from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
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

from collect.reinfolib import REINFOLIB_API_KEY_ENV  # noqa: E402

ENDPOINT = "https://www.reinfolib.mlit.go.jp/ex-api/external/XKT015"
SCHEMA_VERSION = "1.0.0"
AVAILABLE_YEARS = list(range(2011, 2024))
RETRY_STATUSES = {429, 500, 502, 503, 504}
CONTROL_CHARACTER_PATTERN = re.compile(r"[\u0000-\u001F\u007F-\u009F]")
MULTI_SPACE_PATTERN = re.compile(r"\s+")
STATION_SUFFIX_PATTERN = re.compile(r"駅$")
OPERATOR_ALIASES = {
    "東日本旅客鉄道": "JR東日本",
    "東海旅客鉄道": "JR東海",
    "西日本旅客鉄道": "JR西日本",
    "北海道旅客鉄道": "JR北海道",
    "四国旅客鉄道": "JR四国",
    "九州旅客鉄道": "JR九州",
    "日本貨物鉄道": "JR貨物",
}
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


class StationPassengerCollectError(RuntimeError):
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
        raise StationPassengerCollectError(f"unsupported area: {args.area}")

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


def fetch_tile(
    *,
    tile: Tile,
    api_key: str,
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
) -> dict[str, Any]:
    params = urlencode(
        {
            "response_format": "geojson",
            "z": str(tile.z),
            "x": str(tile.x),
            "y": str(tile.y),
        }
    )
    request = Request(f"{ENDPOINT}?{params}")
    request.add_header("Ocp-Apim-Subscription-Key", api_key)
    request.add_header("Accept", "application/json")
    request.add_header("Accept-Encoding", "gzip")
    request.add_header("User-Agent", "map-lgb-fond-station-passengers/0.1")

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
                raise StationPassengerCollectError(
                    f"XKT015 returned HTTP {error.code} for tile {tile}: {detail}"
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
                raise StationPassengerCollectError(
                    f"failed to fetch XKT015 tile {tile}: {error}"
                ) from error
            time.sleep(2**attempt)
    raise StationPassengerCollectError(f"failed to fetch XKT015 tile {tile}")


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
        raise StationPassengerCollectError("GeoJSON response must be an object")
    if data.get("type") != "FeatureCollection":
        raise StationPassengerCollectError("GeoJSON type must be FeatureCollection")
    if not isinstance(data.get("features"), list):
        raise StationPassengerCollectError("GeoJSON features must be a list")


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = normalized.replace("\u3000", " ")
    normalized = CONTROL_CHARACTER_PATTERN.sub("", normalized)
    normalized = MULTI_SPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def normalize_station_name(value: object) -> str:
    normalized = normalize_text(value)
    return STATION_SUFFIX_PATTERN.sub("", normalized)


def normalize_operator_name(value: object) -> str:
    normalized = normalize_text(value)
    return OPERATOR_ALIASES.get(normalized, normalized)


def passenger_year_fields() -> dict[int, dict[str, str]]:
    fields: dict[int, dict[str, str]] = {}
    index = 6
    for year in AVAILABLE_YEARS:
        fields[year] = {
            "duplicate_code": f"S12_{index:03d}",
            "availability_code": f"S12_{index + 1:03d}",
            "note": f"S12_{index + 2:03d}",
            "passengers": f"S12_{index + 3:03d}",
        }
        index += 4
    return fields


def normalize_passenger_count(value: object, is_available: bool) -> int | None:
    if not is_available or value in (None, ""):
        return None
    try:
        count = int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None
    return count if count >= 0 else None


def is_available_code(value: object) -> bool:
    text = normalize_text(value)
    return text not in {"", "0", "9", "なし", "無", "不明"}


def normalize_feature(
    feature: dict[str, Any],
    tile: Tile,
    fetched_at: str,
) -> dict[str, Any] | None:
    if feature.get("type") != "Feature":
        return None
    geometry = feature.get("geometry")
    properties = feature.get("properties")
    if not isinstance(geometry, dict) or not isinstance(properties, dict):
        return None
    longitude, latitude = extract_representative_coordinate(geometry)
    if longitude is None or latitude is None:
        return None
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        return None

    station_name = normalize_text(properties.get("S12_001_ja"))
    if not station_name:
        return None

    passenger_history = []
    for year, fields in passenger_year_fields().items():
        availability_code = normalize_text(properties.get(fields["availability_code"])) or None
        is_available = is_available_code(availability_code)
        passenger_history.append(
            {
                "year": year,
                "passengerCount": normalize_passenger_count(
                    properties.get(fields["passengers"]),
                    is_available,
                ),
                "availabilityCode": availability_code,
                "duplicateCode": normalize_text(properties.get(fields["duplicate_code"])) or None,
                "note": normalize_text(properties.get(fields["note"])) or None,
                "isAvailable": is_available,
            }
        )

    latest = get_latest_passenger_record(passenger_history)
    return {
        "stationCode": normalize_text(properties.get("S12_001c")) or None,
        "groupCode": normalize_text(properties.get("S12_001g")) or None,
        "stationName": station_name,
        "normalizedStationName": normalize_station_name(station_name),
        "operatorName": normalize_text(properties.get("S12_002_ja")),
        "normalizedOperatorName": normalize_operator_name(properties.get("S12_002_ja")),
        "lineName": normalize_text(properties.get("S12_003_ja")),
        "normalizedLineName": normalize_text(properties.get("S12_003_ja")),
        "railwayTypeCode": normalize_text(properties.get("S12_004")) or None,
        "operatorTypeCode": normalize_text(properties.get("S12_005")) or None,
        "location": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "passengerHistory": passenger_history,
        "latestPassengerCount": latest["passengerCount"] if latest else None,
        "latestPassengerYear": latest["year"] if latest else None,
        "source": {
            "provider": "MLIT",
            "apiId": "XKT015",
            "fetchedAt": fetched_at,
            "tile": {"z": tile.z, "x": tile.x, "y": tile.y},
        },
    }


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_representative_coordinate(
    geometry: dict[str, Any],
) -> tuple[float | None, float | None]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Point" and isinstance(coordinates, list) and len(coordinates) >= 2:
        return _to_float(coordinates[0]), _to_float(coordinates[1])
    if geometry_type == "LineString" and isinstance(coordinates, list):
        points = [
            (_to_float(point[0]), _to_float(point[1]))
            for point in coordinates
            if isinstance(point, list) and len(point) >= 2
        ]
        valid_points = [(lon, lat) for lon, lat in points if lon is not None and lat is not None]
        if valid_points:
            longitude = sum(point[0] for point in valid_points) / len(valid_points)
            latitude = sum(point[1] for point in valid_points) / len(valid_points)
            return longitude, latitude
    return None, None


def get_latest_passenger_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid_records = [record for record in records if record.get("passengerCount") is not None]
    if not valid_records:
        return None
    return max(valid_records, key=lambda record: record["year"])


def create_record_deduplication_key(record: dict[str, Any]) -> tuple[object, ...]:
    location = record["location"]
    return (
        record.get("stationCode"),
        record.get("normalizedOperatorName"),
        record.get("normalizedLineName"),
        round(location["longitude"], 6),
        round(location["latitude"], 6),
    )


def deduplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[object, ...], dict[str, Any]] = {}
    for record in records:
        by_key.setdefault(create_record_deduplication_key(record), record)
    return list(by_key.values())


def create_station_group_id(record: dict[str, Any]) -> str:
    group_code = record.get("groupCode")
    station_code = record.get("stationCode")
    if group_code:
        return f"grp:{group_code}"
    if station_code:
        return f"sta:{station_code}"
    location = record["location"]
    source = (
        f"{record['normalizedStationName']}:{location['latitude']:.5f}:{location['longitude']:.5f}"
    )
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return f"generated:{digest}"


def aggregate_passenger_counts(values: list[int | None]) -> tuple[int | None, str]:
    valid_counts = {value for value in values if value is not None and value >= 0}
    if not valid_counts:
        return None, "unavailable"
    if len(valid_counts) == 1:
        return next(iter(valid_counts)), "deduplicated"
    return max(valid_counts), "max_fallback"


def aggregate_station_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records_by_group: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        records_by_group.setdefault(create_station_group_id(record), []).append(record)

    groups = []
    for group_id, group_records in records_by_group.items():
        first = group_records[0]
        passenger_history = []
        for year in AVAILABLE_YEARS:
            counts = [
                history["passengerCount"]
                for record in group_records
                for history in record["passengerHistory"]
                if history["year"] == year
            ]
            passenger_count, method = aggregate_passenger_counts(counts)
            passenger_history.append(
                {
                    "year": year,
                    "passengerCount": passenger_count,
                    "aggregationMethod": method,
                    "sourceRecordCount": len(counts),
                }
            )
        latest = get_latest_passenger_record(passenger_history)
        operators = sorted(
            {
                record["normalizedOperatorName"]
                for record in group_records
                if record["normalizedOperatorName"]
            }
        )
        lines = sorted(
            {
                record["normalizedLineName"]
                for record in group_records
                if record["normalizedLineName"]
            }
        )
        station_codes = sorted(
            {record["stationCode"] for record in group_records if record.get("stationCode")}
        )
        latitudes = [record["location"]["latitude"] for record in group_records]
        longitudes = [record["location"]["longitude"] for record in group_records]
        latest_count = latest["passengerCount"] if latest else None
        groups.append(
            {
                "stationGroupId": group_id,
                "groupCode": first.get("groupCode"),
                "stationName": first["stationName"],
                "normalizedStationName": first["normalizedStationName"],
                "location": {
                    "latitude": sum(latitudes) / len(latitudes),
                    "longitude": sum(longitudes) / len(longitudes),
                },
                "stationCodes": station_codes,
                "operators": operators,
                "lines": lines,
                "lineCount": len(lines),
                "operatorCount": len(operators),
                "passengerHistory": passenger_history,
                "latestPassengerCount": latest_count,
                "latestPassengerYear": latest["year"] if latest else None,
                "stationScale": {
                    "rank": calculate_station_rank(latest_count),
                    "logPassengerCount": calculate_log_passenger_count(latest_count),
                },
            }
        )
    return sorted(groups, key=lambda group: group["stationGroupId"])


def calculate_station_rank(passenger_count: int | None) -> str | None:
    if passenger_count is None:
        return None
    if passenger_count >= 500_000:
        return "S"
    if passenger_count >= 100_000:
        return "A"
    if passenger_count >= 50_000:
        return "B"
    if passenger_count >= 20_000:
        return "C"
    if passenger_count >= 5_000:
        return "D"
    return "E"


def calculate_log_passenger_count(passenger_count: int | None) -> float | None:
    if passenger_count is None:
        return None
    return math.log1p(passenger_count)


def build_summary(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": group["stationGroupId"],
            "code": group["groupCode"],
            "name": group["stationName"],
            "lat": group["location"]["latitude"],
            "lon": group["location"]["longitude"],
            "passengers": group["latestPassengerCount"],
            "passengerYear": group["latestPassengerYear"],
            "rank": group["stationScale"]["rank"],
            "lineCount": group["lineCount"],
        }
        for group in groups
    ]


def write_station_groups_csv(groups: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "station_group_id",
                "group_code",
                "station_name",
                "normalized_station_name",
                "lat",
                "lon",
                "latest_passenger_count",
                "latest_passenger_year",
                "rank",
                "log_passenger_count",
                "line_count",
                "operator_count",
                "station_codes",
                "operators",
                "lines",
            ],
        )
        writer.writeheader()
        for group in groups:
            writer.writerow(
                {
                    "station_group_id": group["stationGroupId"],
                    "group_code": group["groupCode"],
                    "station_name": group["stationName"],
                    "normalized_station_name": group["normalizedStationName"],
                    "lat": group["location"]["latitude"],
                    "lon": group["location"]["longitude"],
                    "latest_passenger_count": group["latestPassengerCount"],
                    "latest_passenger_year": group["latestPassengerYear"],
                    "rank": group["stationScale"]["rank"],
                    "log_passenger_count": group["stationScale"]["logPassengerCount"],
                    "line_count": group["lineCount"],
                    "operator_count": group["operatorCount"],
                    "station_codes": "|".join(group["stationCodes"]),
                    "operators": "|".join(group["operators"]),
                    "lines": "|".join(group["lines"]),
                }
            )
    return output_path


def raw_tile_path(raw_dir: Path, run_id: str, tile: Tile) -> Path:
    return raw_dir / run_id / f"z{tile.z}" / str(tile.x) / f"{tile.y}.geojson"


def save_json(path: Path, data: object, *, compact: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def collect_station_passengers(
    *,
    tiles: list[Tile],
    raw_dir: Path,
    processed_dir: Path,
    cache_dir: Path,
    api_key: str,
    run_id: str,
    cache: bool,
    force: bool,
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

    for tile_index, tile in enumerate(tiles, start=1):
        if progress_interval > 0 and (tile_index == 1 or tile_index % progress_interval == 0):
            print(f"station passenger tiles: {tile_index}/{len(tiles)}", file=sys.stderr)
        path = raw_tile_path(raw_dir, run_id, tile)
        try:
            if cache and path.exists() and not force:
                payload = json.loads(path.read_text(encoding="utf-8"))
            else:
                payload = fetch_tile(
                    tile=tile,
                    api_key=api_key,
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
                    request_interval_seconds=request_interval_seconds,
                )
                save_json(path, payload, compact=True)
            features = payload.get("features", [])
            manifest_tiles.append(
                {
                    "z": tile.z,
                    "x": tile.x,
                    "y": tile.y,
                    "status": "empty" if len(features) == 0 else "completed",
                    "featureCount": len(features),
                    "fetchedAt": fetched_at,
                }
            )
            for index, feature in enumerate(features):
                record = normalize_feature(feature, tile, fetched_at)
                if record is None:
                    invalid_features.append({"tile": tile.__dict__, "featureIndex": index})
                else:
                    raw_records.append(record)
        except (OSError, StationPassengerCollectError, json.JSONDecodeError) as error:
            failed_tiles.append({"tile": tile.__dict__, "error": str(error)})
            manifest_tiles.append(
                {
                    "z": tile.z,
                    "x": tile.x,
                    "y": tile.y,
                    "status": "failed",
                    "featureCount": 0,
                    "fetchedAt": fetched_at,
                    "error": str(error),
                }
            )

    records = deduplicate_records(raw_records)
    groups = aggregate_station_groups(records)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "source": {
            "provider": "国土交通省",
            "service": "不動産情報ライブラリ",
            "apiId": "XKT015",
            "dataset": "駅別乗降客数",
        },
        "generatedAt": fetched_at,
        "tileCount": len(tiles),
        "completedTileCount": sum(1 for tile in manifest_tiles if tile["status"] == "completed"),
        "emptyTileCount": sum(1 for tile in manifest_tiles if tile["status"] == "empty"),
        "failedTileCount": len(failed_tiles),
        "stationLineCount": len(records),
        "stationGroupCount": len(groups),
        "availableYears": AVAILABLE_YEARS,
    }

    manifest_path = raw_dir / run_id / "manifest.json"
    lines_path = processed_dir / "station_lines.json"
    groups_path = processed_dir / "station_groups.json"
    csv_path = processed_dir / "station_groups.csv"
    summary_path = processed_dir / "station_passenger_summary.json"
    metadata_path = processed_dir / "metadata.json"
    failed_path = cache_dir / "failed_tiles.json"
    invalid_path = cache_dir / "invalid_features.json"

    save_json(manifest_path, {"tiles": manifest_tiles, **metadata})
    save_json(lines_path, records)
    save_json(groups_path, groups)
    write_station_groups_csv(groups, csv_path)
    save_json(summary_path, build_summary(groups), compact=True)
    save_json(metadata_path, metadata)
    save_json(failed_path, failed_tiles)
    save_json(invalid_path, invalid_features)

    return {
        "manifest": manifest_path,
        "station_lines": lines_path,
        "station_groups": groups_path,
        "station_groups_csv": csv_path,
        "summary": summary_path,
        "metadata": metadata_path,
        "failed_tiles": len(failed_tiles),
        "invalid_features": len(invalid_features),
        "station_groups_count": len(groups),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect MLIT XKT015 station passenger data.")
    parser.add_argument("--area", choices=sorted(AREAS), default="capital")
    parser.add_argument("--zoom", type=int, default=11)
    parser.add_argument("--tile", nargs=3, type=int, metavar=("Z", "X", "Y"))
    parser.add_argument("--north", type=float)
    parser.add_argument("--south", type=float)
    parser.add_argument("--east", type=float)
    parser.add_argument("--west", type=float)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/xkt015"))
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("data/processed/station_passengers"),
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/station_passengers"))
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--request-interval-seconds", type=float, default=1.0)
    parser.add_argument("--progress-interval", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_env_file(Path(__file__).resolve().parents[2] / ".env")
    try:
        tiles = build_tiles(args)
    except (StationPassengerCollectError, ValueError) as error:
        print(f"station passenger collect failed: {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(
            "station passenger dry-run: "
            f"tiles={len(tiles)} requests={len(tiles)} area={args.area} zoom={args.zoom}"
        )
        return 0

    api_key = os.getenv(REINFOLIB_API_KEY_ENV)
    if not api_key:
        print(
            f"station passenger collect failed: {REINFOLIB_API_KEY_ENV} is not set",
            file=sys.stderr,
        )
        return 1

    try:
        outputs = collect_station_passengers(
            tiles=tiles,
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            cache_dir=args.cache_dir,
            api_key=api_key,
            run_id=args.run_id,
            cache=args.cache,
            force=args.force,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            request_interval_seconds=args.request_interval_seconds,
            progress_interval=args.progress_interval,
        )
    except (StationPassengerCollectError, ValueError) as error:
        print(f"station passenger collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected station passengers: "
        f"tiles={len(tiles)} groups={outputs['station_groups_count']} "
        f"failed_tiles={outputs['failed_tiles']} invalid_features={outputs['invalid_features']} "
        f"csv={outputs['station_groups_csv']}"
    )
    return 0 if outputs["failed_tiles"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
