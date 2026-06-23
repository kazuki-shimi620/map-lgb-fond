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
from train.model import train_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--export-onnx", action="store_true")
    parser.add_argument("--db-path", default="db/experiments.db")
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
            model = train_model(train_x, train_y, config.categorical_features)
            predictions = model.predict(test_x)
            metrics = calculate_metrics(test_y, predictions)

            paths = build_artifact_paths(config.output_dir, config.region)
            save_pickle(model, paths["pkl"])
            save_json(encoding.dictionary, paths["categories"])
            save_json(_build_metadata(config, metrics), paths["metadata"])
            save_json(build_price_history(df), paths["history"])

            if args.export_onnx:
                export_onnx_if_available(model, len(config.features), paths["onnx"])

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
            if is_latest:
                copy_for_frontend(paths, config.frontend_public_dir, config.region)
            print(
                f"success train: {config.region} split={split_name} "
                f"train={len(train_x)} test={len(test_x)} mae={metrics['mae']:.2f}"
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

    train_mask = df["transaction_year"] < config.test_year
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


def _build_metadata(config: TrainingConfig, metrics: dict[str, float]) -> dict[str, object]:
    return {
        "region": config.region,
        "modelName": f"{config.region}_latest",
        "mae": metrics["mae"],
        "latestTrainingYear": config.latest_training_year,
        "featureOrder": config.features,
    }


if __name__ == "__main__":
    raise SystemExit(main())
