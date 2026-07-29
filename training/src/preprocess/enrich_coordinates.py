from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluate.address_coordinate_coverage import load_address_points_csv  # noqa: E402


def enrich_property_coordinates(
    property_df,
    address_points_df,
    *,
    include_municipality_fallback: bool = False,
):
    result = property_df.copy()
    result["coordinate_source"] = "none"
    if "lat" not in result.columns:
        result["lat"] = None
    if "lon" not in result.columns:
        result["lon"] = None
    if address_points_df.empty:
        return result

    address = address_points_df.dropna(subset=["prefecture", "municipality", "lat", "lon"]).copy()
    if address.empty:
        return result

    existing_coordinates = result["lat"].notna() & result["lon"].notna()
    result.loc[existing_coordinates, "coordinate_source"] = "input"

    if "district_name" in result.columns:
        town_points = address.dropna(subset=["district_name"]).drop_duplicates(
            ["prefecture", "municipality", "district_name"]
        )
        result = _apply_coordinate_match(
            result,
            town_points[["prefecture", "municipality", "district_name", "lat", "lon"]],
            on=["prefecture", "municipality", "district_name"],
            source="town",
        )

        prefix_points = build_district_prefix_points(result, address)
        if not prefix_points.empty:
            result = _apply_coordinate_match(
                result,
                prefix_points,
                on=["prefecture", "municipality", "district_name"],
                source="district_prefix",
            )

    if include_municipality_fallback:
        municipality_points = (
            address.groupby(["prefecture", "municipality"], dropna=False)[["lat", "lon"]]
            .mean()
            .reset_index()
        )
        result = _apply_coordinate_match(
            result,
            municipality_points,
            on=["prefecture", "municipality"],
            source="municipality",
        )

    return result


def build_district_prefix_points(property_df, address_points_df):
    import pandas as pd

    if "district_name" not in property_df.columns:
        return pd.DataFrame()
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
                "lat": float(scoped["lat"].mean()),
                "lon": float(scoped["lon"].mean()),
            }
        )
    return pd.DataFrame(rows)


def enrich_regions(
    *,
    regions: list[str],
    processed_dir: Path,
    output_dir: Path,
    address_points_csv: Path,
    include_municipality_fallback: bool = False,
) -> dict:
    import pandas as pd

    address_points = load_address_points_csv(address_points_csv)
    output_dir.mkdir(parents=True, exist_ok=True)
    region_summaries = {}
    for region in regions:
        source_path = processed_dir / f"{region}.parquet"
        output_path = output_dir / f"{region}.parquet"
        df = pd.read_parquet(source_path)
        enriched = enrich_property_coordinates(
            df,
            address_points,
            include_municipality_fallback=include_municipality_fallback,
        )
        enriched.to_parquet(output_path, index=False)
        region_summaries[region] = {
            "sourcePath": str(source_path),
            "outputPath": str(output_path),
            "recordCount": int(len(enriched)),
            "coordinateCount": int((enriched["lat"].notna() & enriched["lon"].notna()).sum()),
            "coordinateSourceCounts": {
                str(key): int(value)
                for key, value in enriched["coordinate_source"].value_counts().to_dict().items()
            },
        }

    metadata = {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "addressPointsCsv": str(address_points_csv),
        "includeMunicipalityFallback": include_municipality_fallback,
        "regions": region_summaries,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def _apply_coordinate_match(result, points, *, on: list[str], source: str):
    match = result.merge(
        points.rename(columns={"lat": "_match_lat", "lon": "_match_lon"}),
        how="left",
        on=on,
    )
    needs_coordinate = result["lat"].isna() | result["lon"].isna()
    matched = needs_coordinate & match["_match_lat"].notna() & match["_match_lon"].notna()
    result.loc[matched, "lat"] = match.loc[matched, "_match_lat"].to_numpy()
    result.loc[matched, "lon"] = match.loc[matched, "_match_lon"].to_numpy()
    result.loc[matched, "coordinate_source"] = source
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attach representative coordinates to property data."
    )
    parser.add_argument("--regions", nargs="+", default=["tokyo", "kanagawa", "saitama", "chiba"])
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/with_address_coordinates"),
    )
    parser.add_argument(
        "--address-points-csv",
        type=Path,
        default=Path("data/processed/address_points/town_points.csv"),
    )
    parser.add_argument("--include-municipality-fallback", action="store_true")
    args = parser.parse_args()

    metadata = enrich_regions(
        regions=args.regions,
        processed_dir=args.processed_dir,
        output_dir=args.output_dir,
        address_points_csv=args.address_points_csv,
        include_municipality_fallback=args.include_municipality_fallback,
    )
    total = sum(region["coordinateCount"] for region in metadata["regions"].values())
    print(f"enriched coordinates: rows={total} output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
