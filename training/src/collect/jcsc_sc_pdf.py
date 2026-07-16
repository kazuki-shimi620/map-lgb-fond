from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import pdfplumber
import pypdfium2 as pdfium

SCHEMA_VERSION = "0.1.0"
SOURCE_NAME = "JCSC全国商業施設一覧PDF"
DEFAULT_SOURCE_URL = (
    "https://www.jcsc.or.jp/wpjcsc/wp-content/uploads/2026/05/"
    "35212d5b060e16d7f8db21681d51d151.pdf"
)
DEFAULT_OUTPUT_DIR = Path("data/processed/jcsc_pdf")
DEFAULT_EXISTING_CSV = Path("data/processed/jcsc/jcsc_sc_open.csv")
DEFAULT_MUNICIPALITY_PREFECTURE_CSV = Path("data/processed/address_points/town_points.csv")
DEFAULT_OCR_SCALE = 2.0
ROW_Y_TOLERANCE = 0.006
AREA_PATTERN = re.compile(r"^\d[\d,.]*$")
OPEN_DATE_PATTERN = re.compile(r"(?P<year>\d{4})年(?P<month>\d{1,2})月")
LOCATION_WITH_NAME_PATTERN = re.compile(r"^(?P<location>.+?[市区町村])\s*(?P<name>.+)$")
NAME_NORMALIZE_PATTERN = re.compile(r"[\s・･（）()「」『』【】\[\]、,./／\-]")
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
CSV_FIELDNAMES = [
    "source",
    "source_url",
    "page",
    "column",
    "prefecture",
    "municipality",
    "district",
    "name",
    "store_area_raw",
    "store_area_sqm",
    "open_date_raw",
    "open_year",
    "open_month",
    "ocr_confidence_avg",
    "parse_warnings",
]
PAGE_AUDIT_FIELDNAMES = [
    "page",
    "extracted_rows",
    "open_date_rows",
    "ocr_year_char_count",
    "ocr_month_char_count",
    "ocr_open_date_like_count",
    "row_minus_year_chars",
    "row_minus_month_chars",
    "row_minus_open_date_like",
    "audit_warning",
]


@dataclass(frozen=True)
class OcrToken:
    text: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


@dataclass
class SideState:
    municipality: str = ""
    district: str = ""
    pending_name: str = ""
    pending_confidences: list[float] | None = None


class JcscPdfCollectError(RuntimeError):
    pass


def collect_jcsc_sc_pdf(
    *,
    pdf_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    existing_csv: Path | None = DEFAULT_EXISTING_CSV,
    municipality_prefecture_csv: Path | None = DEFAULT_MUNICIPALITY_PREFECTURE_CSV,
    source_url: str = DEFAULT_SOURCE_URL,
    page_limit: int | None = None,
    ocr_scale: float = DEFAULT_OCR_SCALE,
) -> dict[str, Path | int]:
    if not pdf_path.exists():
        raise JcscPdfCollectError(f"PDF not found: {pdf_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = extract_pdf_rows(
        pdf_path=pdf_path,
        source_url=source_url,
        page_limit=page_limit,
        ocr_scale=ocr_scale,
    )
    municipality_prefecture_map = load_municipality_prefecture_map(municipality_prefecture_csv)
    rows = infer_prefectures_from_municipality(rows, municipality_prefecture_map)
    csv_path = output_dir / "jcsc_sc_pdf_facilities.csv"
    new_candidates_path = output_dir / "jcsc_sc_pdf_new_candidates.csv"
    metadata_path = output_dir / "metadata.json"
    write_csv(csv_path, rows)
    new_candidates = diff_new_candidates(rows, existing_csv) if existing_csv else []
    write_csv(new_candidates_path, new_candidates, fieldnames=CSV_FIELDNAMES + ["match_key"])
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE_NAME,
        "sourceUrl": source_url,
        "pdfPath": str(pdf_path),
        "existingCsv": str(existing_csv) if existing_csv else None,
        "municipalityPrefectureCsv": (
            str(municipality_prefecture_csv) if municipality_prefecture_csv else None
        ),
        "recordCount": len(rows),
        "newCandidateCount": len(new_candidates),
        "prefectureCount": len(
            {str(row.get("prefecture") or "") for row in rows if row.get("prefecture")}
        ),
        "parseWarningCounts": summarize_parse_warnings(rows),
        "pageLimit": page_limit,
        "ocrScale": ocr_scale,
        "notes": [
            "PDFは通常テキストを持たないため、pypdfium2で画像化しmacOS Vision OCRで抽出する。",
            "OCR初版のため、SC名・面積・オープン日のサンプル目視確認を前提にする。",
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "csv": csv_path,
        "new_candidates": new_candidates_path,
        "metadata": metadata_path,
        "record_count": len(rows),
        "new_candidate_count": len(new_candidates),
    }


