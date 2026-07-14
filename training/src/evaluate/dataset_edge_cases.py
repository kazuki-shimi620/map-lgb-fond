from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SEGMENTS = {
    "old_building": lambda df: df["age"] >= 40,
    "very_old_building": lambda df: df["age"] >= 50,
    "station_far": lambda df: df["station_distance"] >= 30,
    "station_very_far": lambda df: df["station_distance"] >= 60,
    "high_price": lambda df: df["price"] >= 100_000_000,
    "luxury_unit_price": lambda df: df["price_per_sqm"] >= 2_000_000,
    "small_area": lambda df: df["area"] <= 25,
    "large_area": lambda df: df["area"] >= 100,
}


def build_edge_case_report(df, *, region: str, source_path: str) -> dict[str, Any]:
    prepared = df.copy()
    prepared["price_per_sqm"] = prepared["price"] / prepared["area"]

    segments = [_summarize_segment("all", prepared)]
    for name, selector in SEGMENTS.items():
        segments.append(_summarize_segment(name, prepared[selector(prepared)]))

    return _attach_share(
        {
            "region": region,
            "sourcePath": source_path,
            "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
            "recordCount": int(len(prepared)),
            "segments": segments,
        }
    )


def save_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    region = str(report["region"])
    json_path = output_dir / f"{region}_edge_cases.json"
    markdown_path = output_dir / f"{region}_edge_cases.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report['region']} edge case summary",
        "",
        f"* source: `{report['sourcePath']}`",
        f"* records: {report['recordCount']:,}",
        f"* generatedAt: {report['generatedAt']}",
        "",
        "| segment | count | share | median price | median unit price | median age | median walk |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for segment in report["segments"]:
        lines.append(
            "| {name} | {count:,} | {share:.2%} | {median_price:,.0f} | "
            "{median_unit_price:,.0f} | {median_age:.1f} | {median_walk:.1f} |".format(
                name=segment["name"],
                count=segment["count"],
                share=segment["share"],
                median_price=segment["price"]["median"],
                median_unit_price=segment["pricePerSqm"]["median"],
                median_age=segment["age"]["median"],
                median_walk=segment["stationDistance"]["median"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _summarize_segment(name: str, df) -> dict[str, Any]:
    return {
        "name": name,
        "count": int(len(df)),
        "share": 0.0,
        "price": _numeric_summary(df, "price"),
        "pricePerSqm": _numeric_summary(df, "price_per_sqm"),
        "age": _numeric_summary(df, "age"),
        "stationDistance": _numeric_summary(df, "station_distance"),
    }


def _numeric_summary(df, column: str) -> dict[str, float]:
    if df.empty:
        return {"min": 0.0, "p05": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    series = df[column]
    return {
        "min": float(series.min()),
        "p05": float(series.quantile(0.05)),
        "median": float(series.median()),
        "p95": float(series.quantile(0.95)),
        "max": float(series.max()),
    }


def _attach_share(report: dict[str, Any]) -> dict[str, Any]:
    total = report["recordCount"]
    for segment in report["segments"]:
        segment["share"] = segment["count"] / total if total else 0.0
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--output-dir", default="outputs/reports")
    args = parser.parse_args()

    import pandas as pd

    input_path = Path(args.input)
    df = pd.read_parquet(input_path)
    report = build_edge_case_report(df, region=args.region, source_path=str(input_path))
    paths = save_report(report, Path(args.output_dir))
    print(f"edge case report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
