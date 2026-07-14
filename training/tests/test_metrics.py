import pytest

from evaluate.metrics import calculate_residual_quantiles


def test_calculate_residual_quantiles_uses_prediction_residuals():
    quantiles = calculate_residual_quantiles(
        [100.0, 200.0, 400.0, 800.0],
        [90.0, 250.0, 350.0, 700.0],
    )

    assert quantiles["p025"] == pytest.approx(-45.5)
    assert quantiles["p975"] == pytest.approx(96.25)


def test_calculate_residual_quantiles_handles_empty_input():
    assert calculate_residual_quantiles([], []) == {"p025": 0.0, "p975": 0.0}
