from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from features.population_stats import (  # noqa: E402
    add_population_features,
    load_population_stats_csv,
)

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]


def build_population_coverage_report(
    *,
    property_df,
    population_stats_df,
    source_paths: list[str],
    population_stats_csv: Path,
) -> dict[str, Any]:
    enriched = add_population_features(property_df, population_stats_df)
    record_count = int(len(enriched))
    matched = int(enriched["has_population_data"].sum()) if record_count else 0

    return {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourcePaths": source_paths,
        "populationStatsCsv": str(population_stats_csv),
        "populationStatsCsvBytes": _file_size(population_stats_csv),
        "recordCount": record_count,
        "populationStatsCount": int(len(population_stats_df)),
        "matchedRowCount": matched,
        "matchRate": matched / record_count if record_count else 0.0,
        "municipalityPopulation": _numeric_summary(enriched, "municipality_population"),
        "municipalityHouseholds": _numeric_summary(enriched, "municipality_households"),
        "municipalityPopulationDensity": _numeric_summary(
            enriched,
            "municipality_population_density",
        ),
        "municipalityAgingRate": _numeric_summary(enriched, "municipality_aging_rate"),
        "municipalityWorkingAgeRate": _numeric_summary(
            enriched,
            "municipality_working_age_rate",
        ),
        "populationChange5yRate": _numeric_summary(enriched, "population_change_5y_rate"),
        "householdPersonsAvg": _numeric_summary(enriched, "household_persons_avg"),
    }


def save_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "population_coverage.json"
    markdown_path = output_dir / "population_coverage.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 人口統計データカバレッジ",
        "",
        f"* generatedAt: {report['generatedAt']}",
        f"* populationStatsCsv: `{report['populationStatsCsv']}`",
        f"* populationStatsCsvBytes: {report['populationStatsCsvBytes']:,}",
        f"* propertyRecords: {report['recordCount']:,}",
        f"* populationStatsRecords: {report['populationStatsCount']:,}",
        f"* matchedRows: {report['matchedRowCount']:,}",
        f"* matchRate: {report['matchRate']:.2%}",
        "",
        "| feature | min | median | p95 | max |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for key in [
        "municipalityPopulation",
        "municipalityHouseholds",
        "municipalityPopulationDensity",
        "municipalityAgingRate",
        "municipalityWorkingAgeRate",
        "populationChange5yRate",
        "householdPersonsAvg",
    ]:
        summary = report[key]
        lines.append(
            f"| {key} | {summary['min']:.3f} | {summary['median']:.3f} | "
            f"{summary['p95']:.3f} | {summary['max']:.3f} |"
        )
    lines.append("")
    return "\n".join(lines)


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _numeric_summary(df, column: str) -> dict[str, float]:
    if df.empty or column not in df.columns:
        return {"min": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    series = df[column]
    return {
        "min": float(series.min()),
        "median": float(series.median()),
        "p95": float(series.quantile(0.95)),
        "max": float(series.max()),
    }


def _load_property_frames(regions: list[str], processed_dir: Path):
    import pandas as pd

    frames = []
    source_paths = []
    for region in regions:
        path = processed_dir / f"{region}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Processed dataset not found: {path}")
        frame = pd.read_parquet(path)
        frame["source_region"] = region
        frames.append(frame)
        source_paths.append(str(path))
    return pd.concat(frames, ignore_index=True), source_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize population stats data coverage.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--population-stats-csv",
        type=Path,
        default=Path("data/processed/population/municipality_population.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/reports"))
    args = parser.parse_args()

    property_df, source_paths = _load_property_frames(args.regions, args.processed_dir)
    population_stats = load_population_stats_csv(args.population_stats_csv)
    report = build_population_coverage_report(
        property_df=property_df,
        population_stats_df=population_stats,
        source_paths=source_paths,
        population_stats_csv=args.population_stats_csv,
    )
    paths = save_report(report, args.output_dir)
    print(f"population coverage report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
