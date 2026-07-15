from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_urban_planning_collection(rows: list[dict[str, str]]) -> dict[str, Any]:
    areas = []
    for row in rows:
        geometry = _parse_geometry(row.get("geometry_json"))
        if geometry is None:
            continue
        bbox = _geometry_bbox(geometry)
        if bbox is None:
            continue
        areas.append(
            {
                "areaType": _text(row.get("area_type")) or "unknown",
                "prefecture": _text(row.get("prefecture")),
                "municipality": _text(row.get("city_name")),
                "areaName": _text(row.get("area_name")),
                "zoningType": _text(row.get("zoning_type")) or _text(row.get("area_name")),
                "floorAreaRatio": _float_or_zero(row.get("floor_area_ratio")),
                "buildingCoverageRatio": _float_or_zero(
                    row.get("building_coverage_ratio")
                ),
                "bbox": bbox,
                "geometry": geometry,
            }
        )

    return {
        "schemaVersion": 1,
        "source": "reinfolib_xkt001_xkt002_xkt003",
        "sourceLabel": "国土交通省 不動産情報ライブラリ 都市計画決定GISデータ",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "areaCount": len(areas),
        "areas": areas,
    }


def read_urban_planning_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_collection(collection: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return output_path


def _geometry_bbox(geometry: dict[str, Any]) -> list[float] | None:
    points = list(_iter_geometry_points(geometry))
    if not points:
        return None
    lons = [point[0] for point in points]
    lats = [point[1] for point in points]
    return [min(lons), min(lats), max(lons), max(lats)]


def _iter_geometry_points(geometry: dict[str, Any]):
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        yield from _iter_polygon_points(coordinates)
    elif geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        for polygon in coordinates:
            yield from _iter_polygon_points(polygon)


def _iter_polygon_points(polygon: object):
    if not isinstance(polygon, list):
        return
    for ring in polygon:
        if not isinstance(ring, list):
            continue
        for coordinate in ring:
            if _is_coordinate(coordinate):
                yield float(coordinate[0]), float(coordinate[1])


def _is_coordinate(value: object) -> bool:
    return isinstance(value, list | tuple) and len(value) >= 2


def _parse_geometry(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return None
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _float_or_zero(value: object) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export lightweight urban planning areas")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/urban_planning/urban_planning_areas.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../frontend/public/urban-planning/urban_planning_areas.json"),
    )
    args = parser.parse_args()

    rows = read_urban_planning_csv(args.input)
    output = write_collection(build_urban_planning_collection(rows), args.output)
    print(f"exported urban planning areas: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