def extract_pdf_rows(
    *,
    pdf_path: Path,
    source_url: str,
    page_limit: int | None = None,
    ocr_scale: float = DEFAULT_OCR_SCALE,
) -> list[dict[str, Any]]:
    page_count = get_page_count(pdf_path)
    target_count = min(page_count, page_limit) if page_limit else page_count
    pdf = pdfium.PdfDocument(str(pdf_path))
    rows: list[dict[str, Any]] = []
    current_prefecture = ""
    states = {"left": SideState(), "right": SideState()}
    with tempfile.TemporaryDirectory(prefix="jcsc_pdf_ocr_") as tmpdir:
        tmp = Path(tmpdir)
        for page_index in range(target_count):
            image_path = render_page(pdf, page_index, tmp, ocr_scale)
            tokens = recognize_image(image_path)
            page_prefectures = [token.text for token in tokens if token.text in PREFECTURE_NAMES]
            if page_prefectures and not current_prefecture:
                current_prefecture = page_prefectures[0]
            page_rows, current_prefecture = parse_page_tokens(
                tokens=tokens,
                page=page_index + 1,
                source_url=source_url,
                initial_prefecture=current_prefecture,
                states=states,
            )
            rows.extend(page_rows)
    return rows


def audit_pdf_month_counts(
    *,
    pdf_path: Path,
    facilities_csv: Path,
    output_csv: Path,
    page_limit: int | None = None,
    ocr_scale: float = DEFAULT_OCR_SCALE,
) -> list[dict[str, Any]]:
    if not pdf_path.exists():
        raise JcscPdfCollectError(f"PDF not found: {pdf_path}")
    if not facilities_csv.exists():
        raise JcscPdfCollectError(f"facilities CSV not found: {facilities_csv}")
    page_count = get_page_count(pdf_path)
    target_count = min(page_count, page_limit) if page_limit else page_count
    rows_by_page: dict[int, list[dict[str, str]]] = {
        page: [] for page in range(1, target_count + 1)
    }
    with facilities_csv.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            try:
                page = int(row.get("page") or 0)
            except ValueError:
                continue
            if 1 <= page <= target_count:
                rows_by_page.setdefault(page, []).append(row)

    pdf = pdfium.PdfDocument(str(pdf_path))
    audit_rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="jcsc_pdf_month_audit_") as tmpdir:
        tmp = Path(tmpdir)
        for page_index in range(target_count):
            page = page_index + 1
            image_path = render_page(pdf, page_index, tmp, ocr_scale)
            tokens = recognize_image(image_path)
            page_text = " ".join(token.text for token in tokens)
            extracted_rows = len(rows_by_page.get(page, []))
            open_date_rows = sum(1 for row in rows_by_page.get(page, []) if row.get("open_month"))
            year_char_count = page_text.count("年")
            month_char_count = page_text.count("月")
            open_date_like_count = len(OPEN_DATE_PATTERN.findall(page_text))
            audit_warning = []
            if extracted_rows != year_char_count:
                audit_warning.append("row_year_char_mismatch")
            if extracted_rows != month_char_count:
                audit_warning.append("row_month_char_mismatch")
            if extracted_rows != open_date_like_count:
                audit_warning.append("row_open_date_like_mismatch")
            audit_rows.append(
                {
                    "page": page,
                    "extracted_rows": extracted_rows,
                    "open_date_rows": open_date_rows,
                    "ocr_year_char_count": year_char_count,
                    "ocr_month_char_count": month_char_count,
                    "ocr_open_date_like_count": open_date_like_count,
                    "row_minus_year_chars": extracted_rows - year_char_count,
                    "row_minus_month_chars": extracted_rows - month_char_count,
                    "row_minus_open_date_like": extracted_rows - open_date_like_count,
                    "audit_warning": "|".join(audit_warning),
                }
            )
    write_csv(output_csv, audit_rows, fieldnames=PAGE_AUDIT_FIELDNAMES)
    return audit_rows


