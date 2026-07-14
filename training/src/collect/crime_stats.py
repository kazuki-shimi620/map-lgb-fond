from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

SCHEMA_VERSION = "1.0.0"
DEFAULT_OUTPUT_DIR = Path("data/processed/crime")
FIELDNAMES = [
    "year",
    "prefecture",
    "municipality",
    "city_code",
    "area_unit",
    "crime_type",
    "crime_count",
    "population_total",
    "crime_count_per_1000_population",
    "source",
    "source_url",
    "notes",
]


class CrimeStatsCollectError(RuntimeError):
    pass


def collect_crime_stats(
    *,
    input_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Path | int]:
    if not input_path.exists():
        raise CrimeStatsCollectError(f"Crime stats input file not found: {input_path}")

    raw_rows = _read_input(input_path)
    rows = normalize_crime_rows(raw_rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "crime_municipality.csv"
    metadata_path = output_dir / "metadata.json"
    _write_csv(csv_path, rows)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "sourceInput": str(input_path),
        "rowCount": len(rows),
        "years": sorted({row["year"] for row in rows if row["year"] is not None}),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"crime_municipality_csv": csv_path, "metadata": metadata_path, "row_count": len(rows)}


def normalize_crime_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [_normalize_crime_row(row) for row in rows]
    normalized = [
        row
        for row in normalized
        if row["year"] is not None
        and row["prefecture"]
        and row["municipality"]
        and row["crime_type"]
    ]
    return sorted(
        normalized,
        key=lambda row: (
            int(row["year"]),
            str(row["prefecture"]),
            str(row["municipality"]),
            str(row["crime_type"]),
        ),
    )


def _normalize_crime_row(row: dict[str, Any]) -> dict[str, Any]:
    crime_count = _to_float(_pick(row, "crime_count", "count", "recognized_count"))
    population_total = _to_float(_pick(row, "population_total", "population"))
    per_1000 = _to_float(
        _pick(
            row,
            "crime_count_per_1000_population",
            "crime_per_1000_population",
            "per_1000_population",
        )
    )
    if per_1000 is None and crime_count is not None and population_total:
        per_1000 = crime_count / population_total * 1000

    return {
        "year": _to_int(_pick(row, "year", "crime_year", "survey_year")),
        "prefecture": _to_text(_pick(row, "prefecture", "prefecture_name")),
        "municipality": _to_text(_pick(row, "municipality", "city", "municipality_name")),
        "city_code": _to_text(_pick(row, "city_code", "municipality_code")),
        "area_unit": _to_text(_pick(row, "area_unit", "unit")) or "municipality",
        "crime_type": _to_text(_pick(row, "crime_type", "category")) or "刑法犯総数",
        "crime_count": crime_count,
        "population_total": population_total,
        "crime_count_per_1000_population": per_1000,
        "source": _to_text(_pick(row, "source")) or "crime_stats",
        "source_url": _to_text(_pick(row, "source_url", "sourceUrl")),
        "notes": _to_text(_pick(row, "notes", "note")),
    }


def _read_input(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return _read_csv(path)
    if suffix in {".tsv"}:
        return _read_csv(path, delimiter="\t")
    if suffix == ".xlsx":
        return _read_xlsx(path)
    raise CrimeStatsCollectError(f"Unsupported crime stats input format: {path.suffix}")


def _read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file, delimiter=delimiter))


def _read_xlsx(path: Path) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(path) as archive:
            shared_strings = _read_shared_strings(archive)
            sheet_xml = _read_first_sheet_xml(archive)
    except (KeyError, zipfile.BadZipFile) as error:
        raise CrimeStatsCollectError(f"Invalid xlsx crime stats input: {path}") from error

    table = _parse_xlsx_sheet(sheet_xml, shared_strings)
    if not table:
        return []

    header = [_normalize_header(value) for value in table[0]]
    rows = []
    for values in table[1:]:
        if not any(value not in (None, "") for value in values):
            continue
        row = {header[index]: value for index, value in enumerate(values) if index < len(header)}
        rows.append(row)
    return rows


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    namespace = _namespace(root.tag)
    strings = []
    for item in root.findall(f"{namespace}si"):
        texts = [node.text or "" for node in item.findall(f".//{namespace}t")]
        strings.append("".join(texts))
    return strings


def _read_first_sheet_xml(archive: zipfile.ZipFile) -> bytes:
    try:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        namespace = _namespace(workbook.tag)
        relationship_id = workbook.find(f".//{namespace}sheet").attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_namespace = _namespace(rels.tag)
        for relationship in rels.findall(f"{rel_namespace}Relationship"):
            if relationship.attrib.get("Id") == relationship_id:
                target = relationship.attrib["Target"].lstrip("/")
                path = target if target.startswith("xl/") else f"xl/{target}"
                return archive.read(path)
    except (AttributeError, KeyError):
        pass
    return archive.read("xl/worksheets/sheet1.xml")


def _parse_xlsx_sheet(sheet_xml: bytes, shared_strings: list[str]) -> list[list[str]]:
    root = ElementTree.fromstring(sheet_xml)
    namespace = _namespace(root.tag)
    rows = []
    for row in root.findall(f".//{namespace}row"):
        values_by_column = {}
        for cell in row.findall(f"{namespace}c"):
            cell_ref = cell.attrib.get("r", "")
            column_index = _column_index(cell_ref)
            values_by_column[column_index] = _cell_value(cell, namespace, shared_strings)
        if values_by_column:
            max_column = max(values_by_column)
            rows.append([values_by_column.get(index, "") for index in range(max_column + 1)])
    return rows


def _cell_value(cell: ElementTree.Element, namespace: str, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{namespace}t")).strip()

    value_node = cell.find(f"{namespace}v")
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        index = int(value)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return value.strip()


def _column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha()).upper()
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return max(index - 1, 0)


def _namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[0] + "}"
    return ""


def _normalize_header(value: object) -> str:
    return str(value or "").strip()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _pick(row: dict[str, Any], *keys: str):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _to_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize municipality crime stats.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        outputs = collect_crime_stats(input_path=args.input, output_dir=args.output_dir)
    except CrimeStatsCollectError as error:
        print(f"crime stats collect failed: {error}", file=sys.stderr)
        return 1

    print(
        "collected crime stats: "
        f"rows={outputs['row_count']} "
        f"csv={outputs['crime_municipality_csv']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
