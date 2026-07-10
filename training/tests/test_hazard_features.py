from __future__ import annotations

import pandas as pd

from features.hazards import (
    add_hazard_features,
    calculate_overall_hazard_score,
    landslide_zone_to_features,
    parse_depth_range,
)


def test_parse_depth_range_handles_common_labels() -> None:
    assert parse_depth_range("0.5m未満") == (0.0, 0.5, 1)
    assert parse_depth_range("0.5m以上3.0m未満") == (0.5, 3.0, 3)
    assert parse_depth_range("5.0m以上") == (5.0, None, 5)
    assert parse_depth_range("区域外") == (None, None, None)


def test_landslide_zone_to_features_scores_special_warning() -> None:
    assert landslide_zone_to_features("区域外") == (0, 100.0, 0.0)
    assert landslide_zone_to_features("土砂災害警戒区域") == (4, 30.0, 0.0)
    assert landslide_zone_to_features("土砂災害特別警戒区域") == (5, 0.0, 1.0)
    assert landslide_zone_to_features("データなし") == (None, None, 0.0)


def test_calculate_overall_hazard_score_weights_lowest_score() -> None:
    score = calculate_overall_hazard_score(
        {
            "flood": 55.0,
            "landslide": 100.0,
            "tsunami": None,
            "storm_surge": 75.0,
        }
    )

    assert round(score or 0.0, 2) == 63.25


def test_add_hazard_features_pivots_long_records_by_municipality_and_year() -> None:
    properties = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "transaction_year": 2024,
            },
            {
                "prefecture": "東京都",
                "municipality": "港区",
                "transaction_year": 2024,
            },
        ]
    )
    hazards = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "feature_year": 2024,
                "hazard_type": "flood",
                "risk_level": 3,
                "depth_max": 2.0,
                "source_available": True,
            },
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "feature_year": 2024,
                "hazard_type": "landslide",
                "zone_type": "区域外",
                "source_available": True,
            },
        ]
    )

    actual = add_hazard_features(properties, hazards)

    assert actual.loc[0, "hazard_flood_risk_level"] == 3
    assert actual.loc[0, "hazard_flood_depth_max"] == 2.0
    assert actual.loc[0, "hazard_landslide_risk_level"] == 0
    assert actual.loc[0, "hazard_available_count"] == 2
    assert actual.loc[1, "hazard_available_count"] == 0


def test_add_hazard_features_can_join_by_coordinates() -> None:
    properties = pd.DataFrame(
        [
            {
                "lat": 35.681236,
                "lon": 139.767125,
                "transaction_year": 2024,
            }
        ]
    )
    hazards = pd.DataFrame(
        [
            {
                "latitude": 35.6812361,
                "longitude": 139.7671251,
                "feature_year": 2024,
                "hazard_overall_score": 55.0,
                "hazard_available_count": 1,
                "hazard_flood_risk_level": 3,
            }
        ]
    )

    actual = add_hazard_features(properties, hazards)

    assert actual.loc[0, "hazard_overall_score"] == 55.0
    assert actual.loc[0, "hazard_flood_risk_level"] == 3
