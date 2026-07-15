from __future__ import annotations

import math
from pathlib import Path

LAND_PRICE_FEATURES = [
    "land_price_city_avg_yen_per_sqm",
    "land_price_city_yoy_rate",
    "land_price_points_city_count",
    "nearest_land_price_yen_per_sqm",
    "nearest_land_price_distance_km",
    "land_price_points_within_2km",
    "has_land_price_data",
]


def load_land_price_points_csv(path: str | Path):
    import pandas as pd

    points = pd.read_csv(path)
    numeric_columns = [
        "year",
        "lat",
        "lon",
        "current_price_yen_per_sqm",
        "year_on_year_change_rate",
    ]
    for column in numeric_columns:
        if column in points.columns:
            points[column] = pd.to_numeric(points[column], errors="coerce")
    return points


def load_land_price_city_summary_csv(path: str | Path):
    import pandas as pd

    summary = pd.read_csv(path)
    numeric_columns = [
        "year",
        "point_count",
        "avg_price_yen_per_sqm",
        "median_price_yen_per_sqm",
        "avg_yoy_rate",
    ]
    for column in numeric_columns:
        if column in summary.columns:
            summary[column] = pd.to_numeric(summary[column], errors="coerce")
    return summary


def add_land_price_features(property_df, points_df, city_summary_df):
    result = property_df.copy()
    if points_df.empty and city_summary_df.empty:
        return _fill_missing_land_price_features(result)

    city_features = _build_city_year_features(city_summary_df)
    if not city_features.empty:
        result = result.merge(
            city_features,
            how="left",
            left_on=["prefecture", "municipality", "transaction_year"],
            right_on=["prefecture", "municipality", "feature_year"],
        ).drop(columns=["feature_year"])

    if _has_coordinate_columns(result) and not points_df.empty:
        nearest_features = _build_nearest_point_features(result, points_df)
        result = result.join(nearest_features)

    return _fill_missing_land_price_features(result)


def _build_city_year_features(city_summary_df):
    import pandas as pd

    if city_summary_df.empty:
        return pd.DataFrame()

    summary = city_summary_df.dropna(subset=["year", "prefecture", "municipality"]).copy()
    rows = []
    keys = summary[["prefecture", "municipality"]].drop_duplicates()
    years = sorted(summary["year"].dropna().astype(int).unique())
    for key in keys.itertuples(index=False):
        scoped = summary[
            (summary["prefecture"] == key.prefecture)
            & (summary["municipality"] == key.municipality)
        ]
        for year in years:
            latest = scoped[scoped["year"] <= year]
            if latest.empty:
                continue
            latest_year = int(latest["year"].max())
            latest_rows = latest[latest["year"] == latest_year]
            point_count = float(latest_rows["point_count"].fillna(0.0).sum())
            rows.append(
                {
                    "prefecture": key.prefecture,
                    "municipality": key.municipality,
                    "feature_year": year,
                    "land_price_city_avg_yen_per_sqm": _weighted_average(
                        latest_rows,
                        "avg_price_yen_per_sqm",
                        "point_count",
                    ),
                    "land_price_city_yoy_rate": _weighted_average(
                        latest_rows,
                        "avg_yoy_rate",
                        "point_count",
                    ),
                    "land_price_points_city_count": point_count,
                }
            )
    return pd.DataFrame(rows)


