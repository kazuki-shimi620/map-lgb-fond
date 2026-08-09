from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DEFAULT_THRESHOLDS = (10_000.0, 20_000.0, 50_000.0, 100_000.0)


def summarize_park_areas(
    path: Path,
    *,
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> dict[str, object]:
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    values = sorted(float(row["area_sqm"]) for row in rows if row.get("area_sqm"))
    if not values:
        raise ValueError(f"park area data is empty: {path}")

    source_counts: dict[str, int] = {}
    for row in rows:
        source = row.get("area_source", "") or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1

    def percentile(ratio: float) -> float:
        index = round((len(values) - 1) * ratio)
        return round(values[index], 2)

    threshold_counts = {
        str(int(threshold)): {
            "count": sum(value >= threshold for value in values),
            "rate": round(sum(value >= threshold for value in values) / len(values), 4),
        }
        for threshold in thresholds
    }
    return {
        "input": str(path),
        "rowCount": len(values),
        "areaSourceCounts": source_counts,
        "areaSqm": {
            "min": round(values[0], 2),
            "p25": percentile(0.25),
            "p50": percentile(0.5),
            "p75": percentile(0.75),
            "p90": percentile(0.9),
            "p95": percentile(0.95),
            "max": round(values[-1], 2),
        },
        "thresholdsSqm": threshold_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize OSM park area thresholds.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = summarize_park_areas(args.input)
    content = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
