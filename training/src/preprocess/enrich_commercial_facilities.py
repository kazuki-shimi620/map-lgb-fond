from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evaluate.address_coordinate_coverage import load_address_points_csv  # noqa: E402

MANUAL_COORDINATE_FIELDNAMES = [
    "match_key",
    "name",
    "prefecture",
    "municipality",
    "address",
    "lat",
    "lon",
    "source_url",
    "source_type",
    "confidence",
    "verified_at",
    "notes",
]
MUNICIPALITY_ALIAS_FIELDNAMES = [
    "source_prefecture",
    "source_municipality",
    "source_district",
    "source_name",
    "corrected_prefecture",
    "corrected_municipality",
    "notes",
]
ROW_CORRECTION_FIELDNAMES = [
    "source_page",
    "source_column",
    "source_store_area_sqm",
    "source_open_year",
    "source_open_month",
    "corrected_name",
    "corrected_prefecture",
    "corrected_municipality",
    "corrected_open_year",
    "corrected_open_month",
    "address",
    "notes",
]
COORDINATE_REVIEW_FIELDNAMES = [
    "review_reason",
    "match_key",
    "name",
    "prefecture",
    "municipality",
    "district",
    "store_area_sqm",
    "open_year",
    "open_month",
    "coordinate_source",
    "coordinate_confidence",
    "parse_warnings",
    "search_query",
    "google_maps_search_url",
]


def enrich_commercial_facility_coordinates(
    commercial_df,
    address_points_df,
    manual_coordinates_df=None,
    municipality_aliases_df=None,
    row_corrections_df=None,
    *,
    allow_municipality_fallback: bool = False,
):
    result = commercial_df.copy()
    if "lat" not in result.columns:
        result["lat"] = None
    if "lon" not in result.columns:
        result["lon"] = None
    if "address" not in result.columns:
        result["address"] = ""
    result["coordinate_source"] = "none"
    result["coordinate_confidence"] = ""
    result["coordinate_source_url"] = ""
    result["coordinate_notes"] = ""
    row_corrections = _build_row_correction_index(row_corrections_df)
    if row_corrections:
        apply_row_corrections(result, row_corrections)
    municipality_aliases = _build_municipality_alias_index(municipality_aliases_df)
    if municipality_aliases:
        apply_municipality_aliases(result, municipality_aliases)
    manual_index = _build_manual_coordinate_index(manual_coordinates_df)
    if manual_index:
        for index, row in result.iterrows():
            match = _match_manual_coordinate(row, manual_index)
            if match is None:
                continue
            result.at[index, "lat"] = match["lat"]
            result.at[index, "lon"] = match["lon"]
            result.at[index, "address"] = _text(match.get("address"))
            result.at[index, "coordinate_source"] = f"manual:{_text(match.get('source_type'))}"
            result.at[index, "coordinate_confidence"] = _text(match.get("confidence"))
            result.at[index, "coordinate_source_url"] = _text(match.get("source_url"))
            result.at[index, "coordinate_notes"] = _text(match.get("notes"))

    if address_points_df.empty or result.empty:
        return result

    address_points = address_points_df.dropna(
        subset=["prefecture", "municipality", "district_name", "lat", "lon"]
    ).copy()
    if address_points.empty:
        return result

    address_index = _build_address_index(address_points)
    municipality_index = _build_municipality_index(address_points)
    for index, row in result.iterrows():
        if _has_coordinates(row):
            if result.at[index, "coordinate_source"] == "none":
                result.at[index, "coordinate_source"] = "input"
            continue
        match = _match_address_point(row, address_index)
        coordinate_source = "address_point"
        coordinate_confidence = "medium"
        if match is None and allow_municipality_fallback:
            match = _match_municipality_point(row, municipality_index)
            coordinate_source = "municipality_representative"
            coordinate_confidence = "low"
        if match is None:
            continue
        result.at[index, "lat"] = match["lat"]
        result.at[index, "lon"] = match["lon"]
        matched_prefecture = _text(match.get("prefecture"))
        matched_municipality = _text(match.get("municipality"))
        coordinate_notes = [item for item in _text(row.get("coordinate_notes")).split("|") if item]
        if matched_prefecture and matched_prefecture != _text(row.get("prefecture")):
            result.at[index, "prefecture"] = matched_prefecture
            coordinate_notes.append("prefecture_inferred_from_municipality")
        if matched_municipality and matched_municipality != _text(
            row.get("city") or row.get("municipality")
        ):
            municipality_column = "city" if "city" in result.columns else "municipality"
            result.at[index, municipality_column] = matched_municipality
        if _text(match.get("match_method")) == "fuzzy_municipality":
            coordinate_notes.append("fuzzy_municipality")
        if coordinate_notes:
            result.at[index, "coordinate_notes"] = "|".join(coordinate_notes)
        result.at[index, "coordinate_source"] = coordinate_source
        result.at[index, "coordinate_confidence"] = coordinate_confidence
    return result


