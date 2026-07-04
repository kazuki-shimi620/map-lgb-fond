from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluate.metrics import calculate_metrics  # noqa: E402
from export.artifacts import export_onnx_if_available, save_json  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from train.model import train_model  # noqa: E402

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]
BASE_FEATURES = [
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
BASE_CATEGORICAL_FEATURES = [
    "prefecture",
    "municipality",
    "station",
    "room_layout",
    "building_type",
]


@dataclass(frozen=True)
class Candidate:
    name: str
    n_estimators: int
    learning_rate: float
    num_leaves: int
    max_depth: int
    min_child_samples: int
    include_station: bool = True


CANDIDATES = [
    Candidate("capital_shared_300", 300, 0.05, 31, -1, 20),
    Candidate("capital_balanced_220", 220, 0.065, 31, 7, 50),
    Candidate("capital_compact_160", 160, 0.08, 24, 6, 80),
    Candidate("capital_compact_no_station_160", 160, 0.08, 24, 6, 80, False),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare browser model accuracy and ONNX size")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparisons"))
    parser.add_argument("--train-start-year", type=int, default=2005)
    parser.add_argument("--test-year", type=int, default=2025)
    args = parser.parse_args()

    report = compare_models(
        regions=args.regions,
        processed_dir=args.processed_dir,
        public_dir=args.public_dir,
        output_dir=args.output_dir,
        train_start_year=args.train_start_year,
        test_year=args.test_year,
    )
    print(render_markdown(report))
    return 0


def compare_models(
    *,
    regions: list[str],
    processed_dir: Path,
    public_dir: Path,
    output_dir: Path,
    train_start_year: int,
    test_year: int,
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
    data = data[
        (data["transaction_year"] >= train_start_year)
        & (data["transaction_year"] <= test_year)
    ].copy()
    train_mask = data["transaction_year"] < test_year
    test_mask = data["transaction_year"] == test_year
    if not train_mask.any() or not test_mask.any():
        raise ValueError("Both training rows and test-year rows are required")

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [_published_baseline(regions, public_dir)]
    for candidate in CANDIDATES:
        rows.append(
            _train_candidate(
                candidate=candidate,
                data=data,
                train_mask=train_mask,
                test_mask=test_mask,
                output_dir=output_dir,
            )
        )

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "regions": regions,
        "trainStartYear": train_start_year,
        "testYear": test_year,
        "trainCount": int(train_mask.sum()),
        "testCount": int(test_mask.sum()),
        "candidates": rows,
    }
    save_json(report, output_dir / "capital_model_comparison.json")
    (output_dir / "capital_model_comparison.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    return report


def _published_baseline(regions: list[str], public_dir: Path) -> dict[str, object]:
    metrics = []
    total_bytes = 0
    total_gzip_bytes = 0
    for region in regions:
        metadata_path = public_dir / "metadata" / f"{region}_latest_metadata.json"
        model_path = public_dir / "models" / f"{region}_latest.onnx"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        evaluation = metadata["evaluation"]
        metrics.append(
            {
                "region": region,
                "testCount": int(evaluation["testCount"]),
                **evaluation["metrics"],
            }
        )
        total_bytes += model_path.stat().st_size
        total_gzip_bytes += len(gzip.compress(model_path.read_bytes(), mtime=0))

    test_count = sum(row["testCount"] for row in metrics)
    mae = sum(row["mae"] * row["testCount"] for row in metrics) / test_count
    rmse = (
        sum(row["rmse"] ** 2 * row["testCount"] for row in metrics) / test_count
    ) ** 0.5
    mape = sum(row["mape"] * row["testCount"] for row in metrics) / test_count
    return {
        "name": "published_prefecture_models",
        "modelCount": len(regions),
        "onnxBytes": total_bytes,
        "onnxGzipBytes": total_gzip_bytes,
        "trainingSeconds": None,
        "metrics": {"mae": mae, "rmse": rmse, "mape": mape},
        "regionMetrics": metrics,
    }


def _train_candidate(*, candidate: Candidate, data, train_mask, test_mask, output_dir: Path):
    features = list(BASE_FEATURES)
    categorical_features = list(BASE_CATEGORICAL_FEATURES)
    if not candidate.include_station:
        features.remove("station")
        categorical_features.remove("station")

    encoding = build_and_apply_category_dictionary(data, categorical_features)
    encoded = encoding.dataframe
    model_params = {
        "n_estimators": candidate.n_estimators,
        "learning_rate": candidate.learning_rate,
        "num_leaves": candidate.num_leaves,
        "max_depth": candidate.max_depth,
        "min_child_samples": candidate.min_child_samples,
        "random_state": 42,
        "n_jobs": -1,
    }
    started = time.perf_counter()
    model = train_model(
        encoded.loc[train_mask, features],
        encoded.loc[train_mask, "price"],
        categorical_features,
        model_params,
    )
    training_seconds = time.perf_counter() - started
    predictions = model.predict(encoded.loc[test_mask, features])
    metrics = calculate_metrics(encoded.loc[test_mask, "price"], predictions)

    region_metrics = []
    test_regions = encoded.loc[test_mask, "source_region"]
    test_targets = encoded.loc[test_mask, "price"]
    for region in sorted(test_regions.unique()):
        region_mask = test_regions == region
        region_metrics.append(
            {
                "region": region,
                "testCount": int(region_mask.sum()),
                **calculate_metrics(test_targets[region_mask], predictions[region_mask.to_numpy()]),
            }
        )

    onnx_path = output_dir / f"{candidate.name}.onnx"
    export_onnx_if_available(model, len(features), onnx_path)
    onnx_bytes = onnx_path.stat().st_size if onnx_path.exists() else None
    onnx_gzip_bytes = (
        len(gzip.compress(onnx_path.read_bytes(), mtime=0)) if onnx_path.exists() else None
    )
    save_json(encoding.dictionary, output_dir / f"{candidate.name}_categories.json")
    return {
        "name": candidate.name,
        "modelCount": 1,
        "onnxBytes": onnx_bytes,
        "onnxGzipBytes": onnx_gzip_bytes,
        "trainingSeconds": training_seconds,
        "features": features,
        "modelParams": model_params,
        "metrics": metrics,
        "regionMetrics": region_metrics,
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 首都圏モデル比較",
        "",
        f"学習期間: {report['trainStartYear']}〜{int(report['testYear']) - 1}",
        f"評価年: {report['testYear']}",
        f"学習件数: {report['trainCount']:,}",
        f"評価件数: {report['testCount']:,}",
        "",
        "| 候補 | モデル数 | MAE | RMSE | MAPE | ONNX容量 | gzip容量 | 学習秒 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["candidates"]:
        metrics = row["metrics"]
        size = _format_bytes(row["onnxBytes"])
        gzip_size = _format_bytes(row["onnxGzipBytes"])
        seconds = "-" if row["trainingSeconds"] is None else f"{row['trainingSeconds']:.1f}"
        lines.append(
            f"| {row['name']} | {row['modelCount']} | {metrics['mae']:,.0f} | "
            f"{metrics['rmse']:,.0f} | {metrics['mape']:.2f}% | {size} | {gzip_size} | "
            f"{seconds} |"
        )
    lines.append("")
    return "\n".join(lines)


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    return f"{value / 1024 / 1024:.2f} MB"


if __name__ == "__main__":
    raise SystemExit(main())
