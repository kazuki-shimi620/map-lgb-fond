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

from features.education_facilities import add_education_features, load_education_facilities_csv  # noqa: E402

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]


def build_education_coverage_report(
    *,
    property_df,
    education_facilities_df,
    source_paths: list[str],
    education_facilities_csv: Path,
) -> dict[str, Any]:
    enriched = add_education_features(property_df, education_facilities_df)
    record_count = int(len(enriched))
    matched = int(enriched["has_education_data"].sum()) if record_count else 0

    return {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourcePaths": source_paths,
        "educationFacilitiesCsv": str(education_facilities_csv),
        "educationFacilitiesCsvBytes": education_facilities_csv.stat().st_size
        if education_facilities_csv.exists()
        else 0,
        "recordCount": record_count,
        "facilityCount": int(len(education_facilities_df)),
        "matchedRowCount": matched,
        "matchRate": matched / record_count if record_count else 0.0,
        "facilityTypeCounts": _value_counts(education_facilities_df, "facility_type"),
        "nearestElementaryDistanceKm": _numeric_summary(
            enriched,
            "nearest_elementary_school_distance_km",
        ),
        "nearestJuniorHighDistanceKm": _numeric_summary(
            enriched,
            "nearest_junior_high_school_distance_km",
        ),
        "nurseryCountWithin500m": _numeric_summary(enriched, "nursery_count_within_500m"),
        "nurseryCountWithin1km": _numeric_summary(enriched, "nursery_count_within_1km"),
        "kindergartenCountWithin1km": _numeric_summary(enriched, "kindergarten_count_within_1km"),
    }


def save_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "education_coverage.json"
    markdown_path = output_dir / "education_coverage.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 教育施設データカバレッジ",
        "",
        f"* generatedAt: {report['generatedAt']}",
        f"* educationFacilitiesCsv: `{report['educationFacilitiesCsv']}`",
        f"* educationFacilitiesCsvBytes: {report['educationFacilitiesCsvBytes']:,}",
        f"* propertyRecords: {report['recordCount']:,}",
        f"* facilityRecords: {report['facilityCount']:,}",
        f"* matchedRows: {report['matchedRowCount']:,}",
        f"* matchRate: {report['matchRate']:.2%}",
        "",
        "## facility_type",
        "",
        _counts_table(report["facilityTypeCounts"]),
        "",
        "## numeric summaries",
        "",
        "| feature | min | median | p95 | max |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for key in [
        "nearestElementaryDistanceKm",
        "nearestJuniorHighDistanceKm",
        "nurseryCountWithin500m",
        "nurseryCountWithin1km",
        "kindergartenCountWithin1km",
    ]:
        summary = report[key]
        lines.append(
            f"| {key} | {summary['min']:.3f} | {summary['median']:.3f} | "
            f"{summary['p95']:.3f} | {summary['max']:.3f} |"
        )
    lines.append("")
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
    if df.empty or column not in df.columns:
        return {}
    values = Counter(str(value) for value in df[column].fillna("unknown"))
    return dict(sorted(values.items(), key=lambda item: (-item[1], item[0])))


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
    parser = argparse.ArgumentParser(description="Summarize education facility data coverage.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--education-facilities-csv",
        type=Path,
        default=Path("data/processed/education/education_facilities.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/reports"))
    args = parser.parse_args()

    property_df, source_paths = _load_property_frames(args.regions, args.processed_dir)
    education_facilities = load_education_facilities_csv(args.education_facilities_csv)
    report = build_education_coverage_report(
        property_df=property_df,
        education_facilities_df=education_facilities,
        source_paths=source_paths,
        education_facilities_csv=args.education_facilities_csv,
    )
    paths = save_report(report, args.output_dir)
    print(f"education coverage report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
