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
DEFAULT_APIS = ["XKT004", "XKT005", "XKT006", "XKT007"]
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
    "XKT004": "elementary_school_district",
    "XKT005": "junior_high_school_district",
    "XKT006": "school",
    "XKT007": "preschool",
}
DISTRICT_APIS = {"XKT004", "XKT005"}
FACILITY_APIS = {"XKT006", "XKT007"}
SCHOOL_DISTRICT_FIELDNAMES = [
    "source_api",
    "district_type",
    "administrative_area_code",
    "school_code",
    "school_name",
    "operator_name",
    "address",
    "geometry_type",
    "geometry_json",
    "source_url",
]
EDUCATION_FACILITY_FIELDNAMES = [
    "source_api",
    "facility_type",
    "administrative_area_code",
    "facility_code",
    "facility_name",
    "facility_class_code",
    "facility_class_name",
    "administrator_code",
    "closed_code",
    "lat",
    "lon",
    "address",
    "source_url",
]


class EducationFacilityCollectError(RuntimeError):
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


def build_tile_url(
    *,
    api_id: str,
    tile: Tile,
    administrative_area_codes: list[str],
) -> str:
    params = {
        "response_format": "geojson",
        "z": str(tile.z),
        "x": str(tile.x),
        "y": str(tile.y),
    }
    if api_id in DISTRICT_APIS and administrative_area_codes:
        params["administrativeAreaCode"] = ",".join(administrative_area_codes)
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
    request.add_header("User-Agent", "map-lgb-fond-education/0.1")
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
                raise EducationFacilityCollectError(f"HTTP {error.code}: {detail}") from error
            time.sleep(min(60.0, 2.0 * (2**attempt)))
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            if attempt >= max_retries:
                raise EducationFacilityCollectError(f"failed to fetch tile: {error}") from error
            time.sleep(2**attempt)
    raise EducationFacilityCollectError("failed to fetch tile")


def validate_geojson(data: object) -> None:
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise EducationFacilityCollectError("GeoJSON type must be FeatureCollection")
    if not isinstance(data.get("features"), list):
        raise EducationFacilityCollectError("GeoJSON features must be a list")


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
    if api_id in DISTRICT_APIS:
        return normalize_district(properties, geometry, api_id=api_id, source_url=source_url)
    if api_id in FACILITY_APIS:
        return normalize_facility(properties, geometry, api_id=api_id, source_url=source_url)
    return None


def normalize_district(
    properties: dict[str, Any],
    geometry: dict[str, Any],
    *,
    api_id: str,
    source_url: str,
) -> dict[str, Any]:
    if api_id == "XKT004":
        area_key, operator_key, code_key, name_key, address_key = (
            "A27_001",
            "A27_002",
            "A27_003",
            "A27_004_ja",
            "A27_005",
        )
    else:
        area_key, operator_key, code_key, name_key, address_key = (
            "A32_001",
            "A32_002",
            "A32_003",
            "A32_004_ja",
            "A32_005",
        )
    return {
        "source_api": api_id,
        "district_type": API_LABELS[api_id],
        "administrative_area_code": _text(properties.get(area_key)),
        "school_code": _text(properties.get(code_key)),
        "school_name": _text(properties.get(name_key)),
        "operator_name": _text(properties.get(operator_key)),
        "address": _text(properties.get(address_key)),
        "geometry_type": _text(geometry.get("type")),
        "geometry_json": json.dumps(geometry, ensure_ascii=False, separators=(",", ":")),
        "source_url": source_url,
    }


def normalize_facility(
    properties: dict[str, Any],
    geometry: dict[str, Any],
    *,
    api_id: str,
    source_url: str,
) -> dict[str, Any] | None:
    lon, lat = extract_point_coordinate(geometry)
    if lon is None or lat is None:
        return None
    if api_id == "XKT006":
        facility_type = _text(properties.get("P29_003_name_ja"))
        return {
            "source_api": api_id,
            "facility_type": facility_type,
            "administrative_area_code": _text(properties.get("P29_001")),
            "facility_code": _text(properties.get("P29_002")),
            "facility_name": _text(properties.get("P29_004_ja")),
            "facility_class_code": _text(properties.get("P29_003")),
            "facility_class_name": facility_type,
            "administrator_code": _text(properties.get("P29_006")),
            "closed_code": _text(properties.get("P29_007")),
            "lat": lat,
            "lon": lon,
            "address": _text(properties.get("P29_005_ja")),
            "source_url": source_url,
        }
    facility_type = _text(
        properties.get("schoolClassCode_name_ja")
        or properties.get("welfareFacilityMinorClassCode")
        or "保育園"
    )
    return {
        "source_api": api_id,
        "facility_type": facility_type,
        "administrative_area_code": _text(properties.get("administrativeAreaCode")),
        "facility_code": _text(properties.get("schoolCode") or properties.get("preSchoolName_ja")),
        "facility_name": _text(properties.get("preSchoolName_ja")),
        "facility_class_code": _text(
            properties.get("schoolClassCode") or properties.get("welfareFacilityMinorClassCode")
        ),
        "facility_class_name": facility_type,
        "administrator_code": _text(properties.get("administratorCode")),
        "closed_code": _text(properties.get("closeSchoolCode")),
        "lat": lat,
        "lon": lon,
        "address": _text(properties.get("location_ja")),
        "source_url": source_url,
    }


