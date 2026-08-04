from __future__ import annotations

from math import sqrt

MIN_SEGMENT_SAMPLE_COUNT = 100


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


def calculate_segment_metrics(
    dataframe,
    predictions,
    *,
    minimum_sample_count: int = MIN_SEGMENT_SAMPLE_COUNT,
) -> dict[str, object]:
    """Summarize holdout errors without exposing unstable small-segment metrics."""
    import numpy as np
    import pandas as pd

    target = dataframe.reset_index(drop=True).copy()
    target["_prediction"] = np.asarray(predictions, dtype=float)
    dimensions = {
        "price": pd.cut(
            target["price"],
            bins=[float("-inf"), 30_000_000, 50_000_000, 80_000_000, float("inf")],
            labels=["3000万円未満", "3000〜5000万円", "5000〜8000万円", "8000万円以上"],
            right=False,
        ),
        "age": pd.cut(
            target["age"],
            bins=[float("-inf"), 10, 20, 30, float("inf")],
            labels=["築10年未満", "築10〜19年", "築20〜29年", "築30年以上"],
            right=False,
        ),
        "area": pd.cut(
            target["area"],
            bins=[float("-inf"), 40, 60, 80, float("inf")],
            labels=["40㎡未満", "40〜59㎡", "60〜79㎡", "80㎡以上"],
            right=False,
        ),
    }
    if "prefecture" in target.columns:
        dimensions["prefecture"] = target["prefecture"].fillna("不明").astype(str)

    grouped: dict[str, list[dict[str, object]]] = {}
    for dimension, labels in dimensions.items():
        rows = []
        for label in labels.dropna().unique():
            mask = labels == label
            count = int(mask.sum())
            metrics = (
                calculate_metrics(target.loc[mask, "price"], target.loc[mask, "_prediction"])
                if count >= minimum_sample_count
                else None
            )
            rows.append({"label": str(label), "count": count, "metrics": metrics})
        grouped[dimension] = rows

    return {
        "minimumSampleCount": minimum_sample_count,
        "dimensions": grouped,
    }
