import pandas as pd
import pytest

from features.future_population import (
    add_clipped_future_population_features,
    add_future_population_features,
)


def test_add_future_population_features_joins_coordinates() -> None:
    properties = pd.DataFrame([{"lat": 35.0, "lon": 139.0}, {"lat": 36.0, "lon": 140.0}])
    population = pd.DataFrame(
        [
            {
                "lat": 35.0,
                "lon": 139.0,
                "future_population_change_2030_rate": -10.0,
                "future_population_change_2040_rate": -20.0,
                "has_future_population_data": 1.0,
            }
        ]
    )

    actual = add_future_population_features(properties, population)

    assert actual.loc[0, "future_population_change_2030_rate"] == -10.0
    assert actual.loc[1, "has_future_population_data"] == 0.0


def test_add_clipped_future_population_features_reports_thresholds() -> None:
    data = pd.DataFrame(
        {
            "future_population_change_2030_rate": [-100.0, 0.0, 100.0],
            "future_population_change_2040_rate": [-200.0, 0.0, 200.0],
            "has_future_population_data": [1.0, 1.0, 1.0],
        }
    )

    actual, thresholds = add_clipped_future_population_features(
        data, lower=0.25, upper=0.75
    )

    assert thresholds["future_population_change_2030_rate"] == {
        "lower": -50.0,
        "upper": 50.0,
    }
    assert actual.loc[0, "future_population_change_2030_rate_clipped"] == pytest.approx(-50.0)
