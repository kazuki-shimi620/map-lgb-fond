from __future__ import annotations

import pandas as pd

from preprocess.enrich_coordinates import enrich_property_coordinates


def test_enrich_property_coordinates_prefers_town_then_prefix() -> None:
    properties = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "丸の内",
            },
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "大手町",
            },
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "存在しない町",
            },
        ]
    )
    points = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "丸の内",
                "lat": 35.681236,
                "lon": 139.767125,
            },
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "大手町一丁目",
                "lat": 35.686944,
                "lon": 139.763056,
            },
        ]
    )

    enriched = enrich_property_coordinates(properties, points)

    assert enriched.loc[0, "coordinate_source"] == "town"
    assert enriched.loc[0, "lat"] == 35.681236
    assert enriched.loc[1, "coordinate_source"] == "district_prefix"
    assert enriched.loc[1, "lon"] == 139.763056
    assert enriched.loc[2, "coordinate_source"] == "none"


def test_enrich_property_coordinates_can_use_municipality_fallback() -> None:
    enriched = enrich_property_coordinates(
        pd.DataFrame(
            [
                {
                    "prefecture": "東京都",
                    "municipality": "千代田区",
                    "district_name": "存在しない町",
                }
            ]
        ),
        pd.DataFrame(
            [
                {
                    "prefecture": "東京都",
                    "municipality": "千代田区",
                    "district_name": "丸の内",
                    "lat": 35.681236,
                    "lon": 139.767125,
                }
            ]
        ),
        include_municipality_fallback=True,
    )

    assert enriched.loc[0, "coordinate_source"] == "municipality"
    assert enriched.loc[0, "lat"] == 35.681236
