from __future__ import annotations

import pandas as pd

from preprocess.enrich_commercial_facilities import enrich_commercial_facility_coordinates


def test_enrich_commercial_facility_coordinates_matches_longest_district() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "丸の内テストSC",
                "prefecture": "東京都",
                "city": "千代田区",
                "address_raw": "東京都千代田区丸の内一丁目1-1",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "丸の内",
                "lat": 35.680,
                "lon": 139.760,
            },
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "丸の内一丁目",
                "lat": 35.681,
                "lon": 139.761,
            },
        ]
    )

    enriched = enrich_commercial_facility_coordinates(commercial, address_points)

    assert enriched.loc[0, "coordinate_source"] == "address_point"
    assert enriched.loc[0, "lat"] == 35.681
    assert enriched.loc[0, "lon"] == 139.761


def test_enrich_commercial_facility_coordinates_keeps_existing_coordinates() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "座標ありSC",
                "prefecture": "東京都",
                "city": "千代田区",
                "address_raw": "東京都千代田区丸の内一丁目1-1",
                "lat": 35.0,
                "lon": 139.0,
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "丸の内一丁目",
                "lat": 35.681,
                "lon": 139.761,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(commercial, address_points)

    assert enriched.loc[0, "coordinate_source"] == "input"
    assert enriched.loc[0, "lat"] == 35.0
    assert enriched.loc[0, "lon"] == 139.0
