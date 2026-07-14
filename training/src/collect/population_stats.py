from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCHEMA_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = Path("data/processed/population")
DEFAULT_RAW_DIR = Path("data/raw/population")
ESTAT_APP_ID_ENV = "ESTAT_APP_ID"
ESTAT_ENDPOINT = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"
FIELDNAMES = [
    "year",
    "prefecture",
    "municipality",
    "city_code",
    "population_total",
    "households_total",
    "population_density_per_km2",
    "aging_rate",
    "working_age_rate",
    "under_15_rate",
    "population_change_5y_rate",
    "household_persons_avg",
    "area_km2",
    "source",
    "source_url",
]
ESTAT_VALUE_FIELDS = {
    "population_total",
    "households_total",
    "population_under_15",
    "population_15_to_64",
    "population_65_plus",
    "area_km2",
    "population_density_per_km2",
}
PREFECTURE_BY_CODE = {
    "01": "北海道",
    "02": "青森県",
    "03": "岩手県",
    "04": "宮城県",
    "05": "秋田県",
    "06": "山形県",
    "07": "福島県",
    "08": "茨城県",
    "09": "栃木県",
    "10": "群馬県",
    "11": "埼玉県",
    "12": "千葉県",
    "13": "東京都",
    "14": "神奈川県",
    "15": "新潟県",
    "16": "富山県",
    "17": "石川県",
    "18": "福井県",
    "19": "山梨県",
    "20": "長野県",
    "21": "岐阜県",
    "22": "静岡県",
    "23": "愛知県",
    "24": "三重県",
    "25": "滋賀県",
    "26": "京都府",
    "27": "大阪府",
    "28": "兵庫県",
    "29": "奈良県",
    "30": "和歌山県",
    "31": "鳥取県",
    "32": "島根県",
    "33": "岡山県",
    "34": "広島県",
    "35": "山口県",
    "36": "徳島県",
    "37": "香川県",
    "38": "愛媛県",
    "39": "高知県",
    "40": "福岡県",
    "41": "佐賀県",
    "42": "長崎県",
    "43": "熊本県",
    "44": "大分県",
    "45": "宮崎県",
    "46": "鹿児島県",
    "47": "沖縄県",
}


class PopulationStatsCollectError(RuntimeError):
    pass


def collect_population_stats(
    *,
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path | int]:
    if not input_path.exists():
        raise PopulationStatsCollectError(f"Population input CSV not found: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_rows = _read_csv(input_path)
    rows = normalize_population_rows(raw_rows)
    output_path = output_dir / "municipality_population.csv"
    metadata_path = output_dir / "metadata.json"

    _write_csv(output_path, rows)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourceInput": str(input_path),
        "rowCount": len(rows),
        "years": sorted({row["year"] for row in rows if row["year"] is not None}),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "municipality_population_csv": output_path,
        "metadata": metadata_path,
        "row_count": len(rows),
    }


def collect_population_stats_from_estat(
    *,
    app_id: str,
    stats_data_id: str,
    item_specs: dict[str, dict[str, str]],
    area_codes: list[str],
    time_codes: list[str],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    timeout_seconds: int = 60,
) -> dict[str, Path | int]:
    if not app_id:
        raise PopulationStatsCollectError(f"{ESTAT_APP_ID_ENV} is required")
    if not item_specs:
        raise PopulationStatsCollectError("--estat-item is required for e-Stat collection")

    payload, source_url = fetch_estat_stats_data(
        app_id=app_id,
        stats_data_id=stats_data_id,
        area_codes=area_codes,
        time_codes=time_codes,
        timeout_seconds=timeout_seconds,
    )
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{stats_data_id}.json"
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = normalize_estat_population_response(
        payload,
        item_specs=item_specs,
        source_url=source_url,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "municipality_population.csv"
    metadata_path = output_dir / "metadata.json"
    _write_csv(output_path, rows)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "e-Stat API",
        "statsDataId": stats_data_id,
        "sourceUrl": source_url,
        "raw": str(raw_path),
        "rowCount": len(rows),
        "years": sorted({row["year"] for row in rows if row["year"] is not None}),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "municipality_population_csv": output_path,
        "metadata": metadata_path,
        "raw": raw_path,
        "row_count": len(rows),
    }


