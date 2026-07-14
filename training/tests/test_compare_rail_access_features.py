from __future__ import annotations

from evaluate.compare_rail_access_features import (
    RAIL_ACCESS_FEATURES,
    RailAccessCandidate,
    feature_lists,
    render_markdown,
)


def test_feature_lists_adds_rail_access_categories_and_can_remove_station() -> None:
    candidate = RailAccessCandidate(
        "rail_access_no_station",
        RAIL_ACCESS_FEATURES,
        include_station=False,
    )

    features, categorical_features = feature_lists(candidate)

    assert "station" not in features
    assert "station" not in categorical_features
    assert "nearest_station_time_to_tokyo" in features
    assert "closest_major_terminal" in features
    assert "closest_major_terminal" in categorical_features


def test_render_markdown_includes_rail_access_counts() -> None:
    report = {
        "regions": ["tokyo"],
        "trainStartYear": 2015,
        "testYears": [2025],
        "rowCount": 10,
        "railAccessCount": 3,
        "matchedRowCount": 8,
        "candidates": [
            {
                "name": "rail_access",
                "includeStation": True,
                "railAccessFeatures": ["nearest_station_time_to_tokyo"],
                "trainingSeconds": 1.25,
                "metrics": {"mae": 1.0, "rmse": 2.0, "mape": 3.0},
                "deploymentArtifacts": {
                    "onnxBytes": 1024 * 1024,
                    "onnxGzipBytes": 512 * 1024,
                    "categoriesGzipBytes": 1024,
                },
                "featureImportance": [
                    {"feature": "nearest_station_time_to_tokyo", "importance": 10.0}
                ],
            }
        ],
    }

    markdown = render_markdown(report)

    assert "路線利便性駅数: 3" in markdown
    assert "路線利便性特徴量マッチ件数: 8" in markdown
    assert "1.00 MB" in markdown
