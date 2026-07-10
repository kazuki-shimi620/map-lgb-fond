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


def test_load_config_resolves_hazard_features_csv(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "region: sample",
                "features:",
                "  - area",
                "hazard_features_csv: data/processed/hazards/hazard_features.csv",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.hazard_features_csv
    assert config.hazard_features_csv.endswith(
        "data/processed/hazards/hazard_features.csv"
    )


def test_load_config_resolves_commercial_facilities_csv(tmp_path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "region: sample",
                "features:",
                "  - area",
                "commercial_facilities_csv: data/processed/jcsc/jcsc_sc_open.csv",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.commercial_facilities_csv
    assert config.commercial_facilities_csv.endswith(
        "data/processed/jcsc/jcsc_sc_open.csv"
    )
