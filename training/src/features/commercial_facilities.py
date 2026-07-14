from __future__ import annotations

from pathlib import Path

COMMERCIAL_FEATURES = [
    "sc_city_open_count_cumulative",
    "sc_city_open_count_last_3y",
    "sc_city_store_area_sum_cumulative",
    "sc_city_tenant_count_sum_cumulative",
    "sc_prefecture_open_count_last_3y",
    "has_sc_data_coverage",
]


def load_commercial_facilities_csv(path: str | Path):
    import pandas as pd

    facilities = pd.read_csv(path)
    numeric_columns = ["open_year", "store_area_sqm", "tenant_count"]
    for column in numeric_columns:
        facilities[column] = pd.to_numeric(facilities[column], errors="coerce")
    return facilities


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

    facilities = facilities_df.copy()
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
