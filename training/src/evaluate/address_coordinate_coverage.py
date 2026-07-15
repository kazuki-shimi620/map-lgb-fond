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

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]


def build_address_coordinate_coverage_report(
    *,
    property_df,
    address_points_df,
    source_paths: list[str],
    address_points_csv: Path,
) -> dict[str, Any]:
    record_count = int(len(property_df))
    property_coordinate_count = _coordinate_count(property_df)
    district_count = _district_count(property_df)
    matched = match_address_points(property_df, address_points_df)
    matched_count = int(matched["coordinate_match_level"].ne("none").sum()) if record_count else 0
    town_matched_count = int(matched["coordinate_match_level"].eq("town").sum()) if record_count else 0
    district_prefix_matched_count = (
        int(matched["coordinate_match_level"].eq("district_prefix").sum()) if record_count else 0
    )
    municipality_matched_count = (
        int(matched["coordinate_match_level"].eq("municipality").sum()) if record_count else 0
    )

    return {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourcePaths": source_paths,
        "addressPointsCsv": str(address_points_csv),
        "addressPointsCsvBytes": address_points_csv.stat().st_size
        if address_points_csv.exists()
        else 0,
        "recordCount": record_count,
        "propertyCoordinateCount": property_coordinate_count,
        "propertyCoordinateRate": property_coordinate_count / record_count if record_count else 0.0,
        "propertyDistrictCount": district_count,
        "propertyDistrictRate": district_count / record_count if record_count else 0.0,
        "addressPointCount": int(len(address_points_df)),
        "matchedRowCount": matched_count,
        "matchRate": matched_count / record_count if record_count else 0.0,
        "townMatchedRowCount": town_matched_count,
        "townMatchRate": town_matched_count / record_count if record_count else 0.0,
        "districtPrefixMatchedRowCount": district_prefix_matched_count,
        "districtPrefixMatchRate": district_prefix_matched_count / record_count
        if record_count
        else 0.0,
        "municipalityMatchedRowCount": municipality_matched_count,
        "municipalityMatchRate": municipality_matched_count / record_count
        if record_count
        else 0.0,
        "matchLevelCounts": _value_counts(matched, "coordinate_match_level"),
    }


def match_address_points(property_df, address_points_df):
    import pandas as pd

    result = property_df.copy()
    result["coordinate_match_level"] = "none"
    if result.empty or address_points_df.empty:
        return result

    address = address_points_df.dropna(subset=["prefecture", "municipality", "lat", "lon"]).copy()
    if address.empty:
        return result

    if "district_name" in result.columns:
        town_points = address.dropna(subset=["district_name"]).drop_duplicates(
            ["prefecture", "municipality", "district_name"]
        ).rename(
            columns={"lat": "_town_lat", "lon": "_town_lon"}
        )
        town = result.merge(
            town_points[
                ["prefecture", "municipality", "district_name", "_town_lat", "_town_lon"]
            ],
            how="left",
            on=["prefecture", "municipality", "district_name"],
        )
        town_match = town["_town_lat"].notna() & town["_town_lon"].notna()
        result.loc[town_match, "coordinate_match_level"] = "town"

        prefix_points = _build_district_prefix_points(result, address)
        if not prefix_points.empty:
            prefix = result.merge(
                prefix_points,
                how="left",
                on=["prefecture", "municipality", "district_name"],
            )
            prefix_match = (
                result["coordinate_match_level"].eq("none")
                & prefix["_district_prefix_lat"].notna()
                & prefix["_district_prefix_lon"].notna()
            )
            result.loc[prefix_match, "coordinate_match_level"] = "district_prefix"

    municipality_points = (
        address.groupby(["prefecture", "municipality"], dropna=False)[["lat", "lon"]]
        .mean()
        .reset_index()
        .rename(columns={"lat": "_municipality_lat", "lon": "_municipality_lon"})
    )
    municipality = result.merge(
        municipality_points,
        how="left",
        on=["prefecture", "municipality"],
    )
    municipality_match = (
        result["coordinate_match_level"].eq("none")
        & municipality["_municipality_lat"].notna()
        & municipality["_municipality_lon"].notna()
    )
    result.loc[municipality_match, "coordinate_match_level"] = "municipality"
    return result