def get_page_count(pdf_path: Path) -> int:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def render_page(pdf: pdfium.PdfDocument, page_index: int, output_dir: Path, scale: float) -> Path:
    page = pdf[page_index]
    image = page.render(scale=scale).to_pil()
    output_path = output_dir / f"page_{page_index + 1:03d}.png"
    image.save(output_path)
    return output_path


def recognize_image(image_path: Path) -> list[OcrToken]:
    try:
        from ocrmac import ocrmac
    except ImportError as exc:
        raise JcscPdfCollectError(
            "ocrmac is required for PDF OCR. Run with `uv run --extra ocr python "
            "src/collect/jcsc_sc_pdf.py ...` on macOS."
        ) from exc

    recognizer = ocrmac.OCR(
        str(image_path),
        recognition_level="accurate",
        language_preference=["ja-JP"],
        confidence_threshold=0.0,
    )
    tokens = []
    for text, confidence, bbox in recognizer.recognize():
        normalized = normalize_text(text)
        if not normalized:
            continue
        tokens.append(
            OcrToken(
                text=normalized,
                confidence=float(confidence),
                x=float(bbox[0]),
                y=float(bbox[1]),
                width=float(bbox[2]),
                height=float(bbox[3]),
            )
        )
    return tokens


def parse_page_tokens(
    *,
    tokens: list[OcrToken],
    page: int,
    source_url: str,
    initial_prefecture: str,
    states: dict[str, SideState],
) -> tuple[list[dict[str, Any]], str]:
    current_prefecture = initial_prefecture
    rows: list[dict[str, Any]] = []
    side_lines = group_tokens_by_side_line(tokens)
    for _y, side, line in side_lines:
        if not current_prefecture:
            page_prefectures = [token.text for token in tokens if token.text in PREFECTURE_NAMES]
            if page_prefectures:
                current_prefecture = page_prefectures[0]
        line_text = " ".join(token.text for token in line)
        prefectures = [token.text for token in line if token.text in PREFECTURE_NAMES]
        if prefectures:
            current_prefecture = prefectures[0]
            for state in states.values():
                state.municipality = ""
                state.district = ""
                state.pending_name = ""
                state.pending_confidences = None
            continue
        row = parse_side_line(
            tokens=line,
            page=page,
            source_url=source_url,
            column=side,
            prefecture=current_prefecture,
            state=states[side],
        )
        if row:
            rows.append(row)
        if is_noise_line(line_text):
            continue
    rows.extend(
        extract_missing_area_rows(
            side_lines=side_lines,
            existing_rows=rows,
            page=page,
            source_url=source_url,
            initial_prefecture=initial_prefecture,
        )
    )
    return rows, current_prefecture


