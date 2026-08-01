from __future__ import annotations

from typing import Any

SCALE_LABELS = {
    "small": "小規模",
    "medium": "中規模",
    "large": "大規模",
    "very_large": "超大型",
    "unknown": "規模不明",
}


def classify_commercial_facility_scale(
    store_area_sqm: float | None, tenant_count: int | None
) -> dict[str, Any]:
    if store_area_sqm is not None and store_area_sqm > 0:
        code = _area_scale(store_area_sqm)
        basis = "store_area_sqm"
    elif tenant_count is not None and tenant_count > 0:
        code = _tenant_scale(tenant_count)
        basis = "tenant_count"
    else:
        code = "unknown"
        basis = "unknown"
    return {"scaleCode": code, "scaleLabel": SCALE_LABELS[code], "scaleBasis": basis}


def _area_scale(value: float) -> str:
    if value < 5_000:
        return "small"
    if value < 15_000:
        return "medium"
    if value < 40_000:
        return "large"
    return "very_large"


def _tenant_scale(value: int) -> str:
    if value < 20:
        return "small"
    if value < 50:
        return "medium"
    if value < 150:
        return "large"
    return "very_large"
