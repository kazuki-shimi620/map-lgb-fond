from __future__ import annotations

import json
import re
import zipfile
from datetime import date
from pathlib import Path


REQUIRED_COLUMNS = [
    "price",
    "area",
    "age",
    "station_distance",
    "prefecture",
    "municipality",
    "station",
    "room_layout",
    "building_type",
    "transaction_year",
]


def preprocess_csv(input_path: str | Path, output_path: str | Path) -> Path:
    import pandas as pd

    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    df = read_raw_dataset(input_file)
    return preprocess_dataframe(df, output_file)


def preprocess_files(input_paths: list[str | Path], output_path: str | Path) -> Path:
    import pandas as pd

    if not input_paths:
        raise ValueError("At least one input file is required")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    frames = [read_raw_dataset(Path(input_path)) for input_path in input_paths]
    df = pd.concat(frames, ignore_index=True)
    return preprocess_dataframe(df, output_file)


def preprocess_dataframe(df, output_file: Path) -> Path:
    df = normalize_columns(df)
    df = drop_missing_records(df)
    df = remove_iqr_outliers(df, ["price", "area"])
    df.to_parquet(output_file, index=False)
    return output_file


def read_raw_dataset(input_file: Path):
    import pandas as pd

    if input_file.suffix.lower() == ".zip":
        return read_zipped_csv(input_file)

    if input_file.suffix.lower() == ".json":
        payload = json.loads(input_file.read_text(encoding="utf-8"))
        records = _extract_records(payload)
        return normalize_mlit_records(records)

    return read_csv_dataset(input_file)


def read_zipped_csv(input_file: Path):
    with zipfile.ZipFile(input_file) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV file found in zip: {input_file}")
        with archive.open(csv_names[0]) as file:
            return read_csv_dataset(file)


def read_csv_dataset(input_file):
    import pandas as pd

    for encoding in ("utf-8", "utf-8-sig", "cp932", "shift_jis"):
        try:
            df = pd.read_csv(input_file, encoding=encoding, low_memory=False)
            return normalize_japanese_mlit_columns(df)
        except UnicodeDecodeError:
            if hasattr(input_file, "seek"):
                input_file.seek(0)
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, "Could not decode CSV")


def normalize_japanese_mlit_columns(df):
    if "取引価格（総額）" not in df.columns:
        return df

    target = df.copy()
    if "種類" in target.columns:
        target = target[target["種類"] == "中古マンション等"]

    transaction_year = target["取引時期"].map(_parse_transaction_year)
    building_year = target["建築年"].map(_parse_building_year)

    normalized = {
        "price": target["取引価格（総額）"].map(_to_number),
        "area": target["面積（㎡）"].map(_to_number),
        "age": [
            _calculate_age(year, trade_year or date.today().year)
            for year, trade_year in zip(building_year, transaction_year, strict=False)
        ],
        "station_distance": target["最寄駅：距離（分）"].map(_parse_station_distance),
        "prefecture": target["都道府県名"],
        "municipality": target["市区町村名"],
        "station": target["最寄駅：名称"],
        "room_layout": target["間取り"].fillna("unknown"),
        "building_type": target["建物の構造"].fillna("unknown"),
        "transaction_year": transaction_year,
    }

    import pandas as pd

    return pd.DataFrame(normalized)


def normalize_mlit_records(records: list[dict]):
    import pandas as pd

    rows = []
    current_year = date.today().year
    for record in records:
        transaction_year = _parse_transaction_year(_pick(record, "Period", "period"))
        building_year = _parse_building_year(_pick(record, "BuildingYear", "buildingYear"))
        rows.append(
            {
                "price": _to_number(_pick(record, "TradePrice", "tradePrice")),
                "area": _to_number(_pick(record, "Area", "area")),
                "age": _calculate_age(building_year, transaction_year or current_year),
                "station_distance": _parse_station_distance(
                    _pick(
                        record,
                        "TimeToNearestStation",
                        "TimeToNearestStationMin",
                        "station_distance",
                    )
                ),
                "prefecture": _pick(record, "Prefecture", "prefecture"),
                "municipality": _pick(record, "Municipality", "municipality"),
                "station": _pick(
                    record,
                    "NearestStation",
                    "Station",
                    "station",
                    "DistrictName",
                ),
                "room_layout": _pick(record, "FloorPlan", "floorPlan") or "unknown",
                "building_type": _pick(record, "Structure", "structure") or "unknown",
                "transaction_year": transaction_year,
            }
        )

    return pd.DataFrame(rows)


def normalize_columns(df):
    next_df = df.copy()
    for column in REQUIRED_COLUMNS:
        if column not in next_df.columns:
            next_df[column] = None

    numeric_columns = ["price", "area", "age", "station_distance", "transaction_year"]
    for column in numeric_columns:
        next_df[column] = next_df[column].astype("float64")

    next_df["transaction_year"] = next_df["transaction_year"].astype("int64")
    return next_df


def drop_missing_records(df):
    return df.dropna(subset=REQUIRED_COLUMNS)


def remove_iqr_outliers(df, columns: list[str]):
    filtered = df.copy()
    for column in columns:
        q1 = filtered[column].quantile(0.25)
        q3 = filtered[column].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        filtered = filtered[(filtered[column] >= lower) & (filtered[column] <= upper)]
    return filtered


def _extract_records(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        for key in ("data", "Data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [record for record in value if isinstance(record, dict)]
        return [payload]
    return []


def _pick(record: dict, *keys: str):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_number(value) -> float | None:
    if value in (None, ""):
        return None
    text = str(value).replace(",", "").replace("㎡", "")
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def _parse_transaction_year(value) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"(\d{4})", str(value))
    return int(match.group(1)) if match else None


def _parse_building_year(value) -> int | None:
    if value in (None, ""):
        return None
    text = str(value)
    western = re.search(r"(\d{4})", text)
    if western:
        return int(western.group(1))

    era_offsets = {
        "昭和": 1925,
        "平成": 1988,
        "令和": 2018,
    }
    for era, offset in era_offsets.items():
        if text.startswith(era):
            year_match = re.search(r"(\d+)", text)
            if year_match:
                return offset + int(year_match.group(1))
    return None


def _calculate_age(building_year: int | None, transaction_year: int) -> float | None:
    if building_year is None:
        return None
    return max(0, float(transaction_year - building_year))


def _parse_station_distance(value) -> float:
    if value in (None, ""):
        return 0.0
    text = str(value)
    if "30分" in text and "60分" in text:
        return 45.0
    if "1H" in text or "1時間" in text:
        return 60.0
    number = _to_number(text)
    return number if number is not None else 0.0
