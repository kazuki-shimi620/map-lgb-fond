from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.regions import (  # noqa: E402
    CAPITAL_MODEL_BY_PREFECTURE,
    REGIONAL_CLUSTERS,
    build_cluster_by_prefecture,
)
from evaluate.compare_station_passenger_features import (  # noqa: E402
    STATION_SCALE_NUMERIC_FEATURES,
)
from evaluate.metrics import calculate_metrics  # noqa: E402
from export.artifacts import save_json  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from features.station_passengers import (  # noqa: E402
    add_station_passenger_features,
    load_station_passengers_csv,
)
from train.model import train_model  # noqa: E402
from train.train_regional_models import (  # noqa: E402
    CATEGORICAL_FEATURES,
    FEATURES,
    MODEL_PARAMS,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare regional station scale features.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/national.parquet"))
    parser.add_argument(
        "--station-passengers-csv",
        type=Path,
        default=Path("data/processed/station_passengers/station_groups.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/comparisons/regional_station_passenger_dry_run"),
    )
    parser.add_argument("--sample-size-per-cluster", type=int, default=30_000)
    parser.add_argument("--train-start-year", type=int, default=2015)
    parser.add_argument("--test-years", nargs="+", type=int, default=[2023, 2024, 2025])
    args = parser.parse_args()

    report = compare_regional_station_features(
        input_path=args.input,
        station_passengers_csv=args.station_passengers_csv,
        output_dir=args.output_dir,
        sample_size_per_cluster=args.sample_size_per_cluster,
        train_start_year=args.train_start_year,
        test_years=args.test_years,
    )
    print(render_markdown(report))
    return 0


def compare_regional_station_features(
    *,
    input_path: Path,
    station_passengers_csv: Path,
    output_dir: Path,
    sample_size_per_cluster: int,
    train_start_year: int,
    test_years: list[int],
) -> dict[str, object]:
    import pandas as pd

    data = pd.read_parquet(input_path)
    data = data[data["transaction_year"] >= train_start_year].copy()
    data["model_group"] = data["prefecture"].map(build_cluster_by_prefecture())
    stations = load_station_passengers_csv(station_passengers_csv)
    data = add_station_passenger_features(data, stations)

    rows = []
    for cluster, prefectures in REGIONAL_CLUSTERS.items():
        cluster_data = data[data["model_group"] == cluster].copy()
        served_prefectures = [
            prefecture
            for prefecture in prefectures
            if prefecture not in CAPITAL_MODEL_BY_PREFECTURE
        ]
        source_count = len(cluster_data)
        if 0 < sample_size_per_cluster < source_count:
            cluster_data = cluster_data.sample(
                n=sample_size_per_cluster, random_state=42
            )
        baseline = _backtest(
            cluster_data, FEATURES, test_years, served_prefectures
        )
        station_scale = _backtest(
            cluster_data,
            FEATURES + STATION_SCALE_NUMERIC_FEATURES,
            test_years,
            served_prefectures,
        )
        served_mask = cluster_data["prefecture"].isin(served_prefectures)
        rows.append(
            {
                "cluster": cluster,
                "servedPrefectures": served_prefectures,
                "sourceCount": source_count,
                "sampleCount": len(cluster_data),
                "evaluationCount": int(served_mask.sum()),
                "coverage": float(
                    cluster_data.loc[served_mask, "has_station_passenger_data"].mean()
                ),
                "baseline": baseline,
                "stationScale": station_scale,
                "maeDelta": station_scale["metrics"]["mae"] - baseline["metrics"]["mae"],
                "rmseDelta": station_scale["metrics"]["rmse"]
                - baseline["metrics"]["rmse"],
                "mapeDelta": station_scale["metrics"]["mape"]
                - baseline["metrics"]["mape"],
            }
        )
    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input": str(input_path),
        "stationPassengersCsv": str(station_passengers_csv),
        "trainStartYear": train_start_year,
        "testYears": test_years,
        "sampleSizePerCluster": sample_size_per_cluster,
        "clusters": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(report, output_dir / "regional_station_passenger_dry_run.json")
    (output_dir / "regional_station_passenger_dry_run.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    return report


def _backtest(
    data,
    features: list[str],
    test_years: list[int],
    evaluation_prefectures: list[str],
) -> dict[str, object]:
    encoded = build_and_apply_category_dictionary(data, CATEGORICAL_FEATURES).dataframe
    started = time.perf_counter()
    folds = []
    for test_year in test_years:
        train_mask = encoded["transaction_year"] < test_year
        test_mask = (encoded["transaction_year"] == test_year) & data[
            "prefecture"
        ].isin(evaluation_prefectures)
        if not train_mask.any() or not test_mask.any():
            continue
        model = train_model(
            encoded.loc[train_mask, features],
            encoded.loc[train_mask, "price"],
            CATEGORICAL_FEATURES,
            MODEL_PARAMS,
        )
        predictions = model.predict(encoded.loc[test_mask, features])
        folds.append(
            {
                "testYear": test_year,
                "testCount": int(test_mask.sum()),
                "metrics": calculate_metrics(encoded.loc[test_mask, "price"], predictions),
            }
        )
    total = sum(fold["testCount"] for fold in folds)
    if not total:
        raise ValueError("train/test rows are required")
    metrics = {
        "mae": sum(fold["metrics"]["mae"] * fold["testCount"] for fold in folds)
        / total,
        "rmse": (
            sum(fold["metrics"]["rmse"] ** 2 * fold["testCount"] for fold in folds)
            / total
        )
        ** 0.5,
        "mape": sum(fold["metrics"]["mape"] * fold["testCount"] for fold in folds)
        / total,
    }
    return {"metrics": metrics, "folds": folds, "seconds": time.perf_counter() - started}


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 地方モデル駅規模特徴量 dry-run",
        "",
        f"* 評価年: {', '.join(map(str, report['testYears']))}",
        f"* 地域別最大サンプル: {report['sampleSizePerCluster']:,}",
        "",
        "| 地域 | 元件数 | サンプル | coverage | baseline MAE | 駅規模 MAE | "
        "MAE差 | RMSE差 | MAPE差 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["clusters"]:
        lines.append(
            f"| {row['cluster']} | {row['sourceCount']:,} | {row['sampleCount']:,} | "
            f"{row['coverage']:.1%} | {row['baseline']['metrics']['mae']:,.0f} | "
            f"{row['stationScale']['metrics']['mae']:,.0f} | {row['maeDelta']:+,.0f} | "
            f"{row['rmseDelta']:+,.0f} | {row['mapeDelta']:+.2f}pt |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
