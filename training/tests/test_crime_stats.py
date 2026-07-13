from __future__ import annotations

import csv

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
