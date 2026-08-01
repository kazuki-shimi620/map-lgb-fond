from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluate.compare_models import BASE_CATEGORICAL_FEATURES, BASE_FEATURES  # noqa: E402
from evaluate.metrics import calculate_metrics  # noqa: E402
from export.artifacts import save_json  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from features.future_population import (  # noqa: E402
    CLIPPED_FUTURE_POPULATION_FEATURES,
    FUTURE_POPULATION_FEATURES,
    add_clipped_future_population_features,
    add_future_population_features,
    load_future_population_csv,
)
from train.model import train_model  # noqa: E402

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]
DEFAULT_TEST_YEARS = [2023, 2024, 2025]


@dataclass(frozen=True)
class Candidate:
    name: str
    features: list[str]


CANDIDATES = [
    Candidate("baseline", []),
    Candidate("future_population_raw", FUTURE_POPULATION_FEATURES),
    Candidate("future_population_clipped", CLIPPED_FUTURE_POPULATION_FEATURES),
]


def compare_future_population_features(
    *,
    regions: list[str],
    processed_dir: Path,
    features_csv: Path,
    output_dir: Path,
    train_start_year: int,
    test_years: list[int],
) -> dict[str, object]:
    import pandas as pd

    frames = [pd.read_parquet(processed_dir / f"{region}.parquet") for region in regions]
    data = pd.concat(frames, ignore_index=True)
    data = data[data["transaction_year"] >= train_start_year].copy()
    future_population = load_future_population_csv(features_csv)
    data = add_future_population_features(data, future_population)
    data, thresholds = add_clipped_future_population_features(data)

    encoding = build_and_apply_category_dictionary(data, BASE_CATEGORICAL_FEATURES)
    encoded = encoding.dataframe
    candidates = [
        _backtest(candidate, encoded=encoded, test_years=test_years)
        for candidate in CANDIDATES
    ]
    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "regions": regions,
        "trainStartYear": train_start_year,
        "testYears": test_years,
        "rowCount": len(data),
        "coordinateCount": len(future_population),
        "matchedRowCount": int(data["has_future_population_data"].sum()),
        "clipThresholds": thresholds,
        "candidates": candidates,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(report, output_dir / "future_population_feature_backtest.json")
    (output_dir / "future_population_feature_backtest.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    return report


def _backtest(candidate: Candidate, *, encoded, test_years: list[int]) -> dict[str, object]:
    features = BASE_FEATURES + candidate.features
    folds = []
    started = time.perf_counter()
    for test_year in test_years:
        train_mask = encoded["transaction_year"] < test_year
        test_mask = encoded["transaction_year"] == test_year
        model = train_model(
            encoded.loc[train_mask, features],
            encoded.loc[train_mask, "price"],
            BASE_CATEGORICAL_FEATURES,
            {
                "n_estimators": 180,
                "learning_rate": 0.075,
                "num_leaves": 31,
                "max_depth": 7,
                "min_child_samples": 80,
                "random_state": 42,
                "n_jobs": -1,
            },
        )
        predictions = model.predict(encoded.loc[test_mask, features])
        folds.append(
            {
                "testYear": test_year,
                "trainCount": int(train_mask.sum()),
                "testCount": int(test_mask.sum()),
                "metrics": calculate_metrics(encoded.loc[test_mask, "price"], predictions),
            }
        )
    return {
        "name": candidate.name,
        "features": candidate.features,
        "folds": folds,
        "metrics": _weighted_metrics(folds),
        "trainingSeconds": time.perf_counter() - started,
    }


def _weighted_metrics(folds: list[dict[str, object]]) -> dict[str, float]:
    total = sum(fold["testCount"] for fold in folds)
    return {
        "mae": sum(fold["metrics"]["mae"] * fold["testCount"] for fold in folds) / total,
        "rmse": (
            sum(fold["metrics"]["rmse"] ** 2 * fold["testCount"] for fold in folds) / total
        )
        ** 0.5,
        "mape": sum(fold["metrics"]["mape"] * fold["testCount"] for fold in folds)
        / total,
    }


def render_markdown(report: dict[str, object]) -> str:
    baseline = report["candidates"][0]["metrics"]
    lines = [
        "# 将来人口特徴量バックテスト",
        "",
        f"対象: {', '.join(report['regions'])}",
        f"学習開始年: {report['trainStartYear']}",
        f"評価年: {', '.join(map(str, report['testYears']))}",
        f"物件件数: {report['rowCount']:,}",
        f"特徴量一致行: {report['matchedRowCount']:,}",
        "",
        "| 候補 | MAE | baseline差 | RMSE | MAPE | 学習秒 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["candidates"]:
        metrics = row["metrics"]
        lines.append(
            f"| {row['name']} | {metrics['mae']:,.0f} | "
            f"{metrics['mae'] - baseline['mae']:+,.0f} | {metrics['rmse']:,.0f} | "
            f"{metrics['mape']:.2f}% | {row['trainingSeconds']:.1f} |"
        )
    lines.extend(
        [
            "",
            "## クリップ閾値",
            "",
            "```json",
            json.dumps(report["clipThresholds"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest XKT013 future population features")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("data/processed/with_address_coordinates")
    )
    parser.add_argument(
        "--features-csv", type=Path, default=Path("data/processed/future_population/features.csv")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparisons"))
    parser.add_argument("--train-start-year", type=int, default=2020)
    parser.add_argument("--test-years", nargs="+", type=int, default=DEFAULT_TEST_YEARS)
    args = parser.parse_args()
    report = compare_future_population_features(
        regions=args.regions,
        processed_dir=args.processed_dir,
        features_csv=args.features_csv,
        output_dir=args.output_dir,
        train_start_year=args.train_start_year,
        test_years=args.test_years,
    )
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
