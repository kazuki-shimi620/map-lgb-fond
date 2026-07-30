import pandas as pd
import pytest

from features.nearby_pois import add_nearby_poi_features, feature_names


def test_add_nearby_poi_features_calculates_distance_and_counts() -> None:
    properties = pd.DataFrame([{"lat": 35.0, "lon": 139.0}])
    pois = pd.DataFrame(
        [
            {"category_id": "cinema", "lat": 35.0, "lon": 139.005},
            {"category_id": "cinema", "lat": 35.0, "lon": 139.02},
            {"category_id": "museum", "lat": 36.0, "lon": 140.0},
        ]
    )

    actual = add_nearby_poi_features(properties, pois, categories=("cinema",))
    nearest, within_1km, within_3km = feature_names("cinema")

    assert actual.loc[0, nearest] == pytest.approx(0.456, abs=0.01)
    assert actual.loc[0, within_1km] == 1
    assert actual.loc[0, within_3km] == 2


def test_add_nearby_poi_features_handles_missing_coordinates() -> None:
    properties = pd.DataFrame([{"lat": None, "lon": None}])
    pois = pd.DataFrame([{"category_id": "museum", "lat": 35.0, "lon": 139.0}])

    actual = add_nearby_poi_features(properties, pois, categories=("museum",))

    assert actual[feature_names("museum")].sum(axis=None) == 0