def extract_missing_area_rows(
    *,
    side_lines: list[tuple[float, str, list[OcrToken]]],
    existing_rows: list[dict[str, Any]],
    page: int,
    source_url: str,
    initial_prefecture: str,
) -> list[dict[str, Any]]:
    existing_keys = {
        (
            str(row.get("column") or ""),
            normalize_facility_name(str(row.get("name") or "")),
            str(row.get("open_year") or ""),
            str(row.get("open_month") or ""),
        )
        for row in existing_rows
    }
    current_prefecture = initial_prefecture
    states = {"left": SideState(), "right": SideState()}
    supplemental_rows: list[dict[str, Any]] = []
    for _y, side, line in side_lines:
        line_text = " ".join(token.text for token in line)
        prefectures = [token.text for token in line if token.text in PREFECTURE_NAMES]
        if prefectures:
            current_prefecture = prefectures[0]
            for state in states.values():
                state.municipality = ""
                state.district = ""
                state.pending_name = ""
                state.pending_confidences = None
            continue
        if is_noise_line(line_text):
            continue
        row = parse_missing_area_side_line(
            tokens=line,
            page=page,
            source_url=source_url,
            column=side,
            prefecture=current_prefecture,
            state=states[side],
        )
        if not row:
            continue
        key = (
            str(row.get("column") or ""),
            normalize_facility_name(str(row.get("name") or "")),
            str(row.get("open_year") or ""),
            str(row.get("open_month") or ""),
        )
        if key in existing_keys:
            continue
        existing_keys.add(key)
        supplemental_rows.append(row)
    return supplemental_rows


def group_tokens_by_side_line(tokens: list[OcrToken]) -> list[tuple[float, str, list[OcrToken]]]:
    side_lines: list[tuple[float, str, list[OcrToken]]] = []
    for side in ("left", "right"):
        tokens_for_side = [token for token in tokens if token_side(token) == side]
        for line in group_tokens_by_line(tokens_for_side):
            side_lines.append((max(token.y for token in line), side, line))
    return sorted(side_lines, key=lambda item: (-item[0], item[1]))


def group_tokens_by_line(tokens: list[OcrToken]) -> list[list[OcrToken]]:
    sorted_tokens = sorted(tokens, key=lambda token: (-token.y, token.x))
    lines: list[list[OcrToken]] = []
    for token in sorted_tokens:
        if not lines or abs(lines[-1][0].y - token.y) > ROW_Y_TOLERANCE:
            lines.append([token])
        else:
            lines[-1].append(token)
    return [sorted(line, key=lambda token: token.x) for line in lines]


def token_side(token: OcrToken) -> str | None:
    if 0.07 <= token.x < 0.50:
        return "left"
    if 0.50 <= token.x < 0.94:
        return "right"
    return None


