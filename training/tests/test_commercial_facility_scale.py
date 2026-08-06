import pytest
import pandas as pd

from features.commercial_facility_scale import (
    add_commercial_facility_scale_columns,
    classify_commercial_facility_scale,
)


@pytest.mark.parametrize(
    ("area", "expected"),
    [(4999, "small"), (5000, "medium"), (15000, "large"), (40000, "very_large")],
)
def test_classify_commercial_facility_scale_uses_store_area(area: float, expected: str) -> None:
    actual = classify_commercial_facility_scale(area, 999)

    assert actual["scaleCode"] == expected
    assert actual["scaleBasis"] == "store_area_sqm"


def test_classify_commercial_facility_scale_falls_back_to_tenant_count() -> None:
    actual = classify_commercial_facility_scale(None, 150)

    assert actual == {
        "scaleCode": "very_large",
        "scaleLabel": "超大型",
        "scaleBasis": "tenant_count",
    }


def test_classify_commercial_facility_scale_keeps_unknown() -> None:
    assert classify_commercial_facility_scale(None, None)["scaleCode"] == "unknown"


def test_add_commercial_facility_scale_columns_uses_area_and_tenant_fallback() -> None:
    source = pd.DataFrame(
        {
            "name": ["面積あり", "テナントのみ", "規模不明"],
            "store_area_sqm": [4_999, None, None],
            "tenant_count": [999, 50, None],
        }
    )

    actual = add_commercial_facility_scale_columns(source)

    assert actual["scale_code"].tolist() == ["small", "large", "unknown"]
    assert actual["scale_label"].tolist() == ["小規模", "大規模", "規模不明"]
    assert actual["scale_basis"].tolist() == [
        "store_area_sqm",
        "tenant_count",
        "unknown",
    ]
    assert "scale_code" not in source.columns


def test_add_commercial_facility_scale_columns_supports_missing_tenant_column() -> None:
    source = pd.DataFrame({"store_area_sqm": [40_000, None]})

    actual = add_commercial_facility_scale_columns(source)

    assert actual["scale_code"].tolist() == ["very_large", "unknown"]