def _build_address_index(address_points_df) -> dict[tuple[str, str], list[dict[str, object]]]:
    records: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in address_points_df.to_dict(orient="records"):
        key = (str(row["prefecture"]).strip(), str(row["municipality"]).strip())
        records.setdefault(key, []).append(row)
    for rows in records.values():
        rows.sort(key=lambda item: len(str(item["district_name"])), reverse=True)
    return records


def _build_municipality_index(address_points_df) -> dict[tuple[str, str], dict[str, object]]:
    records: dict[tuple[str, str], list[dict[str, object]]] = {}
    alias_records: dict[str, list[dict[str, object]]] = {}
    for row in address_points_df.to_dict(orient="records"):
        prefecture = str(row["prefecture"]).strip()
        municipality = str(row["municipality"]).strip()
        aliases = _municipality_aliases(municipality)
        for key in _municipality_index_keys(prefecture, municipality):
            records.setdefault(key, []).append(row)
        for alias in aliases:
            alias_records.setdefault(alias, []).append(row)

        city = _city_without_ward(municipality)
        if city:
            records.setdefault((prefecture, city), []).append(row)

    representatives = {}
    for alias, rows in alias_records.items():
        prefectures = {str(row["prefecture"]).strip() for row in rows}
        municipalities = {str(row["municipality"]).strip() for row in rows}
        if len(prefectures) == 1 and len(municipalities) == 1:
            records.setdefault(("", alias), rows)

    for key, rows in records.items():
        lat_values = [float(row["lat"]) for row in rows]
        lon_values = [float(row["lon"]) for row in rows]
        first = rows[0]
        representatives[key] = {
            "prefecture": str(first["prefecture"]).strip(),
            "municipality": str(first["municipality"]).strip(),
            "lat": sum(lat_values) / len(lat_values),
            "lon": sum(lon_values) / len(lon_values),
        }
    return representatives


def _municipality_index_keys(prefecture: str, municipality: str) -> list[tuple[str, str]]:
    return [(prefecture, name) for name in _municipality_aliases(municipality)]


def _municipality_aliases(municipality: str) -> list[str]:
    names = [municipality]
    if "ケ" in municipality:
        names.append(municipality.replace("ケ", "ヶ"))
    if "ヶ" in municipality:
        names.append(municipality.replace("ヶ", "ケ"))
    if "郡" in municipality:
        names.append(municipality.split("郡", 1)[1])
    if municipality.endswith(("市", "町", "村")) and len(municipality) > 1:
        names.append(municipality[:-1])
    if "郡" in municipality and municipality.endswith(("町", "村")):
        short_name = municipality.split("郡", 1)[1]
        names.append(short_name[:-1])
    unique_names = []
    for name in names:
        if name and name not in unique_names:
            unique_names.append(name)
    return unique_names


def _match_address_point(row, address_index) -> dict[str, object] | None:
    prefecture = _text(row.get("prefecture"))
    municipality = _text(row.get("city") or row.get("municipality"))
    address = _text(row.get("address_raw") or row.get("address"))
    if not prefecture or not municipality or not address:
        return None
    candidates = address_index.get((prefecture, municipality), [])
    if not candidates:
        return None
    address_tail = address.replace(prefecture, "", 1).replace(municipality, "", 1)
    normalized_address_tail = _normalize_address_for_match(address_tail)
    for candidate in candidates:
        district = _text(candidate.get("district_name"))
        normalized_district = _normalize_address_for_match(district)
        if district and (
            address_tail.startswith(district)
            or district in address_tail
            or normalized_address_tail.startswith(normalized_district)
            or normalized_district in normalized_address_tail
        ):
            return candidate
    return None