def parse_side_line(
    *,
    tokens: list[OcrToken],
    page: int,
    source_url: str,
    column: str,
    prefecture: str,
    state: SideState,
) -> dict[str, Any] | None:
    buckets = bucket_side_tokens(tokens, column)
    location_text = join_tokens(buckets["location"])
    name_text = join_tokens(buckets["name"])
    area_text = join_tokens(buckets["area"])
    date_text = join_tokens(buckets["date"])
    name_text, area_text = split_trailing_area_from_name(name_text, area_text)
    warnings: list[str] = []
    if location_text:
        location_text, location_name = split_location_and_name(location_text)
        if location_name:
            name_text = combine_name(location_name, name_text)
        if looks_like_municipality(location_text):
            state.municipality = location_text
            state.district = ""
        elif location_text.endswith("区"):
            state.district = location_text
        elif location_text:
            warnings.append(f"location_unclassified:{location_text}")
    if is_header_or_noise(name_text, area_text, date_text):
        return None
    if name_text and not area_text and not date_text:
        state.pending_name = combine_name(state.pending_name, name_text)
        state.pending_confidences = (state.pending_confidences or []) + [
            token.confidence for token in tokens
        ]
        return None
    if not name_text and not area_text and not date_text:
        return None
    if not area_text or not date_text:
        if name_text and not date_text:
            state.pending_name = combine_name(state.pending_name, name_text)
            state.pending_confidences = (state.pending_confidences or []) + [
                token.confidence for token in tokens
            ]
        return None
    full_name = combine_name(state.pending_name, name_text)
    confidences = [token.confidence for token in tokens]
    if state.pending_confidences:
        confidences.extend(state.pending_confidences)
    state.pending_name = ""
    state.pending_confidences = None
    area_value = parse_store_area_sqm(area_text)
    open_year, open_month = parse_open_year_month(date_text)
    if area_value is None:
        warnings.append("area_parse_failed")
    if open_year is None:
        warnings.append("open_date_parse_failed")
    if not full_name:
        warnings.append("name_missing")
    if not prefecture:
        warnings.append("prefecture_missing")
    if not state.municipality:
        warnings.append("municipality_missing")
    return {
        "source": "jcsc_pdf",
        "source_url": source_url,
        "page": page,
        "column": column,
        "prefecture": prefecture,
        "municipality": state.municipality,
        "district": state.district,
        "name": full_name,
        "store_area_raw": area_text,
        "store_area_sqm": area_value if area_value is not None else "",
        "open_date_raw": date_text,
        "open_year": open_year if open_year is not None else "",
        "open_month": open_month if open_month is not None else "",
        "ocr_confidence_avg": round(mean(confidences), 4) if confidences else "",
        "parse_warnings": "|".join(warnings),
    }


def parse_missing_area_side_line(
    *,
    tokens: list[OcrToken],
    page: int,
    source_url: str,
    column: str,
    prefecture: str,
    state: SideState,
) -> dict[str, Any] | None:
    buckets = bucket_side_tokens(tokens, column)
    location_text = join_tokens(buckets["location"])
    name_text = join_tokens(buckets["name"])
    area_text = join_tokens(buckets["area"])
    date_text = join_tokens(buckets["date"])
    name_text, area_text = split_trailing_area_from_name(name_text, area_text)
    if location_text:
        location_text, location_name = split_location_and_name(location_text)
        if location_name:
            name_text = combine_name(location_name, name_text)
        if looks_like_municipality(location_text):
            state.municipality = location_text
            state.district = ""
        elif location_text.endswith("区"):
            state.district = location_text
    if is_header_or_noise(name_text, area_text, date_text):
        return None
    if name_text and not area_text and not date_text:
        state.pending_name = combine_name(state.pending_name, name_text)
        state.pending_confidences = (state.pending_confidences or []) + [
            token.confidence for token in tokens
        ]
        return None
    if date_text and not area_text and state.pending_name:
        state.pending_name = ""
        state.pending_confidences = None
        return None
    if not date_text or area_text or not name_text or state.pending_name:
        return None
    open_year, open_month = parse_open_year_month(date_text)
    if open_year is None:
        return None
    warnings = ["area_missing"]
    if not prefecture:
        warnings.append("prefecture_missing")
    if not state.municipality:
        warnings.append("municipality_missing")
    confidences = [token.confidence for token in tokens]
    return {
        "source": "jcsc_pdf",
        "source_url": source_url,
        "page": page,
        "column": column,
        "prefecture": prefecture,
        "municipality": state.municipality,
        "district": state.district,
        "name": name_text,
        "store_area_raw": "",
        "store_area_sqm": "",
        "open_date_raw": date_text,
        "open_year": open_year,
        "open_month": open_month,
        "ocr_confidence_avg": round(mean(confidences), 4) if confidences else "",
        "parse_warnings": "|".join(warnings),
    }


