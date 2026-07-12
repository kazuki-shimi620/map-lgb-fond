from __future__ import annotations

import argparse
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
from train.model import train_model  # noqa: E402

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]
DEFAULT_TRAIN_START_YEARS = [2005, 2015]
DEFAULT_TEST_YEARS = [2023, 2024, 2025]


@dataclass(frozen=True)
class OutlierFilterCandidate:
    name: str
    description: str
    max_price: float | None = None
    max_unit_price: float | None = None
    min_area: float | None = None
    max_area: float | None = None
    max_age: float | None = None
    max_station_distance: float | None = None
    n_estimators: int = 180
    learning_rate: float = 0.075
    num_leaves: int = 31
    max_depth: int = 7
    min_child_samples: int = 80


CANDIDATES = [
    OutlierFilterCandidate("current_processed", "現行の前処理済みデータをそのまま使う"),
    OutlierFilterCandidate(
        "trim_luxury_unit_price",
        "極端な高平米単価を除外する",
        max_unit_price=2_000_000,
    ),
    OutlierFilterCandidate(
        "trim_high_price",
        "高額帯を除外する",
        max_price=100_000_000,
    ),
    OutlierFilterCandidate(
        "trim_area_edges",
        "極端に狭い/広い面積を除外する",
        min_area=25,
        max_area=100,
    ),
    OutlierFilterCandidate(
        "trim_operational_edges",
        "駅遠/築古を除外する",
        max_age=50,
        max_station_distance=60,
    ),
    OutlierFilterCandidate(
        "trim_strict_edges",
        "高額・高平米単価・面積端・駅遠・築古をまとめて除外する",
        max_price=100_000_000,
        max_unit_price=2_000_000,
        min_area=25,
        max_area=100,
        max_age=50,
        max_station_distance=60,
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest outlier filter candidates.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparisons"))
    parser.add_argument(
        "--train-start-years", nargs="+", type=int, default=DEFAULT_TRAIN_START_YEARS
    )
    parser.add_argument("--test-years", nargs="+", type=int, default=DEFAULT_TEST_YEARS)
    args = parser.parse_args()

    report = compare_outlier_filters(
        regions=args.regions,
        processed_dir=args.processed_dir,
        output_dir=args.output_dir,
        train_start_years=args.train_start_years,
        test_years=args.test_years,
    )
    print(render_markdown(report))
    return 0


def compare_outlier_filters(
    *,
    regions: list[str],
    processed_dir: Path,
    output_dir: Path,
    train_start_years: list[int],
    test_years: list[int],
) -> dict[str, object]:
    import pandas as pd

    frames = []
    for region in regions:
        path = processed_dir / f"{region}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Processed dataset not found: {path}")
        frame = pd.read_parquet(path)
        frame["source_region"] = region
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for train_start_year in train_start_years:
        scoped = data[data["transaction_year"] >= train_start_year].copy()
        for candidate in CANDIDATES:
            rows.append(
                _backtest_candidate(
                    candidate=candidate,
                    data=scoped,
                    train_start_year=train_start_year,
                    test_years=test_years,
                )
            )

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "regions": regions,
        "trainStartYears": train_start_years,
        "testYears": test_years,
        "rowCount": len(data),
        "candidates": rows,
    }
    save_json(report, output_dir / "outlier_filter_backtest.json")
    (output_dir / "outlier_filter_backtest.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    return report


def apply_outlier_filter(data, candidate: OutlierFilterCandidate):
    filtered = data.copy()
    price_per_sqm = filtered["price"] / filtered["area"]
    mask = filtered["price"].notna()
    if candidate.max_price is not None:
        mask &= filtered["price"] <= candidate.max_price
    if candidate.max_unit_price is not None:
        mask &= price_per_sqm <= candidate.max_unit_price
    if candidate.min_area is not None:
        mask &= filtered["area"] >= candidate.min_area
    if candidate.max_area is not None:
        mask &= filtered["area"] <= candidate.max_area
    if candidate.max_age is not None:
        mask &= filtered["age"] <= candidate.max_age
    if candidate.max_station_distance is not None:
        mask &= filtered["station_distance"] <= candidate.max_station_distance
    return filtered[mask].copy()


def _backtest_candidate(
    *,
    candidate: OutlierFilterCandidate,
    data,
    train_start_year: int,
    test_years: list[int],
) -> dict[str, object]:
    filtered = apply_outlier_filter(data, candidate)
    encoding = build_and_apply_category_dictionary(filtered, BASE_CATEGORICAL_FEATURES)
    encoded = encoding.dataframe
    folds = []
    started = time.perf_counter()

    for test_year in test_years:
        train_mask = encoded["transaction_year"] < test_year
        test_mask = encoded["transaction_year"] == test_year
        if not train_mask.any() or not test_mask.any():
            continue
        model = train_model(
            encoded.loc[train_mask, BASE_FEATURES],
            encoded.loc[train_mask, "price"],
            BASE_CATEGORICAL_FEATURES,
            _model_params(candidate),
        )
        predictions = model.predict(encoded.loc[test_mask, BASE_FEATURES])
        folds.append(
            {
                "testYear": test_year,
                "trainCount": int(train_mask.sum()),
                "testCount": int(test_mask.sum()),
                "metrics": calculate_metrics(encoded.loc[test_mask, "price"], predictions),
            }
        )

    return {
        "name": f"{candidate.name}_{train_start_year}",
        "candidate": candidate.name,
        "description": candidate.description,
        "trainStartYear": train_start_year,
        "originalRowCount": len(data),
        "filteredRowCount": len(filtered),
        "removedRowCount": len(data) - len(filtered),
        "removedShare": (len(data) - len(filtered)) / len(data) if len(data) else 0.0,
        "filters": _filter_summary(candidate),
        "trainingSeconds": time.perf_counter() - started,
        "folds": folds,
        "metrics": _weighted_metrics(folds),
    }


def _filter_summary(candidate: OutlierFilterCandidate) -> dict[str, float | None]:
    return {
        "maxPrice": candidate.max_price,
        "maxUnitPrice": candidate.max_unit_price,
        "minArea": candidate.min_area,
        "maxArea": candidate.max_area,
        "maxAge": candidate.max_age,
        "maxStationDistance": candidate.max_station_distance,
    }


def _model_params(candidate: OutlierFilterCandidate) -> dict[str, object]:
    return {
        "n_estimators": candidate.n_estimators,
        "learning_rate": candidate.learning_rate,
        "num_leaves": candidate.num_leaves,
        "max_depth": candidate.max_depth,
        "min_child_samples": candidate.min_child_samples,
        "random_state": 42,
        "n_jobs": -1,
    }


def _weighted_metrics(folds: list[dict[str, object]]) -> dict[str, float]:
    if not folds:
        return {"mae": float("nan"), "rmse": float("nan"), "mape": float("nan")}

    total = sum(fold["testCount"] for fold in folds)
    mae = sum(fold["metrics"]["mae"] * fold["testCount"] for fold in folds) / total
    rmse = (sum(fold["metrics"]["rmse"] ** 2 * fold["testCount"] for fold in folds) / total) ** 0.5
    mape = sum(fold["metrics"]["mape"] * fold["testCount"] for fold in folds) / total
    return {"mae": mae, "rmse": rmse, "mape": mape}


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 外れ値処理候補バックテスト",
        "",
        f"対象地域: {', '.join(report['regions'])}",
        f"学習開始年: {', '.join(str(year) for year in report['trainStartYears'])}",
        f"評価年: {', '.join(str(year) for year in report['testYears'])}",
        f"物件件数: {report['rowCount']:,}",
        "",
        "| 候補 | trainStart | 除外件数 | 除外率 | MAE | RMSE | MAPE | 学習秒 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["candidates"]:
        metrics = row["metrics"]
        lines.append(
            f"| {row['candidate']} | {row['trainStartYear']} | "
            f"{row['removedRowCount']:,} | {row['removedShare']:.2%} | "
            f"{metrics['mae']:,.0f} | {metrics['rmse']:,.0f} | {metrics['mape']:.2f}% | "
            f"{row['trainingSeconds']:.1f} |"
        )
    lines.append("")
    lines.append("## 候補の意味")
    for row in report["candidates"]:
        lines.append(f"- {row['candidate']}: {row['description']}")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
