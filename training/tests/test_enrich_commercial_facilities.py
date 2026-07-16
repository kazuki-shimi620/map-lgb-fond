from __future__ import annotations

import pandas as pd

from preprocess.enrich_commercial_facilities import (
    build_google_maps_search_query,
    build_google_maps_search_url,
    enrich_commercial_facility_coordinates,
)


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


def test_enrich_commercial_facility_coordinates_prefers_manual_coordinates() -> None:
    commercial = pd.DataFrame(
        [
            {
                "match_key": "東京都|テストモール",
                "name": "テストモール",
                "prefecture": "東京都",
                "municipality": "千代田区",
            }
        ]
    )
    manual = pd.DataFrame(
        [
            {
                "match_key": "東京都|テストモール",
                "address": "東京都千代田区丸の内一丁目1-1",
                "lat": 35.681,
                "lon": 139.761,
                "source_url": "https://www.google.com/maps/search/?api=1&query=テストモール",
                "source_type": "google_map",
                "confidence": "high",
                "notes": "施設名で検索して確認",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "丸の内一丁目",
                "lat": 35.0,
                "lon": 139.0,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(commercial, address_points, manual)

    assert enriched.loc[0, "coordinate_source"] == "manual:google_map"
    assert enriched.loc[0, "coordinate_confidence"] == "high"
    assert enriched.loc[0, "lat"] == 35.681
    assert enriched.loc[0, "lon"] == 139.761


def test_enrich_commercial_facility_coordinates_uses_municipality_fallback() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "PDF由来SC",
                "prefecture": "東京都",
                "municipality": "千代田区",
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
            },
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "district_name": "有楽町一丁目",
                "lat": 35.674,
                "lon": 139.762,
            },
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "coordinate_source"] == "municipality_representative"
    assert enriched.loc[0, "coordinate_confidence"] == "low"
    assert enriched.loc[0, "lat"] == (35.681 + 35.674) / 2


def test_enrich_commercial_facility_coordinates_matches_countyless_town() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "PDF由来町SC",
                "prefecture": "北海道",
                "municipality": "余市町",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "北海道",
                "municipality": "余市郡余市町",
                "district_name": "朝日町",
                "lat": 43.193712,
                "lon": 140.780153,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "coordinate_source"] == "municipality_representative"
    assert enriched.loc[0, "municipality"] == "余市郡余市町"
    assert enriched.loc[0, "lat"] == 43.193712


def test_enrich_commercial_facility_coordinates_corrects_prefecture_by_unique_town() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "PDF由来県ずれSC",
                "prefecture": "宮城県",
                "municipality": "藤崎町",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "青森県",
                "municipality": "南津軽郡藤崎町",
                "district_name": "大字藤崎",
                "lat": 40.656,
                "lon": 140.499,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "prefecture"] == "青森県"
    assert enriched.loc[0, "municipality"] == "南津軽郡藤崎町"
    assert enriched.loc[0, "coordinate_notes"] == "prefecture_inferred_from_municipality"


def test_enrich_commercial_facility_coordinates_matches_ke_variant() -> None:
    commercial = pd.DataFrame(
        [{"name": "PDF由来SC", "prefecture": "茨城県", "municipality": "龍ケ崎市"}]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "茨城県",
                "municipality": "龍ヶ崎市",
                "district_name": "佐貫一丁目",
                "lat": 35.930,
                "lon": 140.138,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "municipality"] == "龍ヶ崎市"
    assert enriched.loc[0, "lat"] == 35.930


def test_enrich_commercial_facility_coordinates_fuzzy_matches_ocr_typo() -> None:
    commercial = pd.DataFrame(
        [{"name": "PDF由来SC", "prefecture": "栃木県", "municipality": "宇部宮市"}]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "栃木県",
                "municipality": "宇都宮市",
                "district_name": "馬場通り一丁目",
                "lat": 36.560,
                "lon": 139.883,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "municipality"] == "宇都宮市"
    assert enriched.loc[0, "coordinate_notes"] == "fuzzy_municipality"


