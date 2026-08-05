from common.regions import REGIONAL_CLUSTERS
from train.train_regional_models import (
    FEATURES,
    MODEL_PARAMS,
    _build_metadata,
    features_for_cluster,
)


class DummyModel:
    feature_importances_ = list(range(len(FEATURES)))


def test_production_regional_model_configuration_matches_selected_candidate():
    assert len(REGIONAL_CLUSTERS) == 8
    assert MODEL_PARAMS["n_estimators"] == 160
    assert MODEL_PARAMS["num_leaves"] == 24
    assert "station" in FEATURES
    assert "station_passenger_log" in features_for_cluster("kanto")
    assert features_for_cluster("tohoku") == FEATURES


def test_regional_metadata_describes_evaluation_and_deployment():
    metadata = _build_metadata(
        model_id="regional_tohoku",
        cluster="tohoku",
        prefectures=REGIONAL_CLUSTERS["tohoku"],
        train_start_year=2005,
        test_year=2025,
        train_count=100,
        test_count=20,
        deployment_count=120,
        metrics={"mae": 1.0, "rmse": 2.0, "mape": 3.0},
        residual_quantiles={"p025": -10.0, "p975": 20.0},
        segment_metrics={"minimumSampleCount": 100, "dimensions": {}},
        model=DummyModel(),
        input_ranges={"area": {"min": 20.0, "max": 100.0}},
        input_baselines={"area": 60.0, "roomLayout": "3LDK"},
    )

    assert metadata["modelScope"] == "regional"
    assert metadata["evaluation"]["testCount"] == 20
    assert metadata["evaluation"]["residualQuantiles"] == {"p025": -10.0, "p975": 20.0}
    assert metadata["evaluation"]["segments"]["minimumSampleCount"] == 100
    assert metadata["deployment"]["trainCount"] == 120
    assert metadata["prefectures"] == REGIONAL_CLUSTERS["tohoku"]
    assert metadata["inputRanges"] == {"area": {"min": 20.0, "max": 100.0}}
    assert metadata["inputBaselines"] == {"area": 60.0, "roomLayout": "3LDK"}
