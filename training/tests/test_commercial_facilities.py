from __future__ import annotations

import pandas as pd

from features.commercial_facilities import add_commercial_facility_features


def test_add_commercial_facility_features_uses_prior_years_only() -> None:
    properties = pd.DataFrame(
        [
            {"prefecture": "東京都", "municipality": "調布市", "transaction_year": 2020},
            {"prefecture": "東京都", "municipality": "調布市", "transaction_year": 2021},
            {"prefecture": "東京都", "municipality": "調布市", "transaction_year": 2023},
            {"prefecture": "大阪府", "municipality": "大阪市", "transaction_year": 2023},
        ]
    )
    facilities = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "city": "調布市",
                "open_year": 2020,
                "store_area_sqm": 1000.0,
                "tenant_count": 10,
            },
            {
                "prefecture": "東京都",
                "city": "調布市",
                "open_year": 2022,
                "store_area_sqm": 2000.0,
                "tenant_count": 20,
            },
            {
                "prefecture": "大阪府",
                "city": "大阪市",
                "open_year": 2021,
                "store_area_sqm": 3000.0,
                "tenant_count": 30,
            },
        ]
    )

    actual = add_commercial_facility_features(properties, facilities, data_start_year=2015)

    assert actual.loc[0, "sc_city_open_count_cumulative"] == 0
    assert actual.loc[1, "sc_city_open_count_cumulative"] == 1
    assert actual.loc[2, "sc_city_open_count_cumulative"] == 2
    assert actual.loc[2, "sc_city_open_count_last_3y"] == 2
    assert actual.loc[2, "sc_city_store_area_sum_cumulative"] == 3000
    assert actual.loc[2, "sc_city_tenant_count_sum_cumulative"] == 30
    assert actual.loc[3, "sc_prefecture_open_count_last_3y"] == 1
