from __future__ import annotations

from pathlib import Path

CRIME_NUMERIC_FEATURES = [
    "crime_count_per_1000_population",
    "crime_count",
    "crime_year",
    "has_crime_data",
]
CRIME_CATEGORICAL_FEATURES = ["crime_area_unit"]
CRIME_FEATURES = CRIME_NUMERIC_FEATURES + CRIME_CATEGORICAL_FEATURES


def load_crime_stats_csv(path: str | Path):
    import pandas as pd

    crime = pd.read_csv(path)
    numeric_columns = [
        "year",
        "crime_count",
        "population_total",
        "crime_count_per_1000_population",
    ]
    for column in numeric_columns:
        if column in crime.columns:
            crime[column] = pd.to_numeric(crime[column], errors="coerce")
    return crime


def add_crime_features(
    property_df,
    crime_df,
    population_df=None,
    *,
    crime_type: str = "刑法犯総数",
):
    result = property_df.copy()
    crime_features = _build_city_year_features(
        crime_df,
        population_df=population_df,
        crime_type=crime_type,
    )
    if not crime_features.empty:
        result = result.merge(
            crime_features,
            how="left",
            left_on=["prefecture", "municipality", "transaction_year"],
            right_on=["prefecture", "municipality", "feature_year"],
        ).drop(columns=["feature_year"])
    return _fill_missing_features(result)


def _build_city_year_features(crime_df, population_df=None, *, crime_type: str):
    import pandas as pd

    required_columns = {"year", "prefecture", "municipality", "crime_type"}
    if crime_df.empty or not required_columns.issubset(crime_df.columns):
        return pd.DataFrame()
    crime = crime_df.dropna(subset=["year", "prefecture", "municipality"]).copy()
    if crime.empty:
        return pd.DataFrame()
    crime = crime[crime["crime_type"].fillna("") == crime_type]
    if crime.empty:
        return pd.DataFrame()
    if population_df is not None and not population_df.empty:
        crime = _attach_population(crime, population_df)
    crime["crime_count_per_1000_population"] = crime.apply(_per_1000, axis=1)

    rows = []
    keys = crime[["prefecture", "municipality"]].drop_duplicates()
    years = sorted(crime["year"].dropna().astype(int).unique())
    for key in keys.itertuples(index=False):
        scoped = crime[
            (crime["prefecture"] == key.prefecture)
            & (crime["municipality"] == key.municipality)
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
                    "crime_count_per_1000_population": _value(
                        latest_row,
                        "crime_count_per_1000_population",
                    ),
                    "crime_count": _value(latest_row, "crime_count"),
                    "crime_year": _value(latest_row, "year"),
                    "crime_area_unit": _text(latest_row.get("area_unit")) or "unknown",
                }
            )
    return pd.DataFrame(rows)


def _attach_population(crime, population_df):
    import pandas as pd

    population = population_df.dropna(subset=["year", "prefecture", "municipality"]).copy()
    if population.empty:
        return crime
    rows = []
    for crime_row in crime.to_dict(orient="records"):
        scoped = population[
            (population["prefecture"] == crime_row["prefecture"])
            & (population["municipality"] == crime_row["municipality"])
            & (population["year"] <= crime_row["year"])
        ]
        row = dict(crime_row)
        if _is_missing(row.get("population_total")) and not scoped.empty:
            latest = scoped.sort_values("year").iloc[-1]
            row["population_total"] = latest.get("population_total")
        rows.append(row)
    return pd.DataFrame(rows)


def _per_1000(row) -> float:
    value = row.get("crime_count_per_1000_population")
    if not _is_missing(value):
        return float(value)
    crime_count = row.get("crime_count")
    population_total = row.get("population_total")
    if _is_missing(crime_count) or _is_missing(population_total) or not population_total:
        return 0.0
    return float(crime_count) / float(population_total) * 1000


def _fill_missing_features(result):
    for feature in CRIME_NUMERIC_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = result[feature].fillna(0.0)
    if "crime_area_unit" not in result.columns:
        result["crime_area_unit"] = "unknown"
    result["crime_area_unit"] = result["crime_area_unit"].fillna("unknown").replace("", "unknown")
    result["has_crime_data"] = (result["crime_count"] > 0).astype(float)
    return result


def _value(row, column: str) -> float:
    value = row.get(column)
    if _is_missing(value):
        return 0.0
    return float(value)


def _is_missing(value: object) -> bool:
    return value is None or value != value


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
