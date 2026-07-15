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
API_ID = "XKT010"
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
MEDICAL_FACILITY_FIELDNAMES = [
    "source_api",
    "facility_class_code",
    "facility_class_name",
    "facility_name",
    "address",
    "medical_subjects",
    "founder_class_code",
    "bed_count",
    "emergency_hospital_code",
    "disaster_base_hospital_code",
    "lat",
    "lon",
    "source_url",
]
NEARBY_FACILITY_FIELDNAMES = [
    "id",
    "category_id",
    "name",
    "lat",
    "lon",
    "prefecture",
    "municipality",
    "address",
    "source",
    "updated_at",
]


class MedicalFacilityCollectError(RuntimeError):
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


def build_tile_url(*, tile: Tile) -> str:
    params = {
        "response_format": "geojson",
        "z": str(tile.z),
        "x": str(tile.x),
        "y": str(tile.y),
    }
    return f"{REINFOLIB_BASE_URL}/{API_ID}?{urlencode(params)}"


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
    request.add_header("User-Agent", "map-lgb-fond-medical-facilities/0.1")
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
                raise MedicalFacilityCollectError(f"HTTP {error.code}: {detail}") from error
            time.sleep(min(60.0, 2.0 * (2**attempt)))
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            if attempt >= max_retries:
                raise MedicalFacilityCollectError(f"failed to fetch tile: {error}") from error
            time.sleep(2**attempt)
    raise MedicalFacilityCollectError("failed to fetch tile")


def validate_geojson(data: object) -> None:
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise MedicalFacilityCollectError("GeoJSON type must be FeatureCollection")
    if not isinstance(data.get("features"), list):
        raise MedicalFacilityCollectError("GeoJSON features must be a list")


def normalize_feature(feature: dict[str, Any], *, source_url: str) -> dict[str, Any] | None:
    if feature.get("type") != "Feature":
        return None
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None
    lon, lat = extract_point_coordinate(geometry)
    if lon is None or lat is None:
        return None

    medical_subjects = [
        _text(properties.get(key))
        for key in ["P04_004", "P04_005", "P04_006", "medical_subject_ja"]
        if _text(properties.get(key))
    ]
    return {
        "source_api": API_ID,
        "facility_class_code": _text(properties.get("P04_001")),
        "facility_class_name": _text(properties.get("P04_001_name_ja")),
        "facility_name": _text(properties.get("P04_002_ja")),
        "address": _text(properties.get("P04_003_ja")),
        "medical_subjects": ";".join(dict.fromkeys(medical_subjects)),
        "founder_class_code": _text(properties.get("P04_007")),
        "bed_count": _to_int(properties.get("P04_008")),
        "emergency_hospital_code": _text(properties.get("P04_009")),
        "disaster_base_hospital_code": _text(properties.get("P04_010")),
        "lat": lat,
        "lon": lon,
        "source_url": source_url,
    }


def extract_point_coordinate(geometry: dict[str, Any]) -> tuple[float | None, float | None]:
    coordinates = geometry.get("coordinates")
    if geometry.get("type") != "Point" or not isinstance(coordinates, list) or len(coordinates) < 2:
        return None, None
    lon = _to_float(coordinates[0])
    lat = _to_float(coordinates[1])
    return lon, lat


def collect_medical_facilities(
    *,
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
    rows = []
    manifest = []
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    for tile in tiles:
        source_url = build_tile_url(tile=tile)
        path = raw_tile_path(raw_dir, run_id, tile)
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
                "apiId": API_ID,
                "z": tile.z,
                "x": tile.x,
                "y": tile.y,
                "featureCount": len(features),
            }
        )
        for feature in features:
            record = normalize_feature(feature, source_url=source_url)
            if record:
                rows.append(record)

    facility_rows = deduplicate(rows, ["facility_class_name", "facility_name", "lat", "lon"])
    nearby_rows = [to_nearby_facility_row(row) for row in facility_rows]
    processed_dir.mkdir(parents=True, exist_ok=True)
    facilities_path = processed_dir / "medical_facilities.csv"
    nearby_path = processed_dir / "nearby_medical_facilities.csv"
    metadata_path = processed_dir / "metadata.json"
    write_csv(facilities_path, facility_rows, MEDICAL_FACILITY_FIELDNAMES)
    write_csv(nearby_path, nearby_rows, NEARBY_FACILITY_FIELDNAMES)
    save_json(
        metadata_path,
        {
            "schemaVersion": SCHEMA_VERSION,
            "generatedAt": generated_at,
            "apiId": API_ID,
            "tileCount": len(tiles),
            "requestCount": len(tiles),
            "facilityCount": len(facility_rows),
            "nearbyFacilityCount": len(nearby_rows),
            "tiles": manifest,
        },
    )
    return {
        "medical_facilities_csv": facilities_path,
        "nearby_facilities_csv": nearby_path,
        "metadata": metadata_path,
        "facility_count": len(facility_rows),
        "nearby_facility_count": len(nearby_rows),
    }


def to_nearby_facility_row(row: dict[str, Any]) -> dict[str, Any]:
    lat = float(row["lat"])
    lon = float(row["lon"])
    name = _text(row.get("facility_name"))
    return {
        "id": build_facility_id("hospital", name, lat, lon),
        "category_id": "hospital",
        "name": name,
        "lat": lat,
        "lon": lon,
        "prefecture": "",
        "municipality": "",
        "address": _text(row.get("address")),
        "source": "reinfolib_xkt010",
        "updated_at": "",
    }


def build_facility_id(category_id: str, name: str, lat: float, lon: float) -> str:
    safe_name = "".join(char if char.isalnum() else "_" for char in name.lower()).strip("_")
    return f"{category_id}_{safe_name}_{lat:.6f}_{lon:.6f}"


def deduplicate(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    by_key = {}
    for row in rows:
        key = tuple(row.get(item) for item in keys)
        by_key.setdefault(key, row)
    return sorted(by_key.values(), key=lambda row: tuple(_text(row.get(key)) for key in keys))


def raw_tile_path(raw_dir: Path, run_id: str, tile: Tile) -> Path:
    return raw_dir / run_id / API_ID / f"z{tile.z}" / str(tile.x) / f"{tile.y}.geojson"


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
        raise MedicalFacilityCollectError(f"unsupported area: {args.area}")
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


def _to_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect medical facility data.")
    parser.add_argument("--area", default=DEFAULT_AREA)
    parser.add_argument("--zoom", type=int, default=DEFAULT_ZOOM)
    parser.add_argument("--tile", nargs=3, type=int)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/medical"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/medical"))
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--request-interval-seconds", type=float, default=1.0)
    parser.add_argument("--api-key", default=os.environ.get(REINFOLIB_API_KEY_ENV, ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        tiles = build_tiles(args)
        if args.dry_run:
            print(
                "medical facilities dry-run: "
                f"api={API_ID} tiles={len(tiles)} requests={len(tiles)} "
                f"area={args.area} zoom={args.zoom}"
            )
            return 0
        if not args.api_key:
            raise MedicalFacilityCollectError(f"{REINFOLIB_API_KEY_ENV} is required")
        outputs = collect_medical_facilities(
            tiles=tiles,
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
    except MedicalFacilityCollectError as error:
        print(f"medical facility collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected medical facilities: "
        f"facilities={outputs['facility_count']} "
        f"nearby={outputs['nearby_facility_count']} "
        f"facilities_csv={outputs['medical_facilities_csv']} "
        f"nearby_csv={outputs['nearby_facilities_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
