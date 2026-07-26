from __future__ import annotations

import argparse
import csv
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MANUAL_FIELDS = [
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
EXTRA_REVIEW_FIELDS = [
    "query",
    "candidate_status",
    "candidate_name",
    "candidate_display_name",
    "candidate_lat",
    "candidate_lon",
    "candidate_url",
    "unresolved_reason",
]


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalized_name(value: object) -> str:
    return re.sub(r"[\s　・･（）()\-/／、,\.。]", "", text(value).lower())


def canonical_name(value: object) -> str:
    return (
        normalized_name(value)
        .replace("バーク", "パーク")
        .replace("ショッピングセンター", "sc")
        .replace("ショッピングモール", "モール")
    )


def score_name(query_name: str, osm_name: str, display_name: str) -> int:
    query = canonical_name(query_name)
    candidate_name = canonical_name(osm_name)
    display = canonical_name(display_name)
    if not query:
        return 0
    if candidate_name and (query in candidate_name or candidate_name in query):
        return 4
    if query in display:
        return 3

    tokens = [
        token
        for token in re.split(
            r"(イオンモール|イオンタウン|ららぽーと|ゆめタウン|アリオ|アウトレット|"
            r"百貨店|モール|プラザ|タウン|ウォーク|フジグラン|フォレストモール|"
            r"アピタ|ピアゴ)",
            query_name,
        )
        if len(normalized_name(token)) >= 3
    ]
    if len(tokens) >= 2 and all(canonical_name(token) in display for token in tokens[:2]):
        return 2
    return 0


def prefecture_matches(prefecture: str, display_name: str) -> bool:
    return not prefecture or prefecture in display_name


def municipality_matches(municipality: str, display_name: str) -> bool:
    if not municipality or municipality in display_name:
        return True
    if municipality.endswith("区") and "市" in municipality:
        return municipality.split("市", 1)[0] + "市" in display_name
    if "郡" in municipality:
        return municipality.split("郡", 1)[-1] in display_name
    return False


def geocode(query: str) -> tuple[str, list[dict[str, object]]]:
    url = "https://nominatim.openstreetmap.org/search?" + urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
            "addressdetails": 1,
            "countrycodes": "jp",
        }
    )
    request = Request(
        url,
        headers={"User-Agent": "map-lgb-fond commercial facility geocode review"},
    )
    with urlopen(request, timeout=25) as response:
        return url, json.loads(response.read().decode())


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_queries(row: dict[str, str]) -> list[str]:
    name = text(row.get("name"))
    prefecture = text(row.get("prefecture"))
    municipality = text(row.get("municipality") or row.get("city"))
    queries = []
    for query in [f"{name} {prefecture} {municipality}", f"{name} {prefecture}", name]:
        normalized = " ".join(query.split())
        if normalized and normalized not in queries:
            queries.append(normalized)
    return queries


def review_row(row: dict[str, str], base_fields: list[str], **extra: object) -> dict[str, object]:
    output = {field: row.get(field, "") for field in base_fields}
    output.update(extra)
    return output


def compact_review_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    compact = []
    seen = set()
    for row in reversed(rows):
        key = (
            text(row.get("prefecture")),
            normalized_name(row.get("name")),
            text(row.get("candidate_status")),
            text(row.get("query")),
        )
        if key in seen:
            continue
        seen.add(key)
        compact.append(row)
    return list(reversed(compact))


