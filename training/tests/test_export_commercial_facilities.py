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
                "lat": "35.681236",
                "lon": "139.767125",
                "coordinate_source": "address_point",
                "coordinate_confidence": "medium",
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

    assert summary["schemaVersion"] == 3
    assert summary["latestOpenYear"] == 2026
    assert summary["coverage"]["area"] == "全国"
    assert summary["coverage"]["facilityCount"] == 3
    assert summary["coverage"]["coordinateCount"] == 1
    assert summary["coverage"]["reliableCoordinateCount"] == 1
    assert summary["coverage"]["storeAreaMissingCount"] == 1
    assert summary["coverage"]["scaleCounts"] == {"small": 2, "unknown": 1}
    assert tokyo["scCount"] == 2
    assert tokyo["storeAreaSumSqm"] == 3200.5
    assert tokyo["tenantCountSum"] == 32
    assert chiyoda["recentOpenings"][0]["name"] == "東京新SC"
    assert chiyoda["recentOpenings"][1]["name"] == "東京テストSC"
    assert chiyoda["facilities"][0]["storeAreaSqm"] == 2000
    assert chiyoda["facilities"][0]["tenantCount"] == 20
    assert chiyoda["facilities"][0]["scaleCode"] == "small"
    assert chiyoda["facilities"][0]["scaleBasis"] == "store_area_sqm"
    assert chiyoda["facilities"][1]["storeAreaSqm"] == 1200.5
    assert chiyoda["facilities"][1]["tenantCount"] == 12
    assert osaka["storeAreaSumSqm"] == 0
    assert osaka["tenantCountSum"] == 0


def test_build_commercial_facility_summary_accepts_pdf_municipality_column() -> None:
    summary = build_commercial_facility_summary(
        [
            {
                "open_year": "2001",
                "open_month": "10",
                "name": "PDF由来SC",
                "prefecture": "北海道",
                "municipality": "函館市",
                "store_area_sqm": "15947",
                "tenant_count": "",
            }
        ]
    )

    assert summary["prefectures"]["北海道"]["scCount"] == 1
    assert summary["cities"]["北海道|函館市"]["recentOpenings"][0]["name"] == "PDF由来SC"
