from __future__ import annotations

import pytest

from preprocess.cleaning import normalize_mlit_records, preprocess_dataframe


def test_normalize_mlit_records_keeps_only_condominiums() -> None:
    records = [
        {
            "Type": "中古マンション等",
            "TradePrice": "50000000",
            "Area": "60",
            "BuildingYear": "2010年",
            "Period": "2024年第1四半期",
            "Prefecture": "東京都",
            "Municipality": "千代田区",
            "DistrictName": "丸の内",
            "FloorPlan": "2LDK",
            "Structure": "ＲＣ",
        },
        {
            "Type": "宅地(土地と建物)",
            "TradePrice": "80000000",
            "Area": "100",
            "BuildingYear": "2015年",
            "Period": "2024年第1四半期",
            "Prefecture": "東京都",
            "Municipality": "千代田区",
        },
    ]

    normalized = normalize_mlit_records(records)

    assert len(normalized) == 1
    assert normalized.iloc[0]["price"] == 50_000_000
    assert normalized.iloc[0]["station"] is None
    assert normalized.iloc[0]["station_distance"] is None


def test_preprocess_rejects_api_records_without_station_features(tmp_path) -> None:
    normalized = normalize_mlit_records(
        [
            {
                "Type": "中古マンション等",
                "TradePrice": "50000000",
                "Area": "60",
                "BuildingYear": "2010年",
                "Period": "2024年第1四半期",
                "Prefecture": "東京都",
                "Municipality": "千代田区",
                "FloorPlan": "2LDK",
                "Structure": "ＲＣ",
            }
        ]
    )

    with pytest.raises(ValueError, match="XIT001 does not provide"):
        preprocess_dataframe(normalized, tmp_path / "tokyo.parquet")