def geocode_low_confidence(
    *,
    enriched_csv: Path,
    manual_coordinates_csv: Path,
    review_csv: Path,
    max_queries: int,
    sleep_seconds: float,
    verified_at: str,
) -> dict[str, object]:
    manual_rows = load_csv(manual_coordinates_csv)
    enriched_rows = load_csv(enriched_csv)
    review_rows = load_csv(review_csv)
    if not enriched_rows:
        raise ValueError(f"enriched CSV is empty or missing: {enriched_csv}")

    base_fields = list(enriched_rows[0].keys())
    existing = {
        (row.get("prefecture", ""), normalized_name(row.get("name", "")))
        for row in manual_rows
    }
    reviewed = {
        (row.get("prefecture", ""), normalized_name(row.get("name", "")))
        for row in review_rows
        if row.get("candidate_status") in {"added", "unresolved", "error"}
    }
    low_confidence_rows = [
        row
        for row in enriched_rows
        if row.get("coordinate_source") == "municipality_representative"
    ]
    low_confidence_rows.sort(
        key=lambda row: float(row.get("store_area_sqm") or 0),
        reverse=True,
    )

    added_rows = []
    queried = 0
    for row in low_confidence_rows:
        if queried >= max_queries:
            break
        name = text(row.get("name"))
        prefecture = text(row.get("prefecture"))
        municipality = text(row.get("municipality") or row.get("city"))
        key = (prefecture, normalized_name(name))
        if not name or key in existing or key in reviewed:
            continue

        best = None
        errors = []
        last_url = ""
        queries = build_queries(row)
        for query in queries:
            if queried >= max_queries:
                break
            queried += 1
            try:
                last_url, candidates = geocode(query)
            except Exception as error:  # noqa: BLE001
                errors.append(f"{query}: {error}")
                candidates = []

            for candidate in candidates:
                candidate_name = text(candidate.get("name"))
                display_name = text(candidate.get("display_name"))
                if not prefecture_matches(prefecture, display_name):
                    continue
                name_score = score_name(name, candidate_name, display_name)
                if name_score <= 0:
                    continue
                municipality_score = 1 if municipality_matches(municipality, display_name) else 0
                if municipality and not municipality_score and name_score < 4:
                    continue
                score = (
                    name_score,
                    municipality_score,
                    float(candidate.get("importance") or 0),
                )
                if best is None or score > best[0]:
                    best = (score, candidate, last_url, query)

            time.sleep(sleep_seconds)
            if best and best[0][0] >= 4 and best[0][1] >= 1:
                break

        if best:
            _, candidate, source_url, query = best
            display_name = text(candidate.get("display_name"))
            candidate_name = text(candidate.get("name"))
            manual_row = {
                "match_key": "",
                "name": name,
                "prefecture": prefecture,
                "municipality": municipality,
                "address": display_name,
                "lat": text(candidate.get("lat")),
                "lon": text(candidate.get("lon")),
                "source_url": source_url,
                "source_type": "osm_nominatim_low_confidence_batch",
                "confidence": "medium",
                "verified_at": verified_at,
                "notes": (
                    "low_confidence_batch_name_prefecture_match:"
                    f"{candidate_name};query:{query}"
                ),
            }
            manual_rows.append(manual_row)
            added_rows.append(manual_row)
            existing.add(key)
            review_rows.append(
                review_row(
                    row,
                    base_fields,
                    query=query,
                    candidate_status="added",
                    candidate_name=candidate_name,
                    candidate_display_name=display_name,
                    candidate_lat=manual_row["lat"],
                    candidate_lon=manual_row["lon"],
                    candidate_url=source_url,
                    unresolved_reason="",
                )
            )
        else:
            review_rows.append(
                review_row(
                    row,
                    base_fields,
                    query=" / ".join(queries),
                    candidate_status="error" if errors else "unresolved",
                    candidate_name="",
                    candidate_display_name="",
                    candidate_lat="",
                    candidate_lon="",
                    candidate_url=last_url,
                    unresolved_reason=(
                        " | ".join(errors[:2])
                        if errors
                        else "no_name_prefecture_matched_candidate"
                    ),
                )
            )

    write_csv(manual_coordinates_csv, MANUAL_FIELDS, manual_rows)
    review_fields = base_fields + EXTRA_REVIEW_FIELDS
    write_csv(review_csv, review_fields, compact_review_rows(review_rows))
    return {
        "queried": queried,
        "added": len(added_rows),
        "manualRows": len(manual_rows),
        "reviewRows": len(review_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve low-confidence commercial facility representative coordinates."
    )
    parser.add_argument(
        "--enriched-csv",
        type=Path,
        default=Path("data/processed/jcsc_pdf/jcsc_sc_pdf_new_candidates_with_coordinates.csv"),
    )
    parser.add_argument(
        "--manual-coordinates-csv",
        type=Path,
        default=Path("data/manual/facilities/commercial_facility_manual_coordinates.csv"),
    )
    parser.add_argument(
        "--review-csv",
        type=Path,
        default=Path("data/manual/facilities/commercial_facility_low_confidence_geocode_review.csv"),
    )
    parser.add_argument("--max-queries", type=int, default=120)
    parser.add_argument("--sleep-seconds", type=float, default=1.05)
    parser.add_argument("--verified-at", default="2026-07-16")
    args = parser.parse_args()

    metadata = geocode_low_confidence(
        enriched_csv=args.enriched_csv,
        manual_coordinates_csv=args.manual_coordinates_csv,
        review_csv=args.review_csv,
        max_queries=args.max_queries,
        sleep_seconds=args.sleep_seconds,
        verified_at=args.verified_at,
    )
    print(
        "geocoded low-confidence commercial facilities: "
        f"queried={metadata['queried']} added={metadata['added']} "
        f"manual_rows={metadata['manualRows']} review_rows={metadata['reviewRows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
