from __future__ import annotations

import pandas as pd
import pytest

from evaluate.education_coverage import build_education_coverage_report, render_markdown


def test_build_education_coverage_report_counts_matches(tmp_path) -> None:
    education_csv = tmp_path / "education_facilities.csv"
    education_csv.write_text("facility_type,lat,lon\n", encoding="utf-8")
    properties = pd.DataFrame(
        [
            {"lat": 35.681236, "lon": 139.767125},
            {"lat": 35.0, "lon": 139.0},
        ]
    )
    facilities = pd.DataFrame(
        [
            {"facility_type": "小学校", "lat": 35.6813, "lon": 139.7672},
            {"facility_type": "中学校", "lat": 35.6814, "lon": 139.7673},
            {"facility_type": "保育園", "lat": 35.6815, "lon": 139.7674},
        ]
    )

    report = build_education_coverage_report(
        property_df=properties,
        education_facilities_df=facilities,
        source_paths=["tokyo.parquet"],
        education_facilities_csv=education_csv,
    )

    assert report["recordCount"] == 2
    assert report["facilityCount"] == 3
    assert report["matchedRowCount"] == 1
    assert report["matchRate"] == pytest.approx(0.5)
    assert report["facilityTypeCounts"]["小学校"] == 1
    assert report["nearestElementaryDistanceKm"]["min"] < 0.1


def test_render_markdown_includes_match_rate() -> None:
    markdown = render_markdown(
        {
            "generatedAt": "2026-07-15T00:00:00+00:00",
            "educationFacilitiesCsv": "education_facilities.csv",
            "educationFacilitiesCsvBytes": 100,
            "recordCount": 10,
            "facilityCount": 3,
            "matchedRowCount": 8,
            "matchRate": 0.8,
            "facilityTypeCounts": {"小学校": 1, "中学校": 1, "保育園": 1},
            "nearestElementaryDistanceKm": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "nearestJuniorHighDistanceKm": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "nurseryCountWithin500m": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "nurseryCountWithin1km": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "kindergartenCountWithin1km": {"min": 0, "median": 1, "p95": 2, "max": 3},
        }
    )

    assert "matchRate: 80.00%" in markdown
    assert "| 小学校 | 1 |" in markdown