def _normalize_address_for_match(value: str) -> str:
    normalized = _text(value)
    digit_map = {
        "1": "一",
        "2": "二",
        "3": "三",
        "4": "四",
        "5": "五",
        "6": "六",
        "7": "七",
        "8": "八",
        "9": "九",
        "10": "十",
    }
    for digit, kanji in sorted(digit_map.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = re.sub(rf"{digit}(?=丁目)", kanji, normalized)
    return normalized


def _match_municipality_point(row, municipality_index) -> dict[str, object] | None:
    prefecture = _text(row.get("prefecture"))
    municipality = _text(row.get("city") or row.get("municipality"))
    district = _text(row.get("district"))
    if not prefecture or not (municipality or district):
        return None
    candidates = [municipality] if municipality else []
    if district:
        candidates.insert(0, f"{municipality}{district}")
        candidates.append(district)
    for candidate in candidates:
        if match := municipality_index.get((prefecture, candidate)):
            return match
        if match := municipality_index.get(("", candidate)):
            return match
    return _find_fuzzy_municipality_match(prefecture, candidates, municipality_index)


def _find_fuzzy_municipality_match(
    prefecture: str,
    candidates: list[str],
    municipality_index: dict[tuple[str, str], dict[str, object]],
) -> dict[str, object] | None:
    if not prefecture:
        return None
    best_match = None
    best_score = 0.0
    for candidate in candidates:
        if len(candidate) < 3:
            continue
        for (key_prefecture, key_municipality), match in municipality_index.items():
            if key_prefecture != prefecture or not key_municipality:
                continue
            if abs(len(candidate) - len(key_municipality)) > 2:
                continue
            score = SequenceMatcher(None, candidate, key_municipality).ratio()
            if score > best_score:
                best_score = score
                best_match = match
    if best_match is not None and best_score >= 0.72:
        return {**best_match, "match_method": "fuzzy_municipality", "match_score": best_score}
    return None


def _build_manual_coordinate_index(manual_coordinates_df) -> dict[str, dict[str, object]]:
    if manual_coordinates_df is None or manual_coordinates_df.empty:
        return {}
    index = {}
    for row in manual_coordinates_df.to_dict(orient="records"):
        lat = _parse_float(row.get("lat"))
        lon = _parse_float(row.get("lon"))
        if lat is None or lon is None:
            continue
        key = _text(row.get("match_key")) or _manual_match_key(row)
        if key:
            index[key] = {**row, "lat": lat, "lon": lon}
    return index


def _build_row_correction_index(
    row_corrections_df,
) -> dict[tuple[str, str, str, str, str], dict[str, str]]:
    if row_corrections_df is None or row_corrections_df.empty:
        return {}
    corrections = {}
    for row in row_corrections_df.to_dict(orient="records"):
        key = _row_correction_key(
            page=row.get("source_page"),
            column=row.get("source_column"),
            store_area_sqm=row.get("source_store_area_sqm"),
            open_year=row.get("source_open_year"),
            open_month=row.get("source_open_month"),
        )
        if not any(key):
            continue
        corrections[key] = {
            "name": _text(row.get("corrected_name")),
            "prefecture": _text(row.get("corrected_prefecture")),
            "municipality": _text(row.get("corrected_municipality")),
            "open_year": _numeric_key(row.get("corrected_open_year")),
            "open_month": _numeric_key(row.get("corrected_open_month")),
            "address": _text(row.get("address")),
            "notes": _text(row.get("notes")),
        }
    return corrections


def apply_row_corrections(
    result,
    row_corrections: dict[tuple[str, str, str, str, str], dict[str, str]],
):
    for index, row in result.iterrows():
        key = _row_correction_key(
            page=row.get("page"),
            column=row.get("column"),
            store_area_sqm=row.get("store_area_sqm"),
            open_year=row.get("open_year"),
            open_month=row.get("open_month"),
        )
        correction = row_corrections.get(key)
        if correction is None:
            continue
        if correction["name"]:
            result.at[index, "name"] = correction["name"]
        if correction["prefecture"]:
            result.at[index, "prefecture"] = correction["prefecture"]
        if correction["municipality"]:
            municipality_column = "city" if "city" in result.columns else "municipality"
            result.at[index, municipality_column] = correction["municipality"]
        if correction["open_year"]:
            result.at[index, "open_year"] = _value_for_column(
                result, "open_year", correction["open_year"]
            )
        if correction["open_month"]:
            result.at[index, "open_month"] = _value_for_column(
                result, "open_month", correction["open_month"]
            )
        if (
            correction["open_year"]
            and correction["open_month"]
            and "open_date_raw" in result.columns
        ):
            result.at[index, "open_date_raw"] = (
                f"{correction['open_year']}年{correction['open_month']}月"
            )
        if correction["address"]:
            result.at[index, "address"] = correction["address"]
        notes = append_note(_text(row.get("coordinate_notes")), "row_correction")
        if correction["notes"]:
            notes = append_note(notes, correction["notes"])
        result.at[index, "coordinate_notes"] = notes


def _row_correction_key(
    *,
    page: object,
    column: object,
    store_area_sqm: object,
    open_year: object,
    open_month: object,
) -> tuple[str, str, str, str, str]:
    return (
        _text(page),
        _text(column),
        _numeric_key(store_area_sqm),
        _numeric_key(open_year),
        _numeric_key(open_month),
    )


def _numeric_key(value: object) -> str:
    parsed = _parse_float(value)
    if parsed is None:
        return _text(value)
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def _integer_value(value: object) -> int | object:
    parsed = _parse_float(value)
    if parsed is None or not parsed.is_integer():
        return value
    return int(parsed)


def _value_for_column(result, column: str, value: object) -> object:
    dtype_name = str(result[column].dtype)
    if "string" in dtype_name or dtype_name in {"object", "str"}:
        return _numeric_key(value)
    return _integer_value(value)


def _build_municipality_alias_index(
    municipality_aliases_df,
) -> dict[tuple[str, str], dict[str, str]]:
    if municipality_aliases_df is None or municipality_aliases_df.empty:
        return {}
    aliases = {}
    for row in municipality_aliases_df.to_dict(orient="records"):
        source_prefecture = _text(row.get("source_prefecture"))
        source_municipality = _text(row.get("source_municipality"))
        source_district = _text(row.get("source_district"))
        source_name = _manual_name_key(row.get("source_name"))
        corrected_prefecture = _text(row.get("corrected_prefecture"))
        corrected_municipality = _text(row.get("corrected_municipality"))
        if (
            not (source_municipality or source_district or source_name)
            or not corrected_prefecture
            or not corrected_municipality
        ):
            continue
        aliases[(source_prefecture, source_municipality, source_district, source_name)] = {
            "prefecture": corrected_prefecture,
            "municipality": corrected_municipality,
        }
    return aliases


def apply_municipality_aliases(
    result,
    municipality_aliases: dict[tuple[str, str, str, str], dict[str, str]],
):
    for index, row in result.iterrows():
        prefecture = _text(row.get("prefecture"))
        municipality = _text(row.get("city") or row.get("municipality"))
        district = _text(row.get("district"))
        name = _manual_name_key(row.get("name") or row.get("facility_name"))
        if not municipality and not district and not name:
            continue
        match = (
            municipality_aliases.get((prefecture, municipality, district, name))
            or municipality_aliases.get((prefecture, municipality, "", name))
            or municipality_aliases.get((prefecture, "", district, name))
            or municipality_aliases.get((prefecture, "", "", name))
            or municipality_aliases.get(("", municipality, district, name))
            or municipality_aliases.get(("", municipality, "", name))
            or municipality_aliases.get(("", "", district, name))
            or municipality_aliases.get(("", "", "", name))
            or municipality_aliases.get((prefecture, municipality, district, ""))
            or municipality_aliases.get((prefecture, municipality, "", ""))
            or municipality_aliases.get((prefecture, "", district, ""))
            or municipality_aliases.get(("", municipality, district, ""))
            or municipality_aliases.get(("", municipality, "", ""))
            or municipality_aliases.get(("", "", district, ""))
        )
        if match is None:
            continue
        result.at[index, "prefecture"] = match["prefecture"]
        municipality_column = "city" if "city" in result.columns else "municipality"
        result.at[index, municipality_column] = match["municipality"]
        result.at[index, "coordinate_notes"] = append_note(
            _text(row.get("coordinate_notes")), "municipality_alias"
        )


def append_note(current: str, note: str) -> str:
    notes = [item for item in current.split("|") if item]
    if note not in notes:
        notes.append(note)
    return "|".join(notes)


def _match_manual_coordinate(row, manual_index) -> dict[str, object] | None:
    for key in [_text(row.get("match_key")), _manual_match_key(row)]:
        if key and key in manual_index:
            return manual_index[key]
    return None


def _manual_match_key(row) -> str:
    name = _manual_name_key(row.get("name") or row.get("facility_name"))
    prefecture = _text(row.get("prefecture"))
    if not name:
        return ""
    return f"{prefecture}|{name}" if prefecture else name


def _manual_name_key(value: object) -> str:
    name = _text(value)
    if not name:
        return ""
    normalized = (
        name.lower()
        .replace(" ", "")
        .replace("　", "")
        .replace("・", "")
        .replace("･", "")
        .replace("（", "")
        .replace("）", "")
        .replace("(", "")
        .replace(")", "")
    )
    return normalized


def _city_without_ward(value: str) -> str:
    if value.endswith("区") and "市" in value:
        return value.split("市", 1)[0] + "市"
    return ""


def _has_coordinates(row) -> bool:
    try:
        lat = float(row.get("lat"))
        lon = float(row.get("lon"))
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180


def _parse_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def enrich_file(
    *,
    input_csv: Path,
    address_points_csv: Path,
    output_csv: Path,
    manual_coordinates_csv: Path | None = None,
    municipality_aliases_csv: Path | None = None,
    row_corrections_csv: Path | None = None,
    allow_municipality_fallback: bool = False,
) -> dict[str, object]:
    import pandas as pd

    commercial = pd.read_csv(input_csv)
    address_points = load_address_points_csv(address_points_csv)
    manual_coordinates = (
        pd.read_csv(manual_coordinates_csv)
        if manual_coordinates_csv is not None and manual_coordinates_csv.exists()
        else None
    )
    municipality_aliases = (
        pd.read_csv(municipality_aliases_csv)
        if municipality_aliases_csv is not None and municipality_aliases_csv.exists()
        else None
    )
    row_corrections = (
        pd.read_csv(row_corrections_csv)
        if row_corrections_csv is not None and row_corrections_csv.exists()
        else None
    )
    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        manual_coordinates,
        municipality_aliases,
        row_corrections,
        allow_municipality_fallback=allow_municipality_fallback,
    )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(output_csv, index=False)
    review_queue_path = output_csv.with_name(f"{output_csv.stem}_coordinate_review_queue.csv")
    review_queue_count = write_coordinate_review_queue(review_queue_path, enriched)
    coordinate_count = int((enriched["lat"].notna() & enriched["lon"].notna()).sum())
    metadata = {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "inputCsv": str(input_csv),
        "addressPointsCsv": str(address_points_csv),
        "manualCoordinatesCsv": str(manual_coordinates_csv) if manual_coordinates_csv else None,
        "municipalityAliasesCsv": (
            str(municipality_aliases_csv) if municipality_aliases_csv else None
        ),
        "rowCorrectionsCsv": str(row_corrections_csv) if row_corrections_csv else None,
        "outputCsv": str(output_csv),
        "coordinateReviewQueueCsv": str(review_queue_path),
        "recordCount": int(len(enriched)),
        "coordinateCount": coordinate_count,
        "coordinateRate": coordinate_count / len(enriched) if len(enriched) else 0.0,
        "coordinateReviewQueueCount": review_queue_count,
        "coordinateSourceCounts": {
            str(key): int(value)
            for key, value in enriched["coordinate_source"].value_counts().to_dict().items()
        },
        "coordinateNoteCounts": summarize_pipe_separated_counts(enriched, "coordinate_notes"),
    }
    metadata_path = output_csv.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def summarize_pipe_separated_counts(dataframe, column: str) -> dict[str, int]:
    if column not in dataframe.columns:
        return {}
    counts: dict[str, int] = {}
    for value in dataframe[column].fillna("").astype(str):
        for item in [part for part in value.split("|") if part]:
            counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items()))


