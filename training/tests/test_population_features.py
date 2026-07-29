from __future__ import annotations

import pandas as pd
import pytest

from features.population_stats import add_population_features


def test_add_population_features_uses_latest_available_city_year() -> None:
    properties = pd.DataFrame(
        [
            {"prefecture": "東京都", "municipality": "千代田区", "transaction_year": 2020},
            {"prefecture": "東京都", "municipality": "千代田区", "transaction_year": 2023},
            {"prefecture": "東京都", "municipality": "千代田区", "transaction_year": 2025},
            {"prefecture": "東京都", "municipality": "未整備区", "transaction_year": 2025},
        ]
    )
    population = pd.DataFrame(
        [
            {
                "year": 2020,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "population_total": 1000.0,
                "households_total": 500.0,
                "population_density_per_km2": 100.0,
                "aging_rate": 30.0,
                "working_age_rate": 60.0,
                "population_change_5y_rate": 0.0,
                "household_persons_avg": 2.0,
            },
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "population_total": 1100.0,
                "households_total": 550.0,
                "population_density_per_km2": 110.0,
                "aging_rate": 31.0,
                "working_age_rate": 59.0,
                "population_change_5y_rate": 10.0,
                "household_persons_avg": 2.0,
            },
        ]
    )

    actual = add_population_features(properties, population)

    assert actual.loc[0, "municipality_population"] == pytest.approx(1000.0)
    assert actual.loc[1, "municipality_population"] == pytest.approx(1000.0)
    assert actual.loc[2, "municipality_population"] == pytest.approx(1100.0)
    assert actual.loc[2, "municipality_aging_rate"] == pytest.approx(31.0)
    assert actual.loc[2, "population_change_5y_rate"] == pytest.approx(10.0)
    assert actual.loc[2, "has_population_data"] == 1.0
    assert actual.loc[3, "has_population_data"] == 0.0
