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
from features.station_passengers import (  # noqa: E402
    STATION_PASSENGER_CATEGORICAL_FEATURES,
    add_station_passenger_features,
    load_station_passengers_csv,
)
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
STATION_SCALE_NUMERIC_FEATURES = [
    "station_passenger_log",
    "station_line_count",
    "station_operator_count",
    "effective_station_scale",
    "has_station_passenger_data",
]
STATION_SCALE_NUMERIC_FEATURES_WITHOUT_COVERAGE_FLAG = [
    feature for feature in STATION_SCALE_NUMERIC_FEATURES if feature != "has_station_passenger_data"
]
STATION_SCALE_WITH_AGE_FEATURES = STATION_SCALE_NUMERIC_FEATURES + ["station_passenger_age"]


@dataclass(frozen=True)
class StationPassengerCandidate:
    name: str
    station_passenger_features: list[str]
    include_station: bool = True
    include_station_rank: bool = False
    n_estimators: int = 180
    learning_rate: float = 0.075
    num_leaves: int = 31
    max_depth: int = 7
    min_child_samples: int = 80


CANDIDATES = [
    StationPassengerCandidate("baseline_2015_window", []),
    StationPassengerCandidate("station_scale_numeric", STATION_SCALE_NUMERIC_FEATURES),
    StationPassengerCandidate(
        "station_scale_numeric_no_coverage_flag",
        STATION_SCALE_NUMERIC_FEATURES_WITHOUT_COVERAGE_FLAG,
    ),
    StationPassengerCandidate(
        "station_scale_numeric_with_age",
        STATION_SCALE_WITH_AGE_FEATURES,
    ),
    StationPassengerCandidate(
        "station_scale_numeric_rank",
        STATION_SCALE_NUMERIC_FEATURES,
        include_station_rank=True,
    ),
    StationPassengerCandidate("baseline_no_station", [], include_station=False),
    StationPassengerCandidate(
        "station_scale_numeric_no_station",
        STATION_SCALE_NUMERIC_FEATURES,
        include_station=False,
    ),
    StationPassengerCandidate(
        "station_scale_numeric_rank_no_station",
        STATION_SCALE_NUMERIC_FEATURES,
        include_station=False,
        include_station_rank=True,
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest station passenger features.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--station-passengers-csv",
        type=Path,
        default=Path("data/processed/station_passengers/station_groups.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparisons"))
    parser.add_argument("--train-start-year", type=int, default=2015)
    parser.add_argument("--test-years", nargs="+", type=int, default=[2023, 2024, 2025])
    args = parser.parse_args()

    report = compare_station_passenger_features(
        regions=args.regions,
        processed_dir=args.processed_dir,
        station_passengers_csv=args.station_passengers_csv,
        output_dir=args.output_dir,
        train_start_year=args.train_start_year,
        test_years=args.test_years,
    )
    print(render_markdown(report))
    return 0


def compare_station_passenger_features(
    *,
    regions: list[str],
    processed_dir: Path,
    station_passengers_csv: Path,
    output_dir: Path,
    train_start_year: int,
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
    data = data[data["transaction_year"] >= train_start_year].copy()
    stations = load_station_passengers_csv(station_passengers_csv)
    data = add_station_passenger_features(data, stations)

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for candidate in CANDIDATES:
        row = _backtest_candidate(
            candidate=candidate,
            data=data,
            test_years=test_years,
        )
        row["deploymentArtifacts"] = _export_deployment_artifacts(
            candidate=candidate,
            data=data,
            output_dir=output_dir / "station_passenger_feature_models",
        )
        rows.append(row)

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "regions": regions,
        "trainStartYear": train_start_year,
        "testYears": test_years,
        "rowCount": len(data),
        "stationPassengersCsv": str(station_passengers_csv),
        "stationPassengerCount": len(stations),
        "matchedRowCount": int(data["has_station_passenger_data"].sum()),
        "candidates": rows,
    }
    save_json(report, output_dir / "station_passenger_feature_backtest.json")
    (output_dir / "station_passenger_feature_backtest.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    return report


def _backtest_candidate(*, candidate: StationPassengerCandidate, data, test_years: list[int]):
    features, categorical_features = _feature_lists(candidate)
    encoding = build_and_apply_category_dictionary(data, categorical_features)
    encoded = encoding.dataframe
    folds = []
    started = time.perf_counter()
    for test_year in test_years:
        train_mask = (encoded["transaction_year"] >= encoded["transaction_year"].min()) & (
            encoded["transaction_year"] < test_year
        )
        test_mask = encoded["transaction_year"] == test_year
        if not train_mask.any() or not test_mask.any():
            continue
        model = train_model(
            encoded.loc[train_mask, features],
            encoded.loc[train_mask, "price"],
            categorical_features,
            _model_params(candidate),
        )
        predictions = model.predict(encoded.loc[test_mask, features])
        folds.append(
            {
                "testYear": test_year,
                "trainCount": int(train_mask.sum()),
                "testCount": int(test_mask.sum()),
                "metrics": calculate_metrics(encoded.loc[test_mask, "price"], predictions),
                "featureImportance": _feature_importance(model, features),
            }
        )
    return {
        "name": candidate.name,
        "features": features,
        "stationPassengerFeatures": candidate.station_passenger_features,
        "includeStation": candidate.include_station,
        "includeStationRank": candidate.include_station_rank,
        "trainingSeconds": time.perf_counter() - started,
        "folds": folds,
        "metrics": _weighted_metrics(folds),
        "featureImportance": _average_feature_importance(folds),
    }


def _export_deployment_artifacts(
    *, candidate: StationPassengerCandidate, data, output_dir: Path
) -> dict[str, object]:
    features, categorical_features = _feature_lists(candidate)
    encoding = build_and_apply_category_dictionary(data, categorical_features)
    encoded = encoding.dataframe
    model = train_model(
        encoded[features],
        encoded["price"],
        categorical_features,
        _model_params(candidate),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = output_dir / f"{candidate.name}.onnx"
    categories_path = output_dir / f"{candidate.name}_categories.json"
    export_onnx_if_available(model, len(features), onnx_path)
    save_json(encoding.dictionary, categories_path)

    categories_json = json.dumps(encoding.dictionary, ensure_ascii=False).encode("utf-8")
    return {
        "onnxPath": str(onnx_path),
        "onnxBytes": onnx_path.stat().st_size if onnx_path.exists() else None,
        "onnxGzipBytes": _gzip_file_size(onnx_path) if onnx_path.exists() else None,
        "categoriesPath": str(categories_path),
        "categoriesBytes": categories_path.stat().st_size if categories_path.exists() else None,
        "categoriesGzipBytes": _gzip_bytes_size(categories_json),
    }


def _feature_lists(candidate: StationPassengerCandidate) -> tuple[list[str], list[str]]:
    features = BASE_FEATURES + candidate.station_passenger_features
    categorical_features = list(BASE_CATEGORICAL_FEATURES)
    if candidate.include_station_rank:
        features += STATION_PASSENGER_CATEGORICAL_FEATURES
        categorical_features += STATION_PASSENGER_CATEGORICAL_FEATURES
    if not candidate.include_station:
        features.remove("station")
        categorical_features.remove("station")
    return features, categorical_features


def _model_params(candidate: StationPassengerCandidate) -> dict[str, object]:
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


def _feature_importance(model, features: list[str]) -> list[dict[str, object]]:
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return []
    rows = [
        {"feature": feature, "importance": float(importance)}
        for feature, importance in zip(features, importances, strict=False)
    ]
    return sorted(rows, key=lambda row: row["importance"], reverse=True)


def _average_feature_importance(folds: list[dict[str, object]]) -> list[dict[str, object]]:
    totals: dict[str, float] = {}
    for fold in folds:
        for row in fold["featureImportance"]:
            totals[row["feature"]] = totals.get(row["feature"], 0.0) + row["importance"]
    if not folds:
        return []
    averaged = [
        {"feature": feature, "importance": importance / len(folds)}
        for feature, importance in totals.items()
    ]
    return sorted(averaged, key=lambda row: row["importance"], reverse=True)


def _gzip_file_size(path: Path) -> int:
    return len(gzip.compress(path.read_bytes(), mtime=0))


def _gzip_bytes_size(value: bytes) -> int:
    return len(gzip.compress(value, mtime=0))


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 駅乗降客数特徴量バックテスト",
        "",
        f"対象地域: {', '.join(report['regions'])}",
        f"学習開始年: {report['trainStartYear']}",
        f"評価年: {', '.join(str(year) for year in report['testYears'])}",
        f"物件件数: {report['rowCount']:,}",
        f"駅件数: {report['stationPassengerCount']:,}",
        f"駅乗降客数マッチ件数: {report['matchedRowCount']:,}",
        "",
        "| 候補 | 駅乗降客数特徴量 | station | rank | MAE | RMSE | MAPE | "
        "ONNX | gzip | 辞書gzip | 学習秒 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["candidates"]:
        metrics = row["metrics"]
        artifacts = row["deploymentArtifacts"]
        station_features = ", ".join(row["stationPassengerFeatures"]) or "-"
        lines.append(
            f"| {row['name']} | {station_features} | "
            f"{'yes' if row['includeStation'] else 'no'} | "
            f"{'yes' if row['includeStationRank'] else 'no'} | "
            f"{metrics['mae']:,.0f} | {metrics['rmse']:,.0f} | {metrics['mape']:.2f}% | "
            f"{_format_bytes(artifacts['onnxBytes'])} | "
            f"{_format_bytes(artifacts['onnxGzipBytes'])} | "
            f"{_format_bytes(artifacts['categoriesGzipBytes'])} | "
            f"{row['trainingSeconds']:.1f} |"
        )
    lines.append("")
    lines.append("## 上位特徴量")
    for row in report["candidates"]:
        top_features = ", ".join(
            f"{item['feature']}={item['importance']:.0f}" for item in row["featureImportance"][:8]
        )
        lines.append(f"- {row['name']}: {top_features}")
    lines.append("")
    return "\n".join(lines)


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / 1024 / 1024:.2f} MB"


if __name__ == "__main__":
    raise SystemExit(main())