def extract_point_coordinate(geometry: dict[str, Any]) -> tuple[float | None, float | None]:
    coordinates = geometry.get("coordinates")
    if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, None
    lon = _to_float(coordinates[0])
    lat = _to_float(coordinates[1])
    return lon, lat


def collect_education_facilities(
    *,
    api_ids: list[str],
    tiles: list[Tile],
    raw_dir: Path,
    processed_dir: Path,
    api_key: str,
    run_id: str,
    cache: bool,
    force: bool,
    administrative_area_codes: list[str],
    timeout_seconds: int,
    max_retries: int,
    request_interval_seconds: float,
) -> dict[str, Path | int]:
    districts = []
    facilities = []
    manifest = []
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    for api_id in api_ids:
        if api_id not in API_LABELS:
            raise EducationFacilityCollectError(f"unsupported API: {api_id}")
        for tile in tiles:
            source_url = build_tile_url(
                api_id=api_id,
                tile=tile,
                administrative_area_codes=administrative_area_codes,
            )
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
                if not record:
                    continue
                if api_id in DISTRICT_APIS:
                    districts.append(record)
                else:
                    facilities.append(record)

    district_rows = deduplicate(districts, ["source_api", "school_code", "school_name"])
    facility_rows = deduplicate(facilities, ["source_api", "facility_code", "facility_name"])
    processed_dir.mkdir(parents=True, exist_ok=True)
    district_path = processed_dir / "school_districts.csv"
    facility_path = processed_dir / "education_facilities.csv"
    metadata_path = processed_dir / "metadata.json"
    write_csv(district_path, district_rows, SCHOOL_DISTRICT_FIELDNAMES)
    write_csv(facility_path, facility_rows, EDUCATION_FACILITY_FIELDNAMES)
    save_json(
        metadata_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": generated_at,
            "apiIds": api_ids,
            "tileCount": len(tiles),
            "requestCount": len(tiles) * len(api_ids),
            "districtCount": len(district_rows),
            "facilityCount": len(facility_rows),
            "tiles": manifest,
        },
    )
    return {
        "school_districts_csv": district_path,
        "education_facilities_csv": facility_path,
        "metadata": metadata_path,
        "district_count": len(district_rows),
        "facility_count": len(facility_rows),
    }


def deduplicate(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    by_key = {}
    for row in rows:
        key = tuple(row.get(item) for item in keys)
        by_key.setdefault(key, row)
    return sorted(by_key.values(), key=lambda row: tuple(_text(row.get(key)) for key in keys))


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
        raise EducationFacilityCollectError(f"unsupported area: {args.area}")
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


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect education facility data.")
    parser.add_argument("--apis", default=",".join(DEFAULT_APIS))
    parser.add_argument("--area", default=DEFAULT_AREA)
    parser.add_argument("--zoom", type=int, default=DEFAULT_ZOOM)
    parser.add_argument("--tile", nargs=3, type=int)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/education"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/education"))
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--administrative-area-codes", default="")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--request-interval-seconds", type=float, default=1.0)
    parser.add_argument("--api-key", default=os.environ.get(REINFOLIB_API_KEY_ENV, ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        api_ids = [item.strip() for item in args.apis.split(",") if item.strip()]
        tiles = build_tiles(args)
        if args.dry_run:
            print(
                "education facilities dry-run: "
                f"apis={len(api_ids)} tiles={len(tiles)} "
                f"requests={len(api_ids) * len(tiles)} area={args.area} zoom={args.zoom}"
            )
            return 0
        if not args.api_key:
            raise EducationFacilityCollectError(f"{REINFOLIB_API_KEY_ENV} is required")
        outputs = collect_education_facilities(
            api_ids=api_ids,
            tiles=tiles,
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            api_key=args.api_key,
            run_id=args.run_id,
            cache=args.cache,
            force=args.force,
            administrative_area_codes=[
                item.strip() for item in args.administrative_area_codes.split(",") if item.strip()
            ],
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            request_interval_seconds=args.request_interval_seconds,
        )
    except EducationFacilityCollectError as error:
        print(f"education facility collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected education facilities: "
        f"districts={outputs['district_count']} "
        f"facilities={outputs['facility_count']} "
        f"districts_csv={outputs['school_districts_csv']} "
        f"facilities_csv={outputs['education_facilities_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
