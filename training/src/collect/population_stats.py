from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = Path("data/processed/population")
FIELDNAMES = [
    "year",
    "prefecture",
    "municipality",
    "city_code",
    "population_total",
    "households_total",
    "population_density_per_km2",
    "aging_rate",
    "working_age_rate",
    "under_15_rate",
    "population_change_5y_rate",
    "household_persons_avg",
    "area_km2",
    "source",
    "source_url",
]


class PopulationStatsCollectError(RuntimeError):
    pass


def collect_population_stats(
    *,
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path | int]:
    if not input_path.exists():
        raise PopulationStatsCollectError(f"Population input CSV not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_rows = _read_csv(input_path)
    rows = normalize_population_rows(raw_rows)
    output_path = output_dir / "municipality_population.csv"
    metadata_path = output_dir / "metadata.json"

    _write_csv(output_path, rows)
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
    return {
        "municipality_population_csv": output_path,
        "metadata": metadata_path,
        "row_count": len(rows),
    }


def normalize_population_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [_normalize_population_row(row) for row in rows]
    normalized = [
        row
        for row in normalized
        if row["year"] is not None and row["prefecture"] and row["municipality"]
    ]
    _add_population_change_rates(normalized)
    return sorted(
        normalized,
        key=lambda row: (
            int(row["year"]),
            str(row["prefecture"]),
            str(row["municipality"]),
            str(row["city_code"]),
        ),
    )


def _normalize_population_row(row: dict[str, Any]) -> dict[str, Any]:
    population_total = _to_float(_pick(row, "population_total", "population", "total_population"))
    households_total = _to_float(_pick(row, "households_total", "households", "household_total"))
    area_km2 = _to_float(_pick(row, "area_km2", "area"))
    population_density = _to_float(
        _pick(row, "population_density_per_km2", "population_density", "density")
    )
    under_15 = _to_float(_pick(row, "population_under_15", "under_15_population"))
    working_age = _to_float(_pick(row, "population_15_to_64", "working_age_population"))
    age_65_plus = _to_float(_pick(row, "population_65_plus", "age_65_plus_population"))

    if population_density is None and population_total is not None and area_km2:
        population_density = population_total / area_km2

    return {
        "year": _to_int(_pick(row, "year", "survey_year")),
        "prefecture": _to_text(_pick(row, "prefecture", "prefecture_name")),
        "municipality": _to_text(_pick(row, "municipality", "city", "municipality_name")),
        "city_code": _to_text(_pick(row, "city_code", "municipality_code")),
        "population_total": population_total,
        "households_total": households_total,
        "population_density_per_km2": population_density,
        "aging_rate": _rate(age_65_plus, population_total),
        "working_age_rate": _rate(working_age, population_total),
        "under_15_rate": _rate(under_15, population_total),
        "population_change_5y_rate": None,
        "household_persons_avg": _safe_divide(population_total, households_total),
        "area_km2": area_km2,
        "source": _to_text(_pick(row, "source")) or "population_stats",
        "source_url": _to_text(_pick(row, "source_url", "sourceUrl")),
    }


def _add_population_change_rates(rows: list[dict[str, Any]]) -> None:
    by_key = {
        (_population_key(row), int(row["year"])): row
        for row in rows
        if row["year"] is not None
    }
    for row in rows:
        year = int(row["year"])
        current = row["population_total"]
        previous = by_key.get((_population_key(row), year - 5))
        if current is None or not previous or not previous["population_total"]:
            row["population_change_5y_rate"] = 0.0
            continue
        row["population_change_5y_rate"] = (
            (float(current) - float(previous["population_total"]))
            / float(previous["population_total"])
            * 100
        )


def _population_key(row: dict[str, Any]) -> str:
    city_code = row.get("city_code")
    if city_code:
        return f"code:{city_code}"
    return f"name:{row.get('prefecture')}:{row.get('municipality')}"


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


def _safe_divide(numerator: float | None, denominator: float | None) -> float:
    if numerator is None or not denominator:
        return 0.0
    return numerator / denominator


def _rate(value: float | None, total: float | None) -> float:
    if value is None or not total:
        return 0.0
    return value / total * 100


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize municipality population stats.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        outputs = collect_population_stats(
            input_path=args.input,
            output_dir=args.output_dir,
        )
    except PopulationStatsCollectError as error:
        print(f"population stats collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected population stats: "
        f"rows={outputs['row_count']} "
        f"csv={outputs['municipality_population_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
