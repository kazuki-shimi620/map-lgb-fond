from __future__ import annotations

import pytest

import pandas as pd

from preprocess.cleaning import (
    normalize_japanese_mlit_columns,
    normalize_mlit_records,
    preprocess_dataframe,
)


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
    assert normalized.iloc[0]["district_name"] == "丸の内"
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


def test_normalize_mlit_records_keeps_optional_coordinates() -> None:
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
                "DistrictName": "丸の内",
                "NearestStation": "東京",
                "TimeToNearestStation": "5",
                "FloorPlan": "2LDK",
                "Structure": "ＲＣ",
                "Latitude": "35.681236",
                "Longitude": "139.767125",
            }
        ]
    )

    assert normalized.iloc[0]["district_name"] == "丸の内"
    assert normalized.iloc[0]["lat"] == pytest.approx(35.681236)
    assert normalized.iloc[0]["lon"] == pytest.approx(139.767125)


def test_normalize_japanese_mlit_columns_keeps_district_name_and_coordinates() -> None:
    normalized = normalize_japanese_mlit_columns(
        pd.DataFrame(
            [
                {
                    "種類": "中古マンション等",
                    "取引価格（総額）": "50,000,000",
                    "面積（㎡）": "60",
                    "建築年": "2010年",
                    "取引時期": "2024年第1四半期",
                    "都道府県名": "東京都",
                    "市区町村名": "千代田区",
                    "地区名": "丸の内",
                    "最寄駅：名称": "東京",
                    "最寄駅：距離（分）": "5",
                    "間取り": "2LDK",
                    "建物の構造": "ＲＣ",
                    "緯度": "35.681236",
                    "経度": "139.767125",
                }
            ]
        )
    )

    assert normalized.iloc[0]["district_name"] == "丸の内"
    assert normalized.iloc[0]["lat"] == pytest.approx(35.681236)
    assert normalized.iloc[0]["lon"] == pytest.approx(139.767125)
