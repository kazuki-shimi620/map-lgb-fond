from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.0.0"
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
DEFAULT_AREA = "capital"
DEFAULT_CATEGORIES = ["supermarket", "convenience_store", "park"]
AREAS = {
    "capital": {
        "north": 36.3,
        "south": 34.9,
        "east": 140.9,
        "west": 138.6,
    },
    "tokyo": {
        "north": 35.9,
        "south": 35.5,
        "east": 140.0,
        "west": 139.0,
    },
    "kanagawa": {
        "north": 35.7,
        "south": 35.0,
        "east": 139.8,
        "west": 138.9,
    },
    "saitama": {
        "north": 36.3,
        "south": 35.75,
        "east": 139.9,
        "west": 138.7,
    },
    "chiba": {
        "north": 36.2,
        "south": 34.9,
        "east": 140.9,
        "west": 139.7,
    },
}
CATEGORY_TO_FILTERS = {
    "supermarket": [('shop', 'supermarket')],
    "convenience_store": [('shop', 'convenience')],
    "park": [('leisure', 'park')],
}
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
PARK_AREA_FIELDNAMES = [
    "id",
    "name",
    "lat",
    "lon",
    "prefecture",
    "municipality",
    "address",
    "osm_type",
    "osm_id",
    "area_sqm",
    "area_source",
    "source",
    "updated_at",
]
EARTH_RADIUS_METERS = 6_371_008.8


class OsmNearbyFacilityCollectError(RuntimeError):
    pass


def build_overpass_query(
    *,
    categories: list[str],
    south: float,
    west: float,
    north: float,
    east: float,
    timeout_seconds: int,
    include_geometry: bool = False,
) -> str:
    clauses = []
    for category in categories:
        if category not in CATEGORY_TO_FILTERS:
            raise OsmNearbyFacilityCollectError(f"unsupported category: {category}")
        for key, value in CATEGORY_TO_FILTERS[category]:
            selector = f'["{key}"="{value}"]({south},{west},{north},{east})'
            clauses.extend([f"node{selector};", f"way{selector};", f"relation{selector};"])
    joined = "\n  ".join(clauses)
    output = "out center tags geom;" if include_geometry else "out center tags;"
    return f"[out:json][timeout:{timeout_seconds}];\n(\n  {joined}\n);\n{output}"


def fetch_overpass(
    *,
    query: str,
    endpoint: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    body = urlencode({"data": query}).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "map-lgb-fond-osm-nearby-facilities/0.1",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise OsmNearbyFacilityCollectError(f"HTTP {error.code}: {detail}") from error
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise OsmNearbyFacilityCollectError(f"failed to fetch Overpass data: {error}") from error


def collect_osm_nearby_facilities(
    *,
    categories: list[str],
    area: dict[str, float],
    raw_dir: Path,
    processed_dir: Path,
    run_id: str,
    endpoint: str,
    timeout_seconds: int,
    cache: bool,
    force: bool,
    include_geometry: bool = False,
) -> dict[str, Path | int]:
    query = build_overpass_query(
        categories=categories,
        south=area["south"],
        west=area["west"],
        north=area["north"],
        east=area["east"],
        timeout_seconds=timeout_seconds,
        include_geometry=include_geometry,
    )
    raw_path = raw_dir / f"{run_id}.json"
    query_path = raw_dir / f"{run_id}.overpassql"
    if cache and raw_path.exists() and not force:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        payload = fetch_overpass(
            query=query,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
        )
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        query_path.write_text(query + "\n", encoding="utf-8")

    rows = normalize_overpass_elements(payload.get("elements", []))
    park_area_rows = (
        normalize_park_area_elements(payload.get("elements", []))
        if include_geometry
        else []
    )
    processed_dir.mkdir(parents=True, exist_ok=True)
    nearby_path = processed_dir / "nearby_osm_facilities.csv"
    park_areas_path = processed_dir / "park_areas.csv"
    metadata_path = processed_dir / "metadata.json"
    write_csv(nearby_path, rows, NEARBY_FACILITY_FIELDNAMES)
    if include_geometry:
        write_csv(park_areas_path, park_area_rows, PARK_AREA_FIELDNAMES)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "OpenStreetMap Overpass API",
        "license": "Open Database License (ODbL)",
        "categories": categories,
        "includeGeometry": include_geometry,
        "elementCount": len(payload.get("elements", [])),
        "nearbyFacilityCount": len(rows),
        "parkAreaCount": len(park_area_rows),
        "raw": str(raw_path),
        "query": str(query_path),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "nearby_facilities_csv": nearby_path,
        "metadata": metadata_path,
        "park_areas_csv": park_areas_path,
        "element_count": len(payload.get("elements", [])),
        "nearby_facility_count": len(rows),
        "park_area_count": len(park_area_rows),
    }


