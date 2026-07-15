from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import yaml

FRONTEND_SUPPORTED_FEATURES = {
    "prefecture",
    "municipality",
    "station",
    "area",
    "age",
    "station_distance",
    "room_layout",
    "building_type",
    "transaction_year",
    "station_passenger_log",
    "station_line_count",
    "station_operator_count",
    "effective_station_scale",
    "has_station_passenger_data",
    "station_rank",
    "land_price_city_avg_yen_per_sqm",
    "land_price_city_yoy_rate",
    "land_price_points_city_count",
    "nearest_land_price_yen_per_sqm",
    "nearest_land_price_distance_km",
    "land_price_points_within_2km",
    "has_land_price_data",
    "is_commercial_zone",
    "is_residential_zone",
    "floor_area_ratio",
    "building_coverage_ratio",
    "has_zoning_data",
    "city_planning_area_type",
    "zoning_type",
    "location_optimization_area",
}

CATEGORY_DICTIONARY_KEYS = {
    "prefecture": "prefectures",
    "municipality": "municipalities",
    "station": "stations",
    "room_layout": "roomLayouts",
    "building_type": "buildingTypes",
    "station_rank": "station_rank",
    "city_planning_area_type": "city_planning_area_type",
    "zoning_type": "zoning_type",
    "location_optimization_area": "location_optimization_area",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate featureOrder for browser inference.")
    parser.add_argument("--metadata", type=Path, nargs="*", default=[])
    parser.add_argument("--config", type=Path, nargs="*", default=[])
    parser.add_argument("--contract", type=Path, nargs="*", default=[])
    args = parser.parse_args()

    errors = []
    for path in args.metadata:
        errors.extend(validate_metadata_feature_order(path))
    for path in args.config:
        errors.extend(validate_config_features(path))
    for metadata_path in args.contract:
        region = metadata_path.name.removesuffix("_latest_metadata.json")
        categories_path = metadata_path.with_name(f"{region}_latest_categories.json")
        model_path = metadata_path.parents[1] / "models" / f"{region}_latest.onnx"
        errors.extend(
            validate_frontend_artifact_contract(metadata_path, categories_path, model_path)
        )

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("feature order is compatible with frontend inference")
    return 0


def validate_metadata_feature_order(path: Path) -> list[str]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    feature_order = metadata.get("featureOrder", [])
    errors = validate_feature_names(
        path,
        feature_order,
        metadata.get("featureDefaults", {}),
    )
    errors.extend(
        validate_feature_defaults(path, metadata.get("featureDefaults", {}), feature_order)
    )
    return errors


def validate_config_features(path: Path) -> list[str]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_feature_names(path, config.get("features", []))


def validate_frontend_artifact_contract(
    metadata_path: Path,
    categories_path: Path,
    model_path: Path,
) -> list[str]:
    errors = []
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    categories = json.loads(categories_path.read_text(encoding="utf-8"))
    feature_order = metadata.get("featureOrder", [])
    feature_defaults = metadata.get("featureDefaults", {})

    errors.extend(validate_feature_names(metadata_path, feature_order, feature_defaults))
    errors.extend(validate_feature_defaults(metadata_path, feature_defaults, feature_order))
    errors.extend(validate_category_dictionary(categories_path, feature_order, categories))

    input_dimension = read_onnx_feature_dimension(model_path)
    if input_dimension != len(feature_order):
        errors.append(
            f"{model_path}: ONNX input dimension {input_dimension} does not match "
            f"featureOrder length {len(feature_order)}"
        )

    return errors


def validate_category_dictionary(
    path: Path,
    feature_order: list[str],
    categories: dict,
) -> list[str]:
    errors = []
    unknown_id = categories.get("unknownId")
    if not isinstance(unknown_id, int):
        errors.append(f"{path}: unknownId must be an integer")

    for feature_name in feature_order:
        dictionary_key = CATEGORY_DICTIONARY_KEYS.get(feature_name)
        if not dictionary_key:
            continue
        dictionary = categories.get(dictionary_key)
        if not isinstance(dictionary, dict):
            errors.append(f"{path}: missing category dictionary '{dictionary_key}'")

    return errors


def validate_feature_defaults(
    path: Path,
    feature_defaults: dict,
    feature_order: list[str] | None = None,
) -> list[str]:
    errors = []
    if not isinstance(feature_defaults, dict):
        return [f"{path}: featureDefaults must be an object"]
    feature_names = set(feature_order or [])
    for feature_name, value in feature_defaults.items():
        if not isinstance(feature_name, str):
            errors.append(f"{path}: featureDefaults keys must be strings")
        elif feature_order is not None and feature_name not in feature_names:
            errors.append(f"{path}: featureDefaults.{feature_name} is not in featureOrder")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{path}: featureDefaults.{feature_name} must be numeric")
    return errors


def read_onnx_feature_dimension(path: Path) -> int:
    onnx = importlib.import_module("onnx")
    model = onnx.load(path)
    if not model.graph.input:
        raise ValueError(f"{path}: ONNX model has no inputs")
    shape = model.graph.input[0].type.tensor_type.shape
    if len(shape.dim) < 2 or not shape.dim[1].dim_value:
        raise ValueError(f"{path}: ONNX model input feature dimension is not fixed")
    return shape.dim[1].dim_value


def validate_feature_names(
    path: Path,
    features: list[str],
    feature_defaults: dict | None = None,
) -> list[str]:
    defaulted_features = (
        set(feature_defaults.keys()) if isinstance(feature_defaults, dict) else set()
    )
    unsupported = [
        feature
        for feature in features
        if feature not in FRONTEND_SUPPORTED_FEATURES and feature not in defaulted_features
    ]
    if not unsupported:
        return []
    unsupported_list = ", ".join(unsupported)
    return [f"{path}: unsupported frontend feature(s): {unsupported_list}"]


if __name__ == "__main__":
    raise SystemExit(main())
