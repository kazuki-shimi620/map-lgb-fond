from __future__ import annotations

import csv
import json

import pytest

from export.nearby_facilities import (
    NEARBY_FACILITY_FIELDNAMES,
    export_nearby_facilities,
    load_facility_rows,
    write_csv_template,
)


def test_load_facility_rows_normalizes_facilities(tmp_path) -> None:
    input_csv = tmp_path / "nearby_facilities.csv"
    input_csv.write_text(
        "\n".join(
            [
                ",".join(NEARBY_FACILITY_FIELDNAMES),
                "tokyo_hospital,hospital,東京テスト病院,35.681236,139.767125,東京都,千代田区,東京都千代田区丸の内1-1-1,manual,2026-07-15",
                ",convenience_store,テストコンビニ,35.682,139.768,東京都,千代田区,,,",
            ]
        ),
        encoding="utf-8",
    )

    rows = load_facility_rows(input_csv)

    assert [row["categoryId"] for row in rows] == ["convenience_store", "hospital"]
    assert rows[0]["id"].startswith("convenience_store_")
    assert rows[0]["name"] == "テストコンビニ"
    assert rows[0]["lat"] == pytest.approx(35.682)
    assert rows[1]["id"] == "tokyo_hospital"
    assert rows[1]["source"] == "manual"


def test_export_nearby_facilities_writes_not_generated_when_input_is_missing(tmp_path) -> None:
    output = tmp_path / "nearby_facilities.json"

    export_nearby_facilities(
        input_csv=tmp_path / "missing.csv",
        output=output,
        source="manual_or_processed",
        source_label="周辺施設データ",
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["source"] == "not_generated"
    assert payload["sourceLabel"] == "周辺施設データ未生成"
    assert payload["generatedAt"] is None
    assert payload["facilities"] == []
    assert {category["id"] for category in payload["categories"]} >= {
        "hospital",
        "supermarket",
        "commercial_facility",
        "park",
        "convenience_store",
    }


def test_load_facility_rows_rejects_unsupported_category(tmp_path) -> None:
    input_csv = tmp_path / "nearby_facilities.csv"
    input_csv.write_text(
        "\n".join(
            [
                ",".join(NEARBY_FACILITY_FIELDNAMES),
                ",unknown,未対応施設,35.0,139.0,東京都,千代田区,,,",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported category_id"):
        load_facility_rows(input_csv)


def test_write_csv_template_writes_expected_header(tmp_path) -> None:
    output = tmp_path / "nearby_facilities_template.csv"

    write_csv_template(output)

    with output.open(encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        assert next(reader) == NEARBY_FACILITY_FIELDNAMES
        assert list(reader) == []
