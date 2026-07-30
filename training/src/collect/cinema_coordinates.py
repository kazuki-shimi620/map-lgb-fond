from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OUTPUT_FIELDS = [
    "cinema_id",
    "name",
    "prefecture",
    "address",
    "lat",
    "lon",
    "display_name",
    "osm_type",
    "osm_id",
    "source_url",
    "source_type",
    "confidence",
    "verified_at",
]


def text(value: object) -> str:
    return str(value or "").strip()


def normalize_prefecture(value: object) -> str:
    return re.sub(r"\s+", "", text(value))


def address_locality(address: object) -> str:
    value = normalize_prefecture(address)
    value = re.sub(r"^〒?\d{3}-?\d{4}", "", value)
    value = re.sub(r"^(北海道|東京都|大阪府|京都府|.{2,3}県)", "", value)
    city = re.match(r"(.+?市)", value)
    if city:
        return city.group(1)
    ward = re.match(r"(.+?区)", value)
    if ward:
        return ward.group(1)
    if "郡" in value:
        value = value.split("郡", 1)[1]
    town = re.match(r"(.+?[町村])", value)
    return town.group(1) if town else ""


def place_name_from_address(address: object) -> str:
    value = text(address)
    match = re.search(
        r"(?:\d+(?:[-‐‑–—−ー]\d+){1,3}|\d+番地)\s*(.+?)(?:\s*内|\d+F)?$",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    place_name = match.group(1).strip(" ()（）")
    return place_name if len(place_name) >= 4 else ""


def normalize_place_query(value: object) -> str:
    query = text(value)
    query = re.sub(r"terrace\s*mall", "テラスモール", query, flags=re.IGNORECASE)
    return re.sub(r"[・･\s]", "", query)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def cache_path(raw_dir: Path, cinema_id: str, query: str = "") -> Path:
    digest = hashlib.sha1(f"{cinema_id}:{query}".encode()).hexdigest()[:12]
    return raw_dir / f"{digest}.json"


def build_url(address: str) -> str:
    return "https://nominatim.openstreetmap.org/search?" + urlencode(
        {
            "q": address,
            "format": "jsonv2",
            "limit": 5,
            "addressdetails": 1,
            "countrycodes": "jp",
        }
    )


def fetch_candidates(address: str) -> tuple[str, list[dict[str, object]]]:
    url = build_url(address)
    request = Request(
        url,
        headers={"User-Agent": "map-lgb-fond cinema coordinate collector/0.1"},
    )
    with urlopen(request, timeout=30) as response:
        return url, json.loads(response.read().decode())


def select_candidate(
    row: dict[str, str], candidates: list[dict[str, object]]
) -> dict[str, object] | None:
    prefecture = normalize_prefecture(row.get("prefecture"))
    locality = address_locality(row.get("address"))
    for candidate in candidates:
        display_name = normalize_prefecture(candidate.get("display_name"))
        if (not prefecture or prefecture in display_name) and (
            not locality or locality in display_name
        ):
            return candidate
    return None


def collect_coordinates(
    *,
    review_csv: Path,
    output_csv: Path,
    raw_dir: Path,
    max_requests: int,
    sleep_seconds: float,
    dry_run: bool,
    verified_at: str,
) -> dict[str, int]:
    review_rows = read_csv(review_csv)
    existing_rows = read_csv(output_csv)
    review_by_id = {row["cinema_id"]: row for row in review_rows}
    output_by_id = {
        row["cinema_id"]: row
        for row in existing_rows
        if row.get("cinema_id")
        and (
            row["cinema_id"] not in review_by_id
            or select_candidate(
                review_by_id[row["cinema_id"]],
                [{"display_name": row.get("display_name", "")}],
            )
        )
    }
    targets = [row for row in review_rows if row.get("cinema_id") not in output_by_id]
    summary = {
        "targetCount": len(review_rows),
        "existingCount": len(output_by_id),
        "pendingCount": len(targets),
        "requestCount": 0,
        "cacheHitCount": 0,
        "matchedCount": 0,
        "unresolvedCount": 0,
        "errorCount": 0,
    }
    if dry_run:
        print(json.dumps(summary, ensure_ascii=False))
        return summary

    raw_dir.mkdir(parents=True, exist_ok=True)
    for row in targets:
        if summary["requestCount"] >= max_requests:
            break
        source_url = ""
        candidate = None
        try:
            place_name = row.get("mall_name") or place_name_from_address(row["address"])
            queries = [
                row["address"],
                f"{row['name']} {normalize_prefecture(row['prefecture'])}",
                " ".join(
                    part
                    for part in (
                        place_name,
                        normalize_prefecture(row["prefecture"]),
                        address_locality(row["address"]),
                    )
                    if part
                ),
                " ".join(
                    part
                    for part in (
                        normalize_place_query(place_name),
                        normalize_prefecture(row["prefecture"]),
                        address_locality(row["address"]),
                    )
                    if part
                ),
            ]
            for query in dict.fromkeys(query for query in queries if query.strip()):
                path = cache_path(raw_dir, row["cinema_id"], query)
                source_url = build_url(query)
                if path.exists():
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    summary["cacheHitCount"] += 1
                elif summary["requestCount"] < max_requests:
                    summary["requestCount"] += 1
                    source_url, payload = fetch_candidates(query)
                    path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    time.sleep(sleep_seconds)
                else:
                    break
                candidate = select_candidate(row, payload)
                if candidate is not None:
                    break
            if candidate is None:
                summary["unresolvedCount"] += 1
                continue
            output_by_id[row["cinema_id"]] = {
                "cinema_id": row["cinema_id"],
                "name": row["name"],
                "prefecture": normalize_prefecture(row["prefecture"]),
                "address": row["address"],
                "lat": text(candidate.get("lat")),
                "lon": text(candidate.get("lon")),
                "display_name": text(candidate.get("display_name")),
                "osm_type": text(candidate.get("osm_type")),
                "osm_id": text(candidate.get("osm_id")),
                "source_url": source_url,
                "source_type": "osm_nominatim",
                "confidence": "medium",
                "verified_at": verified_at,
            }
            summary["matchedCount"] += 1
        except (OSError, ValueError, json.JSONDecodeError):
            summary["errorCount"] += 1

    write_csv(output_csv, list(output_by_id.values()))
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="大型映画館の公式住所をNominatimで座標化")
    parser.add_argument(
        "--review-csv",
        type=Path,
        default=Path("data/processed/cinemas/official_chain_cinemas_priority_review.csv"),
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("data/processed/cinemas/official_chain_cinema_coordinates.csv"),
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=Path("data/raw/cinemas/geocoding"),
    )
    parser.add_argument("--max-requests", type=int, default=50)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verified-at", default=date.today().isoformat())
    args = parser.parse_args()
    collect_coordinates(
        review_csv=args.review_csv,
        output_csv=args.output_csv,
        raw_dir=args.raw_dir,
        max_requests=args.max_requests,
        sleep_seconds=args.sleep_seconds,
        dry_run=args.dry_run,
        verified_at=args.verified_at,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
