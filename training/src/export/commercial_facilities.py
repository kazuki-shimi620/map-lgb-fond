from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_commercial_facility_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    valid_rows = [normalize_row(row) for row in rows]
    valid_rows = [row for row in valid_rows if row.get("prefecture") and row.get("city")]
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    latest_year = max((_to_int(row.get("open_year")) or 0 for row in valid_rows), default=None)
    if latest_year == 0:
        latest_year = None

    city_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    prefecture_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in valid_rows:
        city_groups[(row["prefecture"], row["city"])].append(row)
        prefecture_groups[row["prefecture"]].append(row)

    return {
        "schemaVersion": 2,
        "source": "jcsc",
        "sourceLabel": "日本ショッピングセンター協会 オープンSC一覧表",
        "generatedAt": generated_at,
        "coverage": {
            "area": "全国",
            "facilityCount": len(valid_rows),
            "coordinateCount": sum(_has_coordinate(row) for row in valid_rows),
            "reliableCoordinateCount": sum(_has_reliable_coordinate(row) for row in valid_rows),
            "storeAreaMissingCount": sum(
                1 for row in valid_rows if _to_float(row.get("store_area_sqm")) is None
            ),
            "coordinateRate": _rate(
                sum(_has_coordinate(row) for row in valid_rows),
                len(valid_rows),
            ),
            "reliableCoordinateRate": _rate(
                sum(_has_reliable_coordinate(row) for row in valid_rows),
                len(valid_rows),
            ),
            "storeAreaMissingRate": _rate(
                sum(1 for row in valid_rows if _to_float(row.get("store_area_sqm")) is None),
                len(valid_rows),
            ),
        },
        "latestOpenYear": latest_year,
        "prefectures": {
            prefecture: _summarize_group(group)
            for prefecture, group in sorted(prefecture_groups.items())
        },
        "cities": {
            _city_key(prefecture, city): {
                "prefecture": prefecture,
                "city": city,
                **_summarize_group(group),
            }
            for (prefecture, city), group in sorted(city_groups.items())
        },
    }


def read_jcsc_csv(path: Path | list[Path]) -> list[dict[str, str]]:
    if isinstance(path, list):
        rows: list[dict[str, str]] = []
        for item in path:
            rows.extend(read_jcsc_csv(item))
        return rows

    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = dict(row)
    if not normalized.get("city") and normalized.get("municipality"):
        normalized["city"] = normalized["municipality"]
    return normalized


def write_summary(summary: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return output_path


def _summarize_group(rows: list[dict[str, str]]) -> dict[str, Any]:
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _to_int(row.get("open_year")) or 0,
            _to_int(row.get("open_month")) or 0,
            row.get("name") or "",
        ),
        reverse=True,
    )
    facilities = [
        {
            "name": row.get("name") or "",
            "openYear": _to_int(row.get("open_year")),
            "openMonth": _to_int(row.get("open_month")),
            "storeAreaSqm": _to_float(row.get("store_area_sqm")),
            "tenantCount": _to_int(row.get("tenant_count")),
        }
        for row in sorted_rows
    ]
    return {
        "scCount": len(rows),
        "storeAreaSumSqm": round(
            sum(_to_float(row.get("store_area_sqm")) or 0.0 for row in rows),
            2,
        ),
        "tenantCountSum": sum(_to_int(row.get("tenant_count")) or 0 for row in rows),
        "latestOpenYear": max((_to_int(row.get("open_year")) or 0 for row in rows), default=0)
        or None,
        "facilities": facilities,
        "recentOpenings": facilities[:3],
    }


def _city_key(prefecture: str, city: str) -> str:
    return f"{prefecture}|{city}"


def _to_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _has_coordinate(row: dict[str, str]) -> bool:
    return _to_float(row.get("lat")) is not None and _to_float(row.get("lon")) is not None


def _has_reliable_coordinate(row: dict[str, str]) -> bool:
    if not _has_coordinate(row):
        return False
    coordinate_source = (row.get("coordinate_source") or "").strip()
    coordinate_confidence = (row.get("coordinate_confidence") or "").strip()
    if coordinate_source == "municipality_representative":
        return False
    if coordinate_confidence and coordinate_confidence not in {"medium", "high"}:
        return False
    return True


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export lightweight commercial facility summary")
    parser.add_argument(
        "--input",
        type=Path,
        nargs="+",
        default=[Path("data/processed/jcsc/jcsc_sc_open.csv")],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../frontend/public/facilities/commercial_facilities.json"),
    )
    args = parser.parse_args()

    rows = read_jcsc_csv(args.input)
    output = write_summary(build_commercial_facility_summary(rows), args.output)
    print(f"exported commercial facility summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