def write_coordinate_review_queue(output_csv: Path, enriched_df) -> int:
    review_rows = []
    for row in enriched_df.to_dict(orient="records"):
        reason = _coordinate_review_reason(row)
        if not reason:
            continue
        search_query = build_google_maps_search_query(row)
        review_rows.append(
            {
                "review_reason": reason,
                "match_key": _text(row.get("match_key")),
                "name": _text(row.get("name") or row.get("facility_name")),
                "prefecture": _text(row.get("prefecture")),
                "municipality": _text(row.get("municipality") or row.get("city")),
                "district": _text(row.get("district")),
                "store_area_sqm": _text(row.get("store_area_sqm")),
                "open_year": _text(row.get("open_year")),
                "open_month": _text(row.get("open_month")),
                "coordinate_source": _text(row.get("coordinate_source")),
                "coordinate_confidence": _text(row.get("coordinate_confidence")),
                "parse_warnings": _text(row.get("parse_warnings")),
                "search_query": search_query,
                "google_maps_search_url": build_google_maps_search_url(search_query),
            }
        )
    review_rows.sort(
        key=lambda item: (
            item["coordinate_source"] != "none",
            "municipality_missing" not in item["parse_warnings"],
            item["prefecture"],
            item["municipality"],
            item["name"],
        )
    )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COORDINATE_REVIEW_FIELDNAMES)
        writer.writeheader()
        writer.writerows(review_rows)
    return len(review_rows)


