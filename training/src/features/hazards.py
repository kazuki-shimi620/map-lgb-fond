from __future__ import annotations

import re
from pathlib import Path

HAZARD_TYPES = ["flood", "landslide", "tsunami", "storm_surge"]
HAZARD_FEATURES = [
    "hazard_overall_score",
    "hazard_available_count",
    "hazard_flood_risk_level",
    "hazard_flood_depth_max",
    "hazard_flood_data_available",
    "hazard_landslide_risk_level",
    "hazard_landslide_special_warning",
    "hazard_landslide_data_available",
    "hazard_tsunami_risk_level",
    "hazard_tsunami_depth_max",
    "hazard_tsunami_data_available",
    "hazard_storm_surge_risk_level",
    "hazard_storm_surge_depth_max",
    "hazard_storm_surge_data_available",
]

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def load_hazard_features_csv(path: str | Path):
    import pandas as pd

    hazards = pd.read_csv(path)
    if "feature_year" not in hazards.columns and "year" in hazards.columns:
        hazards = hazards.rename(columns={"year": "feature_year"})

    for column in ["feature_year", *HAZARD_FEATURES]:
        if column in hazards.columns:
            hazards[column] = pd.to_numeric(hazards[column], errors="coerce")
    return hazards


def add_hazard_features(property_df, hazards_df):
    result = property_df.copy()
    if hazards_df.empty:
        return _fill_missing_hazard_features(result)

    hazards = to_wide_hazard_features(hazards_df)
    join_plan = _build_hazard_join_plan(result, hazards)
    if join_plan is None:
        return _fill_missing_hazard_features(result)

    result, hazards, left_on, right_on, temporary_columns = join_plan
    result = result.merge(
        hazards,
        how="left",
        left_on=left_on,
        right_on=right_on,
    )
    drop_columns = [
        key for key, left_key in zip(right_on, left_on, strict=False) if key != left_key
    ]
    drop_columns.extend([column for column in temporary_columns if column in result.columns])
    if drop_columns:
        result = result.drop(columns=drop_columns)
    return _fill_missing_hazard_features(result)


def parse_depth_range(value: object) -> tuple[float | None, float | None, int | None]:
    if value is None:
        return None, None, None

    text = str(value).strip()
    if not text or text in {"区域外", "データなし", "なし", "不明"}:
        return None, None, None

    numbers = [float(number) for number in _NUMBER_RE.findall(text)]
    if not numbers:
        return None, None, None

    if "未満" in text and "以上" not in text:
        depth_min = 0.0
        depth_max = numbers[0]
    elif "以上" in text and "未満" in text and len(numbers) >= 2:
        depth_min = numbers[0]
        depth_max = numbers[1]
    elif "以上" in text:
        depth_min = numbers[0]
        depth_max = None
    elif len(numbers) >= 2:
        depth_min = numbers[0]
        depth_max = numbers[1]
    else:
        depth_min = numbers[0]
        depth_max = numbers[0]

    if depth_max is None:
        risk_level = depth_to_risk_level(depth_min)
    else:
        risk_level = depth_range_to_risk_level(depth_min, depth_max)
    return depth_min, depth_max, risk_level


def depth_to_risk_level(depth: float | None, *, tsunami: bool = False) -> int | None:
    if depth is None:
        return None
    if tsunami:
        if depth < 0.3:
            return 1
        if depth < 1.0:
            return 2
        if depth < 2.0:
            return 3
        if depth < 5.0:
            return 4
        return 5
    if depth < 0.5:
        return 1
    if depth < 1.0:
        return 2
    if depth < 3.0:
        return 3
    if depth < 5.0:
        return 4
    return 5


def depth_range_to_risk_level(
    depth_min: float | None,
    depth_max: float | None,
    *,
    tsunami: bool = False,
) -> int | None:
    if depth_min is None and depth_max is None:
        return None
    depth = depth_max if depth_max is not None else depth_min
    if depth is None:
        return None
    if tsunami:
        if depth <= 0.3:
            return 1
        if depth <= 1.0:
            return 2
        if depth <= 2.0:
            return 3
        if depth <= 5.0:
            return 4
        return 5
    if depth <= 0.5:
        return 1
    if depth <= 1.0:
        return 2
    if depth <= 3.0:
        return 3
    if depth <= 5.0:
        return 4
    return 5


def score_from_risk_level(risk_level: int | float | None) -> float | None:
    if _is_missing(risk_level):
        return None
    mapping = {
        0: 100.0,
        1: 90.0,
        2: 75.0,
        3: 55.0,
        4: 25.0,
        5: 0.0,
    }
    return mapping.get(int(risk_level))


def landslide_zone_to_features(zone_type: object) -> tuple[int | None, float | None, float]:
    text = "" if zone_type is None else str(zone_type)
    if not text or text in {"データなし", "不明"}:
        return None, None, 0.0
    if "区域外" in text:
        return 0, 100.0, 0.0
    if "特別警戒" in text:
        return 5, 0.0, 1.0
    if "警戒" in text:
        return 4, 30.0, 0.0
    return None, None, 0.0


