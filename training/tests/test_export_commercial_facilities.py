from __future__ import annotations

from export.commercial_facilities import build_commercial_facility_summary


def test_build_commercial_facility_summary_groups_by_city_and_prefecture() -> None:
    summary = build_commercial_facility_summary(
        [
            {
                "open_year": "2024",
                "open_month": "4",
                "name": "東京テストSC",
                "prefecture": "東京都",
                "city": "千代田区",
                "store_area_sqm": "1200.5",
                "tenant_count": "12",
            },
            {
                "open_year": "2026",
                "open_month": "1",
                "name": "東京新SC",
                "prefecture": "東京都",
                "city": "千代田区",
                "store_area_sqm": "2000",
                "tenant_count": "20",
            },
            {
                "open_year": "2025",
                "open_month": "3",
                "name": "大阪テストSC",
                "prefecture": "大阪府",
                "city": "大阪市",
                "store_area_sqm": "",
                "tenant_count": "",
            },
        ]
    )

    tokyo = summary["prefectures"]["東京都"]
    chiyoda = summary["cities"]["東京都|千代田区"]
    osaka = summary["cities"]["大阪府|大阪市"]

    assert summary["schemaVersion"] == 1
    assert summary["latestOpenYear"] == 2026
    assert tokyo["scCount"] == 2
    assert tokyo["storeAreaSumSqm"] == 3200.5
    assert tokyo["tenantCountSum"] == 32
    assert chiyoda["recentOpenings"][0]["name"] == "東京新SC"
    assert chiyoda["recentOpenings"][1]["name"] == "東京テストSC"
    assert osaka["storeAreaSumSqm"] == 0
    assert osaka["tenantCountSum"] == 0
