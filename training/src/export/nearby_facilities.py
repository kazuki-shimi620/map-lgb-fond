from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from features.commercial_facility_scale import (  # noqa: E402
    classify_commercial_facility_scale,
)

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
        "color": "#7c3aed",
        "enabled": True,
        "sourceLabel": "日本ショッピングセンター協会（JCSC）公開PDF・年別ページを基に独自生成",
        "sourceUrl": "https://www.jcsc.or.jp/sc_data/sc_open/sc_list",
        "licenseLabel": "出典を明記して参考情報として配信",
        "coverageArea": "全国（信頼できる座標がある施設のみ）",
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
    {
        "id": "cinema",
        "label": "映画館",
        "color": "#0284c7",
        "enabled": True,
        "sourceLabel": "OpenStreetMap contributors",
        "sourceUrl": "https://www.openstreetmap.org/copyright",
        "licenseLabel": "Open Database License (ODbL)",
        "coverageArea": "全国（OpenStreetMap登録施設）",
    },
    {
        "id": "museum",
        "label": "美術館・博物館",
        "color": "#16a34a",
        "enabled": True,
        "sourceLabel": "OpenStreetMap contributors",
        "sourceUrl": "https://www.openstreetmap.org/copyright",
        "licenseLabel": "Open Database License (ODbL)",
        "coverageArea": "全国9地方（OpenStreetMap登録施設、取得失敗セルは継続補完）",
    },
    {
        "id": "hot_spring",
        "label": "温泉・入浴",
        "color": "#ea580c",
        "enabled": True,
        "sourceLabel": "OpenStreetMap contributors",
        "sourceUrl": "https://www.openstreetmap.org/copyright",
        "licenseLabel": "Open Database License (ODbL)",
        "coverageArea": "全国（公衆浴場node・天然温泉、首都圏はway/relationも含む）",
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


def load_commercial_facility_rows(path: Path | list[Path]) -> list[dict[str, Any]]:
    if isinstance(path, list):
        rows: list[dict[str, Any]] = []
        for item in path:
            rows.extend(load_commercial_facility_rows(item))
        return sorted(rows, key=lambda row: (row["prefecture"], row["municipality"], row["name"]))

    if not path.exists():
        return []

    rows = []
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for line_number, row in enumerate(reader, start=2):
            record = normalize_commercial_facility_row(row, line_number=line_number)
            if record is not None:
                rows.append(record)
    return sorted(rows, key=lambda row: (row["prefecture"], row["municipality"], row["name"]))


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


def normalize_commercial_facility_row(
    row: dict[str, str],
    *,
    line_number: int,
) -> dict[str, Any] | None:
    name = (row.get("name") or row.get("facility_name") or "").strip()
    lat = parse_float(row.get("lat") or row.get("latitude"))
    lon = parse_float(row.get("lon") or row.get("longitude"))

    if not name and lat is None and lon is None:
        return None
    if lat is None and lon is None:
        return None
    if not has_reliable_coordinate(row):
        return None
    if not name:
        raise ValueError(f"commercial line {line_number}: name is required")
    if lat is None or lon is None:
        raise ValueError(f"commercial line {line_number}: lat and lon are required together")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError(f"commercial line {line_number}: lat/lon is outside valid range")

    prefecture = (row.get("prefecture") or "").strip()
    municipality = (row.get("municipality") or row.get("city") or "").strip()
    address = (row.get("address") or "").strip()
    source = (row.get("coordinate_source") or row.get("source") or "jcsc").strip()
    updated_at = (row.get("updated_at") or row.get("updatedAt") or "").strip()
    explicit_id = (row.get("id") or "").strip()
    record_id = explicit_id or build_facility_id("commercial_facility", name, lat, lon)
    store_area_sqm = parse_float(row.get("store_area_sqm"))
    tenant_count = parse_int(row.get("tenant_count"))
    return {
        "id": record_id,
        "categoryId": "commercial_facility",
        "name": name,
        "lat": lat,
        "lon": lon,
        "prefecture": prefecture,
        "municipality": municipality,
        "address": address,
        "source": source,
        "updatedAt": updated_at,
        "storeAreaSqm": store_area_sqm,
        "tenantCount": tenant_count,
        **classify_commercial_facility_scale(store_area_sqm, tenant_count),
    }


def has_reliable_coordinate(row: dict[str, str]) -> bool:
    coordinate_source = (row.get("coordinate_source") or "").strip()
    coordinate_confidence = (row.get("coordinate_confidence") or "").strip()
    if coordinate_source == "municipality_representative":
        return False
    if coordinate_confidence and coordinate_confidence not in {"medium", "high"}:
        return False
    return True


def build_facility_id(category_id: str, name: str, lat: float, lon: float) -> str:
    safe_name = "".join(char if char.isalnum() else "_" for char in name.lower()).strip("_")
    return f"{category_id}_{safe_name}_{lat:.6f}_{lon:.6f}"


def parse_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def parse_int(value: str | None) -> int | None:
    number = parse_float(value)
    return int(number) if number is not None else None


def export_nearby_facilities(
    *,
    input_csv: Path | list[Path],
    commercial_facilities_csv: Path | list[Path] | None = None,
    output: Path,
    source: str,
    source_label: str,
) -> Path:
    input_paths = [input_csv] if isinstance(input_csv, Path) else input_csv
    facilities = []
    for path in input_paths:
        facilities.extend(load_facility_rows(path))
    if commercial_facilities_csv is not None:
        facilities.extend(load_commercial_facility_rows(commercial_facilities_csv))
        facilities = deduplicate_facilities(facilities)
    active_category_ids = {facility["categoryId"] for facility in facilities}
    generated_at = datetime.now(UTC).isoformat(timespec="seconds") if facilities else None
    payload = {
        "schemaVersion": 1,
        "source": source if facilities else "not_generated",
        "sourceLabel": source_label if facilities else "周辺施設データ未生成",
        "generatedAt": generated_at,
        "categories": [
            {**category, "generatedAt": generated_at}
            for category in CATEGORIES
            if category["id"] in active_category_ids
        ],
        "facilities": facilities,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def deduplicate_facilities(facilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = {}
    for facility in facilities:
        key = facility["id"]
        records[key] = facility
    return sorted(
        records.values(),
        key=lambda row: (row["categoryId"], row["prefecture"], row["name"]),
    )


def write_csv_template(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=NEARBY_FACILITY_FIELDNAMES,
            lineterminator="\n",
        )
        writer.writeheader()
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Export nearby facility markers for frontend map.")
    parser.add_argument(
        "--input-csv",
        type=Path,
        nargs="+",
        default=[],
        help=(
            "Optional marker CSVs. Omit in the standard build to publish only curated "
            "commercial facilities."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../frontend/public/facilities/nearby_facilities.json"),
    )
    parser.add_argument(
        "--commercial-facilities-csv",
        type=Path,
        nargs="+",
        default=Path("data/processed/jcsc/jcsc_sc_open.csv"),
        help=(
            "Optional commercial facility CSVs. Rows with reliable lat/lon are exported as markers."
        ),
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
            commercial_facilities_csv=args.commercial_facilities_csv,
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
