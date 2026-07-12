from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.reinfolib import REINFOLIB_API_KEY_ENV  # noqa: E402
from features.hazards import (  # noqa: E402
    landslide_zone_to_features,
    parse_depth_range,
    score_from_risk_level,
    to_wide_hazard_features,
)

SCHEMA_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = Path("data/processed/hazards")
DEFAULT_RAW_DIR = Path("data/raw/hazards")
HAZARD_TYPES = {"flood", "landslide", "tsunami", "storm_surge"}
LONG_FIELDNAMES = [
    "source",
    "source_url",
    "schema_version",
    "feature_year",
    "prefecture",
    "municipality",
    "hazard_type",
    "status",
    "risk_level",
    "score",
    "depth_min",
    "depth_max",
    "zone_type",
    "special_warning",
    "source_available",
    "evaluated_at",
]


class HazardCollectError(RuntimeError):
    pass


def collect_hazards(
    *,
    input_path: Path | None,
    url: str | None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    raw_dir: Path = DEFAULT_RAW_DIR,
    api_key_env: str = REINFOLIB_API_KEY_ENV,
) -> dict[str, Path]:
    if not input_path and not url:
        raise HazardCollectError("--input or --url is required")

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload = _load_payload(
        input_path=input_path, url=url, raw_dir=raw_dir, api_key_env=api_key_env
    )
    records = normalize_hazard_records(_extract_records(payload), source_url=url or str(input_path))

    normalized_json = output_dir / "hazard_records.json"
    long_csv = output_dir / "hazard_records.csv"
    wide_csv = output_dir / "hazard_features.csv"

    normalized_json.write_text(
        json.dumps(
            {
                "schemaVersion": SCHEMA_VERSION,
                "generatedAt": datetime.now(UTC).isoformat(),
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_csv(long_csv, records, LONG_FIELDNAMES)
    _write_wide_csv(wide_csv, records)
    return {
        "normalized_json": normalized_json,
        "long_csv": long_csv,
        "wide_csv": wide_csv,
    }


def normalize_hazard_records(records: list[dict[str, Any]], *, source_url: str | None = None):
    normalized = []
    evaluated_at = datetime.now(UTC).isoformat()
    for record in records:
        hazard_type = _pick(record, "hazard_type", "hazardType", "type", "id")
        if hazard_type not in HAZARD_TYPES:
            continue
        row = {
            "source": _pick(record, "source") or "hazard",
            "source_url": source_url or _pick(record, "source_url", "sourceUrl") or "",
            "schema_version": SCHEMA_VERSION,
            "feature_year": _to_int(_pick(record, "feature_year", "year", "target_year")),
            "prefecture": _pick(record, "prefecture", "prefectureName") or "",
            "municipality": _pick(record, "municipality", "city", "municipalityName") or "",
            "hazard_type": hazard_type,
            "status": _pick(record, "status") or "",
            "risk_level": _to_float(_pick(record, "risk_level", "riskLevel")),
            "score": _to_float(_pick(record, "score")),
            "depth_min": _to_float(_pick(record, "depth_min", "depthMin")),
            "depth_max": _to_float(_pick(record, "depth_max", "depthMax")),
            "zone_type": _pick(record, "zone_type", "zoneType") or "",
            "special_warning": _to_float(_pick(record, "special_warning", "specialWarning")),
            "source_available": _to_bool(
                _pick(record, "source_available", "sourceAvailable", "data_available")
            ),
            "evaluated_at": _pick(record, "evaluated_at", "evaluatedAt") or evaluated_at,
        }
        _complete_hazard_values(row, record)
        normalized.append(row)
    return normalized


def _complete_hazard_values(row: dict[str, Any], record: dict[str, Any]) -> None:
    if row["hazard_type"] == "landslide":
        if row["risk_level"] is None or row["score"] is None:
            risk_level, score, special_warning = landslide_zone_to_features(row["zone_type"])
            row["risk_level"] = row["risk_level"] if row["risk_level"] is not None else risk_level
            row["score"] = row["score"] if row["score"] is not None else score
            row["special_warning"] = (
                row["special_warning"] if row["special_warning"] is not None else special_warning
            )
        return

    depth_label = _pick(record, "depth_label", "depthLabel", "depth_category", "depthCategory")
    if depth_label and (
        row["depth_min"] is None or row["depth_max"] is None or row["risk_level"] is None
    ):
        depth_min, depth_max, risk_level = parse_depth_range(depth_label)
        row["depth_min"] = row["depth_min"] if row["depth_min"] is not None else depth_min
        row["depth_max"] = row["depth_max"] if row["depth_max"] is not None else depth_max
        row["risk_level"] = row["risk_level"] if row["risk_level"] is not None else risk_level
    if row["score"] is None:
        row["score"] = score_from_risk_level(row["risk_level"])


def _load_payload(
    *,
    input_path: Path | None,
    url: str | None,
    raw_dir: Path,
    api_key_env: str,
) -> object:
    if input_path:
        if input_path.suffix.lower() == ".csv":
            return _read_csv_records(input_path)
        return json.loads(input_path.read_text(encoding="utf-8"))

    assert url is not None
    request = Request(url)
    api_key = os.environ.get(api_key_env)
    if api_key:
        request.add_header("Ocp-Apim-Subscription-Key", api_key)
    request.add_header("Accept", "application/json")
    with urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    raw_path = raw_dir / f"hazards_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
    raw_path.write_text(body, encoding="utf-8")
    return json.loads(body)


def _extract_records(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        for key in ("records", "items", "features", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                if key == "features":
                    return [
                        _feature_to_record(feature)
                        for feature in value
                        if isinstance(feature, dict)
                    ]
                return [record for record in value if isinstance(record, dict)]
        return [payload]
    return []


def _feature_to_record(feature: dict[str, Any]) -> dict[str, Any]:
    properties = feature.get("properties")
    return dict(properties) if isinstance(properties, dict) else feature


def _read_csv_records(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_wide_csv(path: Path, records: list[dict[str, Any]]) -> None:
    import pandas as pd

    wide = to_wide_hazard_features(pd.DataFrame(records))
    wide.to_csv(path, index=False)


def _pick(record: dict[str, Any], *keys: str):
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _to_bool(value: object) -> bool:
    if value in (None, ""):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "none", "データなし"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect and normalize hazard features.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--api-key-env", default=REINFOLIB_API_KEY_ENV)
    args = parser.parse_args()

    outputs = collect_hazards(
        input_path=args.input,
        url=args.url,
        output_dir=args.output_dir,
        raw_dir=args.raw_dir,
        api_key_env=args.api_key_env,
    )
    print(f"normalized hazard json: {outputs['normalized_json']}")
    print(f"hazard records csv: {outputs['long_csv']}")
    print(f"hazard feature csv: {outputs['wide_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
