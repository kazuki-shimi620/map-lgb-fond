from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.config import TrainingConfig, load_config
from evaluate.metrics import calculate_metrics
from experiment.database import (
    complete_experiment,
    connect,
    create_dataset,
    create_experiment,
    fail_experiment,
    initialize_database,
    link_experiment_features,
    register_model_if_best,
    upsert_features,
)
from export.artifacts import (
    build_artifact_paths,
    build_price_history,
    copy_for_frontend,
    export_onnx_if_available,
    save_json,
    save_pickle,
)
from features.category_dictionary import build_and_apply_category_dictionary
from features.providers import create_mvp_feature_pipeline
from train.model import train_model, tune_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--export-onnx", action="store_true")
    parser.add_argument("--db-path", default="db/experiments.db")
    parser.add_argument("--publish-policy", choices=["best", "latest"], default="best")
    args = parser.parse_args()

    config = load_config(args.config)
    data_path = _resolve_data_path(config)
    if data_path is None:
        print("skip train: processed dataset is not configured or does not exist")
        return 0

    import pandas as pd

    df = pd.read_parquet(data_path)
    pipeline = create_mvp_feature_pipeline()
    feature_df, _context = pipeline.fit_transform(df)
    encoding = build_and_apply_category_dictionary(feature_df, config.categorical_features)

    features = encoding.dataframe[config.features]
    target = encoding.dataframe[config.target]

    train_mask, test_mask, split_name = _build_train_test_split(encoding.dataframe, config)

    train_x = features[train_mask]
    train_y = target[train_mask]
    test_x = features[test_mask]
    test_y = target[test_mask]
    deployment_mask = _build_deployment_train_mask(encoding.dataframe, config)
    deployment_x = features[deployment_mask]
    deployment_y = target[deployment_mask]

    initialize_database(args.db_path)
    with connect(args.db_path) as connection:
        upsert_features(connection, config.features)
        dataset_id = create_dataset(
            connection,
            name=f"mlit_{config.region}_{config.latest_training_year}",
            source_url="mlit",
            region=config.region,
            record_count=len(df),
        )
        experiment_id = create_experiment(
            connection,
            name=f"{config.region}_lgbm_{config.latest_training_year}",
            dataset_id=dataset_id,
        )
        link_experiment_features(connection, experiment_id, config.features)

        try:
            base_model_params = _build_base_model_params(config)
            tuning_result = _run_tuning_if_enabled(
                config=config,
                dataframe=encoding.dataframe,
                features=features,
                target=target,
                train_mask=train_mask,
                base_model_params=base_model_params,
            )
            model_params = tuning_result["params"] if tuning_result else base_model_params

            evaluation_model = train_model(train_x, train_y, config.categorical_features, model_params)
            predictions = evaluation_model.predict(test_x)
            metrics = calculate_metrics(test_y, predictions)
            deployment_model = train_model(deployment_x, deployment_y, config.categorical_features, model_params)

            paths = build_artifact_paths(config.output_dir, config.region)
            save_pickle(deployment_model, paths["pkl"])
            save_json(encoding.dictionary, paths["categories"])
            save_json(
                _build_metadata(
                    config,
                    metrics,
                    split_name=split_name,
                    train_count=len(train_x),
                    test_count=len(test_x),
                    deployment_count=len(deployment_x),
                    model_params=model_params,
                    tuning_result=tuning_result,
                ),
                paths["metadata"],
            )
            save_json(build_price_history(df), paths["history"])

            if args.export_onnx:
                export_onnx_if_available(deployment_model, len(config.features), paths["onnx"])

            complete_experiment(connection, experiment_id, metrics)
            is_latest = register_model_if_best(
                connection,
                experiment_id=experiment_id,
                model_type="lightgbm",
                region=config.region,
                model_path=str(paths["pkl"]),
                onnx_path=str(paths["onnx"]) if paths["onnx"].exists() else None,
                mae=metrics["mae"],
            )
            should_publish = is_latest or args.publish_policy == "latest"
            if should_publish:
                copy_for_frontend(paths, config.frontend_public_dir, config.region)
            print(
                f"success train: {config.region} split={split_name} "
                f"train={len(train_x)} test={len(test_x)} deploy_train={len(deployment_x)} "
                f"tuning_trials={tuning_result['trials'] if tuning_result else 0} "
                f"mae={metrics['mae']:.2f} publish_policy={args.publish_policy} "
                f"published={should_publish}"
            )
            return 0
        except Exception:
            fail_experiment(connection, experiment_id)
            raise


def _resolve_data_path(config: TrainingConfig) -> Path | None:
    candidates = []
    if config.processed_path:
        candidates.append(Path(config.processed_path))
    candidates.append(Path("data/processed") / f"{config.region}.parquet")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _build_train_test_split(df, config: TrainingConfig):
    import pandas as pd

    train_window = df["transaction_year"] >= config.train_start_year
    train_mask = train_window & (df["transaction_year"] < config.test_year)
    test_mask = df["transaction_year"] == config.test_year
    if train_mask.any() and test_mask.any():
        return train_mask, test_mask, "time_holdout"

    if len(df) < 2:
        raise ValueError("At least two records are required to train and evaluate a model")

    test_size = max(1, int(len(df) * 0.2))
    train_size = len(df) - test_size
    if train_size <= 0:
        train_size = len(df) - 1

    positions = pd.Series(range(len(df)), index=df.index)
    train_mask = positions < train_size
    test_mask = ~train_mask
    return train_mask, test_mask, "single_year_holdout"


