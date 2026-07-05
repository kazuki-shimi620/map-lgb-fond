from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.regions import (  # noqa: E402
    PREFECTURE_TO_SLUG,
    REGIONAL_CLUSTERS,
    build_cluster_by_prefecture,
    validate_cluster_coverage,
)
from evaluate.metrics import calculate_metrics  # noqa: E402
from export.artifacts import (  # noqa: E402
    RECENT_HISTORY_START_YEAR,
    build_artifact_paths,
    build_price_history,
    copy_for_frontend,
    export_onnx_if_available,
    save_json,
    save_pickle,
)
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from train.model import train_model  # noqa: E402

FEATURES = [
    "area",
    "age",
    "station_distance",
    "prefecture",
    "municipality",
    "station",
    "room_layout",
    "building_type",
    "transaction_year",
]
CATEGORICAL_FEATURES = [
    "prefecture",
    "municipality",
    "station",
    "room_layout",
    "building_type",
]
MODEL_PARAMS = {
    "objective": "regression",
    "n_estimators": 160,
    "learning_rate": 0.08,
    "num_leaves": 24,
    "max_depth": 6,
    "min_child_samples": 80,
    "random_state": 42,
    "n_jobs": -1,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Train production regional ONNX models")
    parser.add_argument("--input", type=Path, default=Path("data/processed/national.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/models"))
    parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    parser.add_argument("--train-start-year", type=int, default=2005)
    parser.add_argument("--test-year", type=int, default=2025)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    summary = train_regional_models(
        input_path=args.input,
        output_dir=args.output_dir,
        public_dir=args.public_dir,
        train_start_year=args.train_start_year,
        test_year=args.test_year,
        publish=args.publish,
    )
    for row in summary["models"]:
        print(
            f"success train: {row['modelId']} train={row['trainCount']} "
            f"test={row['testCount']} mae={row['metrics']['mae']:.2f} "
            f"onnx_bytes={row['onnxBytes']} published={args.publish}"
        )
    return 0


def train_regional_models(
    *,
    input_path: Path,
    output_dir: Path,
    public_dir: Path,
    train_start_year: int,
    test_year: int,
    publish: bool,
) -> dict[str, object]:
    import pandas as pd

    data = pd.read_parquet(input_path)
    data = data[
        (data["transaction_year"] >= train_start_year)
        & (data["transaction_year"] <= test_year)
    ].copy()
    validate_cluster_coverage(data["prefecture"].unique())
    data["model_group"] = data["prefecture"].map(build_cluster_by_prefecture())

    rows = []
    for cluster, prefectures in REGIONAL_CLUSTERS.items():
        model_id = f"regional_{cluster}"
        group_data = data[data["model_group"] == cluster].copy()
        train_mask = group_data["transaction_year"] < test_year
        test_mask = group_data["transaction_year"] == test_year
        if not train_mask.any() or not test_mask.any():
            raise ValueError(f"{model_id} requires both training and test rows")

        encoding = build_and_apply_category_dictionary(group_data, CATEGORICAL_FEATURES)
        encoded = encoding.dataframe
        evaluation_model = train_model(
            encoded.loc[train_mask, FEATURES],
            encoded.loc[train_mask, "price"],
            CATEGORICAL_FEATURES,
            MODEL_PARAMS,
        )
        predictions = evaluation_model.predict(encoded.loc[test_mask, FEATURES])
        metrics = calculate_metrics(encoded.loc[test_mask, "price"], predictions)
        deployment_model = train_model(
            encoded[FEATURES], encoded["price"], CATEGORICAL_FEATURES, MODEL_PARAMS
        )

        paths = build_artifact_paths(output_dir, model_id)
        save_pickle(deployment_model, paths["pkl"])
        save_json(encoding.dictionary, paths["categories"])
        save_json(
            _build_metadata(
                model_id=model_id,
                cluster=cluster,
                prefectures=prefectures,
                train_start_year=train_start_year,
                test_year=test_year,
                train_count=int(train_mask.sum()),
                test_count=int(test_mask.sum()),
                deployment_count=len(encoded),
                metrics=metrics,
                model=deployment_model,
            ),
            paths["metadata"],
        )
        save_json(build_price_history(group_data), paths["history"], compact=True)
        exported = export_onnx_if_available(deployment_model, len(FEATURES), paths["onnx"])
        if exported is None:
            raise RuntimeError(f"ONNX export failed: {model_id}")
        if publish:
            copy_for_frontend(paths, public_dir, model_id, include_history=False)
            _publish_prefecture_histories(group_data, prefectures, public_dir)

        rows.append(
            {
                "modelId": model_id,
                "prefectures": prefectures,
                "trainCount": int(train_mask.sum()),
                "testCount": int(test_mask.sum()),
                "deploymentCount": len(encoded),
                "metrics": metrics,
                "onnxBytes": paths["onnx"].stat().st_size,
                "published": publish,
            }
        )

    summary = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "modelArchitecture": "capital-prefecture-plus-regional-compact-160",
        "trainStartYear": train_start_year,
        "testYear": test_year,
        "models": rows,
    }
    save_json(summary, output_dir / "production_regional_summary.json")
    return summary


def _build_metadata(
    *,
    model_id: str,
    cluster: str,
    prefectures: list[str],
    train_start_year: int,
    test_year: int,
    train_count: int,
    test_count: int,
    deployment_count: int,
    metrics: dict[str, float],
    model,
) -> dict[str, object]:
    return {
        "region": model_id,
        "modelName": f"{model_id}_latest",
        "modelScope": "regional",
        "cluster": cluster,
        "prefectures": prefectures,
        "mae": metrics["mae"],
        "latestTrainingYear": test_year,
        "generatedAt": datetime.now().date().isoformat(),
        "featureOrder": FEATURES,
        "evaluation": {
            "split": "time_holdout",
            "trainStartYear": train_start_year,
            "testYear": test_year,
            "trainCount": train_count,
            "testCount": test_count,
            "metrics": metrics,
        },
        "deployment": {
            "trainStartYear": train_start_year,
            "latestTrainingYear": test_year,
            "trainCount": deployment_count,
            "trainedWithAllAvailableRows": True,
        },
        "modelParams": MODEL_PARAMS,
        "featureImportance": _build_feature_importance(model),
    }


def _build_feature_importance(model) -> list[dict[str, object]]:
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return []
    rows = [
        {"feature": feature, "importance": float(importance)}
        for feature, importance in zip(FEATURES, importances, strict=False)
    ]
    return sorted(rows, key=lambda row: row["importance"], reverse=True)


def _publish_prefecture_histories(group_data, prefectures: list[str], public_dir: Path) -> None:
    for prefecture in prefectures:
        slug = PREFECTURE_TO_SLUG[prefecture]
        prefecture_data = group_data[group_data["prefecture"] == prefecture]
        save_json(
            build_price_history(prefecture_data, min_year=RECENT_HISTORY_START_YEAR),
            public_dir / "histories" / f"{slug}_latest_history.json",
            compact=True,
        )
        save_json(
            build_price_history(prefecture_data, max_year=RECENT_HISTORY_START_YEAR - 1),
            public_dir / "histories" / f"{slug}_archive_history.json",
            compact=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