def _build_nearest_point_features(property_df, points_df):
    import numpy as np
    import pandas as pd
    from sklearn.neighbors import BallTree

    points = points_df.dropna(subset=["lat", "lon", "current_price_yen_per_sqm"]).copy()
    result = pd.DataFrame(
        [_empty_nearest_features() for _ in range(len(property_df))],
        index=property_df.index,
    )
    if points.empty or property_df.empty:
        return result

    for column in ["year", "lat", "lon"]:
        points[column] = pd.to_numeric(points[column], errors="coerce")
    points = points.dropna(subset=["year", "lat", "lon"])
    if points.empty:
        return result

    tree_cache = _build_land_price_tree_cache(points, BallTree)
    properties = property_df[["prefecture", "transaction_year", "lat", "lon"]].copy()
    properties["transaction_year"] = pd.to_numeric(
        properties["transaction_year"],
        errors="coerce",
    )
    properties["lat"] = pd.to_numeric(properties["lat"], errors="coerce")
    properties["lon"] = pd.to_numeric(properties["lon"], errors="coerce")
    valid = properties.dropna(subset=["prefecture", "transaction_year", "lat", "lon"])
    if valid.empty:
        return result

    for (prefecture, year), scoped in valid.groupby(
        ["prefecture", valid["transaction_year"].astype(int)],
        sort=False,
    ):
        cache = _select_tree_cache(tree_cache, prefecture=prefecture, year=int(year))
        if cache is None:
            continue
        coordinates_rad = np.radians(scoped[["lat", "lon"]].to_numpy(dtype=float))
        distances_rad, indices = cache["tree"].query(coordinates_rad, k=1)
        distances_km = distances_rad[:, 0] * 6371.0088
        nearest_indices = indices[:, 0]
        within_2km = cache["tree"].query_radius(
            coordinates_rad,
            r=2.0 / 6371.0088,
            count_only=True,
        )
        result.loc[scoped.index, "nearest_land_price_yen_per_sqm"] = cache["prices"][
            nearest_indices
        ]
        result.loc[scoped.index, "nearest_land_price_distance_km"] = distances_km
        result.loc[scoped.index, "land_price_points_within_2km"] = within_2km.astype(float)

    return result


def _build_land_price_tree_cache(points, ball_tree_class):
    import numpy as np

    cache = {}
    for prefecture, prefecture_points in points.groupby("prefecture", sort=False):
        years = sorted(prefecture_points["year"].dropna().astype(int).unique())
        prefecture_trees = {}
        for year in years:
            scoped = prefecture_points[prefecture_points["year"].astype(int) <= year]
            if scoped.empty:
                continue
            coordinates_rad = np.radians(scoped[["lat", "lon"]].to_numpy(dtype=float))
            prefecture_trees[year] = {
                "tree": ball_tree_class(coordinates_rad, metric="haversine"),
                "prices": scoped["current_price_yen_per_sqm"].to_numpy(dtype=float),
            }
        cache[prefecture] = {
            "years": years,
            "trees": prefecture_trees,
        }
    return cache


def _select_tree_cache(tree_cache, *, prefecture: object, year: int):
    prefecture_cache = tree_cache.get(prefecture)
    if prefecture_cache is None:
        return None
    selected_year = None
    for candidate_year in prefecture_cache["years"]:
        if candidate_year <= year:
            selected_year = candidate_year
        else:
            break
    if selected_year is None:
        return None
    return prefecture_cache["trees"].get(selected_year)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _weighted_average(df, value_column: str, weight_column: str) -> float:
    values = df[[value_column, weight_column]].dropna()
    if values.empty:
        return 0.0
    weights = values[weight_column].astype(float)
    if weights.sum() == 0:
        return float(values[value_column].astype(float).mean())
    return float((values[value_column].astype(float) * weights).sum() / weights.sum())


def _fill_missing_land_price_features(result):
    for feature in LAND_PRICE_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = result[feature].fillna(0.0)
    city_columns = ["land_price_city_avg_yen_per_sqm", "land_price_city_yoy_rate"]
    nearest_columns = ["nearest_land_price_yen_per_sqm", "nearest_land_price_distance_km"]
    result["has_land_price_data"] = (
        result[city_columns + nearest_columns].sum(axis=1) > 0
    ).astype(float)
    return result


def _has_coordinate_columns(df) -> bool:
    return "lat" in df.columns and "lon" in df.columns


def _empty_nearest_features() -> dict[str, float]:
    return {
        "nearest_land_price_yen_per_sqm": 0.0,
        "nearest_land_price_distance_km": 0.0,
        "land_price_points_within_2km": 0.0,
    }
