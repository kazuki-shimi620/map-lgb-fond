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
    dimensions = build_segment_labels(target)

    grouped: dict[str, list[dict[str, object]]] = {}
    for dimension, labels in dimensions.items():
        rows = []
        label_values = (
            list(labels.cat.categories)
            if isinstance(labels.dtype, pd.CategoricalDtype)
            else sorted(labels.dropna().unique())
        )
        for label in label_values:
            mask = labels == label
            count = int(mask.sum())
            if count == 0:
                continue
            metrics = (
                calculate_metrics(target.loc[mask, "price"], target.loc[mask, "_prediction"])
                if count >= minimum_sample_count
                else None
            )
            residual_quantiles = (
                calculate_residual_quantiles(
                    target.loc[mask, "price"], target.loc[mask, "_prediction"]
                )
                if count >= minimum_sample_count
                else None
            )
            rows.append(
                {
                    "label": str(label),
                    "count": count,
                    "metrics": metrics,
                    "residualQuantiles": residual_quantiles,
                }
            )
        grouped[dimension] = rows

    return {
        "minimumSampleCount": minimum_sample_count,
        "dimensions": grouped,
    }


def build_segment_labels(dataframe):
    import pandas as pd

    dimensions = {
        "price": pd.cut(
            dataframe["_prediction"],
            bins=[float("-inf"), 30_000_000, 50_000_000, 80_000_000, float("inf")],
            labels=["3000万円未満", "3000〜5000万円", "5000〜8000万円", "8000万円以上"],
            right=False,
        ),
        "age": pd.cut(
            dataframe["age"],
            bins=[float("-inf"), 10, 20, 30, float("inf")],
            labels=["築10年未満", "築10〜19年", "築20〜29年", "築30年以上"],
            right=False,
        ),
        "area": pd.cut(
            dataframe["area"],
            bins=[float("-inf"), 40, 60, 80, float("inf")],
            labels=["40㎡未満", "40〜59㎡", "60〜79㎡", "80㎡以上"],
            right=False,
        ),
    }
    if "prefecture" in dataframe.columns:
        dimensions["prefecture"] = dataframe["prefecture"].fillna("不明").astype(str)
    return dimensions


def compare_segment_intervals(dataframe, predictions, segment_summary) -> dict[str, object]:
    """Compare global and one-dimensional segment intervals on the holdout rows."""
    import numpy as np

    target = dataframe.reset_index(drop=True).copy()
    target["_prediction"] = np.asarray(predictions, dtype=float)
    residuals = target["price"].to_numpy() - target["_prediction"].to_numpy()
    global_quantiles = calculate_residual_quantiles(target["price"], target["_prediction"])
    result = {"global": _interval_result(residuals, [global_quantiles] * len(target))}

    labels_by_dimension = build_segment_labels(target)
    for dimension, rows in segment_summary["dimensions"].items():
        quantiles_by_label = {
            row["label"]: row["residualQuantiles"]
            for row in rows
            if row["residualQuantiles"] is not None
        }
        row_quantiles = [
            quantiles_by_label.get(str(label), global_quantiles)
            for label in labels_by_dimension[dimension]
        ]
        result[dimension] = _interval_result(residuals, row_quantiles)
    return result


def _interval_result(residuals, quantiles) -> dict[str, float]:
    import numpy as np

    lower = np.asarray([item["p025"] for item in quantiles])
    upper = np.asarray([item["p975"] for item in quantiles])
    covered = (residuals >= lower) & (residuals <= upper)
    return {
        "coverage": float(np.mean(covered)),
        "averageWidth": float(np.mean(upper - lower)),
    }