def fetch_estat_stats_data(
    *,
    app_id: str,
    stats_data_id: str,
    area_codes: list[str],
    time_codes: list[str],
    timeout_seconds: int,
) -> tuple[dict[str, Any], str]:
    params = {
        "appId": app_id,
        "statsDataId": stats_data_id,
        "metaGetFlg": "Y",
        "cntGetFlg": "N",
        "explanationGetFlg": "N",
        "annotationGetFlg": "N",
        "sectionHeaderFlg": "1",
    }
    if area_codes:
        params["cdArea"] = ",".join(area_codes)
    if time_codes:
        params["cdTime"] = ",".join(time_codes)
    request_url = f"{ESTAT_ENDPOINT}?{urlencode(params)}"
    safe_params = {**params, "appId": "***"}
    source_url = f"{ESTAT_ENDPOINT}?{urlencode(safe_params)}"
    request = Request(
        request_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "map-lgb-fond/0.1",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8")), source_url


def normalize_estat_population_response(
    payload: dict[str, Any],
    *,
    item_specs: dict[str, dict[str, str]],
    source_url: str,
) -> list[dict[str, Any]]:
    values = _as_list(
        payload.get("GET_STATS_DATA", {})
        .get("STATISTICAL_DATA", {})
        .get("DATA_INF", {})
        .get("VALUE")
    )
    class_map = _estat_class_map(payload)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, dict):
            continue
        attrs = {
            key.removeprefix("@"): str(raw_value)
            for key, raw_value in value.items()
            if key.startswith("@")
        }
        field = _match_estat_item(attrs, item_specs)
        if field is None:
            continue
        area_code = attrs.get("area", "")
        time_code = attrs.get("time", "")
        if not area_code or not time_code:
            continue
        row = grouped.setdefault(
            (area_code, time_code),
            _base_estat_row(
                area_code=area_code,
                time_code=time_code,
                class_map=class_map,
                source_url=source_url,
            ),
        )
        row[field] = _value_text(value)

    return normalize_population_rows(list(grouped.values()))


def parse_estat_item_specs(values: list[str]) -> dict[str, dict[str, str]]:
    specs: dict[str, dict[str, str]] = {}
    for value in values:
        field, _, raw_conditions = value.partition("=")
        field = field.strip()
        if field not in ESTAT_VALUE_FIELDS:
            raise PopulationStatsCollectError(f"unsupported e-Stat item field: {field}")
        conditions = {}
        for raw_condition in raw_conditions.split(","):
            dimension, _, code = raw_condition.partition(":")
            if not dimension or not code:
                raise PopulationStatsCollectError(f"invalid e-Stat item mapping: {value}")
            conditions[dimension.strip()] = code.strip()
        specs[field] = conditions
    return specs


def normalize_population_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [_normalize_population_row(row) for row in rows]
    normalized = [
        row
        for row in normalized
        if row["year"] is not None and row["prefecture"] and row["municipality"]
    ]
    _add_population_change_rates(normalized)
    return sorted(
        normalized,
        key=lambda row: (
            int(row["year"]),
            str(row["prefecture"]),
            str(row["municipality"]),
            str(row["city_code"]),
        ),
    )


def _normalize_population_row(row: dict[str, Any]) -> dict[str, Any]:
    population_total = _to_float(_pick(row, "population_total", "population", "total_population"))
    households_total = _to_float(_pick(row, "households_total", "households", "household_total"))
    area_km2 = _to_float(_pick(row, "area_km2", "area"))
    population_density = _to_float(
        _pick(row, "population_density_per_km2", "population_density", "density")
    )
    under_15 = _to_float(_pick(row, "population_under_15", "under_15_population"))
    working_age = _to_float(_pick(row, "population_15_to_64", "working_age_population"))
    age_65_plus = _to_float(_pick(row, "population_65_plus", "age_65_plus_population"))

    if population_density is None and population_total is not None and area_km2:
        population_density = population_total / area_km2

    return {
        "year": _to_int(_pick(row, "year", "survey_year")),
        "prefecture": _to_text(_pick(row, "prefecture", "prefecture_name")),
        "municipality": _to_text(_pick(row, "municipality", "city", "municipality_name")),
        "city_code": _to_text(_pick(row, "city_code", "municipality_code")),
        "population_total": population_total,
        "households_total": households_total,
        "population_density_per_km2": population_density,
        "aging_rate": _rate(age_65_plus, population_total),
        "working_age_rate": _rate(working_age, population_total),
        "under_15_rate": _rate(under_15, population_total),
        "population_change_5y_rate": None,
        "household_persons_avg": _safe_divide(population_total, households_total),
        "area_km2": area_km2,
        "source": _to_text(_pick(row, "source")) or "population_stats",
        "source_url": _to_text(_pick(row, "source_url", "sourceUrl")),
    }


