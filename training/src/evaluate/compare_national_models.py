from __future__ import annotations

import argparse
import gzip
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.regions import (  # noqa: E402
    build_cluster_by_prefecture,
    validate_cluster_coverage,
)
from evaluate.compare_models import (  # noqa: E402
    BASE_CATEGORICAL_FEATURES,
    BASE_FEATURES,
    Candidate,
    _format_bytes,
)
from evaluate.metrics import calculate_metrics  # noqa: E402
from export.artifacts import export_onnx_if_available, save_json  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from train.model import train_model  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare nationwide and regional browser models")
    parser.add_argument("--input", type=Path, default=Path("data/processed/national.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparisons/national"))
    parser.add_argument("--train-start-year", type=int, default=2005)
    parser.add_argument("--test-year", type=int, default=2025)
    args = parser.parse_args()

    report = compare_national_models(
        input_path=args.input,
        output_dir=args.output_dir,
        train_start_year=args.train_start_year,
        test_year=args.test_year,
    )
    print(render_national_markdown(report))
    return 0


def compare_national_models(
    *, input_path: Path, output_dir: Path, train_start_year: int, test_year: int
) -> dict[str, object]:
    import pandas as pd

    data = pd.read_parquet(input_path)
    data = data[
        (data["transaction_year"] >= train_start_year) & (data["transaction_year"] <= test_year)
    ].copy()
    train_mask = data["transaction_year"] < test_year
    test_mask = data["transaction_year"] == test_year
    validate_cluster_coverage(data["prefecture"].unique())
    cluster_by_prefecture = build_cluster_by_prefecture()
    data["model_group"] = data["prefecture"].map(cluster_by_prefecture)
    data["nationwide_group"] = "nationwide"
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = [
        (
            Candidate("nationwide_balanced_220", 220, 0.065, 31, 7, 50),
            "nationwide_group",
        ),
        (Candidate("regional_balanced_220", 220, 0.065, 31, 7, 50), "model_group"),
        (Candidate("regional_compact_160", 160, 0.08, 24, 6, 80), "model_group"),
    ]
    rows = [
        _train_grouped_candidate(
            candidate=candidate,
            group_column=group_column,
            data=data,
            test_year=test_year,
            output_dir=output_dir,
        )
        for candidate, group_column in candidates
    ]
    correction_candidate = Candidate("nationwide_balanced_220", 220, 0.065, 31, 7, 50)
    rows.extend(
        [
            _train_residual_correction_candidate(
                name="nationwide_regional_residual_220",
                candidate=correction_candidate,
                correction_column="model_group",
                data=data,
                test_year=test_year,
                output_dir=output_dir,
            ),
            _train_residual_correction_candidate(
                name="nationwide_prefecture_residual_220",
                candidate=correction_candidate,
                correction_column="prefecture",
                data=data,
                test_year=test_year,
                output_dir=output_dir,
            ),
        ]
    )
    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "trainStartYear": train_start_year,
        "testYear": test_year,
        "trainCount": int(train_mask.sum()),
        "testCount": int(test_mask.sum()),
        "prefectureCount": int(data["prefecture"].nunique()),
        "stationCount": int(data["station"].nunique()),
        "candidates": rows,
    }
    save_json(report, output_dir / "national_model_comparison.json")
    (output_dir / "national_model_comparison.md").write_text(
        render_national_markdown(report), encoding="utf-8"
    )
    return report


def _train_grouped_candidate(
    *, candidate: Candidate, group_column: str, data, test_year: int, output_dir: Path
):
    all_targets = []
    all_predictions = []
    group_rows = []
    training_seconds = 0.0

    for group in sorted(data[group_column].unique()):
        group_mask = data[group_column] == group
        group_data = data[group_mask].copy()
        group_train_mask = group_data["transaction_year"] < test_year
        group_test_mask = ~group_train_mask
        encoding = build_and_apply_category_dictionary(group_data, BASE_CATEGORICAL_FEATURES)
        encoded = encoding.dataframe
        params = {
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
            encoded.loc[group_train_mask, BASE_FEATURES],
            encoded.loc[group_train_mask, "price"],
            BASE_CATEGORICAL_FEATURES,
            params,
        )
        training_seconds += time.perf_counter() - started
        targets = encoded.loc[group_test_mask, "price"]
        predictions = model.predict(encoded.loc[group_test_mask, BASE_FEATURES])
        all_targets.append(targets.to_numpy())
        all_predictions.append(predictions)

        group_dir = output_dir / candidate.name
        group_dir.mkdir(parents=True, exist_ok=True)
        onnx_path = group_dir / f"{group}.onnx"
        export_onnx_if_available(model, len(BASE_FEATURES), onnx_path)
        save_json(encoding.dictionary, group_dir / f"{group}_categories.json")
        onnx_bytes = onnx_path.stat().st_size
        gzip_bytes = len(gzip.compress(onnx_path.read_bytes(), mtime=0))
        group_rows.append(
            {
                "group": group,
                "trainCount": int(group_train_mask.sum()),
                "testCount": int(group_test_mask.sum()),
                "onnxBytes": onnx_bytes,
                "onnxGzipBytes": gzip_bytes,
                "metrics": calculate_metrics(targets, predictions),
            }
        )

    targets = np.concatenate(all_targets)
    predictions = np.concatenate(all_predictions)
    return {
        "name": candidate.name,
        "modelCount": len(group_rows),
        "onnxBytes": sum(row["onnxBytes"] for row in group_rows),
        "maxOnnxBytes": max(row["onnxBytes"] for row in group_rows),
        "onnxGzipBytes": sum(row["onnxGzipBytes"] for row in group_rows),
        "maxOnnxGzipBytes": max(row["onnxGzipBytes"] for row in group_rows),
        "trainingSeconds": training_seconds,
        "metrics": calculate_metrics(targets, predictions),
        "groups": group_rows,
    }


