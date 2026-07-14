from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CATEGORIES = [
    {
        "id": "hospital",
        "label": "病院",
        "color": "#dc2626",
        "enabled": True,
    },
    {
        "id": "supermarket",
        "label": "スーパー",
        "color": "#16a34a",
        "enabled": True,
    },
    {
        "id": "commercial_facility",
        "label": "商業施設",
        "color": "#9333ea",
        "enabled": True,
    },
    {
        "id": "park",
        "label": "公園",
        "color": "#15803d",
        "enabled": True,
    },
    {
        "id": "convenience_store",
        "label": "コンビニ",
        "color": "#f97316",
        "enabled": True,
    },
]

CATEGORY_IDS = {category["id"] for category in CATEGORIES}
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


def load_facility_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows = []
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for line_number, row in enumerate(reader, start=2):
            record = normalize_facility_row(row, line_number=line_number)
            if record is not None:
                rows.append(record)
    return sorted(rows, key=lambda row: (row["categoryId"], row["prefecture"], row["name"]))


def normalize_facility_row(row: dict[str, str], *, line_number: int) -> dict[str, Any] | None:
    category_id = (row.get("category_id") or row.get("categoryId") or "").strip()
    name = (row.get("name") or "").strip()
    lat = parse_float(row.get("lat"))
    lon = parse_float(row.get("lon"))

    if not category_id and not name and lat is None and lon is None:
        return None
    if category_id not in CATEGORY_IDS:
        raise ValueError(f"line {line_number}: unsupported category_id '{category_id}'")
    if not name:
        raise ValueError(f"line {line_number}: name is required")
    if lat is None or lon is None:
        raise ValueError(f"line {line_number}: lat and lon are required")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"line {line_number}: lat/lon is outside valid range")

    explicit_id = (row.get("id") or "").strip()
    prefecture = (row.get("prefecture") or "").strip()
    municipality = (row.get("municipality") or "").strip()
    address = (row.get("address") or "").strip()
    source = (row.get("source") or "").strip()
    updated_at = (row.get("updated_at") or row.get("updatedAt") or "").strip()

    record_id = explicit_id or build_facility_id(category_id, name, lat, lon)
    return {
        "id": record_id,
        "categoryId": category_id,
        "name": name,
        "lat": lat,
        "lon": lon,
        "prefecture": prefecture,
        "municipality": municipality,
        "address": address,
        "source": source,
        "updatedAt": updated_at,
    }


def build_facility_id(category_id: str, name: str, lat: float, lon: float) -> str:
    safe_name = "".join(char if char.isalnum() else "_" for char in name.lower()).strip("_")
    return f"{category_id}_{safe_name}_{lat:.6f}_{lon:.6f}"


def parse_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def export_nearby_facilities(
    *,
    input_csv: Path,
    output: Path,
    source: str,
    source_label: str,
) -> Path:
    facilities = load_facility_rows(input_csv)
    payload = {
        "schemaVersion": 1,
        "source": source if facilities else "not_generated",
        "sourceLabel": source_label if facilities else "周辺施設データ未生成",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds") if facilities else None,
        "categories": CATEGORIES,
        "facilities": facilities,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def write_csv_template(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=NEARBY_FACILITY_FIELDNAMES)
        writer.writeheader()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Export nearby facility markers for frontend map.")
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("data/processed/facilities/nearby_facilities.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../frontend/public/facilities/nearby_facilities.json"),
    )
    parser.add_argument("--source", default="manual_or_processed")
    parser.add_argument("--source-label", default="周辺施設データ")
    parser.add_argument(
        "--write-template",
        type=Path,
        help="Write a nearby facility CSV template and exit.",
    )
    args = parser.parse_args()

    if args.write_template:
        output = write_csv_template(args.write_template)
        print(f"wrote nearby facilities template: {output}")
        return 0

    try:
        output = export_nearby_facilities(
            input_csv=args.input_csv,
            output=args.output,
            source=args.source,
            source_label=args.source_label,
        )
    except ValueError as error:
        print(f"nearby facilities export failed: {error}")
        return 1

    print(f"exported nearby facilities: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
