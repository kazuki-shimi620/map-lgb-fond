from __future__ import annotations

import pandas as pd

from evaluate.dataset_edge_cases import build_edge_case_report, render_markdown


def test_build_edge_case_report_counts_segments() -> None:
    df = pd.DataFrame(
        [
            {
                "price": 40_000_000,
                "area": 50,
                "age": 10,
                "station_distance": 8,
            },
            {
                "price": 120_000_000,
                "area": 50,
                "age": 55,
                "station_distance": 65,
            },
            {
                "price": 30_000_000,
                "area": 20,
                "age": 42,
                "station_distance": 35,
            },
        ]
    )

    report = build_edge_case_report(df, region="tokyo", source_path="data/processed/tokyo.parquet")
    segments = {segment["name"]: segment for segment in report["segments"]}

    assert report["recordCount"] == 3
    assert segments["all"]["count"] == 3
    assert segments["old_building"]["count"] == 2
    assert segments["very_old_building"]["count"] == 1
    assert segments["station_far"]["count"] == 2
    assert segments["station_very_far"]["count"] == 1
    assert segments["high_price"]["count"] == 1
    assert segments["luxury_unit_price"]["count"] == 1
    assert segments["small_area"]["count"] == 1
    assert segments["old_building"]["share"] == 2 / 3


def test_render_markdown_contains_summary_table() -> None:
    df = pd.DataFrame(
        [
            {
                "price": 40_000_000,
                "area": 50,
                "age": 10,
                "station_distance": 8,
            }
        ]
    )

    report = build_edge_case_report(df, region="tokyo", source_path="data/processed/tokyo.parquet")
    markdown = render_markdown(report)

    assert "# tokyo edge case summary" in markdown
    assert "| all | 1 | 100.00% |" in markdown
