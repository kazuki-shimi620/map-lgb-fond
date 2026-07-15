from __future__ import annotations

import csv
import json

import pytest

from export.nearby_facilities import (
    NEARBY_FACILITY_FIELDNAMES,
    export_nearby_facilities,
    load_commercial_facility_rows,
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
        commercial_facilities_csv=None,
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


def test_load_commercial_facility_rows_uses_rows_with_coordinates(tmp_path) -> None:
    input_csv = tmp_path / "jcsc_sc_open.csv"
    input_csv.write_text(
        "\n".join(
            [
                "name,prefecture,city,address,lat,lon,source",
                "東京テストSC,東京都,千代田区,東京都千代田区丸の内1-1-1,35.681236,139.767125,jcsc_geocoded",
                "緯度経度なしSC,東京都,中央区,,,",
            ]
        ),
        encoding="utf-8",
    )

    rows = load_commercial_facility_rows(input_csv)

    assert len(rows) == 1
    assert rows[0]["categoryId"] == "commercial_facility"
    assert rows[0]["name"] == "東京テストSC"
    assert rows[0]["municipality"] == "千代田区"
    assert rows[0]["source"] == "jcsc_geocoded"


def test_export_nearby_facilities_merges_commercial_facility_coordinates(tmp_path) -> None:
    nearby_csv = tmp_path / "nearby_facilities.csv"
    nearby_csv.write_text(
        "\n".join(
            [
                ",".join(NEARBY_FACILITY_FIELDNAMES),
                ",hospital,東京テスト病院,35.68,139.76,東京都,千代田区,,,",
            ]
        ),
        encoding="utf-8",
    )
    commercial_csv = tmp_path / "jcsc_sc_open.csv"
    commercial_csv.write_text(
        "\n".join(
            [
                "name,prefecture,city,address,lat,lon",
                "東京テストSC,東京都,千代田区,東京都千代田区丸の内1-1-1,35.681236,139.767125",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "nearby_facilities.json"

    export_nearby_facilities(
        input_csv=nearby_csv,
        commercial_facilities_csv=commercial_csv,
        output=output,
        source="manual_or_processed",
        source_label="周辺施設データ",
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [facility["categoryId"] for facility in payload["facilities"]] == [
        "commercial_facility",
        "hospital",
    ]


def test_export_nearby_facilities_merges_multiple_input_csvs(tmp_path) -> None:
    hospital_csv = tmp_path / "nearby_hospitals.csv"
    hospital_csv.write_text(
        "\n".join(
            [
                ",".join(NEARBY_FACILITY_FIELDNAMES),
                ",hospital,東京テスト病院,35.68,139.76,東京都,千代田区,,,",
            ]
        ),
        encoding="utf-8",
    )
    osm_csv = tmp_path / "nearby_osm.csv"
    osm_csv.write_text(
        "\n".join(
            [
                ",".join(NEARBY_FACILITY_FIELDNAMES),
                ",supermarket,テストスーパー,35.69,139.77,東京都,千代田区,,,",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "nearby_facilities.json"

    export_nearby_facilities(
        input_csv=[hospital_csv, osm_csv],
        commercial_facilities_csv=None,
        output=output,
        source="manual_or_processed",
        source_label="周辺施設データ",
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert [facility["categoryId"] for facility in payload["facilities"]] == [
        "hospital",
        "supermarket",
    ]


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
