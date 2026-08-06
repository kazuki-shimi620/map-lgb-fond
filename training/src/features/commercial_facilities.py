from __future__ import annotations

import math
from pathlib import Path

from features.commercial_facility_scale import add_commercial_facility_scale_columns

SCALE_CODES = ("small", "medium", "large", "very_large")
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

    rows = []
    for property_row in result.itertuples(index=False):
        property_lat = getattr(property_row, "lat", None)
        property_lon = getattr(property_row, "lon", None)
        transaction_year = getattr(property_row, "transaction_year", None)
        if (
            _is_missing_number(property_lat)
            or _is_missing_number(property_lon)
            or _is_missing_number(transaction_year)
        ):
            rows.append(_empty_spatial_features())
            continue

        opened = located[located["open_year"] < int(transaction_year)].copy()
        if opened.empty:
            rows.append(_empty_spatial_features())
            continue

        opened["distance_km"] = opened.apply(
            lambda facility, base_lat=float(property_lat), base_lon=float(property_lon): (
                _haversine_km(base_lat, base_lon, float(facility["lat"]), float(facility["lon"]))
            ),
            axis=1,
        )
        nearest = opened.loc[opened["distance_km"].idxmin()]
        within_1km = opened[opened["distance_km"] <= 1.0]
        within_3km = opened[opened["distance_km"] <= 3.0]
        spatial_features = {
            "nearest_sc_distance_km": float(nearest["distance_km"]),
            "nearest_sc_opened_years": float(int(transaction_year) - int(nearest["open_year"])),
            "sc_count_within_1km": float(len(within_1km)),
            "sc_count_within_3km": float(len(within_3km)),
            "sc_store_area_sum_within_3km": float(within_3km["store_area_sqm"].sum()),
            "sc_tenant_count_sum_within_3km": float(within_3km["tenant_count"].sum()),
        }
        for scale in SCALE_CODES:
            scale_facilities = opened[opened["scale_code"] == scale]
            spatial_features[f"nearest_sc_{scale}_distance_km"] = (
                float(scale_facilities["distance_km"].min()) if not scale_facilities.empty else 0.0
            )
            spatial_features[f"sc_{scale}_count_within_3km"] = float(
                (scale_facilities["distance_km"] <= 3.0).sum()
            )
        rows.append(spatial_features)

    import pandas as pd

    spatial = pd.DataFrame(rows, index=result.index)
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


def _is_missing_number(value: object) -> bool:
    if value is None:
        return True
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
