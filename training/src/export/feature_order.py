from __future__ import annotations

import argparse
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
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate featureOrder for browser inference.")
    parser.add_argument("--metadata", type=Path, nargs="*", default=[])
    parser.add_argument("--config", type=Path, nargs="*", default=[])
    args = parser.parse_args()

    errors = []
    for path in args.metadata:
        errors.extend(validate_metadata_feature_order(path))
    for path in args.config:
        errors.extend(validate_config_features(path))

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("feature order is compatible with frontend inference")
    return 0


def validate_metadata_feature_order(path: Path) -> list[str]:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    return validate_feature_names(path, metadata.get("featureOrder", []))


def validate_config_features(path: Path) -> list[str]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_feature_names(path, config.get("features", []))


def validate_feature_names(path: Path, features: list[str]) -> list[str]:
    unsupported = [feature for feature in features if feature not in FRONTEND_SUPPORTED_FEATURES]
    if not unsupported:
        return []
    unsupported_list = ", ".join(unsupported)
    return [f"{path}: unsupported frontend feature(s): {unsupported_list}"]


if __name__ == "__main__":
    raise SystemExit(main())
