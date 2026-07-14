from __future__ import annotations

import csv

import pytest

from collect.population_stats import (
    collect_population_stats,
    normalize_estat_population_response,
    normalize_population_rows,
    parse_estat_item_specs,
)


def test_normalize_population_rows_calculates_rates_and_5y_change() -> None:
    rows = normalize_population_rows(
        [
            {
                "year": "2020",
                "prefecture": "東京都",
                "municipality": "千代田区",
                "city_code": "13101",
                "population_total": "1000",
                "households_total": "500",
                "population_under_15": "100",
                "population_15_to_64": "600",
                "population_65_plus": "300",
                "area_km2": "10",
            },
            {
                "year": "2025",
                "prefecture": "東京都",
                "municipality": "千代田区",
                "city_code": "13101",
                "population_total": "1100",
                "households_total": "550",
                "population_under_15": "110",
                "population_15_to_64": "660",
                "population_65_plus": "330",
                "area_km2": "10",
            },
        ]
    )

    latest = rows[1]

    assert latest["population_density_per_km2"] == pytest.approx(110.0)
    assert latest["aging_rate"] == pytest.approx(30.0)
    assert latest["working_age_rate"] == pytest.approx(60.0)
    assert latest["under_15_rate"] == pytest.approx(10.0)
    assert latest["household_persons_avg"] == pytest.approx(2.0)
    assert latest["population_change_5y_rate"] == pytest.approx(10.0)


def test_collect_population_stats_writes_normalized_csv(tmp_path) -> None:
    input_path = tmp_path / "population.csv"
    input_path.write_text(
        "\n".join(
            [
                "year,prefecture,municipality,population_total,households_total,area_km2",
                "2025,東京都,千代田区,1000,500,10",
            ]
        ),
        encoding="utf-8",
    )

    outputs = collect_population_stats(
        input_path=input_path,
        output_dir=tmp_path / "processed",
    )

    with outputs["municipality_population_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert outputs["row_count"] == 1
    assert rows[0]["municipality"] == "千代田区"
    assert rows[0]["population_density_per_km2"] == "100.0"


def test_normalize_estat_population_response_uses_item_specs() -> None:
    payload = {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "CLASS_INF": {
                    "CLASS_OBJ": [
                        {
                            "@id": "area",
                            "CLASS": {"@code": "13101", "@name": "東京都千代田区"},
                        },
                        {
                            "@id": "time",
                            "CLASS": {"@code": "2020000000", "@name": "2020年"},
                        },
                        {
                            "@id": "cat01",
                            "CLASS": [
                                {"@code": "001", "@name": "人口総数"},
                                {"@code": "002", "@name": "世帯総数"},
                                {"@code": "003", "@name": "15歳未満人口"},
                                {"@code": "004", "@name": "15〜64歳人口"},
                                {"@code": "005", "@name": "65歳以上人口"},
                            ],
                        },
                    ]
                },
                "DATA_INF": {
                    "VALUE": [
                        {"@area": "13101", "@time": "2020000000", "@cat01": "001", "$": "1000"},
                        {"@area": "13101", "@time": "2020000000", "@cat01": "002", "$": "500"},
                        {"@area": "13101", "@time": "2020000000", "@cat01": "003", "$": "100"},
                        {"@area": "13101", "@time": "2020000000", "@cat01": "004", "$": "600"},
                        {"@area": "13101", "@time": "2020000000", "@cat01": "005", "$": "300"},
                    ]
                },
            }
        }
    }
    item_specs = parse_estat_item_specs(
        [
            "population_total=cat01:001",
            "households_total=cat01:002",
            "population_under_15=cat01:003",
            "population_15_to_64=cat01:004",
            "population_65_plus=cat01:005",
        ]
    )

    rows = normalize_estat_population_response(
        payload,
        item_specs=item_specs,
        source_url="https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData",
    )

    assert rows[0]["year"] == 2020
    assert rows[0]["prefecture"] == "東京都"
    assert rows[0]["municipality"] == "千代田区"
    assert rows[0]["population_total"] == pytest.approx(1000.0)
    assert rows[0]["households_total"] == pytest.approx(500.0)
    assert rows[0]["aging_rate"] == pytest.approx(30.0)
