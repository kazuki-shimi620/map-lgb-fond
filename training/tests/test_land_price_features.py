from __future__ import annotations

import pandas as pd
import pytest

from features.land_prices import add_land_price_features, haversine_km


def test_add_land_price_features_uses_latest_city_summary_without_coordinates() -> None:
    properties = pd.DataFrame(
        [
            {"prefecture": "東京都", "municipality": "千代田区", "transaction_year": 2024},
            {"prefecture": "東京都", "municipality": "千代田区", "transaction_year": 2025},
            {"prefecture": "東京都", "municipality": "未整備区", "transaction_year": 2025},
        ]
    )
    city_summary = pd.DataFrame(
        [
            {
                "year": 2024,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "city_code": "13101",
                "use_category": "住宅地",
                "point_count": 1,
                "avg_price_yen_per_sqm": 1000.0,
                "avg_yoy_rate": 1.0,
            },
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "city_code": "13101",
                "use_category": "住宅地",
                "point_count": 3,
                "avg_price_yen_per_sqm": 1500.0,
                "avg_yoy_rate": 2.0,
            },
        ]
    )

    actual = add_land_price_features(properties, pd.DataFrame(), city_summary)

    assert actual.loc[0, "land_price_city_avg_yen_per_sqm"] == pytest.approx(1000.0)
    assert actual.loc[1, "land_price_city_avg_yen_per_sqm"] == pytest.approx(1500.0)
    assert actual.loc[1, "land_price_city_yoy_rate"] == pytest.approx(2.0)
    assert actual.loc[1, "land_price_points_city_count"] == pytest.approx(3.0)
    assert actual.loc[1, "has_land_price_data"] == 1.0
    assert actual.loc[2, "has_land_price_data"] == 0.0


def test_add_land_price_features_adds_nearest_point_when_coordinates_exist() -> None:
    properties = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "transaction_year": 2025,
                "lat": 35.681236,
                "lon": 139.767125,
            }
        ]
    )
    points = pd.DataFrame(
        [
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "lat": 35.6813,
                "lon": 139.7672,
                "current_price_yen_per_sqm": 3000.0,
            },
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "lat": 35.7,
                "lon": 139.8,
                "current_price_yen_per_sqm": 1000.0,
            },
        ]
    )

    actual = add_land_price_features(properties, points, pd.DataFrame())

    assert actual.loc[0, "nearest_land_price_yen_per_sqm"] == pytest.approx(3000.0)
    assert actual.loc[0, "nearest_land_price_distance_km"] < 0.02
    assert actual.loc[0, "land_price_points_within_2km"] == pytest.approx(1.0)
    assert actual.loc[0, "has_land_price_data"] == 1.0


def test_haversine_km_returns_zero_for_same_point() -> None:
    assert haversine_km(35.0, 139.0, 35.0, 139.0) == pytest.approx(0.0)