def normalize_overpass_elements(elements: object) -> list[dict[str, Any]]:
    if not isinstance(elements, list):
        return []
    rows = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        row = normalize_overpass_element(element)
        if row:
            rows.append(row)
    return deduplicate(rows)


def normalize_overpass_element(element: dict[str, Any]) -> dict[str, Any] | None:
    tags = element.get("tags")
    if not isinstance(tags, dict):
        tags = {}
    category_id = category_from_tags(tags)
    if category_id is None:
        return None
    lat, lon = element_lat_lon(element)
    if lat is None or lon is None:
        return None
    name = _text(tags.get("name") or tags.get("name:ja") or tags.get("brand"))
    if not name:
        name = {
            "supermarket": "スーパー",
            "convenience_store": "コンビニ",
            "park": "公園",
        }[category_id]
    address = build_address(tags)
    osm_type = _text(element.get("type"))
    osm_id = _text(element.get("id"))
    return {
        "id": f"osm_{osm_type}_{osm_id}",
        "category_id": category_id,
        "name": name,
        "lat": lat,
        "lon": lon,
        "prefecture": _text(tags.get("addr:province")),
        "municipality": _text(tags.get("addr:city") or tags.get("addr:town")),
        "address": address,
        "source": "openstreetmap_odbl",
        "updated_at": "",
    }


def normalize_park_area_elements(elements: object) -> list[dict[str, Any]]:
    if not isinstance(elements, list):
        return []
    rows = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        row = normalize_park_area_element(element)
        if row:
            rows.append(row)
    by_id = {row["id"]: row for row in rows}
    return sorted(by_id.values(), key=lambda row: (row["name"], row["id"]))


def normalize_park_area_element(element: dict[str, Any]) -> dict[str, Any] | None:
    tags = element.get("tags")
    if not isinstance(tags, dict) or category_from_tags(tags) != "park":
        return None
    area_sqm, area_source = element_area_sqm(element)
    if area_sqm is None:
        return None
    lat, lon = element_lat_lon(element)
    if lat is None or lon is None:
        return None
    name = _text(tags.get("name") or tags.get("name:ja")) or "公園"
    address = build_address(tags)
    osm_type = _text(element.get("type"))
    osm_id = _text(element.get("id"))
    return {
        "id": f"osm_{osm_type}_{osm_id}",
        "name": name,
        "lat": lat,
        "lon": lon,
        "prefecture": _text(tags.get("addr:province")),
        "municipality": _text(tags.get("addr:city") or tags.get("addr:town")),
        "address": address,
        "osm_type": osm_type,
        "osm_id": osm_id,
        "area_sqm": round(area_sqm, 2),
        "area_source": area_source,
        "source": "openstreetmap_odbl",
        "updated_at": "",
    }


def category_from_tags(tags: dict[str, Any]) -> str | None:
    if _text(tags.get("shop")) == "supermarket":
        return "supermarket"
    if _text(tags.get("shop")) == "convenience":
        return "convenience_store"
    if _text(tags.get("leisure")) == "park":
        return "park"
    return None


def element_area_sqm(element: dict[str, Any]) -> tuple[float | None, str]:
    geometry = element.get("geometry")
    if isinstance(geometry, list):
        area = polygon_area_sqm(geometry)
        if area is not None:
            return area, "geometry"
    bounds = element.get("bounds")
    if isinstance(bounds, dict):
        area = bounds_area_sqm(bounds)
        if area is not None:
            return area, "bounds"
    return None, ""


