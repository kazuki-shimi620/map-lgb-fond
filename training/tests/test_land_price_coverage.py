from __future__ import annotations

import pandas as pd
import pytest

from evaluate.land_price_coverage import build_land_price_coverage_report, render_markdown


def test_build_land_price_coverage_report_counts_matches(tmp_path) -> None:
    points_csv = tmp_path / "land_price_points.csv"
    city_csv = tmp_path / "land_price_city_summary.csv"
    points_csv.write_text("year,lat,lon,current_price_yen_per_sqm\n", encoding="utf-8")
    city_csv.write_text("year,prefecture,municipality,avg_price_yen_per_sqm\n", encoding="utf-8")
    properties = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "transaction_year": 2025,
                "lat": 35.681236,
                "lon": 139.767125,
            },
            {
                "prefecture": "東京都",
                "municipality": "未整備区",
                "transaction_year": 2025,
                "lat": None,
                "lon": None,
            },
        ]
    )
    points = pd.DataFrame(
        [
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "lat": 35.6813,
                "lon": 139.7672,
                "current_price_yen_per_sqm": 3000.0,
            }
        ]
    )
    city_summary = pd.DataFrame(
        [
            {
                "year": 2025,
                "prefecture": "東京都",
                "municipality": "千代田区",
                "point_count": 2,
                "avg_price_yen_per_sqm": 2500.0,
                "avg_yoy_rate": 3.5,
            }
        ]
    )

    report = build_land_price_coverage_report(
        property_df=properties,
        land_price_points_df=points,
        land_price_city_summary_df=city_summary,
        source_paths=["tokyo.parquet"],
        land_price_points_csv=points_csv,
        land_price_city_summary_csv=city_csv,
    )

    assert report["recordCount"] == 2
    assert report["pointCount"] == 1
    assert report["citySummaryCount"] == 1
    assert report["matchedRowCount"] == 1
    assert report["matchRate"] == pytest.approx(0.5)
    assert report["cityAveragePriceYenPerSqm"]["max"] == pytest.approx(2500.0)
    assert report["nearestPriceYenPerSqm"]["max"] == pytest.approx(3000.0)


def test_render_markdown_includes_match_rate() -> None:
    markdown = render_markdown(
        {
            "generatedAt": "2026-07-15T00:00:00+00:00",
            "landPricePointsCsv": "land_price_points.csv",
            "landPricePointsCsvBytes": 100,
            "landPriceCitySummaryCsv": "land_price_city_summary.csv",
            "landPriceCitySummaryCsvBytes": 200,
            "recordCount": 10,
            "pointCount": 3,
            "citySummaryCount": 2,
            "matchedRowCount": 8,
            "matchRate": 0.8,
            "cityAveragePriceYenPerSqm": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "cityYoyRate": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "nearestPriceYenPerSqm": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "nearestDistanceKm": {"min": 0, "median": 1, "p95": 2, "max": 3},
            "pointsWithin2km": {"min": 0, "median": 1, "p95": 2, "max": 3},
        }
    )

    assert "matchRate: 80.00%" in markdown
    assert "| cityYoyRate | 0.000 | 1.000 | 2.000 | 3.000 |" in markdown
