from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_municipality_land_price_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    valid_rows = [
        row
        for row in rows
        if row.get("prefecture") and row.get("municipality") and _to_int(row.get("year"))
    ]
    grouped: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in valid_rows:
        grouped[
            (
                row["prefecture"],
                row["municipality"],
                int(_to_int(row.get("year")) or 0),
            )
        ].append(row)

    cities: dict[str, dict[str, Any]] = {}
    latest_year = max((year for _, _, year in grouped), default=None)
    for (prefecture, municipality, year), group in sorted(grouped.items()):
        key = _city_key(prefecture, municipality)
        city = cities.setdefault(
            key,
            {
                "prefecture": prefecture,
                "municipality": municipality,
                "years": {},
            },
        )
        point_count = sum(_to_float(row.get("point_count")) or 0.0 for row in group)
        city["years"][str(year)] = {
            "avgPriceYenPerSqm": _weighted_average(
                group,
                "avg_price_yen_per_sqm",
                "point_count",
            ),
            "yoyRate": _weighted_average(group, "avg_yoy_rate", "point_count"),
            "pointCount": point_count,
        }

    return {
        "schemaVersion": 1,
        "source": "reinfolib_xpt002",
        "sourceLabel": "国土交通省 不動産情報ライブラリ 地価公示・地価調査",
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "latestYear": latest_year,
        "cities": cities,
    }


def read_city_summary_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_summary(summary: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return output_path


def _weighted_average(
    rows: list[dict[str, str]],
    value_column: str,
    weight_column: str,
) -> float:
    pairs = [
        (value, weight)
        for row in rows
        if (value := _to_float(row.get(value_column))) is not None
        and (weight := _to_float(row.get(weight_column))) is not None
    ]
    if not pairs:
        return 0.0
    weight_sum = sum(weight for _, weight in pairs)
    if weight_sum == 0:
        return sum(value for value, _ in pairs) / len(pairs)
    return sum(value * weight for value, weight in pairs) / weight_sum


def _city_key(prefecture: str, municipality: str) -> str:
    return f"{prefecture}|{municipality}"


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Export lightweight land price summary")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/land_prices/land_price_city_summary.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../frontend/public/land-prices/municipality_land_prices.json"),
    )
    args = parser.parse_args()

    rows = read_city_summary_csv(args.input)
    output = write_summary(build_municipality_land_price_summary(rows), args.output)
    print(f"exported land price summary: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
