from __future__ import annotations

import pytest

from evaluate.compare_train_start_years import render_markdown, weighted_metrics


def test_weighted_metrics_aggregates_by_test_count() -> None:
    rows = [
        {
            "testCount": 3,
            "metrics": {"mae": 10.0, "rmse": 20.0, "mape": 5.0},
        },
        {
            "testCount": 1,
            "metrics": {"mae": 30.0, "rmse": 40.0, "mape": 9.0},
        },
    ]

    metrics = weighted_metrics(rows)

    assert metrics["mae"] == pytest.approx(15.0)
    assert metrics["rmse"] == pytest.approx(700.0**0.5)
    assert metrics["mape"] == pytest.approx(6.0)


def test_render_markdown_includes_comparison_rows() -> None:
    report = {
        "configs": ["configs/tokyo.yaml"],
        "trainStartYears": [2005, 2015],
        "testYears": [2025],
        "comparisons": [
            {
                "trainStartYear": 2015,
                "testYear": 2025,
                "metrics": {"mae": 1.0, "rmse": 2.0, "mape": 3.0},
                "regions": [
                    {
                        "region": "tokyo",
                        "trainCount": 10,
                        "testCount": 2,
                        "trainingSeconds": 1.25,
                        "metrics": {"mae": 1.0, "rmse": 2.0, "mape": 3.0},
                    }
                ],
            }
        ],
    }

    markdown = render_markdown(report)

    assert "学習開始年の複数holdout比較" in markdown
    assert "| 2015 | 2025 | 1 | 2 | 3.00% | 2 | 1.2 |" in markdown
    assert "tokyo" in markdown
