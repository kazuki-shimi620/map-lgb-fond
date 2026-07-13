from __future__ import annotations

from evaluate.compare_population_features import (
    POPULATION_FEATURES,
    PopulationCandidate,
    feature_lists,
    render_markdown,
)


def test_feature_lists_can_add_population_features_and_remove_station() -> None:
    candidate = PopulationCandidate(
        "population_no_station",
        POPULATION_FEATURES,
        include_station=False,
    )

    features, categorical_features = feature_lists(candidate)

    assert "station" not in features
    assert "station" not in categorical_features
    assert "municipality_population" in features
    assert "population_change_5y_rate" in features


def test_render_markdown_includes_population_counts() -> None:
    report = {
        "regions": ["tokyo"],
        "trainStartYear": 2015,
        "testYears": [2025],
        "rowCount": 10,
        "populationStatsCount": 3,
        "matchedRowCount": 8,
        "candidates": [
            {
                "name": "population",
                "includeStation": True,
                "populationFeatures": ["municipality_population"],
                "trainingSeconds": 1.25,
                "metrics": {"mae": 1.0, "rmse": 2.0, "mape": 3.0},
                "deploymentArtifacts": {
                    "onnxBytes": 1024 * 1024,
                    "onnxGzipBytes": 512 * 1024,
                    "categoriesGzipBytes": 1024,
                },
                "featureImportance": [
                    {"feature": "municipality_population", "importance": 10.0}
                ],
            }
        ],
    }

    markdown = render_markdown(report)

    assert "人口統計件数: 3" in markdown
    assert "人口統計特徴量マッチ件数: 8" in markdown
    assert "1.00 MB" in markdown
