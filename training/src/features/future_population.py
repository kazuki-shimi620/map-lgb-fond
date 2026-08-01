from __future__ import annotations

from pathlib import Path

FUTURE_POPULATION_FEATURES = [
    "future_population_change_2030_rate",
    "future_population_change_2040_rate",
    "has_future_population_data",
]
CLIPPED_FUTURE_POPULATION_FEATURES = [
    "future_population_change_2030_rate_clipped",
    "future_population_change_2040_rate_clipped",
    "has_future_population_data",
]


def load_future_population_csv(path: str | Path):
    import pandas as pd

    return pd.read_csv(path)


def add_future_population_features(property_df, future_population_df):
    result = property_df.copy()
    if future_population_df.empty:
        return _fill_missing(result)
    columns = ["lat", "lon", *FUTURE_POPULATION_FEATURES]
    available = [column for column in columns if column in future_population_df.columns]
    result = result.merge(
        future_population_df[available].drop_duplicates(["lat", "lon"]),
        on=["lat", "lon"],
        how="left",
    )
    return _fill_missing(result)


def add_clipped_future_population_features(data, *, lower: float = 0.01, upper: float = 0.99):
    result = data.copy()
    thresholds = {}
    matched = result["has_future_population_data"].eq(1)
    for column in FUTURE_POPULATION_FEATURES[:2]:
        values = result.loc[matched, column]
        low = float(values.quantile(lower)) if not values.empty else 0.0
        high = float(values.quantile(upper)) if not values.empty else 0.0
        result[f"{column}_clipped"] = result[column].clip(low, high)
        thresholds[column] = {"lower": low, "upper": high}
    return result, thresholds


def _fill_missing(result):
    for column in FUTURE_POPULATION_FEATURES:
        if column not in result.columns:
            result[column] = 0.0
        result[column] = result[column].fillna(0.0).astype(float)
    return result