def calculate_overall_hazard_score(scores: dict[str, float | None]) -> float | None:
    available = {
        hazard_type: score
        for hazard_type, score in scores.items()
        if hazard_type in HAZARD_TYPES and score is not None
    }
    if not available:
        return None

    weights = {
        "flood": 0.35,
        "landslide": 0.30,
        "tsunami": 0.20,
        "storm_surge": 0.15,
    }
    total_weight = sum(weights[hazard_type] for hazard_type in available)
    weighted = (
        sum(available[hazard_type] * weights[hazard_type] for hazard_type in available)
        / total_weight
    )
    return min(available.values()) * 0.6 + weighted * 0.4


def to_wide_hazard_features(hazards):
    import pandas as pd

    if any(feature in hazards.columns for feature in HAZARD_FEATURES):
        return hazards.copy()

    required = {"prefecture", "municipality", "feature_year", "hazard_type"}
    if not required.issubset(set(hazards.columns)):
        return pd.DataFrame()

    rows = []
    grouped = hazards.groupby(["prefecture", "municipality", "feature_year"], dropna=False)
    for keys, scoped in grouped:
        row = {
            "prefecture": keys[0],
            "municipality": keys[1],
            "feature_year": keys[2],
        }
        scores: dict[str, float | None] = {}
        for hazard_type in HAZARD_TYPES:
            item = scoped[scoped["hazard_type"] == hazard_type]
            if item.empty:
                scores[hazard_type] = None
                continue
            record = item.iloc[0]
            risk_level = record.get("risk_level")
            score = record.get("score")
            if hazard_type == "landslide" and _is_missing(score) and _is_missing(risk_level):
                risk_level, score, _ = landslide_zone_to_features(record.get("zone_type"))
            scores[hazard_type] = (
                score if not _is_missing(score) else score_from_risk_level(risk_level)
            )
            _assign_hazard_record(row, hazard_type, record)
        row["hazard_available_count"] = float(
            sum(1 for value in scores.values() if value is not None)
        )
        row["hazard_overall_score"] = calculate_overall_hazard_score(scores)
        rows.append(row)
    return pd.DataFrame(rows)


def _assign_hazard_record(row: dict, hazard_type: str, record) -> None:
    import pandas as pd

    if hazard_type == "landslide":
        risk_level = record.get("risk_level")
        zone_type = record.get("zone_type")
        special_warning = record.get("special_warning")
        if pd.isna(risk_level):
            risk_level, _, inferred_special_warning = landslide_zone_to_features(zone_type)
            if pd.isna(special_warning):
                special_warning = inferred_special_warning
        row["hazard_landslide_risk_level"] = risk_level
        row["hazard_landslide_special_warning"] = special_warning
        row["hazard_landslide_data_available"] = _source_available(record)
        return

    prefix = {
        "flood": "hazard_flood",
        "tsunami": "hazard_tsunami",
        "storm_surge": "hazard_storm_surge",
    }[hazard_type]
    row[f"{prefix}_risk_level"] = record.get("risk_level")
    row[f"{prefix}_depth_max"] = record.get("depth_max")
    row[f"{prefix}_data_available"] = _source_available(record)


def _source_available(record) -> float:
    value = record.get("source_available", record.get("data_available", 1.0))
    return 1.0 if bool(value) else 0.0


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _build_hazard_join_plan(properties, hazards):
    if "property_id" in properties.columns and "property_id" in hazards.columns:
        return properties, hazards, ["property_id"], ["property_id"], []

    property_lat = _find_first_column(properties, ["lat", "latitude"])
    property_lon = _find_first_column(properties, ["lon", "lng", "longitude"])
    hazard_lat = _find_first_column(hazards, ["lat", "latitude"])
    hazard_lon = _find_first_column(hazards, ["lon", "lng", "longitude"])
    if property_lat and property_lon and hazard_lat and hazard_lon:
        next_properties = properties.copy()
        next_hazards = hazards.copy()
        next_properties["_hazard_lat_key"] = next_properties[property_lat].map(_coordinate_key)
        next_properties["_hazard_lon_key"] = next_properties[property_lon].map(_coordinate_key)
        next_hazards["_hazard_lat_key"] = next_hazards[hazard_lat].map(_coordinate_key)
        next_hazards["_hazard_lon_key"] = next_hazards[hazard_lon].map(_coordinate_key)
        left_on = ["_hazard_lat_key", "_hazard_lon_key"]
        right_on = ["_hazard_lat_key", "_hazard_lon_key"]
        temporary_columns = ["_hazard_lat_key", "_hazard_lon_key"]
        if "feature_year" in next_hazards.columns and "transaction_year" in next_properties.columns:
            left_on.append("transaction_year")
            right_on.append("feature_year")
        return next_properties, next_hazards, left_on, right_on, temporary_columns

    keys = [
        key
        for key in ["prefecture", "municipality", "feature_year"]
        if key in hazards.columns
        and (
            key in properties.columns
            or (key == "feature_year" and "transaction_year" in properties.columns)
        )
    ]
    if not keys:
        return None
    left_on = ["transaction_year" if key == "feature_year" else key for key in keys]
    return properties, hazards, left_on, keys, []


def _find_first_column(df, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _coordinate_key(value: object) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _fill_missing_hazard_features(result):
    for feature in HAZARD_FEATURES:
        if feature not in result.columns:
            result[feature] = 0.0
        result[feature] = result[feature].fillna(0.0)
    return result
