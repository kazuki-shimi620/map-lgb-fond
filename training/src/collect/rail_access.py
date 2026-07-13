from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from features.station_passengers import normalize_station_name  # noqa: E402

DEFAULT_TERMINAL_STATIONS_CSV = Path("data/manual/rail/terminal_stations.csv")
DEFAULT_TRAVEL_TIMES_CSV = Path("data/manual/rail/major_station_travel_times.csv")
DEFAULT_OUTPUT_DIR = Path("data/processed/rail")
SCHEMA_VERSION = "1.0.0"
DESTINATIONS = ["tokyo", "shinjuku", "shibuya", "yokohama"]
DESTINATION_LABELS = {
    "東京": "tokyo",
    "新宿": "shinjuku",
    "渋谷": "shibuya",
    "横浜": "yokohama",
}
RAIL_ACCESS_FIELDNAMES = [
    "station",
    "normalized_station_name",
    "nearest_station_is_terminal",
    "terminal_group",
    "major_terminal_min_time",
    "major_terminal_min_transfer_count",
    "closest_major_terminal",
    "destination_count",
    "source",
    "source_year",
] + [
    column
    for destination in DESTINATIONS
    for column in (f"time_to_{destination}", f"transfers_to_{destination}")
]


class RailAccessCollectError(RuntimeError):
    pass


def collect_rail_access(
    *,
    terminal_stations_csv: Path = DEFAULT_TERMINAL_STATIONS_CSV,
    travel_times_csv: Path = DEFAULT_TRAVEL_TIMES_CSV,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path | int]:
    if not terminal_stations_csv.exists():
        raise RailAccessCollectError(f"Terminal stations CSV not found: {terminal_stations_csv}")
    if not travel_times_csv.exists():
        raise RailAccessCollectError(f"Travel times CSV not found: {travel_times_csv}")

    terminals = _read_csv(terminal_stations_csv)
    travel_times = _read_csv(travel_times_csv)
    rows = build_rail_access_rows(terminals, travel_times)

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "rail_access.csv"
    metadata_path = output_dir / "metadata.json"
    _write_csv(csv_path, rows)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "terminalStationsCsv": str(terminal_stations_csv),
        "travelTimesCsv": str(travel_times_csv),
        "rowCount": len(rows),
        "destinations": DESTINATIONS,
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"rail_access_csv": csv_path, "metadata": metadata_path, "row_count": len(rows)}


def build_rail_access_rows(
    terminal_rows: list[dict[str, Any]],
    travel_time_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    terminal_by_station = {
        normalize_station_name(row.get("station_name")): row
        for row in terminal_rows
        if normalize_station_name(row.get("station_name"))
    }
    grouped: dict[str, dict[str, Any]] = {}
    for row in travel_time_rows:
        origin = _text(row.get("origin_station"))
        destination = _text(row.get("destination_station"))
        normalized_origin = normalize_station_name(origin)
        destination_key = DESTINATION_LABELS.get(normalize_station_name(destination))
        if not normalized_origin or destination_key is None:
            continue
        access_row = grouped.setdefault(
            normalized_origin,
            _base_row(origin, terminal_by_station.get(normalized_origin)),
        )
        minutes = _to_float(row.get("travel_time_minutes"))
        transfers = _to_float(row.get("transfer_count"))
        access_row[f"time_to_{destination_key}"] = minutes
        access_row[f"transfers_to_{destination_key}"] = transfers
        access_row["source"] = _first_text(access_row.get("source"), row.get("source"))
        access_row["source_year"] = _first_text(
            access_row.get("source_year"),
            row.get("source_year"),
        )

    for row in terminal_rows:
        normalized_station = normalize_station_name(row.get("station_name"))
        if normalized_station:
            grouped.setdefault(normalized_station, _base_row(row.get("station_name"), row))

    rows = []
    for row in grouped.values():
        _finalize_row(row)
        rows.append(row)
    return sorted(rows, key=lambda row: row["normalized_station_name"])


def _base_row(station: object, terminal_row: dict[str, Any] | None) -> dict[str, Any]:
    station_name = _text(station)
    terminal_row = terminal_row or {}
    return {
        "station": station_name,
        "normalized_station_name": normalize_station_name(station_name),
        "nearest_station_is_terminal": 1.0
        if _text(terminal_row.get("is_terminal")) in {"1", "true", "True", "yes"}
        else 0.0,
        "terminal_group": _text(terminal_row.get("terminal_group")),
        "major_terminal_min_time": None,
        "major_terminal_min_transfer_count": None,
        "closest_major_terminal": "",
        "destination_count": 0,
        "source": _text(terminal_row.get("source")),
        "source_year": _text(terminal_row.get("source_year")),
    }


def _finalize_row(row: dict[str, Any]) -> None:
    candidates = []
    for destination in DESTINATIONS:
        time_key = f"time_to_{destination}"
        transfer_key = f"transfers_to_{destination}"
        minutes = row.get(time_key)
        transfers = row.get(transfer_key)
        if minutes is None:
            row[time_key] = None
            row[transfer_key] = None
            continue
        row["destination_count"] += 1
        candidates.append((float(minutes), float(transfers or 0), destination))

    if candidates:
        minutes, transfers, destination = min(candidates, key=lambda item: (item[0], item[1]))
        row["major_terminal_min_time"] = minutes
        row["major_terminal_min_transfer_count"] = transfers
        row["closest_major_terminal"] = destination


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RAIL_ACCESS_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _first_text(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build rail access features from manual CSVs.")
    parser.add_argument("--terminal-stations-csv", type=Path, default=DEFAULT_TERMINAL_STATIONS_CSV)
    parser.add_argument("--travel-times-csv", type=Path, default=DEFAULT_TRAVEL_TIMES_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        outputs = collect_rail_access(
            terminal_stations_csv=args.terminal_stations_csv,
            travel_times_csv=args.travel_times_csv,
            output_dir=args.output_dir,
        )
    except RailAccessCollectError as error:
        print(f"rail access collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected rail access: "
        f"rows={outputs['row_count']} "
        f"csv={outputs['rail_access_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
