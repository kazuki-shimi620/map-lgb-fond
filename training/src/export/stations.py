from __future__ import annotations

import argparse
import json
import math
import time
import urllib.parse
import urllib.request
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any

from ..common.regions import PREFECTURE_TO_SLUG, build_model_by_prefecture
from ..features.station_passengers import load_station_passengers_csv, normalize_station_name

REGION_TO_PREFECTURE = {slug: prefecture for prefecture, slug in PREFECTURE_TO_SLUG.items()}
MODEL_BY_PREFECTURE = build_model_by_prefecture()

HEARTRAILS_API = "https://express.heartrails.com/api/json"
MAX_API_RETRIES = 3


def normalize_api_station_name(name: str) -> str:
    return (
        name.replace("（", "(")
        .replace("）", ")")
        .split("(", maxsplit=1)[0]
        .replace("ヶ", "ケ")
        .replace("ヵ", "カ")
        .strip()
    )


def fetch_json(params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{HEARTRAILS_API}?{query}"
    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, RemoteDisconnected):
            if attempt == MAX_API_RETRIES:
                raise
            time.sleep(float(attempt))
    raise RuntimeError("unreachable")


def load_category_station_names(public_dir: Path, model_region: str) -> list[str]:
    path = public_dir / "metadata" / f"{model_region}_latest_categories.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("stations", {}).keys())


def build_category_name_lookup(category_names: list[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for name in category_names:
        lookup.setdefault(normalize_api_station_name(name), name)
    return lookup


def build_station_passenger_lookup(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    stations = load_station_passengers_csv(path)
    stations = stations.sort_values(
        ["normalized_station_name", "latest_passenger_count"],
        ascending=[True, False],
    )
    lookup = {}
    for row in stations.to_dict(orient="records"):
        normalized_name = normalize_station_name(row.get("normalized_station_name", ""))
        if not normalized_name:
            continue
        lookup.setdefault(
            normalized_name,
            {
                "station_passenger_log": float(row.get("log_passenger_count") or 0.0),
                "station_line_count": float(row.get("line_count") or 0.0),
                "station_operator_count": float(row.get("operator_count") or 0.0),
                "station_rank": str(row.get("rank") or "unknown"),
            },
        )
    return lookup


def build_station_passenger_candidates(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    stations = load_station_passengers_csv(path)
    stations = stations.sort_values(
        ["normalized_station_name", "latest_passenger_count"],
        ascending=[True, False],
    )
    candidates: dict[str, list[dict[str, Any]]] = {}
    for row in stations.to_dict(orient="records"):
        normalized_name = normalize_station_name(row.get("normalized_station_name", ""))
        if not normalized_name:
            continue
        candidates.setdefault(normalized_name, []).append(
            {
                "lat": _to_float(row.get("lat")),
                "lon": _to_float(row.get("lon")),
                "station_passenger_log": float(row.get("log_passenger_count") or 0.0),
                "station_line_count": float(row.get("line_count") or 0.0),
                "station_operator_count": float(row.get("operator_count") or 0.0),
                "station_rank": str(row.get("rank") or "unknown"),
                "latest_passenger_count": float(row.get("latest_passenger_count") or 0.0),
            }
        )
    return candidates


def select_station_passenger(
    candidates: dict[str, list[dict[str, Any]]],
    station_name: str,
    lat: float,
    lon: float,
) -> dict[str, Any]:
    records = candidates.get(normalize_station_name(station_name), [])
    if not records:
        return {}
    ranked = []
    for record in records:
        station_lat = record.get("lat")
        station_lon = record.get("lon")
        if station_lat is None or station_lon is None:
            continue
        ranked.append(
            (
                _haversine_km(lat, lon, station_lat, station_lon),
                -float(record.get("latest_passenger_count") or 0.0),
                record,
            )
        )
    selected = min(ranked, key=lambda item: (item[0], item[1]))[2] if ranked else records[0]
    return {
        "station_passenger_log": selected["station_passenger_log"],
        "station_line_count": selected["station_line_count"],
        "station_operator_count": selected["station_operator_count"],
        "station_rank": selected["station_rank"],
    }


def fetch_prefecture_stations(prefecture: str, interval_seconds: float) -> list[dict[str, Any]]:
    lines_data = fetch_json({"method": "getLines", "prefecture": prefecture})
    lines = lines_data.get("response", {}).get("line", [])
    stations_by_key: dict[str, dict[str, Any]] = {}

    for line in lines:
        stations_data = fetch_json({"method": "getStations", "line": line})
        for station in stations_data.get("response", {}).get("station", []):
            if station.get("prefecture") != prefecture:
                continue
            key = f"{station.get('name')}:{station.get('x')}:{station.get('y')}"
            stations_by_key.setdefault(key, station)
        time.sleep(interval_seconds)

    return list(stations_by_key.values())


def build_station_records(
    public_dir: Path,
    region: str,
    interval_seconds: float,
    station_passengers_csv: Path,
) -> list[dict[str, Any]]:
    prefecture = REGION_TO_PREFECTURE[region]
    model_region = MODEL_BY_PREFECTURE[prefecture]
    category_lookup = build_category_name_lookup(
        load_category_station_names(public_dir, model_region)
    )
    passenger_candidates = build_station_passenger_candidates(station_passengers_csv)
    stations = fetch_prefecture_stations(prefecture, interval_seconds)
    records_by_name: dict[str, dict[str, Any]] = {}

    for index, station in enumerate(stations, start=1):
        api_name = station["name"]
        station_name = category_lookup.get(normalize_api_station_name(api_name), api_name)
        lat = float(station["y"])
        lon = float(station["x"])
        passenger = select_station_passenger(passenger_candidates, station_name, lat, lon)
        records_by_name.setdefault(
            station_name,
            {
                "station_id": f"{region}_{index:04d}",
                "station_name": station_name,
                "prefecture": prefecture,
                "line_name": station.get("line", ""),
                "lat": lat,
                "lon": lon,
                **passenger,
            },
        )

    return sorted(records_by_name.values(), key=lambda record: record["station_name"])


def export_station_records(
    public_dir: Path,
    region: str,
    interval_seconds: float,
    station_passengers_csv: Path,
) -> Path:
    records = build_station_records(
        public_dir,
        region,
        interval_seconds,
        station_passengers_csv,
    )
    output = public_dir / "stations" / f"{region}_stations.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def _to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export frontend station masters from public railway data."
    )
    parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    parser.add_argument("--regions", nargs="*", default=list(REGION_TO_PREFECTURE))
    parser.add_argument("--interval-seconds", type=float, default=0.05)
    parser.add_argument(
        "--station-passengers-csv",
        type=Path,
        default=Path("data/processed/station_passengers/station_groups.csv"),
    )
    args = parser.parse_args()

    for region in args.regions:
        if region not in REGION_TO_PREFECTURE:
            raise ValueError(f"Unsupported region: {region}")
        output = export_station_records(
            args.public_dir,
            region,
            args.interval_seconds,
            args.station_passengers_csv,
        )
        records = json.loads(output.read_text(encoding="utf-8"))
        print(f"{region}: exported {len(records)} stations to {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