def _coordinate_review_reason(row: dict[str, object]) -> str:
    name = _text(row.get("name") or row.get("facility_name"))
    if not name or len(name) <= 2 or name.lower() in {"and"}:
        return "ocr_name_review"
    coordinate_source = _text(row.get("coordinate_source"))
    if coordinate_source == "none":
        return "coordinate_missing"
    if coordinate_source == "municipality_representative":
        return "low_confidence_municipality_representative"
    return ""


def build_google_maps_search_query(row: dict[str, object]) -> str:
    name = _text(row.get("name") or row.get("facility_name"))
    parse_warnings = _text(row.get("parse_warnings"))
    if "municipality_missing" in parse_warnings or not _text(
        row.get("municipality") or row.get("city")
    ):
        return name
    parts = [
        _text(row.get("prefecture")),
        _text(row.get("municipality") or row.get("city")),
        _text(row.get("district")),
        name,
    ]
    return " ".join(part for part in parts if part)


def build_google_maps_search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def write_manual_coordinate_template(output_csv: Path) -> Path:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=MANUAL_COORDINATE_FIELDNAMES)
        writer.writeheader()
    return output_csv


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attach representative address-point coordinates to JCSC commercial facilities."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path("data/processed/jcsc/jcsc_sc_open.csv"),
    )
    parser.add_argument(
        "--address-points-csv",
        type=Path,
        default=Path("data/processed/address_points/town_points.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/processed/jcsc/jcsc_sc_open_with_coordinates.csv"),
    )
    parser.add_argument("--manual-coordinates-csv", type=Path)
    parser.add_argument("--municipality-aliases-csv", type=Path)
    parser.add_argument("--row-corrections-csv", type=Path)
    parser.add_argument("--allow-municipality-fallback", action="store_true")
    parser.add_argument("--write-manual-template", type=Path)
    args = parser.parse_args()
    if args.write_manual_template:
        output = write_manual_coordinate_template(args.write_manual_template)
        print(f"wrote commercial facility manual coordinate template: {output}")
        return 0

    metadata = enrich_file(
        input_csv=args.input_csv,
        address_points_csv=args.address_points_csv,
        output_csv=args.output_csv,
        manual_coordinates_csv=args.manual_coordinates_csv,
        municipality_aliases_csv=args.municipality_aliases_csv,
        row_corrections_csv=args.row_corrections_csv,
        allow_municipality_fallback=args.allow_municipality_fallback,
    )
    print(
        "enriched commercial facilities: "
        f"coordinates={metadata['coordinateCount']}/{metadata['recordCount']} "
        f"output={args.output_csv}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