def _build_deployment_train_mask(df, config: TrainingConfig):
    return (df["transaction_year"] >= config.train_start_year) & (
        df["transaction_year"] <= config.latest_training_year
    )


def _build_base_model_params(config: TrainingConfig) -> dict[str, object]:
    return {
        "objective": "regression",
        "n_estimators": config.model.n_estimators,
        "learning_rate": config.model.learning_rate,
        "random_state": config.model.random_state,
    }


def _run_tuning_if_enabled(
    *,
    config: TrainingConfig,
    dataframe,
    features,
    target,
    train_mask,
    base_model_params: dict[str, object],
) -> dict[str, object] | None:
    if not config.tuning.enabled:
        return None

    tuning_train_mask, tuning_valid_mask, validation_year = _build_tuning_split(dataframe, train_mask, config)
    result = tune_model(
        features[tuning_train_mask],
        target[tuning_train_mask],
        features[tuning_valid_mask],
        target[tuning_valid_mask],
        config.categorical_features,
        base_params=base_model_params,
        n_trials=config.tuning.n_trials,
        timeout_seconds=config.tuning.timeout_seconds,
        early_stopping_rounds=config.tuning.early_stopping_rounds,
        max_estimators=config.tuning.max_estimators,
        learning_rate_min=config.tuning.learning_rate_min,
        learning_rate_max=config.tuning.learning_rate_max,
        num_leaves_min=config.tuning.num_leaves_min,
        num_leaves_max=config.tuning.num_leaves_max,
        max_depth_min=config.tuning.max_depth_min,
        max_depth_max=config.tuning.max_depth_max,
        min_child_samples_min=config.tuning.min_child_samples_min,
        min_child_samples_max=config.tuning.min_child_samples_max,
        size_penalty_per_iteration=config.tuning.size_penalty_per_iteration,
    )
    result["validation_year"] = validation_year
    result["train_count"] = int(tuning_train_mask.sum())
    result["valid_count"] = int(tuning_valid_mask.sum())
    return result


def _build_tuning_split(df, train_mask, config: TrainingConfig):
    import pandas as pd

    validation_year = config.tuning.validation_year or config.test_year - 1
    tuning_train_mask = train_mask & (df["transaction_year"] < validation_year)
    tuning_valid_mask = train_mask & (df["transaction_year"] == validation_year)
    if tuning_train_mask.any() and tuning_valid_mask.any():
        return tuning_train_mask, tuning_valid_mask, validation_year

    train_positions = pd.Series(range(int(train_mask.sum())), index=df[train_mask].index)
    valid_size = max(1, int(len(train_positions) * 0.2))
    train_size = len(train_positions) - valid_size
    if train_size <= 0:
        raise ValueError("At least two training records are required for tuning")

    tuning_train_mask = pd.Series(False, index=df.index)
    tuning_valid_mask = pd.Series(False, index=df.index)
    tuning_train_mask.loc[train_positions.index[train_positions < train_size]] = True
    tuning_valid_mask.loc[train_positions.index[train_positions >= train_size]] = True
    return tuning_train_mask, tuning_valid_mask, None


def _build_metadata(
    config: TrainingConfig,
    metrics: dict[str, float],
    *,
    split_name: str,
    train_count: int,
    test_count: int,
    deployment_count: int,
    model_params: dict[str, object],
    tuning_result: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "region": config.region,
        "modelName": f"{config.region}_latest",
        "mae": metrics["mae"],
        "latestTrainingYear": config.latest_training_year,
        "featureOrder": config.features,
        "evaluation": {
            "split": split_name,
            "trainStartYear": config.train_start_year,
            "testYear": config.test_year,
            "trainCount": train_count,
            "testCount": test_count,
            "metrics": metrics,
        },
        "deployment": {
            "trainStartYear": config.train_start_year,
            "latestTrainingYear": config.latest_training_year,
            "trainCount": deployment_count,
            "trainedWithAllAvailableRows": True,
        },
        "modelParams": model_params,
        "tuning": {
            "enabled": config.tuning.enabled,
            "nTrials": config.tuning.n_trials,
            "completedTrials": tuning_result["trials"] if tuning_result else 0,
            "validationYear": tuning_result["validation_year"] if tuning_result else None,
            "bestValidationMae": tuning_result["best_validation_mae"] if tuning_result else None,
            "bestTuningScore": tuning_result["best_value"] if tuning_result else None,
            "maxEstimators": config.tuning.max_estimators,
            "numLeavesMax": config.tuning.num_leaves_max,
            "maxDepthMax": config.tuning.max_depth_max,
            "sizePenaltyPerIteration": config.tuning.size_penalty_per_iteration,
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
