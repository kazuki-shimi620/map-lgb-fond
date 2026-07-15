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

from features.land_prices import (  # noqa: E402
    add_land_price_features,
    load_land_price_city_summary_csv,
    load_land_price_points_csv,
)

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]


def build_land_price_coverage_report(
    *,
    property_df,
    land_price_points_df,
    land_price_city_summary_df,
    source_paths: list[str],
    land_price_points_csv: Path,
    land_price_city_summary_csv: Path,
) -> dict[str, Any]:
    enriched = add_land_price_features(
        property_df,
        land_price_points_df,
        land_price_city_summary_df,
    )
    record_count = int(len(enriched))
    matched = int(enriched["has_land_price_data"].sum()) if record_count else 0
    coordinate_count = _coordinate_count(property_df)

    return {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourcePaths": source_paths,
        "landPricePointsCsv": str(land_price_points_csv),
        "landPricePointsCsvBytes": _file_size(land_price_points_csv),
        "landPriceCitySummaryCsv": str(land_price_city_summary_csv),
        "landPriceCitySummaryCsvBytes": _file_size(land_price_city_summary_csv),
        "recordCount": record_count,
        "propertyCoordinateCount": coordinate_count,
        "propertyCoordinateRate": coordinate_count / record_count if record_count else 0.0,
        "pointCount": int(len(land_price_points_df)),
        "citySummaryCount": int(len(land_price_city_summary_df)),
        "matchedRowCount": matched,
        "matchRate": matched / record_count if record_count else 0.0,
        "cityAveragePriceYenPerSqm": _numeric_summary(
            enriched,
            "land_price_city_avg_yen_per_sqm",
        ),
        "cityYoyRate": _numeric_summary(enriched, "land_price_city_yoy_rate"),
        "nearestPriceYenPerSqm": _numeric_summary(enriched, "nearest_land_price_yen_per_sqm"),
        "nearestDistanceKm": _numeric_summary(enriched, "nearest_land_price_distance_km"),
        "pointsWithin2km": _numeric_summary(enriched, "land_price_points_within_2km"),
    }


def save_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "land_price_coverage.json"
    markdown_path = output_dir / "land_price_coverage.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 地価データカバレッジ",
        "",
        f"* generatedAt: {report['generatedAt']}",
        f"* landPricePointsCsv: `{report['landPricePointsCsv']}`",
        f"* landPricePointsCsvBytes: {report['landPricePointsCsvBytes']:,}",
        f"* landPriceCitySummaryCsv: `{report['landPriceCitySummaryCsv']}`",
        f"* landPriceCitySummaryCsvBytes: {report['landPriceCitySummaryCsvBytes']:,}",
        f"* propertyRecords: {report['recordCount']:,}",
        f"* propertyCoordinateRows: {report.get('propertyCoordinateCount', 0):,}",
        f"* propertyCoordinateRate: {report.get('propertyCoordinateRate', 0.0):.2%}",
        f"* pointRecords: {report['pointCount']:,}",
        f"* citySummaryRecords: {report['citySummaryCount']:,}",
        f"* matchedRows: {report['matchedRowCount']:,}",
        f"* matchRate: {report['matchRate']:.2%}",
        "",
        "| feature | min | median | p95 | max |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for key in [
        "cityAveragePriceYenPerSqm",
        "cityYoyRate",
        "nearestPriceYenPerSqm",
        "nearestDistanceKm",
        "pointsWithin2km",
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


def _coordinate_count(df) -> int:
    if df.empty or not {"lat", "lon"}.issubset(df.columns):
        return 0
    return int((df["lat"].notna() & df["lon"].notna()).sum())


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
    parser = argparse.ArgumentParser(description="Summarize land price data coverage.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--land-price-points-csv",
        type=Path,
        default=Path("data/processed/land_prices/land_price_points.csv"),
    )
    parser.add_argument(
        "--land-price-city-summary-csv",
        type=Path,
        default=Path("data/processed/land_prices/land_price_city_summary.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/reports"))
    args = parser.parse_args()

    property_df, source_paths = _load_property_frames(args.regions, args.processed_dir)
    points = load_land_price_points_csv(args.land_price_points_csv)
    city_summary = load_land_price_city_summary_csv(args.land_price_city_summary_csv)
    report = build_land_price_coverage_report(
        property_df=property_df,
        land_price_points_df=points,
        land_price_city_summary_df=city_summary,
        source_paths=source_paths,
        land_price_points_csv=args.land_price_points_csv,
        land_price_city_summary_csv=args.land_price_city_summary_csv,
    )
    paths = save_report(report, args.output_dir)
    print(f"land price coverage report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
