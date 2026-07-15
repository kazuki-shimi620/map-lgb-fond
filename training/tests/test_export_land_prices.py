from __future__ import annotations

import pytest

from export.land_prices import build_municipality_land_price_summary


def test_build_municipality_land_price_summary_groups_by_city_and_year() -> None:
    summary = build_municipality_land_price_summary(
        [
            {
                "year": "2025",
                "prefecture": "東京都",
                "municipality": "千代田区",
                "point_count": "2",
                "avg_price_yen_per_sqm": "1000000",
                "avg_yoy_rate": "2",
            },
            {
                "year": "2025",
                "prefecture": "東京都",
                "municipality": "千代田区",
                "point_count": "1",
                "avg_price_yen_per_sqm": "700000",
                "avg_yoy_rate": "5",
            },
            {
                "year": "2024",
                "prefecture": "東京都",
                "municipality": "千代田区",
                "point_count": "3",
                "avg_price_yen_per_sqm": "900000",
                "avg_yoy_rate": "1.5",
            },
            {
                "year": "",
                "prefecture": "東京都",
                "municipality": "千代田区",
                "point_count": "9",
                "avg_price_yen_per_sqm": "1",
                "avg_yoy_rate": "1",
            },
        ]
    )

    city = summary["cities"]["東京都|千代田区"]
    year_2025 = city["years"]["2025"]

    assert summary["schemaVersion"] == 1
    assert summary["latestYear"] == 2025
    assert city["prefecture"] == "東京都"
    assert year_2025["avgPriceYenPerSqm"] == pytest.approx(900000)
    assert year_2025["yoyRate"] == pytest.approx(3)
    assert year_2025["pointCount"] == 3
    assert city["years"]["2024"]["avgPriceYenPerSqm"] == 900000
