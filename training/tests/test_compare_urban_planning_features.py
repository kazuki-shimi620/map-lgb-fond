from __future__ import annotations

from evaluate.compare_urban_planning_features import (
    UrbanPlanningCandidate,
    feature_lists,
    render_markdown,
)
from features.urban_planning import (
    URBAN_PLANNING_CATEGORICAL_FEATURES,
    URBAN_PLANNING_FEATURES,
)


def test_feature_lists_can_add_urban_planning_features() -> None:
    candidate = UrbanPlanningCandidate("urban_planning", URBAN_PLANNING_FEATURES)

    features, categorical_features = feature_lists(candidate)

    assert "zoning_type" in features
    assert "floor_area_ratio" in features
    for feature in URBAN_PLANNING_CATEGORICAL_FEATURES:
        assert feature in categorical_features


def test_feature_lists_can_remove_station() -> None:
    candidate = UrbanPlanningCandidate(
        "urban_planning_no_station",
        URBAN_PLANNING_FEATURES,
        include_station=False,
    )

    features, categorical_features = feature_lists(candidate)

    assert "station" not in features
    assert "station" not in categorical_features
    assert "zoning_type" in features


def test_render_markdown_includes_metrics_and_match_count() -> None:
    markdown = render_markdown(
        {
            "regions": ["tokyo"],
            "trainStartYear": 2015,
            "testYears": [2025],
            "rowCount": 10,
            "urbanPlanningAreaCount": 3,
            "matchedRowCount": 8,
            "candidates": [
                {
                    "name": "urban_planning",
                    "includeStation": True,
                    "urbanPlanningFeatures": ["zoning_type"],
                    "metrics": {"mae": 1000.0, "rmse": 1200.0, "mape": 10.0},
                    "deploymentArtifacts": {
                        "onnxBytes": 1024,
                        "onnxGzipBytes": 512,
                        "categoriesGzipBytes": 128,
                    },
                    "trainingSeconds": 1.2,
                    "featureImportance": [{"feature": "zoning_type", "importance": 3.0}],
                }
            ],
        }
    )

    assert "用途地域マッチ件数: 8" in markdown
    assert "| urban_planning | yes | zoning_type | 1,000 | 1,200 | 10.00%" in markdown
    assert "- urban_planning: zoning_type=3" in markdown
