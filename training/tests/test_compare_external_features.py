from __future__ import annotations

from evaluate.compare_external_features import (
    COMMERCIAL_FEATURES,
    STATION_SCALE_NUMERIC_FEATURES,
    STATION_SCALE_NUMERIC_FEATURES_WITHOUT_COVERAGE_FLAG,
    ExternalFeatureCandidate,
    feature_lists,
)


def test_feature_lists_can_remove_station_and_add_external_features() -> None:
    candidate = ExternalFeatureCandidate(
        "external_no_station",
        COMMERCIAL_FEATURES,
        STATION_SCALE_NUMERIC_FEATURES,
        include_station=False,
        include_station_rank=True,
    )

    features, categorical_features = feature_lists(candidate)

    assert "station" not in features
    assert "station" not in categorical_features
    assert "station_rank" in features
    assert "station_rank" in categorical_features
    assert "sc_city_open_count_cumulative" in features
    assert "station_passenger_log" in features


def test_feature_lists_can_compare_without_station_coverage_flag() -> None:
    candidate = ExternalFeatureCandidate(
        "station_passenger_no_coverage_flag",
        [],
        STATION_SCALE_NUMERIC_FEATURES_WITHOUT_COVERAGE_FLAG,
    )

    features, _ = feature_lists(candidate)

    assert "station_passenger_log" in features
    assert "effective_station_scale" in features
    assert "has_station_passenger_data" not in features
