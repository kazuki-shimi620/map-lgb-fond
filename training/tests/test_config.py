from __future__ import annotations

from common.config import load_config


def test_load_config_resolves_station_passengers_csv() -> None:
    config = load_config("configs/tokyo.yaml")

    assert config.station_passengers_csv
    assert config.station_passengers_csv.endswith(
        "data/processed/station_passengers/station_groups.csv"
    )
    assert "station" not in config.features
    assert "station_passenger_log" in config.features
    assert "station_rank" in config.categorical_features