def _build_district_prefix_points(property_df, address_points_df):
    import pandas as pd

    keys = (
        property_df[["prefecture", "municipality", "district_name"]]
        .dropna()
        .drop_duplicates()
    )
    rows = []
    for key in keys.itertuples(index=False):
        district_name = str(key.district_name).strip()
        if not district_name:
            continue
        scoped = address_points_df[
            (address_points_df["prefecture"] == key.prefecture)
            & (address_points_df["municipality"] == key.municipality)
            & (address_points_df["district_name"].astype(str).str.startswith(district_name))
        ]
        if scoped.empty:
            continue
        rows.append(
            {
                "prefecture": key.prefecture,
                "municipality": key.municipality,
                "district_name": district_name,
                "_district_prefix_lat": float(scoped["lat"].mean()),
                "_district_prefix_lon": float(scoped["lon"].mean()),
            }
        )
    return pd.DataFrame(rows)


def save_report(report: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "address_coordinate_coverage.json"
    markdown_path = output_dir / "address_coordinate_coverage.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 取引座標付与カバレッジ",
        "",
        f"* generatedAt: {report['generatedAt']}",
        f"* addressPointsCsv: `{report['addressPointsCsv']}`",
        f"* addressPointsCsvBytes: {report['addressPointsCsvBytes']:,}",
        f"* propertyRecords: {report['recordCount']:,}",
        f"* propertyCoordinateRows: {report['propertyCoordinateCount']:,}",
        f"* propertyCoordinateRate: {report['propertyCoordinateRate']:.2%}",
        f"* propertyDistrictRows: {report['propertyDistrictCount']:,}",
        f"* propertyDistrictRate: {report['propertyDistrictRate']:.2%}",
        f"* addressPointRows: {report['addressPointCount']:,}",
        f"* matchedRows: {report['matchedRowCount']:,}",
        f"* matchRate: {report['matchRate']:.2%}",
        f"* townMatchedRows: {report['townMatchedRowCount']:,}",
        f"* townMatchRate: {report['townMatchRate']:.2%}",
        f"* districtPrefixMatchedRows: {report['districtPrefixMatchedRowCount']:,}",
        f"* districtPrefixMatchRate: {report['districtPrefixMatchRate']:.2%}",
        f"* municipalityMatchedRows: {report['municipalityMatchedRowCount']:,}",
        f"* municipalityMatchRate: {report['municipalityMatchRate']:.2%}",
        "",
        "## coordinate_match_level",
        "",
        _counts_table(report["matchLevelCounts"]),
        "",
    ]
    return "\n".join(lines)


def load_address_points_csv(path: Path):
    import pandas as pd

    if not path.exists():
        return pd.DataFrame()
    points = pd.read_csv(path)
    for column in ["lat", "lon"]:
        if column in points.columns:
            points[column] = pd.to_numeric(points[column], errors="coerce")
    return points


def _counts_table(counts: dict[str, int]) -> str:
    lines = [
        "| value | count |",
        "| --- | ---: |",
    ]
    for value, count in counts.items():
        lines.append(f"| {value} | {count:,} |")
    return "\n".join(lines)


def _value_counts(df, column: str) -> dict[str, int]:
    values = Counter(str(value) for value in df[column].fillna("none"))
    return dict(sorted(values.items(), key=lambda item: (-item[1], item[0])))


def _coordinate_count(df) -> int:
    if df.empty or not {"lat", "lon"}.issubset(df.columns):
        return 0
    return int((df["lat"].notna() & df["lon"].notna()).sum())


def _district_count(df) -> int:
    if df.empty or "district_name" not in df.columns:
        return 0
    return int(df["district_name"].fillna("").astype(str).str.strip().ne("").sum())


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
    parser = argparse.ArgumentParser(description="Summarize address coordinate match coverage.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--address-points-csv",
        type=Path,
        default=Path("data/processed/address_points/town_points.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/reports"))
    args = parser.parse_args()

    property_df, source_paths = _load_property_frames(args.regions, args.processed_dir)
    address_points = load_address_points_csv(args.address_points_csv)
    report = build_address_coordinate_coverage_report(
        property_df=property_df,
        address_points_df=address_points,
        source_paths=source_paths,
        address_points_csv=args.address_points_csv,
    )
    paths = save_report(report, args.output_dir)
    print(f"address coordinate coverage report: {paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
