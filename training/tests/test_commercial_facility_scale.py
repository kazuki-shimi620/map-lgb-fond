import pytest

from features.commercial_facility_scale import classify_commercial_facility_scale


@pytest.mark.parametrize(
    ("area", "expected"),
    [(4999, "small"), (5000, "medium"), (15000, "large"), (40000, "very_large")],
)
def test_classify_commercial_facility_scale_uses_store_area(
    area: float, expected: str
) -> None:
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
