from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

BRAND_WORDS = (
    "ローソン",
    "ユナイテッドシネマ",
    "イオンシネマ",
    "tohoシネマズ",
    "tohocinemas",
    "シネプレックス",
    "movix",
    "tジョイ",
    "シネマサンシャイン",
    "109シネマズ",
)


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    normalized = re.sub(r"[^0-9a-zぁ-んァ-ヶ一-龠]", "", text)
    return normalized.replace("terracemall", "テラスモール")


def normalize_prefecture(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def venue_key(value: object) -> str:
    text = normalize_name(value)
    for word in BRAND_WORDS:
        text = text.replace(normalize_name(word), "")
    return text


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _candidate_score(cinema: dict[str, str], candidate: dict[str, str]) -> float:
    full_left = normalize_name(cinema.get("name"))
    full_right = normalize_name(candidate.get("name"))
    key_left = venue_key(cinema.get("name"))
    key_right = venue_key(candidate.get("name"))
    if full_left == full_right:
        return 1.0
    if key_left and key_left == key_right:
        return 0.99
    if len(key_left) >= 4 and key_left in full_right:
        return 0.97
    if min(len(key_left), len(key_right)) < 3:
        return 0.0
    return SequenceMatcher(None, key_left, key_right).ratio()


def match_osm(
    cinema: dict[str, str], osm_rows: list[dict[str, str]]
) -> tuple[dict[str, str] | None, float]:
    scoped = [
        row
        for row in osm_rows
        if row.get("category_id") == "cinema"
        and (
            not row.get("prefecture")
            or not cinema.get("prefecture")
            or normalize_prefecture(row.get("prefecture"))
            == normalize_prefecture(cinema.get("prefecture"))
        )
    ]
    ranked = sorted(
        ((_candidate_score(cinema, row), row) for row in scoped),
        key=lambda item: item[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] < 0.86:
        return None, 0.0
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if ranked[0][0] < 0.99 and ranked[0][0] - second_score < 0.08:
        return None, ranked[0][0]
    return ranked[0][1], ranked[0][0]


def match_jcsc(
    cinema: dict[str, str], jcsc_rows: list[dict[str, str]]
) -> dict[str, str] | None:
    mall_key = normalize_name(cinema.get("mall_name"))
    cinema_key = venue_key(cinema.get("name"))
    address_key = normalize_name(cinema.get("address"))
    keys = ([mall_key] if len(mall_key) >= 4 else []) + (
        [cinema_key] if len(cinema_key) >= 5 else []
    )
    if not keys and not address_key:
        return None
    matches = []
    for row in jcsc_rows:
        if cinema.get("prefecture") and normalize_prefecture(
            row.get("prefecture")
        ) != normalize_prefecture(cinema.get("prefecture")):
            continue
        values = (row.get("name", ""), row.get("key_tenants", ""))
        normalized_values = [normalize_name(value) for value in values if value]
        row_name = normalize_name(row.get("name"))
        if any(
            key == value or key in value
            for key in keys
            for value in normalized_values
        ) or (len(row_name) >= 5 and row_name in address_key):
            matches.append(row)
    located = [
        row
        for row in matches
        if row.get("lat")
        and row.get("lon")
        and row.get("coordinate_source")
        not in {"address_point", "municipality_representative", "none"}
    ]
    unique_names = {normalize_name(row.get("name")) for row in located}
    return located[0] if len(unique_names) == 1 else None


def match_manual(
    cinema: dict[str, str], manual_rows: list[dict[str, str]]
) -> dict[str, str] | None:
    cinema_id = cinema.get("cinema_id", "")
    return next(
        (
            row
            for row in manual_rows
            if cinema_id
            and row.get("cinema_id") == cinema_id
            and row.get("lat")
            and row.get("lon")
        ),
        None,
    )


def review_priority_reason(cinema: dict[str, str]) -> str:
    reasons = []
    try:
        screen_count = int(cinema.get("screen_count", "") or 0)
    except ValueError:
        screen_count = 0
    if screen_count >= 5:
        reasons.append(f"{screen_count}スクリーン")
    if cinema.get("mall_name", "").strip():
        reasons.append("大型商業施設併設候補")
    return "・".join(reasons)


def enrich(
    cinemas: list[dict[str, str]],
    osm_rows: list[dict[str, str]],
    jcsc_rows: list[dict[str, str]],
    manual_rows: list[dict[str, str]] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    output: list[dict[str, str]] = []
    review: list[dict[str, str]] = []
    for source in cinemas:
        row = dict(source)
        osm_match, score = match_osm(row, osm_rows)
        manual_match = match_manual(row, manual_rows or [])
        if manual_match:
            row["lat"] = manual_match.get("lat", "")
            row["lon"] = manual_match.get("lon", "")
            row["coordinate_source"] = manual_match.get("source_type") or (
                f"nominatim:{manual_match.get('osm_type', '')}:"
                f"{manual_match.get('osm_id', '')}"
            )
        elif osm_match:
            row["lat"] = osm_match.get("lat", "")
            row["lon"] = osm_match.get("lon", "")
            row["coordinate_source"] = f"osm:{osm_match.get('id', '')}"
        elif jcsc_match := match_jcsc(row, jcsc_rows):
            row["lat"] = jcsc_match.get("lat", "")
            row["lon"] = jcsc_match.get("lon", "")
            row["coordinate_source"] = f"jcsc:{jcsc_match.get('name', '')}"
        if not row.get("lat") or not row.get("lon"):
            review.append(
                {
                    "cinema_id": row.get("cinema_id", ""),
                    "name": row.get("name", ""),
                    "operator": row.get("operator", ""),
                    "prefecture": row.get("prefecture", ""),
                    "address": row.get("address", ""),
                    "mall_name": row.get("mall_name", ""),
                    "screen_count": row.get("screen_count", ""),
                    "priority_reason": review_priority_reason(row),
                    "best_osm_score": f"{score:.3f}" if score else "",
                    "source_url": row.get("source_url", ""),
                }
            )
        output.append(row)
    return output, review


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="公式映画館一覧をOSM・JCSCで座標補完")
    parser.add_argument("--cinemas", type=Path, required=True)
    parser.add_argument("--osm", type=Path, required=True)
    parser.add_argument("--jcsc", type=Path, action="append", default=[])
    parser.add_argument("--manual-coordinates", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--priority-review-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()

    cinemas = read_csv(args.cinemas)
    osm_rows = read_csv(args.osm)
    jcsc_rows = [row for path in args.jcsc for row in read_csv(path)]
    manual_rows = [row for path in args.manual_coordinates for row in read_csv(path)]
    enriched, review = enrich(cinemas, osm_rows, jcsc_rows, manual_rows)
    fieldnames = list(cinemas[0]) if cinemas else []
    write_csv(args.output, enriched, fieldnames)
    review_fields = [
        "cinema_id",
        "name",
        "operator",
        "prefecture",
        "address",
        "mall_name",
        "screen_count",
        "priority_reason",
        "best_osm_score",
        "source_url",
    ]
    write_csv(args.review_output, review, review_fields)
    priority_review = [row for row in review if row["priority_reason"]]
    write_csv(args.priority_review_output, priority_review, review_fields)
    sources = Counter(
        row.get("coordinate_source", "").split(":", 1)[0] or "unmatched"
        for row in enriched
    )
    report = {
        "official_cinema_count": len(cinemas),
        "osm_cinema_count": sum(row.get("category_id") == "cinema" for row in osm_rows),
        "coordinate_matched_count": len(enriched) - len(review),
        "coordinate_match_rate": (
            round((len(enriched) - len(review)) / len(enriched), 4) if enriched else 0
        ),
        "unmatched_count": len(review),
        "priority_review_count": len(priority_review),
        "coordinate_sources": dict(sorted(sources.items())),
        "operator_counts": dict(
            sorted(Counter(row.get("operator", "") for row in cinemas).items())
        ),
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
