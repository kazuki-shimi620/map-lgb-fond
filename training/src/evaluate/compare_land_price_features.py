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

from evaluate.compare_models import BASE_CATEGORICAL_FEATURES, BASE_FEATURES  # noqa: E402
from evaluate.metrics import calculate_metrics  # noqa: E402
from export.artifacts import export_onnx_if_available, save_json  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from features.land_prices import (  # noqa: E402
    LAND_PRICE_FEATURES,
    add_land_price_features,
    load_land_price_city_summary_csv,
    load_land_price_points_csv,
)
from train.model import train_model  # noqa: E402

DEFAULT_REGIONS = ["tokyo", "kanagawa", "saitama", "chiba"]
DEFAULT_TEST_YEARS = [2023, 2024, 2025]


@dataclass(frozen=True)
class LandPriceCandidate:
    name: str
    land_price_features: list[str]
    include_station: bool = True
    n_estimators: int = 180
    learning_rate: float = 0.075
    num_leaves: int = 31
    max_depth: int = 7
    min_child_samples: int = 80


CANDIDATES = [
    LandPriceCandidate("baseline", []),
    LandPriceCandidate("land_price", LAND_PRICE_FEATURES),
    LandPriceCandidate("baseline_no_station", [], include_station=False),
    LandPriceCandidate("land_price_no_station", LAND_PRICE_FEATURES, include_station=False),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest land price features.")
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument(
        "--land-price-points-csv",
        type=Path,
        default=Path("data/processed/land_prices/land_price_points.csv"),
    )
    parser.add_argument(
        "--land-price-city-summary-csv",
        type=Path,
        default=Path("data/processed/land_prices/land_price_city_summary.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/comparisons"))
    parser.add_argument("--train-start-year", type=int, default=2015)
    parser.add_argument("--test-years", nargs="+", type=int, default=DEFAULT_TEST_YEARS)
    args = parser.parse_args()

    report = compare_land_price_features(
        regions=args.regions,
        processed_dir=args.processed_dir,
        land_price_points_csv=args.land_price_points_csv,
        land_price_city_summary_csv=args.land_price_city_summary_csv,
        output_dir=args.output_dir,
        train_start_year=args.train_start_year,
        test_years=args.test_years,
    )
    print(render_markdown(report))
    return 0


def compare_land_price_features(
    *,
    regions: list[str],
    processed_dir: Path,
    land_price_points_csv: Path,
    land_price_city_summary_csv: Path,
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
    points = load_land_price_points_csv(land_price_points_csv)
    city_summary = load_land_price_city_summary_csv(land_price_city_summary_csv)
    data = add_land_price_features(data, points, city_summary)

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
            output_dir=output_dir / "land_price_feature_models",
        )
        rows.append(row)

    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "regions": regions,
        "trainStartYear": train_start_year,
        "testYears": test_years,
        "rowCount": len(data),
        "landPricePointsCsv": str(land_price_points_csv),
        "landPricePointCount": len(points),
        "landPriceCitySummaryCsv": str(land_price_city_summary_csv),
        "landPriceCitySummaryCount": len(city_summary),
        "matchedRowCount": int(data["has_land_price_data"].sum()),
        "candidates": rows,
    }
    save_json(report, output_dir / "land_price_feature_backtest.json")
    (output_dir / "land_price_feature_backtest.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    return report


def _backtest_candidate(
    *,
    candidate: LandPriceCandidate,
    data,
    test_years: list[int],
) -> dict[str, object]:
    features, categorical_features = feature_lists(candidate)
    encoding = build_and_apply_category_dictionary(data, categorical_features)
    encoded = encoding.dataframe
    folds = []
    started = time.perf_counter()
    for test_year in test_years:
        train_mask = encoded["transaction_year"] < test_year
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
        "landPriceFeatures": candidate.land_price_features,
        "includeStation": candidate.include_station,
        "trainingSeconds": time.perf_counter() - started,
        "folds": folds,
        "metrics": _weighted_metrics(folds),
        "featureImportance": _average_feature_importance(folds),
    }


def feature_lists(candidate: LandPriceCandidate) -> tuple[list[str], list[str]]:
    features = BASE_FEATURES + candidate.land_price_features
    categorical_features = list(BASE_CATEGORICAL_FEATURES)
    if not candidate.include_station:
        features.remove("station")
        categorical_features.remove("station")
    return features, categorical_features


def _export_deployment_artifacts(
    *,
    candidate: LandPriceCandidate,
    data,
    output_dir: Path,
) -> dict[str, object]:
    features, categorical_features = feature_lists(candidate)
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


def _model_params(candidate: LandPriceCandidate) -> dict[str, object]:
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
    rmse = (
        sum(fold["metrics"]["rmse"] ** 2 * fold["testCount"] for fold in folds) / total
    ) ** 0.5
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
        "# 地価特徴量バックテスト",
        "",
        f"対象地域: {', '.join(report['regions'])}",
        f"学習開始年: {report['trainStartYear']}",
        f"評価年: {', '.join(str(year) for year in report['testYears'])}",
        f"物件件数: {report['rowCount']:,}",
        f"地価ポイント件数: {report['landPricePointCount']:,}",
        f"地価市区町村集計件数: {report['landPriceCitySummaryCount']:,}",
        f"地価特徴量マッチ件数: {report['matchedRowCount']:,}",
        "",
        "| 候補 | station | 地価 | MAE | RMSE | MAPE | ONNX | gzip | 辞書gzip | 学習秒 |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report["candidates"]:
        metrics = row["metrics"]
        artifacts = row["deploymentArtifacts"]
        lines.append(
            f"| {row['name']} | {'yes' if row['includeStation'] else 'no'} | "
            f"{_features_label(row['landPriceFeatures'])} | "
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


def _features_label(features: list[str]) -> str:
    return ", ".join(features) if features else "-"


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / 1024 / 1024:.2f} MB"


if __name__ == "__main__":
    raise SystemExit(main())
