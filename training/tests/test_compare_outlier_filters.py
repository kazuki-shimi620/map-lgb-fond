from __future__ import annotations

import pandas as pd

from evaluate.compare_outlier_filters import (
    OutlierFilterCandidate,
    apply_outlier_filter,
    render_markdown,
)


def test_apply_outlier_filter_removes_matching_edges() -> None:
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
                "age": 10,
                "station_distance": 8,
            },
            {
                "price": 80_000_000,
                "area": 30,
                "age": 55,
                "station_distance": 70,
            },
            {
                "price": 70_000_000,
                "area": 20,
                "age": 20,
                "station_distance": 10,
            },
        ]
    )
    candidate = OutlierFilterCandidate(
        "strict",
        "strict filter",
        max_price=100_000_000,
        min_area=25,
        max_age=50,
        max_station_distance=60,
    )

    filtered = apply_outlier_filter(df, candidate)

    assert len(filtered) == 1
    assert filtered.iloc[0]["price"] == 40_000_000


def test_render_markdown_contains_candidate_table() -> None:
    report = {
        "regions": ["tokyo"],
        "trainStartYears": [2015],
        "testYears": [2025],
        "rowCount": 10,
        "candidates": [
            {
                "candidate": "current_processed",
                "description": "現行",
                "trainStartYear": 2015,
                "removedRowCount": 0,
                "removedShare": 0.0,
                "trainingSeconds": 0.1,
                "metrics": {"mae": 1000.0, "rmse": 1200.0, "mape": 1.2},
            }
        ],
    }

    markdown = render_markdown(report)

    assert "# 外れ値処理候補バックテスト" in markdown
    assert "| current_processed | 2015 | 0 | 0.00% | 1,000 | 1,200 | 1.20% |" in markdown
