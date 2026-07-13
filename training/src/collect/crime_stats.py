from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = Path("data/processed/crime")
FIELDNAMES = [
    "year",
    "prefecture",
    "municipality",
    "city_code",
    "area_unit",
    "crime_type",
    "crime_count",
    "population_total",
    "crime_count_per_1000_population",
    "source",
    "source_url",
    "notes",
]


class CrimeStatsCollectError(RuntimeError):
    pass


def collect_crime_stats(
    *,
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path | int]:
    if not input_path.exists():
        raise CrimeStatsCollectError(f"Crime stats input CSV not found: {input_path}")

    raw_rows = _read_csv(input_path)
    rows = normalize_crime_rows(raw_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "crime_municipality.csv"
    metadata_path = output_dir / "metadata.json"
    _write_csv(csv_path, rows)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourceInput": str(input_path),
        "rowCount": len(rows),
        "years": sorted({row["year"] for row in rows if row["year"] is not None}),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"crime_municipality_csv": csv_path, "metadata": metadata_path, "row_count": len(rows)}


def normalize_crime_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [_normalize_crime_row(row) for row in rows]
    normalized = [
        row
        for row in normalized
        if row["year"] is not None
        and row["prefecture"]
        and row["municipality"]
        and row["crime_type"]
    ]
    return sorted(
        normalized,
        key=lambda row: (
            int(row["year"]),
            str(row["prefecture"]),
            str(row["municipality"]),
            str(row["crime_type"]),
        ),
    )


def _normalize_crime_row(row: dict[str, Any]) -> dict[str, Any]:
    crime_count = _to_float(_pick(row, "crime_count", "count", "recognized_count"))
    population_total = _to_float(_pick(row, "population_total", "population"))
    per_1000 = _to_float(
        _pick(
            row,
            "crime_count_per_1000_population",
            "crime_per_1000_population",
            "per_1000_population",
        )
    )
    if per_1000 is None and crime_count is not None and population_total:
        per_1000 = crime_count / population_total * 1000

    return {
        "year": _to_int(_pick(row, "year", "crime_year", "survey_year")),
        "prefecture": _to_text(_pick(row, "prefecture", "prefecture_name")),
        "municipality": _to_text(_pick(row, "municipality", "city", "municipality_name")),
        "city_code": _to_text(_pick(row, "city_code", "municipality_code")),
        "area_unit": _to_text(_pick(row, "area_unit", "unit")) or "municipality",
        "crime_type": _to_text(_pick(row, "crime_type", "category")) or "刑法犯総数",
        "crime_count": crime_count,
        "population_total": population_total,
        "crime_count_per_1000_population": per_1000,
        "source": _to_text(_pick(row, "source")) or "crime_stats",
        "source_url": _to_text(_pick(row, "source_url", "sourceUrl")),
        "notes": _to_text(_pick(row, "notes", "note")),
    }


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _pick(row: dict[str, Any], *keys: str):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize municipality crime stats.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        outputs = collect_crime_stats(input_path=args.input, output_dir=args.output_dir)
    except CrimeStatsCollectError as error:
        print(f"crime stats collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected crime stats: "
        f"rows={outputs['row_count']} "
        f"csv={outputs['crime_municipality_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
