from __future__ import annotations

import pandas as pd
import pytest

from evaluate.address_coordinate_coverage import (
    build_address_coordinate_coverage_report,
    render_markdown,
)


def test_build_address_coordinate_coverage_report_counts_match_levels(tmp_path) -> None:
    address_csv = tmp_path / "town_points.csv"
    address_csv.write_text("prefecture,municipality,district_name,lat,lon\n", encoding="utf-8")
    report = build_address_coordinate_coverage_report(
        property_df=pd.DataFrame(
            [
                {
                    "prefecture": "東京都",
                    "municipality": "千代田区",
                    "district_name": "丸の内",
                },
                {
                    "prefecture": "東京都",
                    "municipality": "千代田区",
                    "district_name": "大手町",
                },
                {
                    "prefecture": "神奈川県",
                    "municipality": "横浜市",
                    "district_name": "",
                },
            ]
        ),
        address_points_df=pd.DataFrame(
            [
                {
                    "prefecture": "東京都",
                    "municipality": "千代田区",
                    "district_name": "丸の内",
                    "lat": 35.681236,
                    "lon": 139.767125,
                },
                {
                    "prefecture": "東京都",
                    "municipality": "千代田区",
                    "district_name": "大手町一丁目",
                    "lat": 35.686944,
                    "lon": 139.763056,
                }
            ]
        ),
        source_paths=["tokyo.parquet"],
        address_points_csv=address_csv,
    )

    assert report["recordCount"] == 3
    assert report["propertyDistrictCount"] == 2
    assert report["propertyDistrictRate"] == pytest.approx(2 / 3)
    assert report["matchedRowCount"] == 2
    assert report["townMatchedRowCount"] == 1
    assert report["districtPrefixMatchedRowCount"] == 1
    assert report["municipalityMatchedRowCount"] == 0
    assert report["matchLevelCounts"] == {"none": 1, "district_prefix": 1, "town": 1}


def test_render_markdown_includes_match_rates() -> None:
    markdown = render_markdown(
        {
            "generatedAt": "2026-07-15T00:00:00+00:00",
            "addressPointsCsv": "town_points.csv",
            "addressPointsCsvBytes": 100,
            "recordCount": 10,
            "propertyCoordinateCount": 0,
            "propertyCoordinateRate": 0.0,
            "propertyDistrictCount": 5,
            "propertyDistrictRate": 0.5,
            "addressPointCount": 3,
            "matchedRowCount": 8,
            "matchRate": 0.8,
            "townMatchedRowCount": 6,
            "townMatchRate": 0.6,
            "districtPrefixMatchedRowCount": 1,
            "districtPrefixMatchRate": 0.1,
            "municipalityMatchedRowCount": 2,
            "municipalityMatchRate": 0.2,
            "matchLevelCounts": {"town": 6, "municipality": 2, "district_prefix": 1, "none": 1},
        }
    )

    assert "matchRate: 80.00%" in markdown
    assert "propertyDistrictRate: 50.00%" in markdown
    assert "districtPrefixMatchRate: 10.00%" in markdown
    assert "| town | 6 |" in markdown
