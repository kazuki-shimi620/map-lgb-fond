from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE_URL = "https://www.jcsc.or.jp"
SC_OPEN_LIST_URL = f"{BASE_URL}/sc_data/sc_open/sc_list"
YEAR_LINK_PATTERN = re.compile(r"(?P<year>20\d{2})年\s*[\(（]一覧表[\)）]")
NOTE_PATTERN = re.compile(r"[（(]?注(?P<num>\d+)[）)]?")
FULL_DATE_PATTERN = re.compile(r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
MONTH_ONLY_PATTERN = re.compile(r"(?P<month>\d{1,2})月")
AREA_NUMBER_PATTERN = re.compile(r"(?P<number>\d[\d,]*(?:\.\d+)?)")
TENANT_COUNT_PATTERN = re.compile(r"\d+")
CORP_MARK_PATTERN = re.compile(r"㈱|（株）|\(株\)")
COMPANY_SPLIT_PATTERN = re.compile(r"[、,，]")
TENANT_SPLIT_PATTERN = re.compile(r"[、,，]")
EMPTY_VALUE_PATTERN = re.compile(r"^([-–—ー]+|非公開)$")
PREFECTURE_NAMES = [
    "北海道",
    "青森県",
    "岩手県",
    "宮城県",
    "秋田県",
    "山形県",
    "福島県",
    "茨城県",
    "栃木県",
    "群馬県",
    "埼玉県",
    "千葉県",
    "東京都",
    "神奈川県",
    "新潟県",
    "富山県",
    "石川県",
    "福井県",
    "山梨県",
    "長野県",
    "岐阜県",
    "静岡県",
    "愛知県",
    "三重県",
    "滋賀県",
    "京都府",
    "大阪府",
    "兵庫県",
    "奈良県",
    "和歌山県",
    "鳥取県",
    "島根県",
    "岡山県",
    "広島県",
    "山口県",
    "徳島県",
    "香川県",
    "愛媛県",
    "高知県",
    "福岡県",
    "佐賀県",
    "長崎県",
    "熊本県",
    "大分県",
    "宮崎県",
    "鹿児島県",
    "沖縄県",
]
PREFECTURE_PATTERN = re.compile("|".join(PREFECTURE_NAMES))
CITY_PATTERN = re.compile(
    r"(?P<prefecture>{})(?P<city>.+?[市区町村])".format("|".join(PREFECTURE_NAMES))
)
SUMMARY_YEARLY_PATTERN = re.compile(r"(?P<raw>20\d{2}年オープンSC総数[：:]\s*(?P<count>\d+)SC)")
SUMMARY_MONTHLY_PATTERN = re.compile(r"(?P<raw>20\d{2}年\d{1,2}月のオープンSC数[：:]\s*\d+SC)")
JST = timezone(timedelta(hours=9))
SCHEMA_VERSION = "1.0.0"
DEFINITION_VERSION = "2025_jcsc_standard"
EXPECTED_HEADER_KEYS = [
    "no",
    "open_date",
    "name",
    "address",
    "developer",
    "store_area",
    "key_tenants",
    "tenant_count",
]
CSV_FIELDNAMES = [
    "source",
    "source_url",
    "target_year",
    "no",
    "open_date_raw",
    "open_year",
    "open_month",
    "open_day",
    "open_date",
    "name",
    "address_raw",
    "prefecture",
    "city",
    "developer_raw",
    "developers",
    "store_area_raw",
    "store_area_sqm",
    "store_area_type",
    "key_tenants_raw",
    "key_tenants",
    "tenant_count_raw",
    "tenant_count",
    "notes",
    "parse_status",
    "warnings",
]


class JcscCollectError(RuntimeError):
    pass


@dataclass(frozen=True)
class Link:
    href: str
    text: str


class JcscHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.links: list[Link] = []
        self.text_parts: list[str] = []
        self._table_stack: list[list[list[str]]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._current_link_href: str | None = None
        self._current_link_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if tag == "table":
            self._table_stack.append([])
        elif tag == "tr" and self._table_stack:
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
        elif tag == "a":
            self._current_link_href = attr.get("href")
            self._current_link_text = []
        elif tag == "br" and self._current_cell is not None:
            self._current_cell.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            self._current_row.append(normalize_space("".join(self._current_cell)))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if any(cell for cell in self._current_row):
                self._table_stack[-1].append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._table_stack:
            table = self._table_stack.pop()
            if table:
                self.tables.append(table)
        elif tag == "a" and self._current_link_href:
            self.links.append(
                Link(
                    self._current_link_href,
                    normalize_space("".join(self._current_link_text or [])),
                )
            )
            self._current_link_href = None
            self._current_link_text = None

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self._current_cell is not None:
            self._current_cell.append(data)
        if self._current_link_text is not None:
            self._current_link_text.append(data)


def normalize_space(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.replace("\xa0", " "))
    return re.sub(r"\s+", " ", normalized).strip()


def fetch_html(url: str, timeout: float = 30.0) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "map-lgb-fond/0.1 (+https://github.com/kazuki-shimi620/map-lgb-fond)"
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(content_type, errors="replace")


def parse_html(html: str) -> JcscHtmlParser:
    parser = JcscHtmlParser()
    parser.feed(html)
    return parser


def resolve_year_url(target_year: int, index_html: str | None = None) -> str:
    html = index_html if index_html is not None else fetch_html(SC_OPEN_LIST_URL)
    parser = parse_html(html)
    links_by_year: dict[int, str] = {}
    for link in parser.links:
        match = YEAR_LINK_PATTERN.search(link.text)
        if match:
            links_by_year[int(match.group("year"))] = urljoin(BASE_URL, link.href)

    if target_year in links_by_year:
        return links_by_year[target_year]

    page_text = normalize_space(" ".join(parser.text_parts))
    current_year = datetime.now(JST).year
    if str(target_year) in page_text or target_year == current_year:
        return SC_OPEN_LIST_URL

    known_years = ", ".join(str(year) for year in sorted(links_by_year))
    raise JcscCollectError(f"year link not found: {target_year} (known years: {known_years})")


def fetch_sc_open_data(
    target_year: int,
    source: str = "jcsc",
    normalize: bool = True,
    include_raw: bool = True,
    *,
    source_url: str | None = None,
    html: str | None = None,
) -> dict[str, Any]:
    if source != "jcsc":
        raise ValueError("only source='jcsc' is supported")

    resolved_url = source_url or (
        SC_OPEN_LIST_URL if html is not None else resolve_year_url(target_year)
    )
    page_html = html if html is not None else fetch_html(resolved_url)
    parsed = parse_html(page_html)
    table = select_sc_table(parsed.tables)
    if not table:
        raise JcscCollectError("SC open data table was not found")

    payload = build_payload(
        target_year=target_year,
        source=source,
        source_url=resolved_url,
        page_text=normalize_space(" ".join(parsed.text_parts)),
        table=table,
        normalize=normalize,
        include_raw=include_raw,
    )
    return payload


def select_sc_table(tables: list[list[list[str]]]) -> list[list[str]] | None:
    for table in tables:
        if not table:
            continue
        header = table[0]
        normalized_header = [normalize_header(cell) for cell in header]
        if "name" in normalized_header and "address" in normalized_header:
            return table
    return None


def normalize_header(value: str) -> str:
    text = re.sub(r"\s+", "", value)
    text = text.replace("（", "(").replace("）", ")")
    if text in {"No", "NO", "No."}:
        return "no"
    if "オープン" in text:
        return "open_date"
    if text in {"SC名", "SC名称"} or ("SC" in text and "名" in text):
        return "name"
    if "所在地" in text:
        return "address"
    if "ディベロッパー" in text or "デベロッパー" in text:
        return "developer"
    if "店舗面積" in text:
        return "store_area"
    if "キーテナント" in text:
        return "key_tenants"
    if "テナント数" in text:
        return "tenant_count"
    return text


def build_payload(
    *,
    target_year: int,
    source: str,
    source_url: str,
    page_text: str,
    table: list[list[str]],
    normalize: bool,
    include_raw: bool,
) -> dict[str, Any]:
    header = [normalize_header(cell) for cell in table[0]]
    summary = parse_summary(page_text)
    items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for row_index, row in enumerate(table[1:], start=1):
        if not any(row):
            continue
        item = parse_row(
            row=row,
            header=header,
            target_year=target_year,
            row_index=row_index,
            normalize=normalize,
            include_raw=include_raw,
        )
        items.append(item)
        if item["warnings"]:
            errors.append(
                {
                    "row_index": row_index,
                    "raw_row": row,
                    "parse_status": item["parse_status"],
                    "warnings": item["warnings"],
                }
            )

    return {
        "meta": {
            "source": source,
            "target_year": target_year,
            "source_url": source_url,
            "fetched_at": datetime.now(JST).isoformat(timespec="seconds"),
            "schema_version": SCHEMA_VERSION,
            "definition_version": DEFINITION_VERSION,
        },
        "summary": summary,
        "items": items,
        "errors": errors,
    }


def parse_summary(page_text: str) -> dict[str, Any]:
    yearly_match = SUMMARY_YEARLY_PATTERN.search(page_text)
    monthly_match = SUMMARY_MONTHLY_PATTERN.search(page_text)
    return {
        "monthly_open_count_raw": monthly_match.group("raw") if monthly_match else None,
        "yearly_open_count_raw": yearly_match.group("raw") if yearly_match else None,
        "yearly_open_count": int(yearly_match.group("count")) if yearly_match else None,
    }


def parse_row(
    *,
    row: list[str],
    header: list[str],
    target_year: int,
    row_index: int,
    normalize: bool,
    include_raw: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    if len(row) != len(header):
        warnings.append("column_count_mismatch")

    values = {key: row[index] if index < len(row) else "" for index, key in enumerate(header)}
    if not set(EXPECTED_HEADER_KEYS).issubset(values):
        positional = {
            key: row[index] if index < len(row) else ""
            for index, key in enumerate(EXPECTED_HEADER_KEYS)
        }
        values = {**positional, **values}

    raw_values = {key: values.get(key, "") for key in EXPECTED_HEADER_KEYS}
    for value in raw_values.values():
        if "\n" in value:
            warnings.append("multiline_cell_detected")
            break

    all_notes = sorted(
        {f"注{number}" for number in NOTE_PATTERN.findall(" ".join(raw_values.values()))}
    )
    if all_notes:
        warnings.append("note_detected")

    if not normalize:
        return {
            "no": raw_values["no"],
            "open_date_raw": raw_values["open_date"],
            "open_year": target_year,
            "name": raw_values["name"],
            "address_raw": raw_values["address"],
            "developer_raw": raw_values["developer"],
            "store_area_raw": raw_values["store_area"],
            "key_tenants_raw": raw_values["key_tenants"],
            "tenant_count_raw": raw_values["tenant_count"],
            "raw": raw_values if include_raw else None,
            "notes": all_notes,
            "parse_status": "warning" if warnings else "ok",
            "warnings": dedupe(warnings),
        }

    no = parse_int(raw_values["no"])
    open_month, open_day, open_date = parse_open_date(raw_values["open_date"], target_year)
    if raw_values["open_date"] and open_month is None and not all_notes:
        warnings.append("open_date_parse_failed")

    prefecture, city = parse_address(raw_values["address"])
    if raw_values["address"] and prefecture is None:
        warnings.append("address_parse_failed")

    store_area_sqm, store_area_type = parse_store_area(raw_values["store_area"])
    if (
        raw_values["store_area"]
        and store_area_sqm is None
        and not is_empty_value(raw_values["store_area"])
    ):
        warnings.append("area_parse_failed")

    tenant_count = parse_tenant_count(raw_values["tenant_count"])
    if (
        raw_values["tenant_count"]
        and tenant_count is None
        and not is_empty_value(raw_values["tenant_count"])
    ):
        warnings.append("tenant_count_parse_failed")

    item: dict[str, Any] = {
        "no": no,
        "open_date_raw": raw_values["open_date"],
        "open_year": target_year,
        "open_month": open_month,
        "open_day": open_day,
        "open_date": open_date,
        "name": strip_notes(raw_values["name"]),
        "address_raw": raw_values["address"],
        "prefecture": prefecture,
        "city": city,
        "developer_raw": raw_values["developer"],
        "developers": split_companies(raw_values["developer"]),
        "store_area_raw": raw_values["store_area"],
        "store_area_sqm": store_area_sqm,
        "store_area_type": store_area_type,
        "key_tenants_raw": raw_values["key_tenants"],
        "key_tenants": split_values(raw_values["key_tenants"], TENANT_SPLIT_PATTERN),
        "tenant_count_raw": raw_values["tenant_count"],
        "tenant_count": tenant_count,
        "notes": all_notes,
        "parse_status": "warning" if warnings else "ok",
        "warnings": dedupe(warnings),
    }
    if include_raw:
        item["raw"] = raw_values
    return item


def parse_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def parse_open_date(value: str, target_year: int) -> tuple[int | None, int | None, str | None]:
    cleaned = strip_notes(value)
    match = FULL_DATE_PATTERN.search(cleaned)
    if match:
        month = int(match.group("month"))
        day = int(match.group("day"))
        return month, day, f"{target_year:04d}-{month:02d}-{day:02d}"

    match = MONTH_ONLY_PATTERN.search(cleaned)
    if match:
        return int(match.group("month")), None, None
    return None, None, None


def parse_address(value: str) -> tuple[str | None, str | None]:
    cleaned = strip_notes(value)
    prefecture_match = PREFECTURE_PATTERN.search(cleaned)
    city_match = CITY_PATTERN.search(cleaned)
    return (
        prefecture_match.group(0) if prefecture_match else None,
        city_match.group("city") if city_match else None,
    )


def parse_store_area(value: str) -> tuple[float | None, str]:
    if "★" in value:
        area_type = "gross_leasable_area"
    elif "◇" in value:
        area_type = "large_scale_retail_store_area"
    else:
        area_type = "store_area"

    match = AREA_NUMBER_PATTERN.search(strip_notes(value))
    if not match:
        return None, area_type
    return float(match.group("number").replace(",", "")), area_type


def parse_tenant_count(value: str) -> int | None:
    match = TENANT_COUNT_PATTERN.search(strip_notes(value).replace(",", ""))
    return int(match.group(0)) if match else None


def split_companies(value: str) -> list[str]:
    cleaned = CORP_MARK_PATTERN.sub("", strip_notes(value))
    return split_values(cleaned, COMPANY_SPLIT_PATTERN)


def split_values(value: str, pattern: re.Pattern[str]) -> list[str]:
    cleaned = strip_notes(value)
    if not cleaned or is_empty_value(cleaned):
        return []
    return [part for part in (normalize_space(part) for part in pattern.split(cleaned)) if part]


def strip_notes(value: str) -> str:
    return normalize_space(NOTE_PATTERN.sub("", value))


def is_empty_value(value: str) -> bool:
    return bool(EMPTY_VALUE_PATTERN.fullmatch(normalize_space(value)))


def dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def write_outputs(
    *,
    payload: dict[str, Any],
    html: str,
    target_year: int,
    raw_dir: Path,
    processed_dir: Path,
    cache_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / f"jcsc_sc_open_{target_year}_raw.html"
    json_path = processed_dir / f"jcsc_sc_open_{target_year}.json"
    csv_path = processed_dir / f"jcsc_sc_open_{target_year}.csv"
    errors_path = cache_dir / f"jcsc_sc_open_{target_year}_errors.json"

    raw_path.write_text(html, encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_items_csv(payload, csv_path)
    errors_path.write_text(
        json.dumps(payload["errors"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return raw_path, json_path, csv_path, errors_path


def write_items_csv(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in flatten_items_for_csv(payload):
            writer.writerow(row)
    return output_path


def flatten_items_for_csv(payload: dict[str, Any]) -> list[dict[str, Any]]:
    meta = payload["meta"]
    rows: list[dict[str, Any]] = []
    for item in payload["items"]:
        rows.append(
            {
                "source": meta["source"],
                "source_url": meta["source_url"],
                "target_year": meta["target_year"],
                "no": item.get("no"),
                "open_date_raw": item.get("open_date_raw"),
                "open_year": item.get("open_year"),
                "open_month": item.get("open_month"),
                "open_day": item.get("open_day"),
                "open_date": item.get("open_date"),
                "name": item.get("name"),
                "address_raw": item.get("address_raw"),
                "prefecture": item.get("prefecture"),
                "city": item.get("city"),
                "developer_raw": item.get("developer_raw"),
                "developers": join_csv_list(item.get("developers")),
                "store_area_raw": item.get("store_area_raw"),
                "store_area_sqm": item.get("store_area_sqm"),
                "store_area_type": item.get("store_area_type"),
                "key_tenants_raw": item.get("key_tenants_raw"),
                "key_tenants": join_csv_list(item.get("key_tenants")),
                "tenant_count_raw": item.get("tenant_count_raw"),
                "tenant_count": item.get("tenant_count"),
                "notes": join_csv_list(item.get("notes")),
                "parse_status": item.get("parse_status"),
                "warnings": join_csv_list(item.get("warnings")),
            }
        )
    return rows


def join_csv_list(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        return "|".join(str(item) for item in value)
    return str(value)


def collect_year(
    *,
    target_year: int,
    raw_dir: Path,
    processed_dir: Path,
    cache_dir: Path,
    use_cache: bool,
    force: bool,
) -> tuple[Path, Path, Path, Path]:
    raw_path = raw_dir / f"jcsc_sc_open_{target_year}_raw.html"
    if use_cache and raw_path.exists() and not force:
        html = raw_path.read_text(encoding="utf-8")
        source_url = resolve_year_url(target_year, html)
    else:
        source_url = resolve_year_url(target_year)
        html = fetch_html(source_url)

    payload = fetch_sc_open_data(target_year=target_year, source_url=source_url, html=html)
    return write_outputs(
        payload=payload,
        html=html,
        target_year=target_year,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        cache_dir=cache_dir,
    )


def build_target_years(args: argparse.Namespace) -> list[int]:
    if args.year:
        return args.year
    if args.from_year is None or args.to_year is None:
        raise JcscCollectError("--year or both --from-year/--to-year are required")
    if args.from_year > args.to_year:
        raise JcscCollectError("--from-year must be less than or equal to --to-year")
    return list(range(args.from_year, args.to_year + 1))


def write_combined_csv(payloads: list[dict[str, Any]], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for payload in payloads:
            for row in flatten_items_for_csv(payload):
                writer.writerow(row)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect JCSC shopping center open data.")
    parser.add_argument("--year", nargs="+", type=int)
    parser.add_argument("--from-year", type=int)
    parser.add_argument("--to-year", type=int)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/jcsc"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/jcsc"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/jcsc"))
    parser.add_argument(
        "--combined-csv",
        type=Path,
        default=Path("data/processed/jcsc/jcsc_sc_open.csv"),
    )
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        collected_payloads: list[dict[str, Any]] = []
        for year in build_target_years(args):
            _, json_path, csv_path, errors_path = collect_year(
                target_year=year,
                raw_dir=args.raw_dir,
                processed_dir=args.processed_dir,
                cache_dir=args.cache_dir,
                use_cache=args.cache,
                force=args.force,
            )
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            collected_payloads.append(payload)
            print(
                f"collected JCSC SC open data: {json_path} "
                f"({len(payload['items'])} items, errors: {len(payload['errors'])}, "
                f"csv: {csv_path}, error log: {errors_path})"
            )
        write_combined_csv(collected_payloads, args.combined_csv)
        print(f"wrote combined JCSC SC CSV: {args.combined_csv}")
    except (JcscCollectError, OSError, ValueError) as error:
        print(f"JCSC collect failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
