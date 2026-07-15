from __future__ import annotations

from evaluate.compare_location_features import (
    LocationFeatureCandidate,
    feature_lists,
    render_markdown,
)
from features.land_prices import LAND_PRICE_FEATURES
from features.urban_planning import (
    URBAN_PLANNING_CATEGORICAL_FEATURES,
    URBAN_PLANNING_FEATURES,
)


def test_feature_lists_can_add_land_price_and_urban_planning_features() -> None:
    candidate = LocationFeatureCandidate(
        "land_price_urban_planning",
        land_price_features=LAND_PRICE_FEATURES,
        urban_planning_features=URBAN_PLANNING_FEATURES,
    )

    features, categorical_features = feature_lists(candidate)

    assert "land_price_city_avg_yen_per_sqm" in features
    assert "nearest_land_price_distance_km" in features
    assert "zoning_type" in features
    assert "floor_area_ratio" in features
    for feature in URBAN_PLANNING_CATEGORICAL_FEATURES:
        assert feature in categorical_features


def test_feature_lists_can_remove_station() -> None:
    candidate = LocationFeatureCandidate(
        "land_price_urban_planning_no_station",
        land_price_features=LAND_PRICE_FEATURES,
        urban_planning_features=URBAN_PLANNING_FEATURES,
        include_station=False,
    )

    features, categorical_features = feature_lists(candidate)

    assert "station" not in features
    assert "station" not in categorical_features
    assert "nearest_land_price_yen_per_sqm" in features
    assert "zoning_type" in features


def test_render_markdown_includes_match_counts_and_metrics() -> None:
    markdown = render_markdown(
        {
            "regions": ["tokyo"],
            "trainStartYear": 2015,
            "testYears": [2025],
            "rowCount": 10,
            "landPricePointCount": 3,
            "landPriceCitySummaryCount": 2,
            "landPriceMatchedRowCount": 8,
            "urbanPlanningAreaCount": 4,
            "urbanPlanningMatchedRowCount": 9,
            "candidates": [
                {
                    "name": "land_price_urban_planning",
                    "includeStation": True,
                    "landPriceFeatures": ["nearest_land_price_yen_per_sqm"],
                    "urbanPlanningFeatures": ["zoning_type"],
                    "metrics": {"mae": 1000.0, "rmse": 1200.0, "mape": 10.0},
                    "deploymentArtifacts": {
                        "onnxBytes": 1024,
                        "onnxGzipBytes": 512,
                        "categoriesGzipBytes": 128,
                    },
                    "trainingSeconds": 1.2,
                    "featureImportance": [
                        {"feature": "nearest_land_price_yen_per_sqm", "importance": 3.0}
                    ],
                }
            ],
        }
    )

    assert "地価特徴量マッチ件数: 8" in markdown
    assert "用途地域マッチ件数: 9" in markdown
    assert (
        "| land_price_urban_planning | yes | nearest_land_price_yen_per_sqm | "
        "zoning_type | 1,000 | 1,200 | 10.00%"
    ) in markdown
    assert "- land_price_urban_planning: nearest_land_price_yen_per_sqm=3" in markdown
