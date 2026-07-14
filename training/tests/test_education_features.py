from __future__ import annotations

import pandas as pd
import pytest

from features.education_facilities import (
    MISSING_DISTANCE_KM,
    add_education_features,
)


def test_add_education_features_calculates_distances_and_counts() -> None:
    properties = pd.DataFrame(
        [
            {
                "lat": 35.0,
                "lon": 139.0,
            }
        ]
    )
    facilities = pd.DataFrame(
        [
            {
                "facility_type": "小学校",
                "facility_name": "第一小学校",
                "lat": 35.001,
                "lon": 139.0,
            },
            {
                "facility_type": "中学校",
                "facility_name": "第一中学校",
                "lat": 35.01,
                "lon": 139.0,
            },
            {
                "facility_type": "保育園",
                "facility_name": "第一保育園",
                "lat": 35.002,
                "lon": 139.0,
            },
            {
                "facility_type": "幼稚園",
                "facility_name": "第一幼稚園",
                "lat": 35.003,
                "lon": 139.0,
            },
        ]
    )

    actual = add_education_features(properties, facilities)

    assert actual.loc[0, "nearest_elementary_school_distance_km"] == pytest.approx(
        0.111,
        abs=0.01,
    )
    assert actual.loc[0, "nearest_junior_high_school_distance_km"] == pytest.approx(
        1.11,
        abs=0.02,
    )
    assert actual.loc[0, "nursery_count_within_500m"] == 1.0
    assert actual.loc[0, "nursery_count_within_1km"] == 1.0
    assert actual.loc[0, "kindergarten_count_within_1km"] == 1.0
    assert actual.loc[0, "has_education_data"] == 1.0


def test_add_education_features_uses_missing_values_without_coordinates() -> None:
    actual = add_education_features(
        pd.DataFrame([{"station": "東京"}]),
        pd.DataFrame(
            [
                {
                    "facility_type": "小学校",
                    "lat": 35.0,
                    "lon": 139.0,
                }
            ]
        ),
    )

    assert actual.loc[0, "nearest_elementary_school_distance_km"] == MISSING_DISTANCE_KM
    assert actual.loc[0, "nearest_junior_high_school_distance_km"] == MISSING_DISTANCE_KM
    assert actual.loc[0, "has_education_data"] == 0.0
