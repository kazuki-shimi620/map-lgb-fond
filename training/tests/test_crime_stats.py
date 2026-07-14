from __future__ import annotations

import csv
import zipfile
from pathlib import Path

import pytest

from collect.crime_stats import collect_crime_stats, normalize_crime_rows


def test_normalize_crime_rows_calculates_per_1000_population() -> None:
    rows = normalize_crime_rows(
        [
            {
                "year": "2025",
                "prefecture": "東京都",
                "municipality": "千代田区",
                "city_code": "13101",
                "crime_type": "刑法犯総数",
                "crime_count": "120",
                "population_total": "60000",
                "source": "東京都オープンデータ",
            }
        ]
    )

    assert rows[0]["crime_count_per_1000_population"] == pytest.approx(2.0)
    assert rows[0]["area_unit"] == "municipality"


def test_collect_crime_stats_writes_normalized_csv(tmp_path) -> None:
    input_path = tmp_path / "crime.csv"
    input_path.write_text(
        "\n".join(
            [
                "year,prefecture,municipality,crime_type,crime_count,population_total",
                "2025,東京都,千代田区,刑法犯総数,120,60000",
            ]
        ),
        encoding="utf-8",
    )

    outputs = collect_crime_stats(input_path=input_path, output_dir=tmp_path / "processed")

    with outputs["crime_municipality_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert outputs["row_count"] == 1
    assert rows[0]["municipality"] == "千代田区"
    assert rows[0]["crime_count_per_1000_population"] == "2.0"


def test_collect_crime_stats_reads_public_data_like_tsv_fixture(tmp_path) -> None:
    input_path = tmp_path / "crime.tsv"
    input_path.write_text(
        "\n".join(
            [
                "survey_year\tprefecture_name\tmunicipality_name\tcategory\tcount\tpopulation",
                "2025\t東京都\t新宿区\t刑法犯総数\t240\t120000",
            ]
        ),
        encoding="utf-8",
    )

    outputs = collect_crime_stats(input_path=input_path, output_dir=tmp_path / "processed")

    with outputs["crime_municipality_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert outputs["row_count"] == 1
    assert rows[0]["municipality"] == "新宿区"
    assert rows[0]["crime_count_per_1000_population"] == "2.0"


def test_collect_crime_stats_reads_public_data_like_xlsx_fixture(tmp_path) -> None:
    input_path = tmp_path / "crime.xlsx"
    _write_minimal_xlsx(
        input_path,
        [
            ["year", "prefecture", "municipality", "crime_type", "crime_count", "population_total"],
            ["2025", "東京都", "渋谷区", "刑法犯総数", "180", "90000"],
        ],
    )

    outputs = collect_crime_stats(input_path=input_path, output_dir=tmp_path / "processed")

    with outputs["crime_municipality_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert outputs["row_count"] == 1
    assert rows[0]["municipality"] == "渋谷区"
    assert rows[0]["crime_count_per_1000_population"] == "2.0"


def _write_minimal_xlsx(path: Path, rows: list[list[str]]) -> None:
    shared_strings = []
    indexes = {}
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            if value not in indexes:
                indexes[value] = len(shared_strings)
                shared_strings.append(value)
            cell_ref = f"{chr(ord('A') + column_index)}{row_index}"
            cells.append(f'<c r="{cell_ref}" t="s"><v>{indexes[value]}</v></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                '<Override PartName="/xl/sharedStrings.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                "</Types>"
            ),
        )
        archive.writestr(
            "_rels/.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/officeDocument" '
                'Target="xl/workbook.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/workbook.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
                "</workbook>"
            ),
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                'relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                + "".join(f"<si><t>{value}</t></si>" for value in shared_strings)
                + "</sst>"
            ),
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f'<sheetData>{"".join(sheet_rows)}</sheetData>'
                "</worksheet>"
            ),
        )