def _add_population_change_rates(rows: list[dict[str, Any]]) -> None:
    by_key = {
        (_population_key(row), int(row["year"])): row
        for row in rows
        if row["year"] is not None
    }
    for row in rows:
        year = int(row["year"])
        current = row["population_total"]
        previous = by_key.get((_population_key(row), year - 5))
        if current is None or not previous or not previous["population_total"]:
            row["population_change_5y_rate"] = 0.0
            continue
        row["population_change_5y_rate"] = (
            (float(current) - float(previous["population_total"]))
            / float(previous["population_total"])
            * 100
        )


def _population_key(row: dict[str, Any]) -> str:
    city_code = row.get("city_code")
    if city_code:
        return f"code:{city_code}"
    return f"name:{row.get('prefecture')}:{row.get('municipality')}"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _estat_class_map(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    class_objects = _as_list(
        payload.get("GET_STATS_DATA", {})
        .get("STATISTICAL_DATA", {})
        .get("CLASS_INF", {})
        .get("CLASS_OBJ")
    )
    result: dict[str, dict[str, str]] = {}
    for class_object in class_objects:
        if not isinstance(class_object, dict):
            continue
        dimension = str(class_object.get("@id", ""))
        if not dimension:
            continue
        result[dimension] = {}
        for item in _as_list(class_object.get("CLASS")):
            if not isinstance(item, dict):
                continue
            code = str(item.get("@code", ""))
            name = str(item.get("@name", ""))
            if code:
                result[dimension][code] = name
    return result


def _base_estat_row(
    *,
    area_code: str,
    time_code: str,
    class_map: dict[str, dict[str, str]],
    source_url: str,
) -> dict[str, Any]:
    area_name = class_map.get("area", {}).get(area_code, "")
    prefecture = _prefecture_from_area(area_code, area_name)
    return {
        "year": _year_from_time(time_code, class_map.get("time", {}).get(time_code, "")),
        "prefecture": prefecture,
        "municipality": _municipality_from_area_name(area_name, prefecture),
        "city_code": area_code,
        "source": "e-Stat API",
        "source_url": source_url,
    }


def _match_estat_item(
    attrs: dict[str, str],
    item_specs: dict[str, dict[str, str]],
) -> str | None:
    for field, conditions in item_specs.items():
        if all(attrs.get(dimension) == code for dimension, code in conditions.items()):
            return field
    return None


def _value_text(value: dict[str, Any]) -> str:
    raw = value.get("$", value.get("#text", ""))
    return str(raw).strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _prefecture_from_area(area_code: str, area_name: str) -> str:
    if area_name:
        for prefecture in PREFECTURE_BY_CODE.values():
            if area_name.startswith(prefecture):
                return prefecture
    return PREFECTURE_BY_CODE.get(area_code[:2], "")


def _municipality_from_area_name(area_name: str, prefecture: str) -> str:
    name = area_name.strip()
    if prefecture and name.startswith(prefecture):
        name = name[len(prefecture) :].strip()
    return name or prefecture


def _year_from_time(time_code: str, time_name: str) -> int | None:
    for value in (time_name, time_code):
        for index in range(max(len(value) - 3, 0)):
            candidate = value[index : index + 4]
            if candidate.isdigit() and 1900 <= int(candidate) <= 2100:
                return int(candidate)
    return None


def _pick(row: dict[str, Any], *keys: str):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _safe_divide(numerator: float | None, denominator: float | None) -> float:
    if numerator is None or not denominator:
        return 0.0
    return numerator / denominator


def _rate(value: float | None, total: float | None) -> float:
    if value is None or not total:
        return 0.0
    return value / total * 100


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize municipality population stats.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--estat-stats-data-id")
    parser.add_argument("--estat-app-id", default=os.environ.get(ESTAT_APP_ID_ENV, ""))
    parser.add_argument("--estat-area-codes", nargs="*", default=[])
    parser.add_argument("--estat-time-codes", nargs="*", default=[])
    parser.add_argument("--estat-item", action="append", default=[])
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    try:
        if args.estat_stats_data_id:
            outputs = collect_population_stats_from_estat(
                app_id=args.estat_app_id,
                stats_data_id=args.estat_stats_data_id,
                item_specs=parse_estat_item_specs(args.estat_item),
                area_codes=args.estat_area_codes,
                time_codes=args.estat_time_codes,
                output_dir=args.output_dir,
                raw_dir=args.raw_dir,
                timeout_seconds=args.timeout_seconds,
            )
        elif args.input:
            outputs = collect_population_stats(
                input_path=args.input,
                output_dir=args.output_dir,
            )
        else:
            raise PopulationStatsCollectError("--input or --estat-stats-data-id is required")
    except PopulationStatsCollectError as error:
        print(f"population stats collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected population stats: "
        f"rows={outputs['row_count']} "
        f"csv={outputs['municipality_population_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