def test_enrich_commercial_facility_coordinates_applies_municipality_alias() -> None:
    commercial = pd.DataFrame(
        [{"name": "PDF由来SC", "prefecture": "北海道", "municipality": "音史町"}]
    )
    aliases = pd.DataFrame(
        [
            {
                "source_prefecture": "北海道",
                "source_municipality": "音史町",
                "corrected_prefecture": "北海道",
                "corrected_municipality": "河東郡音更町",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "北海道",
                "municipality": "河東郡音更町",
                "district_name": "木野大通西一丁目",
                "lat": 42.992,
                "lon": 143.202,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        municipality_aliases_df=aliases,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "municipality"] == "河東郡音更町"
    assert enriched.loc[0, "coordinate_notes"] == "municipality_alias"
    assert enriched.loc[0, "lat"] == 42.992


def test_enrich_commercial_facility_coordinates_applies_district_alias() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "あべのハルカス",
                "prefecture": "京都府",
                "municipality": "",
                "district": "阿倍野区",
            }
        ]
    )
    aliases = pd.DataFrame(
        [
            {
                "source_prefecture": "京都府",
                "source_municipality": "",
                "source_district": "阿倍野区",
                "corrected_prefecture": "大阪府",
                "corrected_municipality": "大阪市阿倍野区",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "大阪府",
                "municipality": "大阪市阿倍野区",
                "district_name": "阿倍野筋一丁目",
                "lat": 34.645732,
                "lon": 135.51332,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        municipality_aliases_df=aliases,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "prefecture"] == "大阪府"
    assert enriched.loc[0, "municipality"] == "大阪市阿倍野区"
    assert enriched.loc[0, "coordinate_notes"] == "municipality_alias"
    assert enriched.loc[0, "lat"] == 34.645732


def test_enrich_commercial_facility_coordinates_applies_name_alias() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "函館昭和タウンプラザ",
                "prefecture": "北海道",
                "municipality": "",
            }
        ]
    )
    aliases = pd.DataFrame(
        [
            {
                "source_prefecture": "北海道",
                "source_municipality": "",
                "source_district": "",
                "source_name": "函館昭和タウンプラザ",
                "corrected_prefecture": "北海道",
                "corrected_municipality": "函館市",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "北海道",
                "municipality": "函館市",
                "district_name": "昭和一丁目",
                "lat": 41.814,
                "lon": 140.743,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        municipality_aliases_df=aliases,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "municipality"] == "函館市"
    assert enriched.loc[0, "coordinate_notes"] == "municipality_alias"
    assert enriched.loc[0, "lat"] == 41.814


def test_enrich_commercial_facility_coordinates_applies_row_correction() -> None:
    commercial = pd.DataFrame(
        [
            {
                "page": 14,
                "column": "left",
                "store_area_sqm": 59000.0,
                "open_year": 2016,
                "open_month": 12,
                "name": "",
                "prefecture": "滋賀県",
                "municipality": "",
            }
        ]
    )
    corrections = pd.DataFrame(
        [
            {
                "source_page": 14,
                "source_column": "left",
                "source_store_area_sqm": 59000,
                "source_open_year": 2016,
                "source_open_month": 12,
                "corrected_name": "イオンモール長久手",
                "corrected_prefecture": "愛知県",
                "corrected_municipality": "長久手市",
                "address": "愛知県長久手市勝入塚501番地",
                "notes": "user_verified_address",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "愛知県",
                "municipality": "長久手市",
                "district_name": "勝入塚",
                "lat": 35.173,
                "lon": 137.039,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        row_corrections_df=corrections,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "name"] == "イオンモール長久手"
    assert enriched.loc[0, "prefecture"] == "愛知県"
    assert enriched.loc[0, "coordinate_notes"] == "row_correction|user_verified_address"
    assert enriched.loc[0, "coordinate_source"] == "address_point"
    assert enriched.loc[0, "lat"] == 35.173


def test_enrich_commercial_facility_coordinates_applies_corrected_open_month() -> None:
    commercial = pd.DataFrame(
        [
            {
                "page": 5,
                "column": "right",
                "store_area_sqm": 5535.0,
                "open_date_raw": "2008年",
                "open_year": "",
                "open_month": "",
                "name": "稲毛オーツパーク",
                "prefecture": "千葉県",
                "municipality": "千葉市",
            }
        ]
    )
    corrections = pd.DataFrame(
        [
            {
                "source_page": 5,
                "source_column": "right",
                "source_store_area_sqm": 5535,
                "source_open_year": "",
                "source_open_month": "",
                "corrected_name": "稲毛オーツパーク",
                "corrected_prefecture": "千葉県",
                "corrected_municipality": "千葉市",
                "corrected_open_year": 2008,
                "corrected_open_month": 1,
                "notes": "pdf_small_mismatch_review",
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        pd.DataFrame(),
        row_corrections_df=corrections,
    )

    assert enriched.loc[0, "open_year"] == "2008"
    assert enriched.loc[0, "open_month"] == "1"
    assert enriched.loc[0, "open_date_raw"] == "2008年1月"
    assert enriched.loc[0, "coordinate_notes"] == "row_correction|pdf_small_mismatch_review"


def test_enrich_commercial_facility_coordinates_matches_numeric_chome_address() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "センチュリープラザ",
                "prefecture": "兵庫県",
                "municipality": "三田市",
                "address": "兵庫県三田市けやき台1丁目10-1",
            }
        ]
    )
    address_points = pd.DataFrame(
        [
            {
                "prefecture": "兵庫県",
                "municipality": "三田市",
                "district_name": "けやき台一丁目",
                "lat": 34.910,
                "lon": 135.190,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(commercial, address_points)

    assert enriched.loc[0, "coordinate_source"] == "address_point"
    assert enriched.loc[0, "lat"] == 34.910


def test_enrich_commercial_facility_coordinates_uses_district_as_municipality() -> None:
    commercial = pd.DataFrame(
        [
            {
                "name": "東京駅一番街",
                "prefecture": "東京都",
                "municipality": "",
                "district": "千代田区",
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
                "lon": 139.767,
            }
        ]
    )

    enriched = enrich_commercial_facility_coordinates(
        commercial,
        address_points,
        allow_municipality_fallback=True,
    )

    assert enriched.loc[0, "municipality"] == "千代田区"
    assert enriched.loc[0, "coordinate_source"] == "municipality_representative"


def test_build_google_maps_search_url_uses_facility_context() -> None:
    query = build_google_maps_search_query(
        {
            "prefecture": "北海道",
            "municipality": "函館市",
            "name": "函館昭和タウンプラザ",
        }
    )

    assert query == "北海道 函館市 函館昭和タウンプラザ"
    assert (
        build_google_maps_search_url(query)
        == "https://www.google.com/maps/search/?api=1&query="
        "%E5%8C%97%E6%B5%B7%E9%81%93+%E5%87%BD%E9%A4%A8%E5%B8%82+"
        "%E5%87%BD%E9%A4%A8%E6%98%AD%E5%92%8C%E3%82%BF%E3%82%A6%E3%83%B3"
        "%E3%83%97%E3%83%A9%E3%82%B6"
    )


def test_build_google_maps_search_query_omits_unreliable_prefecture() -> None:
    query = build_google_maps_search_query(
        {
            "prefecture": "三重県",
            "name": "グラッチェタウン西尾",
            "parse_warnings": "municipality_missing",
        }
    )

    assert query == "グラッチェタウン西尾"
