from __future__ import annotations

import pandas as pd
import pytest

from features.crime_stats import add_crime_features


def test_add_crime_features_uses_population_when_per_1000_is_missing() -> None:
    properties = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "transaction_year": 2025,
            }
        ]
    )
    crime = pd.DataFrame(
        [
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "crime_type": "刑法犯総数",
                "crime_count": 120.0,
                "area_unit": "municipality",
            }
        ]
    )
    population = pd.DataFrame(
        [
            {
                "year": 2020,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "population_total": 60000.0,
            }
        ]
    )

    actual = add_crime_features(properties, crime, population)

    assert actual.loc[0, "crime_count_per_1000_population"] == pytest.approx(2.0)
    assert actual.loc[0, "crime_count"] == 120.0
    assert actual.loc[0, "crime_year"] == 2025
    assert actual.loc[0, "crime_area_unit"] == "municipality"
    assert actual.loc[0, "has_crime_data"] == 1.0


def test_add_crime_features_fills_missing_values() -> None:
    properties = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "未収録",
                "transaction_year": 2025,
            }
        ]
    )

    actual = add_crime_features(properties, pd.DataFrame())

    assert actual.loc[0, "crime_count_per_1000_population"] == 0.0
    assert actual.loc[0, "crime_count"] == 0.0
    assert actual.loc[0, "crime_area_unit"] == "unknown"
    assert actual.loc[0, "has_crime_data"] == 0.0