def bucket_side_tokens(tokens: list[OcrToken], column: str) -> dict[str, list[OcrToken]]:
    buckets: dict[str, list[OcrToken]] = {"location": [], "name": [], "area": [], "date": []}
    for token in tokens:
        x = token.x
        if column == "left":
            if x < 0.125:
                buckets["location"].append(token)
            elif x < 0.335:
                buckets["name"].append(token)
            elif x < 0.405:
                buckets["area"].append(token)
            elif x < 0.495:
                buckets["date"].append(token)
        else:
            if x < 0.565:
                buckets["location"].append(token)
            elif x < 0.780:
                buckets["name"].append(token)
            elif x < 0.845:
                buckets["area"].append(token)
            elif x < 0.940:
                buckets["date"].append(token)
    return buckets


def join_tokens(tokens: list[OcrToken]) -> str:
    return normalize_text(
        " ".join(token.text for token in sorted(tokens, key=lambda token: token.x))
    )


def split_trailing_area_from_name(name_text: str, area_text: str) -> tuple[str, str]:
    if area_text:
        return name_text, area_text
    match = re.match(r"^(?P<name>.+?)[\s　]*(?P<area>\d[\d]*[,.]\d{3})$", name_text)
    if not match:
        return name_text, area_text
    return normalize_text(match.group("name")), match.group("area")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value.replace("\u3000", " "))
    normalized = normalized.replace(" ,", ",").replace(". ", ".")
    return re.sub(r"\s+", " ", normalized).strip()


def combine_name(prefix: str, name: str) -> str:
    parts = [part for part in [prefix, name] if part]
    return normalize_text(" ".join(parts))


def looks_like_municipality(value: str) -> bool:
    return value.endswith(("市", "町", "村"))


def split_location_and_name(value: str) -> tuple[str, str]:
    if looks_like_municipality(value) or value.endswith("区"):
        return value, ""
    match = LOCATION_WITH_NAME_PATTERN.match(value)
    if not match:
        return value, ""
    return match.group("location"), match.group("name")


def is_header_or_noise(name_text: str, area_text: str, date_text: str) -> bool:
    joined = f"{name_text} {area_text} {date_text}"
    if not joined.strip():
        return True
    return any(keyword in joined for keyword in ["SC名", "店舗面積", "オープン日", "資料編"])


def is_noise_line(line_text: str) -> bool:
    return any(
        keyword in line_text for keyword in ["都道府県・市区町村別SC一覧", "地区別・オープン日順"]
    )


def parse_store_area_sqm(value: str) -> float | None:
    text = normalize_text(value).replace(" ", "")
    if not AREA_PATTERN.match(text):
        return None
    if "," not in text and "." in text:
        left, right = text.split(".", 1)
        if len(right) == 3:
            text = left + right
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def parse_open_year_month(value: str) -> tuple[int | None, int | None]:
    match = OPEN_DATE_PATTERN.search(normalize_text(value))
    if not match:
        return None, None
    return int(match.group("year")), int(match.group("month"))


