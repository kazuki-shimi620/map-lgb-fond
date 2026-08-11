from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluate.metrics import calculate_metrics  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from features.nearby_pois import add_nearby_poi_features, feature_names  # noqa: E402
from train.model import train_model  # noqa: E402

BASE_FEATURES = [
    "area", "age", "station_distance", "prefecture", "municipality", "station",
    "room_layout", "building_type", "transaction_year",
]
CATEGORICAL_FEATURES = [
    "prefecture", "municipality", "station", "room_layout", "building_type",
]
PARK_FEATURES = feature_names("large_park")


def load_large_parks(path: Path, minimum_area_sqm: float):
    import pandas as pd

    with path.open(encoding="utf-8", newline="") as file:
        rows = [
            row for row in csv.DictReader(file)
            if row.get("area_source") == "geometry"
            and float(row.get("area_sqm") or 0) >= minimum_area_sqm
        ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=["category_id", "lat", "lon"])
    frame["category_id"] = "large_park"
    frame["lat"] = pd.to_numeric(frame["lat"], errors="coerce")
    frame["lon"] = pd.to_numeric(frame["lon"], errors="coerce")
    return frame[["category_id", "lat", "lon"]].dropna()


def filter_inner_bbox(data, bbox: tuple[float, float, float, float], buffer_km: float):
    south, west, north, east = bbox
    latitude_delta = buffer_km / 111.32
    longitude_delta = buffer_km / (111.32 * math.cos(math.radians((south + north) / 2)))
    return data[
        data["lat"].between(south + latitude_delta, north - latitude_delta)
        & data["lon"].between(west + longitude_delta, east - longitude_delta)
    ].copy()


def compare(*, properties_path: Path, park_areas_path: Path, bbox, minimum_area_sqm: float,
            buffer_km: float, train_start_year: int, test_years: list[int]) -> dict[str, object]:
    import pandas as pd

    data = pd.read_parquet(properties_path)
    data = data[data["transaction_year"] >= train_start_year].copy()
    data = filter_inner_bbox(data, bbox, buffer_km)
    parks = load_large_parks(park_areas_path, minimum_area_sqm)
    data = add_nearby_poi_features(data, parks, categories=("large_park",))
    encoding = build_and_apply_category_dictionary(data, CATEGORICAL_FEATURES)
    encoded = encoding.dataframe
    candidates = {"baseline": BASE_FEATURES, "large_park": BASE_FEATURES + PARK_FEATURES}
    results = []
    for name, features in candidates.items():
        folds = []
        for year in test_years:
            train_mask = encoded["transaction_year"] < year
            test_mask = encoded["transaction_year"] == year
            model = train_model(
                encoded.loc[train_mask, features], encoded.loc[train_mask, "price"],
                CATEGORICAL_FEATURES,
                {"n_estimators": 180, "learning_rate": 0.075, "num_leaves": 31,
                 "max_depth": 7, "min_child_samples": 80, "random_state": 42, "n_jobs": -1},
            )
            predictions = model.predict(encoded.loc[test_mask, features])
            folds.append({"testYear": year, "testCount": int(test_mask.sum()),
                          "metrics": calculate_metrics(encoded.loc[test_mask, "price"], predictions)})
        total = sum(fold["testCount"] for fold in folds)
        metrics = {
            "mae": sum(f["metrics"]["mae"] * f["testCount"] for f in folds) / total,
            "mape": sum(f["metrics"]["mape"] * f["testCount"] for f in folds) / total,
            "rmse": (sum(f["metrics"]["rmse"] ** 2 * f["testCount"] for f in folds) / total) ** 0.5,
        }
        results.append({"name": name, "features": features, "folds": folds, "metrics": metrics})
    baseline, candidate = results
    return {
        "propertiesPath": str(properties_path), "parkAreasPath": str(park_areas_path),
        "bbox": bbox, "bufferKm": buffer_km, "minimumAreaSqm": minimum_area_sqm,
        "rowCount": len(data), "uniqueCoordinateCount": len(data[["lat", "lon"]].drop_duplicates()),
        "parkCount": len(parks), "testYears": test_years, "candidates": results,
        "delta": {key: candidate["metrics"][key] - baseline["metrics"][key]
                  for key in ("mae", "rmse", "mape")},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest large park features with a cached sample.")
    parser.add_argument("--properties", type=Path, required=True)
    parser.add_argument("--park-areas", type=Path, required=True)
    parser.add_argument("--bbox", nargs=4, type=float, required=True)
    parser.add_argument("--minimum-area-sqm", type=float, default=20_000)
    parser.add_argument("--buffer-km", type=float, default=3.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(properties_path=args.properties, park_areas_path=args.park_areas,
                     bbox=tuple(args.bbox), minimum_area_sqm=args.minimum_area_sqm,
                     buffer_km=args.buffer_km, train_start_year=2015,
                     test_years=[2023, 2024, 2025])
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
