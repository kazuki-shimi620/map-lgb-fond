import pandas as pd
import pytest

from evaluate.metrics import calculate_residual_quantiles, calculate_segment_metrics


def test_calculate_residual_quantiles_uses_prediction_residuals():
    quantiles = calculate_residual_quantiles(
        [100.0, 200.0, 400.0, 800.0],
        [90.0, 250.0, 350.0, 700.0],
    )

    assert quantiles["p025"] == pytest.approx(-45.5)
    assert quantiles["p975"] == pytest.approx(96.25)


def test_calculate_residual_quantiles_handles_empty_input():
    assert calculate_residual_quantiles([], []) == {"p025": 0.0, "p975": 0.0}


def test_calculate_segment_metrics_hides_metrics_below_minimum_count():
    dataframe = pd.DataFrame(
        {
            "price": [20_000_000, 25_000_000, 60_000_000],
            "age": [5, 15, 35],
            "area": [35, 55, 85],
            "prefecture": ["東京都", "東京都", "神奈川県"],
        }
    )

    result = calculate_segment_metrics(
        dataframe,
        [18_000_000, 30_000_000, 54_000_000],
        minimum_sample_count=2,
    )

    assert result["minimumSampleCount"] == 2
    price_rows = {row["label"]: row for row in result["dimensions"]["price"]}
    assert price_rows["3000万円未満"]["count"] == 2
    assert price_rows["3000万円未満"]["metrics"]["mae"] == 3_500_000
    assert price_rows["5000〜8000万円"]["count"] == 1
    assert price_rows["5000〜8000万円"]["metrics"] is None

    prefecture_rows = {
        row["label"]: row for row in result["dimensions"]["prefecture"]
    }
    assert prefecture_rows["東京都"]["metrics"] is not None
    assert prefecture_rows["神奈川県"]["metrics"] is None
