from __future__ import annotations

from pathlib import Path

import numpy as np

from features.commercial_facility_scale import add_commercial_facility_scale_columns

SCALE_CODES = ("small", "medium", "large", "very_large")
EARTH_RADIUS_KM = 6371.0088
COMMERCIAL_SCALE_FEATURES = [
    feature
    for scale in SCALE_CODES
    for feature in (
        f"nearest_sc_{scale}_distance_km",
        f"sc_{scale}_count_within_3km",
    )
]

COMMERCIAL_FEATURES = [
    "sc_city_open_count_cumulative",
    "sc_city_open_count_last_3y",
    "sc_city_store_area_sum_cumulative",
    "sc_city_tenant_count_sum_cumulative",
    "sc_prefecture_open_count_last_3y",
    "nearest_sc_distance_km",
    "nearest_sc_opened_years",
    "sc_count_within_1km",
    "sc_count_within_3km",
    "sc_store_area_sum_within_3km",
    "sc_tenant_count_sum_within_3km",
    "has_sc_data_coverage",
] + COMMERCIAL_SCALE_FEATURES


def load_commercial_facilities_csv(path: str | Path | list[str | Path]):
    import pandas as pd

    if isinstance(path, list):
        frames = [pd.read_csv(item) for item in path if Path(item).exists()]
        facilities = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    else:
        facilities = pd.read_csv(path)
    if "city" not in facilities.columns and "municipality" in facilities.columns:
        facilities["city"] = facilities["municipality"]
    elif "city" in facilities.columns and "municipality" in facilities.columns:
        facilities["city"] = facilities["city"].fillna(facilities["municipality"])
    numeric_columns = ["open_year", "store_area_sqm", "tenant_count", "lat", "lon"]
    for column in numeric_columns:
        if column in facilities.columns:
            facilities[column] = pd.to_numeric(facilities[column], errors="coerce")
    return add_commercial_facility_scale_columns(facilities)


def add_commercial_facility_features(
    property_df,
    facilities_df,
    *,
    lookback_years: int = 3,
    data_start_year: int = 2015,
):

    result = property_df.copy()
    if facilities_df.empty:
        for feature in COMMERCIAL_FEATURES:
            result[feature] = 0.0
        return result

    min_year = int(result["transaction_year"].min())
    max_year = int(result["transaction_year"].max())
    years = list(range(min_year, max_year + 1))

    facilities = add_commercial_facility_scale_columns(facilities_df)
    facilities = facilities.dropna(subset=["open_year", "prefecture", "city"])
    facilities["open_year"] = facilities["open_year"].astype(int)
    facilities["store_area_sqm"] = facilities["store_area_sqm"].fillna(0.0)
    facilities["tenant_count"] = facilities["tenant_count"].fillna(0.0)

    city_features = _build_city_year_features(facilities, years, lookback_years)
    prefecture_features = _build_prefecture_year_features(facilities, years, lookback_years)

    result = result.merge(
        city_features,
        how="left",
        left_on=["prefecture", "municipality", "transaction_year"],
        right_on=["prefecture", "municipality", "feature_year"],
    ).drop(columns=["feature_year"])
    result = result.merge(
        prefecture_features,
        how="left",
        left_on=["prefecture", "transaction_year"],
        right_on=["prefecture", "feature_year"],
    ).drop(columns=["feature_year"])
    result = _add_spatial_features(result, facilities)

    for feature in COMMERCIAL_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = result[feature].fillna(0.0)
    result["has_sc_data_coverage"] = (result["transaction_year"] >= data_start_year).astype(float)
    return result


