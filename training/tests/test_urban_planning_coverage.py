from __future__ import annotations

import json

import pandas as pd
import pytest

from evaluate.urban_planning_coverage import (
    build_urban_planning_coverage_report,
    render_markdown,
)


def test_build_urban_planning_coverage_report_counts_matches(tmp_path) -> None:
    urban_csv = tmp_path / "urban_planning_areas.csv"
    urban_csv.write_text("source_api,geometry_json\n", encoding="utf-8")
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [[139.0, 35.0], [140.0, 35.0], [140.0, 36.0], [139.0, 36.0], [139.0, 35.0]]
        ],
    }
    properties = pd.DataFrame(
        [
            {"lat": 35.5, "lon": 139.5},
            {"lat": 34.0, "lon": 139.5},
        ]
    )
    areas = pd.DataFrame(
        [
            {
                "area_type": "zoning",
                "area_name": "商業地域",
                "zoning_type": "商業地域",
                "floor_area_ratio": 600.0,
                "building_coverage_ratio": 80.0,
                "geometry_json": json.dumps(polygon),
            },
            {
                "area_type": "city_planning_area",
                "area_name": "市街化区域",
                "geometry_json": json.dumps(polygon),
            },
        ]
    )

    report = build_urban_planning_coverage_report(
        property_df=properties,
        urban_planning_areas_df=areas,
        source_paths=["tokyo.parquet"],
        urban_planning_csv=urban_csv,
    )

    assert report["recordCount"] == 2
    assert report["propertyCoordinateCount"] == 2
    assert report["propertyCoordinateRate"] == pytest.approx(1.0)
    assert report["areaCount"] == 2
    assert report["zoningMatchedRowCount"] == 1
    assert report["zoningMatchRate"] == pytest.approx(0.5)
    assert report["zoningTypeCounts"]["商業地域"] == 1
    assert report["zoningTypeCounts"]["unknown"] == 1


def test_render_markdown_includes_match_rate() -> None:
    markdown = render_markdown(
        {
            "generatedAt": "2026-07-15T00:00:00+00:00",
            "urbanPlanningCsv": "urban_planning_areas.csv",
            "urbanPlanningCsvBytes": 100,
            "recordCount": 10,
            "propertyCoordinateCount": 5,
            "propertyCoordinateRate": 0.5,
            "areaCount": 3,
            "zoningMatchedRowCount": 8,
            "zoningMatchRate": 0.8,
            "zoningTypeCounts": {"商業地域": 8, "unknown": 2},
            "cityPlanningAreaTypeCounts": {"市街化区域": 8, "unknown": 2},
            "locationOptimizationAreaCounts": {"unknown": 10},
        }
    )

    assert "zoningMatchRate: 80.00%" in markdown
    assert "propertyCoordinateRate: 50.00%" in markdown
    assert "| 商業地域 | 8 |" in markdown
