from __future__ import annotations

from evaluate.compare_external_features import (
    COMMERCIAL_FEATURES,
    HAZARD_FEATURES,
    STATION_SCALE_NUMERIC_FEATURES,
    STATION_SCALE_NUMERIC_FEATURES_WITHOUT_COVERAGE_FLAG,
    ExternalFeatureCandidate,
    _active_candidates,
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


def test_feature_lists_can_add_hazard_features() -> None:
    candidate = ExternalFeatureCandidate(
        "hazard",
        [],
        [],
        hazard_features=HAZARD_FEATURES,
    )

    features, _ = feature_lists(candidate)

    assert "hazard_overall_score" in features
    assert "hazard_flood_risk_level" in features


def test_active_candidates_skip_hazard_when_csv_is_missing() -> None:
    candidates = _active_candidates(hazard_enabled=False)

    assert candidates
    assert all(not candidate.hazard_features for candidate in candidates)
    assert "hazard" not in {candidate.name for candidate in candidates}
