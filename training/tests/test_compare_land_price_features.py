from __future__ import annotations

from evaluate.compare_land_price_features import (
    LAND_PRICE_FEATURES,
    LandPriceCandidate,
    feature_lists,
    render_markdown,
)


def test_feature_lists_can_add_land_price_features_and_remove_station() -> None:
    candidate = LandPriceCandidate(
        "land_price_no_station",
        LAND_PRICE_FEATURES,
        include_station=False,
    )

    features, categorical_features = feature_lists(candidate)

    assert "station" not in features
    assert "station" not in categorical_features
    assert "land_price_city_avg_yen_per_sqm" in features
    assert "nearest_land_price_distance_km" in features


def test_render_markdown_includes_land_price_counts() -> None:
    report = {
        "regions": ["tokyo"],
        "trainStartYear": 2015,
        "testYears": [2025],
        "rowCount": 10,
        "landPricePointCount": 3,
        "landPriceCitySummaryCount": 2,
        "matchedRowCount": 8,
        "candidates": [
            {
                "name": "land_price",
                "includeStation": True,
                "landPriceFeatures": ["land_price_city_avg_yen_per_sqm"],
                "trainingSeconds": 1.25,
                "metrics": {"mae": 1.0, "rmse": 2.0, "mape": 3.0},
                "deploymentArtifacts": {
                    "onnxBytes": 1024 * 1024,
                    "onnxGzipBytes": 512 * 1024,
                    "categoriesGzipBytes": 1024,
                },
                "featureImportance": [
                    {"feature": "land_price_city_avg_yen_per_sqm", "importance": 10.0}
                ],
            }
        ],
    }

    markdown = render_markdown(report)

    assert "地価ポイント件数: 3" in markdown
    assert "地価特徴量マッチ件数: 8" in markdown
    assert "1.00 MB" in markdown
