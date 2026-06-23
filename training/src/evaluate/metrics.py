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
        "mape": float(np.mean(np.abs(errors[non_zero] / actual[non_zero])) * 100) if non_zero.any() else 0.0,
    }
