from __future__ import annotations

from features.providers import create_external_feature_pipeline


def test_create_external_feature_pipeline_returns_none_without_external_features() -> None:
    pipeline = create_external_feature_pipeline(requested_features={"area", "age"})

    assert pipeline is None


def test_create_external_feature_pipeline_registers_requested_providers(tmp_path) -> None:
    station_csv = tmp_path / "station_groups.csv"
    commercial_csv = tmp_path / "jcsc_sc_open.csv"
    hazard_csv = tmp_path / "hazard_features.csv"

    pipeline = create_external_feature_pipeline(
        requested_features={
            "station_passenger_log",
            "sc_city_open_count_cumulative",
            "hazard_overall_score",
        },
        station_passengers_csv=str(station_csv),
        commercial_facilities_csv=str(commercial_csv),
        hazard_features_csv=str(hazard_csv),
    )

    assert pipeline is not None
    assert [provider.csv_path for provider in pipeline.providers] == [
        station_csv,
        commercial_csv,
        hazard_csv,
    ]
