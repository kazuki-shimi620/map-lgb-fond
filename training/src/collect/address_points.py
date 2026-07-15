from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

DEFAULT_SOURCE_URL = "https://geolonia.github.io/japanese-addresses/latest.csv"
SCHEMA_VERSION = "1.0.0"
FIELDNAMES = [
    "prefecture",
    "municipality",
    "district_name",
    "sub_district_name",
    "lat",
    "lon",
    "source",
]


def collect_address_points(
    *,
    input_path: Path | None,
    source_url: str,
    output_dir: Path,
    raw_dir: Path,
) -> dict[str, Any]:
    rows = read_source_rows(input_path=input_path, source_url=source_url, raw_dir=raw_dir)
    normalized = normalize_address_rows(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "town_points.csv"
    metadata_path = output_dir / "metadata.json"
    write_csv(csv_path, normalized)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourceUrl": source_url if input_path is None else str(input_path),
        "rowCount": len(normalized),
        "source": "geolonia_japanese_addresses",
        "sourceLabel": "Geolonia 住所データ",
        "license": "CC BY 4.0",
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"csv": csv_path, "metadata": metadata_path, "row_count": len(normalized)}


def read_source_rows(
    *,
    input_path: Path | None,
    source_url: str,
    raw_dir: Path,
) -> list[dict[str, str]]:
    if input_path is not None:
        with input_path.open(encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))

    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "latest.csv"
    with urlopen(source_url, timeout=120) as response:
        raw_path.write_bytes(response.read())
    with raw_path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def normalize_address_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    normalized = []
    seen = set()
    for row in rows:
        prefecture = _text(_pick(row, "都道府県名", "prefecture"))
        municipality = _text(_pick(row, "市区町村名", "municipality", "city"))
        district_name = _text(_pick(row, "大字町丁目名", "district_name", "town"))
        sub_district_name = _text(_pick(row, "小字・通称名", "sub_district_name", "koaza"))
        lat = _to_float(_pick(row, "緯度（代表点）", "緯度", "lat", "latitude"))
        lon = _to_float(_pick(row, "経度（代表点）", "経度", "lng", "lon", "longitude"))
        if not prefecture or not municipality or not district_name or lat is None or lon is None:
            continue
        key = (prefecture, municipality, district_name, sub_district_name, lat, lon)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "prefecture": prefecture,
                "municipality": municipality,
                "district_name": district_name,
                "sub_district_name": sub_district_name,
                "lat": lat,
                "lon": lon,
                "source": "geolonia_japanese_addresses",
            }
        )
    return normalized


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _pick(row: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _text(value: str | None) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize address representative points.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/address_points"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/address_points"))
    args = parser.parse_args()

    outputs = collect_address_points(
        input_path=args.input,
        source_url=args.source_url,
        output_dir=args.output_dir,
        raw_dir=args.raw_dir,
    )
    print(f"address points: rows={outputs['row_count']} csv={outputs['csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
