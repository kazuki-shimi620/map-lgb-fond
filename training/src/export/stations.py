from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REGION_TO_PREFECTURE = {
    "tokyo": "東京都",
    "saitama": "埼玉県",
    "chiba": "千葉県",
    "kanagawa": "神奈川県",
}

HEARTRAILS_API = "https://express.heartrails.com/api/json"


def normalize_station_name(name: str) -> str:
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
    with urllib.request.urlopen(f"{HEARTRAILS_API}?{query}", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_category_station_names(public_dir: Path, region: str) -> list[str]:
    path = public_dir / "metadata" / f"{region}_latest_categories.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("stations", {}).keys())


def build_category_name_lookup(category_names: list[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for name in category_names:
        lookup.setdefault(normalize_station_name(name), name)
    return lookup


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


def build_station_records(public_dir: Path, region: str, interval_seconds: float) -> list[dict[str, Any]]:
    prefecture = REGION_TO_PREFECTURE[region]
    category_lookup = build_category_name_lookup(load_category_station_names(public_dir, region))
    stations = fetch_prefecture_stations(prefecture, interval_seconds)
    records_by_name: dict[str, dict[str, Any]] = {}

    for index, station in enumerate(stations, start=1):
        api_name = station["name"]
        station_name = category_lookup.get(normalize_station_name(api_name), api_name)
        records_by_name.setdefault(
            station_name,
            {
                "station_id": f"{region}_{index:04d}",
                "station_name": station_name,
                "prefecture": prefecture,
                "line_name": station.get("line", ""),
                "lat": float(station["y"]),
                "lon": float(station["x"]),
            },
        )

    return sorted(records_by_name.values(), key=lambda record: record["station_name"])


def export_station_records(public_dir: Path, region: str, interval_seconds: float) -> Path:
    records = build_station_records(public_dir, region, interval_seconds)
    output = public_dir / "stations" / f"{region}_stations.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Export frontend station masters from public railway data.")
    parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    parser.add_argument("--regions", nargs="*", default=list(REGION_TO_PREFECTURE))
    parser.add_argument("--interval-seconds", type=float, default=0.05)
    args = parser.parse_args()

    for region in args.regions:
        if region not in REGION_TO_PREFECTURE:
            raise ValueError(f"Unsupported region: {region}")
        output = export_station_records(args.public_dir, region, args.interval_seconds)
        records = json.loads(output.read_text(encoding="utf-8"))
        print(f"{region}: exported {len(records)} stations to {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