def polygon_area_sqm(points: list[object]) -> float | None:
    coordinates: list[tuple[float, float]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        lat = _to_float(point.get("lat"))
        lon = _to_float(point.get("lon"))
        if lat is None or lon is None:
            continue
        coordinates.append((lat, lon))
    if len(coordinates) < 3:
        return None
    if coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])
    mean_lat_rad = math.radians(sum(lat for lat, _lon in coordinates) / len(coordinates))
    projected = [
        (
            EARTH_RADIUS_METERS * math.radians(lon) * math.cos(mean_lat_rad),
            EARTH_RADIUS_METERS * math.radians(lat),
        )
        for lat, lon in coordinates
    ]
    area = 0.0
    for (x1, y1), (x2, y2) in zip(projected, projected[1:], strict=False):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def bounds_area_sqm(bounds: dict[str, Any]) -> float | None:
    minlat = _to_float(bounds.get("minlat"))
    minlon = _to_float(bounds.get("minlon"))
    maxlat = _to_float(bounds.get("maxlat"))
    maxlon = _to_float(bounds.get("maxlon"))
    if None in (minlat, minlon, maxlat, maxlon):
        return None
    assert minlat is not None
    assert minlon is not None
    assert maxlat is not None
    assert maxlon is not None
    return polygon_area_sqm(
        [
            {"lat": minlat, "lon": minlon},
            {"lat": minlat, "lon": maxlon},
            {"lat": maxlat, "lon": maxlon},
            {"lat": maxlat, "lon": minlon},
        ]
    )


def element_lat_lon(element: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = _to_float(element.get("lat"))
    lon = _to_float(element.get("lon"))
    if lat is not None and lon is not None:
        return lat, lon
    center = element.get("center")
    if isinstance(center, dict):
        return _to_float(center.get("lat")), _to_float(center.get("lon"))
    bounds = element.get("bounds")
    if isinstance(bounds, dict):
        minlat = _to_float(bounds.get("minlat"))
        minlon = _to_float(bounds.get("minlon"))
        maxlat = _to_float(bounds.get("maxlat"))
        maxlon = _to_float(bounds.get("maxlon"))
        if None not in (minlat, minlon, maxlat, maxlon):
            assert minlat is not None
            assert minlon is not None
            assert maxlat is not None
            assert maxlon is not None
            return (minlat + maxlat) / 2, (minlon + maxlon) / 2
    return None, None


def build_address(tags: dict[str, Any]) -> str:
    explicit = _text(tags.get("addr:full"))
    if explicit:
        return explicit
    parts = [
        _text(tags.get("addr:province")),
        _text(tags.get("addr:city") or tags.get("addr:town")),
        _text(tags.get("addr:suburb")),
        _text(tags.get("addr:neighbourhood")),
        _text(tags.get("addr:block_number")),
        _text(tags.get("addr:housenumber")),
    ]
    return "".join(part for part in parts if part)


def deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row["id"]: row for row in rows}
    return sorted(by_id.values(), key=lambda row: (row["category_id"], row["name"], row["id"]))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


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
    parser = argparse.ArgumentParser(description="Collect nearby facilities from OpenStreetMap.")
    parser.add_argument("--area", default=DEFAULT_AREA)
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"))
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/osm_nearby"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/osm_nearby"))
    parser.add_argument("--run-id", default="latest")
    parser.add_argument("--endpoint", default=OVERPASS_ENDPOINT)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--include-geometry", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        if args.bbox:
            area = {
                "south": args.bbox[0],
                "west": args.bbox[1],
                "north": args.bbox[2],
                "east": args.bbox[3],
            }
            area_label = "bbox"
        else:
            if args.area not in AREAS:
                raise OsmNearbyFacilityCollectError(f"unsupported area: {args.area}")
            area = AREAS[args.area]
            area_label = args.area
        categories = [item.strip() for item in args.categories.split(",") if item.strip()]
        query = build_overpass_query(
            categories=categories,
            timeout_seconds=args.timeout_seconds,
            include_geometry=args.include_geometry,
            **area,
        )
        if args.dry_run:
            print(
                "osm nearby facilities dry-run: "
                f"categories={','.join(categories)} area={area_label} "
                f"bbox={area} queryBytes={len(query.encode('utf-8'))}"
            )
            return 0
        outputs = collect_osm_nearby_facilities(
            categories=categories,
            area=area,
            raw_dir=args.raw_dir,
            processed_dir=args.processed_dir,
            run_id=args.run_id,
            endpoint=args.endpoint,
            timeout_seconds=args.timeout_seconds,
            cache=args.cache,
            force=args.force,
            include_geometry=args.include_geometry,
        )
    except OsmNearbyFacilityCollectError as error:
        print(f"osm nearby facility collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected osm nearby facilities: "
        f"elements={outputs['element_count']} "
        f"nearby={outputs['nearby_facility_count']} "
        f"parkAreas={outputs['park_area_count']} "
        f"csv={outputs['nearby_facilities_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