def _train_residual_correction_candidate(
    *,
    name: str,
    candidate: Candidate,
    correction_column: str,
    data,
    test_year: int,
    output_dir: Path,
):
    group_train_mask = data["transaction_year"] < test_year
    group_test_mask = ~group_train_mask
    encoding = build_and_apply_category_dictionary(data, BASE_CATEGORICAL_FEATURES)
    encoded = encoding.dataframe
    params = {
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
        encoded.loc[group_train_mask, BASE_FEATURES],
        encoded.loc[group_train_mask, "price"],
        BASE_CATEGORICAL_FEATURES,
        params,
    )
    training_seconds = time.perf_counter() - started

    train_predictions = model.predict(encoded.loc[group_train_mask, BASE_FEATURES])
    corrections = build_residual_corrections(
        groups=data.loc[group_train_mask, correction_column],
        residuals=encoded.loc[group_train_mask, "price"].to_numpy() - train_predictions,
    )
    test_predictions = model.predict(encoded.loc[group_test_mask, BASE_FEATURES])
    corrected_predictions = test_predictions + map_residual_corrections(
        data.loc[group_test_mask, correction_column],
        corrections,
    )

    group_dir = output_dir / name
    group_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = group_dir / "nationwide.onnx"
    corrections_path = group_dir / "residual_corrections.json"
    export_onnx_if_available(model, len(BASE_FEATURES), onnx_path)
    save_json(encoding.dictionary, group_dir / "nationwide_categories.json")
    save_json(corrections, corrections_path)

    onnx_bytes = onnx_path.stat().st_size
    gzip_bytes = len(gzip.compress(onnx_path.read_bytes(), mtime=0))
    correction_bytes = corrections_path.stat().st_size
    correction_gzip_bytes = len(gzip.compress(corrections_path.read_bytes(), mtime=0))
    return {
        "name": name,
        "modelCount": 1,
        "onnxBytes": onnx_bytes + correction_bytes,
        "maxOnnxBytes": onnx_bytes,
        "onnxGzipBytes": gzip_bytes + correction_gzip_bytes,
        "maxOnnxGzipBytes": gzip_bytes,
        "correctionBytes": correction_bytes,
        "correctionGzipBytes": correction_gzip_bytes,
        "trainingSeconds": training_seconds,
        "metrics": calculate_metrics(
            encoded.loc[group_test_mask, "price"],
            corrected_predictions,
        ),
        "groups": [
            {
                "group": group,
                "correction": correction,
            }
            for group, correction in corrections["groups"].items()
        ],
    }


def build_residual_corrections(*, groups, residuals, shrinkage_count: int = 2000):
    import pandas as pd

    correction_df = pd.DataFrame({"group": groups.astype(str).to_numpy(), "residual": residuals})
    fallback = float(correction_df["residual"].mean())
    rows = correction_df.groupby("group")["residual"].agg(["mean", "count"]).reset_index()
    corrections: dict[str, float] = {}
    for row in rows.itertuples(index=False):
        weight = float(row.count / (row.count + shrinkage_count))
        corrections[str(row.group)] = float(row.mean * weight + fallback * (1.0 - weight))
    return {
        "schemaVersion": 1,
        "fallback": fallback,
        "shrinkageCount": shrinkage_count,
        "groups": corrections,
    }


def map_residual_corrections(groups, corrections) -> np.ndarray:
    fallback = float(corrections["fallback"])
    correction_by_group = corrections["groups"]
    return np.array(
        [float(correction_by_group.get(str(group), fallback)) for group in groups],
        dtype=float,
    )


def render_national_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 全国モデル比較",
        "",
        f"学習期間: {report['trainStartYear']}〜{int(report['testYear']) - 1}",
        f"評価年: {report['testYear']}",
        f"学習件数: {report['trainCount']:,}",
        f"評価件数: {report['testCount']:,}",
        "",
        "| 候補 | モデル数 | MAE | MAPE | 合計容量 | 最大1モデル | 補正JSON | gzip最大 | 学習秒 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["candidates"]:
        metrics = row["metrics"]
        correction_bytes = row.get("correctionBytes", 0)
        lines.append(
            f"| {row['name']} | {row['modelCount']} | {metrics['mae']:,.0f} | "
            f"{metrics['mape']:.2f}% | {_format_bytes(row['onnxBytes'])} | "
            f"{_format_bytes(row['maxOnnxBytes'])} | {_format_bytes(correction_bytes)} | "
            f"{_format_bytes(row['maxOnnxGzipBytes'])} | {row['trainingSeconds']:.1f} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
