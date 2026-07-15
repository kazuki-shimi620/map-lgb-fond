from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from features.urban_planning import add_urban_planning_features, load_urban_planning_areas_csv  # noqa: E402

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]


def build_urban_planning_coverage_report(
    *,
    property_df,
    urban_planning_areas_df,
    source_paths: list[str],
    urban_planning_csv: Path,
) -> dict[str, Any]:
    enriched = add_urban_planning_features(property_df, urban_planning_areas_df)
    record_count = int(len(enriched))
    zoning_matched = int(enriched["has_zoning_data"].sum()) if record_count else 0
    coordinate_count = _coordinate_count(property_df)

    return {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourcePaths": source_paths,
        "urbanPlanningCsv": str(urban_planning_csv),
        "urbanPlanningCsvBytes": urban_planning_csv.stat().st_size
        if urban_planning_csv.exists()
        else 0,
        "recordCount": record_count,
        "propertyCoordinateCount": coordinate_count,
        "propertyCoordinateRate": coordinate_count / record_count if record_count else 0.0,
        "areaCount": int(len(urban_planning_areas_df)),
        "zoningMatchedRowCount": zoning_matched,
        "zoningMatchRate": zoning_matched / record_count if record_count else 0.0,
        "zoningTypeCounts": _value_counts(enriched, "zoning_type"),
        "cityPlanningAreaTypeCounts": _value_counts(enriched, "city_planning_area_type"),
        "locationOptimizationAreaCounts": _value_counts(enriched, "location_optimization_area"),
    }


def save_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "urban_planning_coverage.json"
    markdown_path = output_dir / "urban_planning_coverage.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 用途地域・都市計画データカバレッジ",
        "",
        f"* generatedAt: {report['generatedAt']}",
        f"* urbanPlanningCsv: `{report['urbanPlanningCsv']}`",
        f"* urbanPlanningCsvBytes: {report['urbanPlanningCsvBytes']:,}",
        f"* propertyRecords: {report['recordCount']:,}",
        f"* propertyCoordinateRows: {report.get('propertyCoordinateCount', 0):,}",
        f"* propertyCoordinateRate: {report.get('propertyCoordinateRate', 0.0):.2%}",
        f"* areaRecords: {report['areaCount']:,}",
        f"* zoningMatchedRows: {report['zoningMatchedRowCount']:,}",
        f"* zoningMatchRate: {report['zoningMatchRate']:.2%}",
        "",
        "## zoning_type",
        "",
        _counts_table(report["zoningTypeCounts"]),
        "",
        "## city_planning_area_type",
        "",
        _counts_table(report["cityPlanningAreaTypeCounts"]),
        "",
        "## location_optimization_area",
        "",
        _counts_table(report["locationOptimizationAreaCounts"]),
        "",
    ]
    return "\n".join(lines)


def _counts_table(counts: dict[str, int]) -> str:
    lines = [
        "| value | count |",
        "| --- | ---: |",
    ]
    for value, count in counts.items():
        lines.append(f"| {value} | {count:,} |")
    return "\n".join(lines)


def _value_counts(df, column: str) -> dict[str, int]:
    values = Counter(str(value) for value in df[column].fillna("unknown"))
    return dict(sorted(values.items(), key=lambda item: (-item[1], item[0])))


def _coordinate_count(df) -> int:
    if df.empty or not {"lat", "lon"}.issubset(df.columns):
        return 0
    return int((df["lat"].notna() & df["lon"].notna()).sum())


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
    parser = argparse.ArgumentParser(description="Summarize urban planning data coverage.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--urban-planning-csv",
        type=Path,
        default=Path("data/processed/urban_planning/urban_planning_areas.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/reports"))
    args = parser.parse_args()

    property_df, source_paths = _load_property_frames(args.regions, args.processed_dir)
    urban_planning_areas = load_urban_planning_areas_csv(args.urban_planning_csv)
    report = build_urban_planning_coverage_report(
        property_df=property_df,
        urban_planning_areas_df=urban_planning_areas,
        source_paths=source_paths,
        urban_planning_csv=args.urban_planning_csv,
    )
    paths = save_report(report, args.output_dir)
    print(f"urban planning coverage report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
