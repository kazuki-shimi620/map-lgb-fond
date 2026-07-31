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
from features.nearby_pois import (  # noqa: E402
    POI_CATEGORIES,
    add_nearby_poi_features,
    feature_names,
    load_nearby_pois_json,
)
from train.model import train_model  # noqa: E402


@dataclass(frozen=True)
class PoiCandidate:
    name: str
    categories: tuple[str, ...]
    include_hazards: bool = False


CANDIDATES = [
    PoiCandidate("baseline", ()),
    PoiCandidate("commercial", ("commercial_facility",)),
    PoiCandidate("cinema", ("cinema",)),
    PoiCandidate("museum", ("museum",)),
    PoiCandidate("hot_spring", ("hot_spring",)),
    PoiCandidate("all_nearby_pois", POI_CATEGORIES),
    PoiCandidate("hazards", (), True),
    PoiCandidate("all_nearby_pois_hazards", POI_CATEGORIES, True),
]
HAZARD_FEATURES = ["flood_risk_level", "landslide_risk_level"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run nearby POI model features.")
    parser.add_argument("--regions", nargs="+", default=["tokyo"])
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("data/processed/with_address_coordinates")
    )
    parser.add_argument(
        "--nearby-facilities-json",
        type=Path,
        default=Path("../frontend/public/facilities/nearby_facilities.json"),
    )
    parser.add_argument(
        "--hazard-point-dir",
        type=Path,
        default=Path("data/processed/hazard_point_features"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs/comparisons/nearby_poi_dry_run")
    )
    parser.add_argument("--sample-size", type=int, default=30_000)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--train-start-year", type=int, default=2015)
    parser.add_argument("--test-years", nargs="+", type=int, default=[2023, 2024, 2025])
    args = parser.parse_args()

    report = compare_nearby_poi_features(
        regions=args.regions,
        processed_dir=args.processed_dir,
        nearby_facilities_json=args.nearby_facilities_json,
        hazard_point_dir=args.hazard_point_dir,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        random_seed=args.random_seed,
        train_start_year=args.train_start_year,
        test_years=args.test_years,
    )
    print(render_markdown(report))
    return 0


def compare_nearby_poi_features(
    *,
    regions: list[str],
    processed_dir: Path,
    nearby_facilities_json: Path,
    hazard_point_dir: Path,
    output_dir: Path,
    sample_size: int,
    random_seed: int,
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
    data = data[
        (data["transaction_year"] >= train_start_year)
        & data["lat"].notna()
        & data["lon"].notna()
    ].copy()
    source_row_count = len(data)
    if 0 < sample_size < len(data):
        data = data.sample(n=sample_size, random_state=random_seed)

    pois = load_nearby_pois_json(nearby_facilities_json)
    started = time.perf_counter()
    data = add_nearby_poi_features(data, pois)
    hazard_features = _load_hazard_features(hazard_point_dir)
    data = data.merge(hazard_features, on=["lat", "lon"], how="left")
    data[HAZARD_FEATURES] = data[HAZARD_FEATURES].fillna(0.0)
    feature_seconds = time.perf_counter() - started

    rows = [_backtest_candidate(candidate, data, test_years) for candidate in CANDIDATES]
    baseline = next(row for row in rows if row["candidate"] == "baseline")
    for row in rows:
        row["maeDelta"] = row["metrics"]["mae"] - baseline["metrics"]["mae"]
        row["rmseDelta"] = row["metrics"]["rmse"] - baseline["metrics"]["rmse"]
        row["mapeDelta"] = row["metrics"]["mape"] - baseline["metrics"]["mape"]

    category_counts = {
        category: int((pois["category_id"] == category).sum()) for category in POI_CATEGORIES
    }
    report = {
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "exploratoryOnly": True,
        "leakageWarning": (
            "POIに開業・閉館履歴がないため、現在の施設座標を過去取引へ付与した探索比較。"
            "本番採用には時点整合データが必要。"
        ),
        "regions": regions,
        "trainStartYear": train_start_year,
        "testYears": test_years,
        "sourceRowCount": source_row_count,
        "sampleSize": len(data),
        "randomSeed": random_seed,
        "trainCount": int((data["transaction_year"] < min(test_years)).sum()),
        "testCount": int(data["transaction_year"].isin(test_years).sum()),
        "nearbyFacilitiesJson": str(nearby_facilities_json),
        "poiCounts": category_counts,
        "featureGenerationSeconds": feature_seconds,
        "hazardPointDir": str(hazard_point_dir),
        "hazardEnabled": not hazard_features.empty,
        "hazardStatus": (
            f"地点別数値CSVを検出（{len(hazard_features):,}座標）"
            if not hazard_features.empty
            else "地図用ラスタのみで地点別数値CSVが未作成のため比較対象外"
        ),
        "candidates": rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json(report, output_dir / "nearby_poi_dry_run.json")
    (output_dir / "nearby_poi_dry_run.md").write_text(
        render_markdown(report), encoding="utf-8"
    )
    return report


def _backtest_candidate(
    candidate: PoiCandidate, data, test_years: list[int]
) -> dict[str, object]:
    features = list(BASE_FEATURES)
    for category in candidate.categories:
        features.extend(feature_names(category))
    if candidate.include_hazards:
        features.extend(HAZARD_FEATURES)
    encoding = build_and_apply_category_dictionary(data, list(BASE_CATEGORICAL_FEATURES))
    encoded = encoding.dataframe

    started = time.perf_counter()
    folds = []
    for test_year in test_years:
        train_mask = encoded["transaction_year"] < test_year
        test_mask = encoded["transaction_year"] == test_year
        if not train_mask.any() or not test_mask.any():
            continue
        model = train_model(
            encoded.loc[train_mask, features],
            encoded.loc[train_mask, "price"],
            list(BASE_CATEGORICAL_FEATURES),
            {
                "n_estimators": 120,
                "learning_rate": 0.075,
                "num_leaves": 31,
                "max_depth": 7,
                "min_child_samples": 80,
                "random_state": 42,
                "n_jobs": -1,
            },
        )
        predictions = model.predict(encoded.loc[test_mask, features])
        test_rows = encoded.loc[test_mask]
        per_region = {}
        for region in sorted(test_rows["source_region"].unique()):
            region_mask = test_rows["source_region"].eq(region).to_numpy()
            per_region[region] = {
                "testCount": int(region_mask.sum()),
                "metrics": calculate_metrics(
                    test_rows.loc[region_mask, "price"], predictions[region_mask]
                ),
            }
        folds.append(
            {
                "testYear": test_year,
                "trainCount": int(train_mask.sum()),
                "testCount": int(test_mask.sum()),
                "metrics": calculate_metrics(test_rows["price"], predictions),
                "perRegion": per_region,
                "featureImportance": _feature_importance(model, features),
            }
        )
    if not folds:
        raise ValueError(f"train/test rows are required for test years {test_years}")
    return {
        "candidate": candidate.name,
        "categories": list(candidate.categories),
        "includeHazards": candidate.include_hazards,
        "features": features,
        "metrics": _weighted_metrics(folds),
        "perRegion": _weighted_region_metrics(folds),
        "folds": folds,
        "trainingSeconds": time.perf_counter() - started,
        "featureImportance": _average_feature_importance(folds),
    }


def _load_hazard_features(hazard_point_dir: Path):
    import pandas as pd

    flood_path = hazard_point_dir / "flood" / "hazard_point_features.csv"
    landslide_path = hazard_point_dir / "landslide" / "hazard_point_features.csv"
    if not flood_path.exists() or not landslide_path.exists():
        return pd.DataFrame(columns=["lat", "lon", *HAZARD_FEATURES])
    flood = pd.read_csv(flood_path, usecols=["lat", "lon", "flood_risk_level"])
    landslide = pd.read_csv(
        landslide_path, usecols=["lat", "lon", "landslide_risk_level"]
    )
    return flood.merge(landslide, on=["lat", "lon"], how="outer")


def _feature_importance(model, features: list[str]) -> list[dict[str, object]]:
    rows = [
        {"feature": feature, "importance": float(value)}
        for feature, value in zip(features, model.feature_importances_, strict=False)
    ]
    return sorted(rows, key=lambda row: row["importance"], reverse=True)


def _average_feature_importance(folds: list[dict[str, object]]) -> list[dict[str, object]]:
    totals: dict[str, float] = {}
    for fold in folds:
        for row in fold["featureImportance"]:
            totals[row["feature"]] = totals.get(row["feature"], 0.0) + row["importance"]
    rows = [
        {"feature": feature, "importance": importance / len(folds)}
        for feature, importance in totals.items()
    ]
    return sorted(rows, key=lambda row: row["importance"], reverse=True)


def _weighted_metrics(folds: list[dict[str, object]]) -> dict[str, float]:
    total = sum(fold["testCount"] for fold in folds)
    return {
        "mae": sum(fold["metrics"]["mae"] * fold["testCount"] for fold in folds) / total,
        "rmse": (
            sum(fold["metrics"]["rmse"] ** 2 * fold["testCount"] for fold in folds) / total
        )
        ** 0.5,
        "mape": sum(fold["metrics"]["mape"] * fold["testCount"] for fold in folds) / total,
    }


def _weighted_region_metrics(folds: list[dict[str, object]]) -> dict[str, object]:
    regions = sorted({region for fold in folds for region in fold["perRegion"]})
    result = {}
    for region in regions:
        rows = [fold["perRegion"][region] for fold in folds if region in fold["perRegion"]]
        total = sum(row["testCount"] for row in rows)
        result[region] = {
            "testCount": total,
            "metrics": {
                "mae": sum(row["metrics"]["mae"] * row["testCount"] for row in rows)
                / total,
                "rmse": (
                    sum(
                        row["metrics"]["rmse"] ** 2 * row["testCount"] for row in rows
                    )
                    / total
                )
                ** 0.5,
                "mape": sum(row["metrics"]["mape"] * row["testCount"] for row in rows)
                / total,
            },
        }
    return result


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# 周辺施設POI特徴量 dry-run",
        "",
        "注意: この結果は探索用であり、そのまま本番採用しない。",
        "",
        str(report["leakageWarning"]),
        "",
        f"* 対象地域: {', '.join(report['regions'])}",
        f"* 元データ件数: {report['sourceRowCount']:,}",
        f"* サンプル件数: {report['sampleSize']:,}",
        f"* random seed: {report['randomSeed']}",
        f"* 学習件数: {report['trainCount']:,}",
        f"* 評価件数: {report['testCount']:,}",
        f"* 評価年: {', '.join(str(year) for year in report['testYears'])}",
        f"* 特徴量生成秒: {report['featureGenerationSeconds']:.2f}",
        f"* ハザード: {report['hazardStatus']}",
        "",
        "| 候補 | MAE | baseline差 | RMSE | baseline差 | MAPE | baseline差 | 学習秒 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["candidates"]:
        metrics = row["metrics"]
        lines.append(
            f"| {row['candidate']} | {metrics['mae']:,.0f} | {row['maeDelta']:+,.0f} | "
            f"{metrics['rmse']:,.0f} | {row['rmseDelta']:+,.0f} | "
            f"{metrics['mape']:.2f}% | {row['mapeDelta']:+.2f}pt | "
            f"{row['trainingSeconds']:.2f} |"
        )
    baseline = next(row for row in report["candidates"] if row["candidate"] == "baseline")
    combined = next(
        row for row in report["candidates"] if row["candidate"] == "all_nearby_pois"
    )
    baseline_folds = {fold["testYear"]: fold for fold in baseline["folds"]}
    lines.extend(
        [
            "",
            "## 評価年別",
            "",
            "| 評価年 | baseline MAE | 全施設 MAE | MAE差 | RMSE差 | MAPE差 |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for fold in combined["folds"]:
        base_fold = baseline_folds[fold["testYear"]]
        lines.append(
            f"| {fold['testYear']} | {base_fold['metrics']['mae']:,.0f} | "
            f"{fold['metrics']['mae']:,.0f} | "
            f"{fold['metrics']['mae'] - base_fold['metrics']['mae']:+,.0f} | "
            f"{fold['metrics']['rmse'] - base_fold['metrics']['rmse']:+,.0f} | "
            f"{fold['metrics']['mape'] - base_fold['metrics']['mape']:+.2f}pt |"
        )
    lines.extend(
        [
            "",
            "## 地域別",
            "",
            "| 地域 | 評価件数 | baseline MAE | 全施設 MAE | MAE差 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for region, row in combined["perRegion"].items():
        base_row = baseline["perRegion"][region]
        lines.append(
            f"| {region} | {row['testCount']:,} | {base_row['metrics']['mae']:,.0f} | "
            f"{row['metrics']['mae']:,.0f} | "
            f"{row['metrics']['mae'] - base_row['metrics']['mae']:+,.0f} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
