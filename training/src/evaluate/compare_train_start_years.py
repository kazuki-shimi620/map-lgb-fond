from __future__ import annotations

import argparse
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.config import load_config  # noqa: E402
from evaluate.metrics import calculate_metrics  # noqa: E402
from export.artifacts import save_json  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from train.model import train_model  # noqa: E402
from train.train import _add_external_features_if_needed, _build_base_model_params  # noqa: E402

DEFAULT_CONFIGS = [
    Path("configs/tokyo.yaml"),
    Path("configs/kanagawa.yaml"),
    Path("configs/saitama.yaml"),
    Path("configs/chiba.yaml"),
]
DEFAULT_TRAIN_START_YEARS = [2005, 2015]
DEFAULT_TEST_YEARS = [2023, 2024, 2025]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare train_start_year candidates.")
    parser.add_argument("--config", type=Path, nargs="+", default=DEFAULT_CONFIGS)
    parser.add_argument(
        "--train-start-years",
        nargs="+",
        type=int,
        default=DEFAULT_TRAIN_START_YEARS,
    )
    parser.add_argument("--test-years", nargs="+", type=int, default=DEFAULT_TEST_YEARS)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparisons"))
    args = parser.parse_args()

    report = compare_train_start_years(
        config_paths=args.config,
        train_start_years=args.train_start_years,
        test_years=args.test_years,
        output_dir=args.output_dir,
    )
    print(render_markdown(report))
    return 0


def compare_train_start_years(
    *,
    config_paths: list[Path],
    train_start_years: list[int],
    test_years: list[int],
    output_dir: Path,
) -> dict[str, object]:
    import pandas as pd

    configs = [load_config(path) for path in config_paths]
    frames_by_region = {}
    for config in configs:
        if not config.processed_path:
            raise ValueError(f"{config.region}: processed_path is required")
        path = Path(config.processed_path)
        if not path.exists():
            raise FileNotFoundError(f"Processed dataset not found: {path}")
        frames_by_region[config.region] = pd.read_parquet(path)

    rows = []
    for train_start_year in train_start_years:
        for test_year in test_years:
            region_rows = [
                _evaluate_region(
                    config=replace(
                        config,
                        train_start_year=train_start_year,
                        test_year=test_year,
                    ),
                    data=frames_by_region[config.region],
                )
                for config in configs
            ]
            rows.append(
                {
                    "trainStartYear": train_start_year,
                    "testYear": test_year,
                    "metrics": weighted_metrics(region_rows),
                    "regions": region_rows,
                }
            )

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "configs": [str(path) for path in config_paths],
        "trainStartYears": train_start_years,
        "testYears": test_years,
        "comparisons": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(report, output_dir / "train_start_year_backtest.json")
    (output_dir / "train_start_year_backtest.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    return report


def _evaluate_region(*, config, data) -> dict[str, object]:
    scoped = data[
        (data["transaction_year"] >= config.train_start_year)
        & (data["transaction_year"] <= config.test_year)
    ].copy()
    scoped = _add_external_features_if_needed(scoped, config)
    train_mask = scoped["transaction_year"] < config.test_year
    test_mask = scoped["transaction_year"] == config.test_year
    if not train_mask.any() or not test_mask.any():
        raise ValueError(
            f"{config.region}: train_start_year={config.train_start_year}, "
            f"test_year={config.test_year} requires both train and test rows"
        )

    encoding = build_and_apply_category_dictionary(scoped, config.categorical_features)
    encoded = encoding.dataframe
    started = time.perf_counter()
    model = train_model(
        encoded.loc[train_mask, config.features],
        encoded.loc[train_mask, config.target],
        config.categorical_features,
        _build_base_model_params(config),
    )
    predictions = model.predict(encoded.loc[test_mask, config.features])
    metrics = calculate_metrics(encoded.loc[test_mask, config.target], predictions)
    return {
        "region": config.region,
        "trainStartYear": config.train_start_year,
        "testYear": config.test_year,
        "trainCount": int(train_mask.sum()),
        "testCount": int(test_mask.sum()),
        "featureCount": len(config.features),
        "features": config.features,
        "metrics": metrics,
        "trainingSeconds": time.perf_counter() - started,
    }


def weighted_metrics(rows: list[dict[str, object]]) -> dict[str, float]:
    total = sum(int(row["testCount"]) for row in rows)
    if total == 0:
        return {"mae": float("nan"), "rmse": float("nan"), "mape": float("nan")}

    mae = sum(row["metrics"]["mae"] * int(row["testCount"]) for row in rows) / total
    rmse = (
        sum(row["metrics"]["rmse"] ** 2 * int(row["testCount"]) for row in rows) / total
    ) ** 0.5
    mape = sum(row["metrics"]["mape"] * int(row["testCount"]) for row in rows) / total
    return {"mae": mae, "rmse": rmse, "mape": mape}


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 学習開始年の複数holdout比較",
        "",
        f"設定: {', '.join(report['configs'])}",
        f"学習開始年: {', '.join(str(year) for year in report['trainStartYears'])}",
        f"評価年: {', '.join(str(year) for year in report['testYears'])}",
        "",
        "| trainStart | testYear | MAE | RMSE | MAPE | testCount | 学習秒 |",
        "|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["comparisons"]:
        metrics = row["metrics"]
        test_count = sum(region["testCount"] for region in row["regions"])
        training_seconds = sum(region["trainingSeconds"] for region in row["regions"])
        lines.append(
            f"| {row['trainStartYear']} | {row['testYear']} | "
            f"{metrics['mae']:,.0f} | {metrics['rmse']:,.0f} | {metrics['mape']:.2f}% | "
            f"{test_count:,} | {training_seconds:.1f} |"
        )

    lines.extend(["", "## 地域別", ""])
    for row in report["comparisons"]:
        lines.append(f"### {row['trainStartYear']} start / {row['testYear']} holdout")
        lines.append("")
        lines.append("| 地域 | MAE | RMSE | MAPE | trainCount | testCount |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for region in row["regions"]:
            metrics = region["metrics"]
            lines.append(
                f"| {region['region']} | {metrics['mae']:,.0f} | "
                f"{metrics['rmse']:,.0f} | {metrics['mape']:.2f}% | "
                f"{region['trainCount']:,} | {region['testCount']:,} |"
            )
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
