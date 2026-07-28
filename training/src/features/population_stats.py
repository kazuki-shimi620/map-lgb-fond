from __future__ import annotations

from pathlib import Path

POPULATION_FEATURES = [
    "municipality_population",
    "municipality_households",
    "municipality_population_density",
    "municipality_aging_rate",
    "municipality_working_age_rate",
    "population_change_5y_rate",
    "household_persons_avg",
    "has_population_data",
]


def load_population_stats_csv(path: str | Path):
    import pandas as pd

    population = pd.read_csv(path)
    numeric_columns = [
        "year",
        "population_total",
        "households_total",
        "population_density_per_km2",
        "aging_rate",
        "working_age_rate",
        "population_change_5y_rate",
        "household_persons_avg",
    ]
    for column in numeric_columns:
        if column in population.columns:
            population[column] = pd.to_numeric(population[column], errors="coerce")
    return population


def add_population_features(property_df, population_df):
    result = property_df.copy()
    if population_df.empty:
        return _fill_missing_population_features(result)

    target_years = result["transaction_year"].dropna().astype(int).unique()
    population_features = _build_city_year_features(population_df, target_years=target_years)
    if not population_features.empty:
        result = result.merge(
            population_features,
            how="left",
            left_on=["prefecture", "municipality", "transaction_year"],
            right_on=["prefecture", "municipality", "feature_year"],
        ).drop(columns=["feature_year"])
    return _fill_missing_population_features(result)


def _build_city_year_features(population_df, *, target_years):
    import pandas as pd

    population = population_df.dropna(subset=["year", "prefecture", "municipality"]).copy()
    if population.empty:
        return pd.DataFrame()

    rows = []
    keys = population[["prefecture", "municipality"]].drop_duplicates()
    years = sorted({int(year) for year in target_years})
    for key in keys.itertuples(index=False):
        scoped = population[
            (population["prefecture"] == key.prefecture)
            & (population["municipality"] == key.municipality)
        ]
        for year in years:
            latest = scoped[scoped["year"] <= year]
            if latest.empty:
                continue
            latest_row = latest.sort_values("year").iloc[-1]
            rows.append(
                {
                    "prefecture": key.prefecture,
                    "municipality": key.municipality,
                    "feature_year": year,
                    "municipality_population": _value(latest_row, "population_total"),
                    "municipality_households": _value(latest_row, "households_total"),
                    "municipality_population_density": _value(
                        latest_row,
                        "population_density_per_km2",
                    ),
                    "municipality_aging_rate": _value(latest_row, "aging_rate"),
                    "municipality_working_age_rate": _value(
                        latest_row,
                        "working_age_rate",
                    ),
                    "population_change_5y_rate": _value(
                        latest_row,
                        "population_change_5y_rate",
                    ),
                    "household_persons_avg": _value(latest_row, "household_persons_avg"),
                }
            )
    return pd.DataFrame(rows)


def _fill_missing_population_features(result):
    for feature in POPULATION_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = result[feature].fillna(0.0)
    signal_columns = [
        "municipality_population",
        "municipality_households",
        "municipality_population_density",
    ]
    result["has_population_data"] = (result[signal_columns].sum(axis=1) > 0).astype(float)
    return result


def _value(row, column: str) -> float:
    value = row.get(column)
    if value != value:
        return 0.0
    return float(value)