def load_municipality_prefecture_map(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    mapping: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            prefecture = row.get("prefecture", "")
            municipality = row.get("municipality", "")
            if not prefecture or not municipality:
                continue
            mapping.setdefault(municipality, prefecture)
            city_match = re.match(r"^(.+市).+区$", municipality)
            if city_match:
                mapping.setdefault(city_match.group(1), prefecture)
    return mapping


def infer_prefectures_from_municipality(
    rows: list[dict[str, Any]], municipality_prefecture_map: dict[str, str]
) -> list[dict[str, Any]]:
    if not municipality_prefecture_map:
        return rows
    inferred_rows = []
    for row in rows:
        inferred_prefecture = infer_prefecture_for_row(row, municipality_prefecture_map)
        if inferred_prefecture and inferred_prefecture != row.get("prefecture"):
            row = dict(row)
            row["prefecture"] = inferred_prefecture
            row["parse_warnings"] = append_warning(
                str(row.get("parse_warnings") or ""),
                "prefecture_inferred_from_municipality",
            )
        inferred_rows.append(row)
    return inferred_rows


def infer_prefecture_for_row(
    row: dict[str, Any], municipality_prefecture_map: dict[str, str]
) -> str:
    municipality = str(row.get("municipality") or "")
    district = str(row.get("district") or "")
    if not municipality:
        return ""
    candidates = [municipality]
    if district:
        candidates.insert(0, f"{municipality}{district}")
    for candidate in candidates:
        if prefecture := municipality_prefecture_map.get(candidate):
            return prefecture
    return ""


def append_warning(current: str, warning: str) -> str:
    warnings = [item for item in current.split("|") if item]
    if warning not in warnings:
        warnings.append(warning)
    return "|".join(warnings)


def summarize_parse_warnings(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        warnings = str(row.get("parse_warnings") or "")
        for warning in [item for item in warnings.split("|") if item]:
            key = warning.split(":", 1)[0]
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def normalize_facility_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    return NAME_NORMALIZE_PATTERN.sub("", normalized)


def diff_new_candidates(
    rows: list[dict[str, Any]], existing_csv: Path | None = DEFAULT_EXISTING_CSV
) -> list[dict[str, Any]]:
    existing_keys = load_existing_facility_keys(existing_csv)
    new_rows = []
    for row in rows:
        key = facility_match_key(
            prefecture=str(row.get("prefecture") or ""),
            name=str(row.get("name") or ""),
        )
        if key not in existing_keys:
            candidate = dict(row)
            candidate["match_key"] = key
            new_rows.append(candidate)
    return new_rows


def load_existing_facility_keys(existing_csv: Path | None) -> set[str]:
    if existing_csv is None or not existing_csv.exists():
        return set()
    keys: set[str] = set()
    with existing_csv.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            key = facility_match_key(
                prefecture=row.get("prefecture", ""),
                name=row.get("name", ""),
            )
            if key:
                keys.add(key)
    return keys


def facility_match_key(*, prefecture: str, name: str) -> str:
    normalized_name = normalize_facility_name(name)
    if not normalized_name:
        return ""
    return f"{prefecture}|{normalized_name}" if prefecture else normalized_name


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames or CSV_FIELDNAMES,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract JCSC nationwide SC PDF by OCR.")
    parser.add_argument(
        "--audit-month-counts",
        action="store_true",
        help="OCR the PDF and compare page row counts with month markers.",
    )
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--existing-csv", type=Path, default=DEFAULT_EXISTING_CSV)
    parser.add_argument(
        "--facilities-csv",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "jcsc_sc_pdf_facilities.csv",
    )
    parser.add_argument(
        "--municipality-prefecture-csv",
        type=Path,
        default=DEFAULT_MUNICIPALITY_PREFECTURE_CSV,
    )
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--page-limit", type=int)
    parser.add_argument("--ocr-scale", type=float, default=DEFAULT_OCR_SCALE)
    args = parser.parse_args()
    if args.audit_month_counts:
        output_csv = args.output_dir / "jcsc_sc_pdf_page_month_audit.csv"
        rows = audit_pdf_month_counts(
            pdf_path=args.pdf,
            facilities_csv=args.facilities_csv,
            output_csv=output_csv,
            page_limit=args.page_limit,
            ocr_scale=args.ocr_scale,
        )
        mismatches = sum(1 for row in rows if row["audit_warning"])
        print(
            "audited jcsc sc pdf month counts: "
            f"pages={len(rows)} mismatches={mismatches} csv={output_csv}"
        )
        return 0

    outputs = collect_jcsc_sc_pdf(
        pdf_path=args.pdf,
        output_dir=args.output_dir,
        existing_csv=args.existing_csv,
        municipality_prefecture_csv=args.municipality_prefecture_csv,
        source_url=args.source_url,
        page_limit=args.page_limit,
        ocr_scale=args.ocr_scale,
    )
    print(
        "extracted jcsc sc pdf: "
        f"records={outputs['record_count']} "
        f"new_candidates={outputs['new_candidate_count']} "
        f"csv={outputs['csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
