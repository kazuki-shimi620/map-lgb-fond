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


def enrich_commercial_facility_coordinates(commercial_df, address_points_df):
    result = commercial_df.copy()
    if "lat" not in result.columns:
        result["lat"] = None
    if "lon" not in result.columns:
        result["lon"] = None
    result["coordinate_source"] = "none"
    if address_points_df.empty or result.empty:
        return result

    address_points = address_points_df.dropna(
        subset=["prefecture", "municipality", "district_name", "lat", "lon"]
    ).copy()
    if address_points.empty:
        return result

    address_index = _build_address_index(address_points)
    for index, row in result.iterrows():
        if _has_coordinates(row):
            result.at[index, "coordinate_source"] = "input"
            continue
        match = _match_address_point(row, address_index)
        if match is None:
            continue
        result.at[index, "lat"] = match["lat"]
        result.at[index, "lon"] = match["lon"]
        result.at[index, "coordinate_source"] = "address_point"
    return result


def _build_address_index(address_points_df) -> dict[tuple[str, str], list[dict[str, object]]]:
    records: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in address_points_df.to_dict(orient="records"):
        key = (str(row["prefecture"]).strip(), str(row["municipality"]).strip())
        records.setdefault(key, []).append(row)
    for rows in records.values():
        rows.sort(key=lambda item: len(str(item["district_name"])), reverse=True)
    return records


def _match_address_point(row, address_index) -> dict[str, object] | None:
    prefecture = _text(row.get("prefecture"))
    municipality = _text(row.get("city") or row.get("municipality"))
    address = _text(row.get("address_raw") or row.get("address"))
    if not prefecture or not municipality or not address:
        return None
    candidates = address_index.get((prefecture, municipality), [])
    if not candidates:
        return None
    address_tail = address.replace(prefecture, "", 1).replace(municipality, "", 1)
    for candidate in candidates:
        district = _text(candidate.get("district_name"))
        if district and (address_tail.startswith(district) or district in address_tail):
            return candidate
    return None


def _has_coordinates(row) -> bool:
    try:
        lat = float(row.get("lat"))
        lon = float(row.get("lon"))
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def enrich_file(
    *,
    input_csv: Path,
    address_points_csv: Path,
    output_csv: Path,
) -> dict[str, object]:
    import pandas as pd

    commercial = pd.read_csv(input_csv)
    address_points = load_address_points_csv(address_points_csv)
    enriched = enrich_commercial_facility_coordinates(commercial, address_points)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(output_csv, index=False)
    coordinate_count = int((enriched["lat"].notna() & enriched["lon"].notna()).sum())
    metadata = {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "inputCsv": str(input_csv),
        "addressPointsCsv": str(address_points_csv),
        "outputCsv": str(output_csv),
        "recordCount": int(len(enriched)),
        "coordinateCount": coordinate_count,
        "coordinateRate": coordinate_count / len(enriched) if len(enriched) else 0.0,
        "coordinateSourceCounts": {
            str(key): int(value)
            for key, value in enriched["coordinate_source"].value_counts().to_dict().items()
        },
    }
    metadata_path = output_csv.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attach representative address-point coordinates to JCSC commercial facilities."
    )
    parser.add_argument("--input-csv", type=Path, default=Path("data/processed/jcsc/jcsc_sc_open.csv"))
    parser.add_argument(
        "--address-points-csv",
        type=Path,
        default=Path("data/processed/address_points/town_points.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/processed/jcsc/jcsc_sc_open_with_coordinates.csv"),
    )
    args = parser.parse_args()

    metadata = enrich_file(
        input_csv=args.input_csv,
        address_points_csv=args.address_points_csv,
        output_csv=args.output_csv,
    )
    print(
        "enriched commercial facilities: "
        f"coordinates={metadata['coordinateCount']}/{metadata['recordCount']} "
        f"output={args.output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
