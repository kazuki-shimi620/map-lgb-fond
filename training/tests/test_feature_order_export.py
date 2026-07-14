from __future__ import annotations

import json

from export.feature_order import validate_config_features, validate_metadata_feature_order


def test_validate_metadata_feature_order_accepts_frontend_supported_features(tmp_path) -> None:
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "featureOrder": [
                    "area",
                    "station_distance",
                    "station_passenger_log",
                    "has_station_passenger_data",
                    "station_rank",
                ]
            }
        ),
        encoding="utf-8",
    )

    assert validate_metadata_feature_order(metadata_path) == []


def test_validate_metadata_feature_order_accepts_explicit_defaulted_feature(tmp_path) -> None:
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "featureOrder": ["area", "experimental_feature"],
                "featureDefaults": {"experimental_feature": 0.0},
            }
        ),
        encoding="utf-8",
    )

    assert validate_metadata_feature_order(metadata_path) == []


def test_validate_metadata_feature_order_rejects_non_numeric_default(tmp_path) -> None:
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "featureOrder": ["area", "experimental_feature"],
                "featureDefaults": {"experimental_feature": "0"},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_metadata_feature_order(metadata_path)

    assert len(errors) == 1
    assert "featureDefaults.experimental_feature" in errors[0]


def test_validate_metadata_feature_order_rejects_unused_default(tmp_path) -> None:
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "featureOrder": ["area"],
                "featureDefaults": {"unused_feature": 0.0},
            }
        ),
        encoding="utf-8",
    )

    errors = validate_metadata_feature_order(metadata_path)

    assert len(errors) == 1
    assert "featureDefaults.unused_feature is not in featureOrder" in errors[0]


def test_validate_config_features_reports_unsupported_features(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "features:",
                "  - area",
                "  - hazard_overall_score",
            ]
        ),
        encoding="utf-8",
    )

    errors = validate_config_features(config_path)

    assert len(errors) == 1
    assert "hazard_overall_score" in errors[0]
