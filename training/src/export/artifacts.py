from __future__ import annotations

import json
import pickle
import shutil
from datetime import datetime
from hashlib import sha256
from pathlib import Path

CAPITAL_REGION_PRIORITY = ["tokyo", "kanagawa", "saitama", "chiba"]
RECENT_HISTORY_START_YEAR = 2020


def save_pickle(model, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as file:
        pickle.dump(model, file)
    return output


def save_json(data: object, path: str | Path, *, compact: bool = False) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        ),
        encoding="utf-8",
    )
    return output


def build_artifact_paths(output_dir: str | Path, region: str) -> dict[str, Path]:
    date = datetime.now().strftime("%Y%m%d")
    base = Path(output_dir)
    return {
        "pkl": base / f"{region}_{date}.pkl",
        "onnx": base / f"{region}_{date}.onnx",
        "categories": base / f"{region}_{date}_categories.json",
        "metadata": base / f"{region}_{date}_metadata.json",
        "history": base / f"{region}_{date}_history.json",
    }


def copy_for_frontend(
    paths: dict[str, Path],
    frontend_public_dir: str | Path,
    region: str,
    *,
    include_history: bool = True,
) -> None:
    public = Path(frontend_public_dir)
    destinations = {
        "onnx": public / "models" / f"{region}_latest.onnx",
        "categories": public / "metadata" / f"{region}_latest_categories.json",
        "metadata": public / "metadata" / f"{region}_latest_metadata.json",
        "history": public / "histories" / f"{region}_latest_history.json",
    }

    for key, destination in destinations.items():
        if key == "history" and not include_history:
            continue
        source = paths.get(key)
        if not source or not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    update_model_manifest(public)


def update_model_manifest(frontend_public_dir: str | Path) -> Path:
    public = Path(frontend_public_dir)
    model_dir = public / "models"
    discovered = {
        path.name.removesuffix("_latest.onnx"): path for path in model_dir.glob("*_latest.onnx")
    }
    ordered_regions = [region for region in CAPITAL_REGION_PRIORITY if region in discovered]
    ordered_regions.extend(sorted(set(discovered) - set(ordered_regions)))

    models = {}
    for region in ordered_regions:
        path = discovered[region]
        models[region] = {
            "path": f"models/{path.name}",
            "version": sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }

    return save_json(
        {
            "schemaVersion": 1,
            "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
            "capitalRegionPriority": CAPITAL_REGION_PRIORITY,
            "models": models,
        },
        public / "model-manifest.json",
    )


def export_onnx_if_available(model, feature_count: int, path: str | Path) -> Path | None:
    try:
        from onnxmltools import convert_lightgbm
        from onnxmltools.convert.common.data_types import FloatTensorType
    except ModuleNotFoundError:
        print("skip onnx export: onnxmltools is not installed")
        return None

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    initial_types = [("input", FloatTensorType([None, feature_count]))]
    onnx_model = convert_lightgbm(model, initial_types=initial_types)
    output.write_bytes(onnx_model.SerializeToString())
    return output


def build_price_history(
    df,
    *,
    min_year: int | None = None,
    max_year: int | None = None,
) -> list[dict[str, object]]:
    target = df.copy()
    if min_year is not None:
        target = target[target["transaction_year"] >= min_year].copy()
    if max_year is not None:
        target = target[target["transaction_year"] <= max_year].copy()
    target["unit_price"] = target["price"] / target["area"]
    target["area_band"] = ((target["area"] // 5) * 5).clip(upper=100).astype(int)
    target["age_band"] = ((target["age"] // 5) * 5).clip(upper=60).astype(int)
    group_columns = ["station", "transaction_year"]
    if "prefecture" in target.columns:
        group_columns.insert(0, "prefecture")

    grouped = target.groupby(group_columns, as_index=False).agg(
        avg_price=("price", "mean"),
        avg_unit_price=("unit_price", "mean"),
        transaction_count=("price", "size"),
    )
    grouped = grouped.rename(columns={"transaction_year": "year"})

    bucket_columns = [*group_columns, "area_band", "age_band"]
    buckets = target.groupby(bucket_columns, as_index=False).agg(
        avg_unit_price=("unit_price", "mean"),
        transaction_count=("price", "size"),
    )
    bucket_lookup: dict[tuple[object, ...], list[list[float | int]]] = {}
    for row in buckets.itertuples(index=False):
        key = tuple(getattr(row, column) for column in group_columns)
        bucket_lookup.setdefault(key, []).append(
            [
                int(row.area_band),
                int(row.age_band),
                float(row.avg_unit_price),
                int(row.transaction_count),
            ]
        )

    records = grouped.to_dict(orient="records")
    for record in records:
        key = tuple(
            record["year"] if column == "transaction_year" else record[column]
            for column in group_columns
        )
        record["comparable_buckets"] = bucket_lookup.get(key, [])
    return records


def build_price_trend_summary(
    df,
    *,
    region: str,
    min_year: int | None = None,
    max_year: int | None = None,
    min_station_years: int = 2,
) -> dict[str, object]:
    target = df.copy()
    if min_year is not None:
        target = target[target["transaction_year"] >= min_year].copy()
    if max_year is not None:
        target = target[target["transaction_year"] <= max_year].copy()
    target["unit_price"] = target["price"] / target["area"]

    latest_year = int(target["transaction_year"].max()) if not target.empty else None
    regional_series = _yearly_unit_price_series(target)
    station_trends = {}
    if "station" in target.columns:
        for station, group in target.groupby("station"):
            series = _yearly_unit_price_series(group)
            trend = _trend_from_series(series)
            if trend["sampleYears"] >= min_station_years:
                station_trends[str(station)] = trend

    return {
        "schemaVersion": 1,
        "region": region,
        "latestTrainingYear": latest_year,
        "regionalTrend": _trend_from_series(regional_series),
        "stationTrends": dict(sorted(station_trends.items())),
    }


def _yearly_unit_price_series(df):
    if df.empty:
        return []
    grouped = (
        df.groupby("transaction_year", as_index=False)
        .agg(avg_unit_price=("unit_price", "mean"))
        .sort_values("transaction_year")
    )
    return [
        (int(row.transaction_year), float(row.avg_unit_price))
        for row in grouped.itertuples(index=False)
        if row.avg_unit_price > 0
    ]


def _trend_from_series(series: list[tuple[int, float]]) -> dict[str, float | int | None]:
    if not series:
        return {
            "annualizedRate": None,
            "volatility": None,
            "sampleYears": 0,
            "startYear": None,
            "endYear": None,
        }

    if len(series) == 1:
        year, _value = series[0]
        return {
            "annualizedRate": None,
            "volatility": None,
            "sampleYears": 1,
            "startYear": year,
            "endYear": year,
        }

    start_year, start_value = series[0]
    end_year, end_value = series[-1]
    elapsed_years = max(1, end_year - start_year)
    annualized_rate = (end_value / start_value) ** (1 / elapsed_years) - 1
    yearly_changes = [
        current_value / previous_value - 1
        for (_previous_year, previous_value), (_current_year, current_value) in zip(
            series,
            series[1:],
            strict=False,
        )
        if previous_value > 0
    ]
    volatility = _population_std(yearly_changes)
    return {
        "annualizedRate": float(annualized_rate),
        "volatility": volatility,
        "sampleYears": len(series),
        "startYear": start_year,
        "endYear": end_year,
    }


def _population_std(values: list[float]) -> float | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return float(variance**0.5)
