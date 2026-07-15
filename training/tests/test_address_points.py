from __future__ import annotations

from collect.address_points import normalize_address_rows


def test_normalize_address_rows_handles_geolonia_columns() -> None:
    rows = normalize_address_rows(
        [
            {
                "都道府県名": "東京都",
                "市区町村名": "千代田区",
                "大字町丁目名": "丸の内",
                "小字・通称名": "",
                "緯度（代表点）": "35.681236",
                "経度（代表点）": "139.767125",
            },
            {
                "都道府県名": "東京都",
                "市区町村名": "千代田区",
                "大字町丁目名": "大手町一丁目",
                "緯度": "35.686944",
                "経度": "139.763056",
            },
            {
                "都道府県名": "東京都",
                "市区町村名": "千代田区",
                "大字町丁目名": "",
                "緯度（代表点）": "35",
                "経度（代表点）": "139",
            },
        ]
    )

    assert rows == [
        {
            "prefecture": "東京都",
            "municipality": "千代田区",
            "district_name": "丸の内",
            "sub_district_name": "",
            "lat": 35.681236,
            "lon": 139.767125,
            "source": "geolonia_japanese_addresses",
        },
        {
            "prefecture": "東京都",
            "municipality": "千代田区",
            "district_name": "大手町一丁目",
            "sub_district_name": "",
            "lat": 35.686944,
            "lon": 139.763056,
            "source": "geolonia_japanese_addresses",
        },
    ]