def _build_city_year_features(facilities, years: list[int], lookback_years: int):
    import pandas as pd

    keys = facilities[["prefecture", "city"]].drop_duplicates()
    rows = []
    for record in keys.itertuples(index=False):
        scoped = facilities[
            (facilities["prefecture"] == record.prefecture) & (facilities["city"] == record.city)
        ]
        for year in years:
            cumulative = scoped[scoped["open_year"] < year]
            recent = scoped[
                (scoped["open_year"] < year) & (scoped["open_year"] >= year - lookback_years)
            ]
            rows.append(
                {
                    "prefecture": record.prefecture,
                    "municipality": record.city,
                    "feature_year": year,
                    "sc_city_open_count_cumulative": float(len(cumulative)),
                    "sc_city_open_count_last_3y": float(len(recent)),
                    "sc_city_store_area_sum_cumulative": float(cumulative["store_area_sqm"].sum()),
                    "sc_city_tenant_count_sum_cumulative": float(cumulative["tenant_count"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _add_spatial_features(result, facilities):
    import pandas as pd
    from sklearn.neighbors import BallTree

    if not {"lat", "lon"}.issubset(result.columns) or not {"lat", "lon"}.issubset(
        facilities.columns
    ):
        return result

    located = facilities.dropna(subset=["lat", "lon", "open_year"]).copy()
    if "coordinate_source" in located.columns:
        located = located[located["coordinate_source"] != "municipality_representative"].copy()
    if "coordinate_confidence" in located.columns:
        located = located[
            located["coordinate_confidence"].isna()
            | located["coordinate_confidence"].isin(["medium", "high"])
        ].copy()
    if located.empty:
        return result

    spatial = pd.DataFrame(
        0.0,
        index=result.index,
        columns=list(_empty_spatial_features()),
    )
    valid_property = result["lat"].notna() & result["lon"].notna()
    valid_property &= result["transaction_year"].notna()
    for transaction_year, property_group in result.loc[valid_property].groupby(
        "transaction_year", sort=True
    ):
        opened = located[located["open_year"] < int(transaction_year)]
        if opened.empty:
            continue
        property_coordinates = np.radians(property_group[["lat", "lon"]].to_numpy())
        facility_coordinates = np.radians(opened[["lat", "lon"]].to_numpy())
        tree = BallTree(facility_coordinates, metric="haversine")
        nearest_radians, _ = tree.query(property_coordinates, k=1)
        within_1km = tree.query_radius(
            property_coordinates, r=1.0 / EARTH_RADIUS_KM, count_only=True
        )
        within_3km_indices = tree.query_radius(property_coordinates, r=3.0 / EARTH_RADIUS_KM)
        row_index = property_group.index
        spatial.loc[row_index, "nearest_sc_distance_km"] = nearest_radians[:, 0] * EARTH_RADIUS_KM
        tied_nearest_indices = tree.query_radius(
            property_coordinates,
            r=nearest_radians[:, 0] + 1e-12,
        )
        stable_nearest_indices = np.fromiter(
            (indices.min() for indices in tied_nearest_indices), dtype=int
        )
        nearest_open_years = opened["open_year"].to_numpy()[stable_nearest_indices]
        spatial.loc[row_index, "nearest_sc_opened_years"] = (
            int(transaction_year) - nearest_open_years
        )
        spatial.loc[row_index, "sc_count_within_1km"] = within_1km.astype(float)
        spatial.loc[row_index, "sc_count_within_3km"] = np.fromiter(
            (len(indices) for indices in within_3km_indices), dtype=float
        )
        store_areas = opened["store_area_sqm"].to_numpy()
        tenant_counts = opened["tenant_count"].to_numpy()
        spatial.loc[row_index, "sc_store_area_sum_within_3km"] = np.fromiter(
            (store_areas[indices].sum() for indices in within_3km_indices), dtype=float
        )
        spatial.loc[row_index, "sc_tenant_count_sum_within_3km"] = np.fromiter(
            (tenant_counts[indices].sum() for indices in within_3km_indices), dtype=float
        )
        for scale in SCALE_CODES:
            scale_facilities = opened[opened["scale_code"] == scale]
            if scale_facilities.empty:
                continue
            scale_tree = BallTree(
                np.radians(scale_facilities[["lat", "lon"]].to_numpy()),
                metric="haversine",
            )
            scale_nearest, _ = scale_tree.query(property_coordinates, k=1)
            scale_within_3km = scale_tree.query_radius(
                property_coordinates,
                r=3.0 / EARTH_RADIUS_KM,
                count_only=True,
            )
            spatial.loc[row_index, f"nearest_sc_{scale}_distance_km"] = (
                scale_nearest[:, 0] * EARTH_RADIUS_KM
            )
            spatial.loc[row_index, f"sc_{scale}_count_within_3km"] = scale_within_3km.astype(float)

    return result.join(spatial)


def _empty_spatial_features() -> dict[str, float]:
    features = {
        "nearest_sc_distance_km": 0.0,
        "nearest_sc_opened_years": 0.0,
        "sc_count_within_1km": 0.0,
        "sc_count_within_3km": 0.0,
        "sc_store_area_sum_within_3km": 0.0,
        "sc_tenant_count_sum_within_3km": 0.0,
    }
    features.update({feature: 0.0 for feature in COMMERCIAL_SCALE_FEATURES})
    return features


def _build_prefecture_year_features(facilities, years: list[int], lookback_years: int):
    import pandas as pd

    keys = facilities[["prefecture"]].drop_duplicates()
    rows = []
    for record in keys.itertuples(index=False):
        scoped = facilities[facilities["prefecture"] == record.prefecture]
        for year in years:
            recent = scoped[
                (scoped["open_year"] < year) & (scoped["open_year"] >= year - lookback_years)
            ]
            rows.append(
                {
                    "prefecture": record.prefecture,
                    "feature_year": year,
                    "sc_prefecture_open_count_last_3y": float(len(recent)),
                }
            )
    return pd.DataFrame(rows)
