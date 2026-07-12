from __future__ import annotations

from math import sqrt


def calculate_metrics(y_true, y_pred) -> dict[str, float]:
    import numpy as np

    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    errors = actual - predicted
    non_zero = actual != 0

    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(sqrt(np.mean(errors**2))),
        "mape": float(np.mean(np.abs(errors[non_zero] / actual[non_zero])) * 100)
        if non_zero.any()
        else 0.0,
    }


def calculate_residual_quantiles(y_true, y_pred) -> dict[str, float]:
    import numpy as np

    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    residuals = actual - predicted
    if residuals.size == 0:
        return {"p025": 0.0, "p975": 0.0}
    return {
        "p025": float(np.quantile(residuals, 0.025)),
        "p975": float(np.quantile(residuals, 0.975)),
    }
