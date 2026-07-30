from src.preprocess.enrich_cinemas import (
    enrich,
    match_jcsc,
    match_manual,
    match_osm,
    normalize_name,
    review_priority_reason,
    venue_key,
)


def test_name_normalization_and_brand_removal() -> None:
    assert normalize_name("ＴＯＨＯシネマズ・新宿") == "tohoシネマズ新宿"
    assert venue_key("TOHOシネマズ 新宿") == "新宿"


def test_match_osm_accepts_same_venue_with_brand_variant() -> None:
    cinema = {"name": "ローソン・ユナイテッドシネマ札幌", "prefecture": "北海道"}
    osm = [
        {
            "id": "osm_node_1",
            "category_id": "cinema",
            "name": "ユナイテッド・シネマ札幌",
            "prefecture": "北海道",
            "lat": "43.0",
            "lon": "141.0",
        }
    ]
    matched, score = match_osm(cinema, osm)
    assert matched is osm[0]
    assert score == 0.99


def test_match_osm_ignores_prefecture_whitespace() -> None:
    cinema = {
        "name": "シネプレックス幸手",
        "prefecture": " 埼玉県",
    }
    osm = [
        {
            "id": "osm_node_1",
            "category_id": "cinema",
            "name": "シネプレックス幸手",
            "prefecture": "埼玉県",
        }
    ]
    matched, score = match_osm(cinema, osm)
    assert matched is osm[0]
    assert score == 1.0


def test_match_osm_accepts_unique_long_location_containment() -> None:
    cinema = {"name": "イオンシネマシアタス調布", "prefecture": "東京都"}
    osm = [
        {
            "id": "osm_node_1",
            "category_id": "cinema",
            "name": "トリエC館 イオンシネマシアタス調布",
            "prefecture": "",
        }
    ]
    matched, score = match_osm(cinema, osm)
    assert matched is osm[0]
    assert score == 0.97


def test_enrich_does_not_accept_ambiguous_fuzzy_match() -> None:
    cinema = {"cinema_id": "x", "name": "イオンシネマ浦和", "prefecture": "埼玉県"}
    osm = [
        {"id": "1", "category_id": "cinema", "name": "浦和館", "prefecture": "埼玉県"},
        {"id": "2", "category_id": "cinema", "name": "浦和座", "prefecture": "埼玉県"},
    ]
    enriched, review = enrich([cinema], osm, [])
    assert enriched[0].get("coordinate_source", "") == ""
    assert len(review) == 1


def test_match_jcsc_rejects_town_representative_coordinate() -> None:
    cinema = {
        "name": "イオンシネマむさし村山",
        "mall_name": "",
        "prefecture": "東京都",
    }
    jcsc = [
        {
            "name": "イオンモールむさし村山",
            "prefecture": "東京都",
            "lat": "35.7",
            "lon": "139.4",
            "coordinate_source": "address_point",
        }
    ]
    assert match_jcsc(cinema, jcsc) is None


def test_match_jcsc_accepts_unique_facility_name_in_official_address() -> None:
    cinema = {
        "name": "109シネマズ四日市",
        "mall_name": "",
        "prefecture": "三重県",
        "address": "三重県四日市市安島1-3-31 トナリエ四日市6F",
    }
    jcsc = [
        {
            "name": "トナリエ四日市",
            "prefecture": "三重県",
            "lat": "34.9688",
            "lon": "136.6167",
            "coordinate_source": "manual:google_maps_name_search",
        }
    ]
    assert match_jcsc(cinema, jcsc) is jcsc[0]


def test_match_jcsc_treats_duplicate_source_rows_as_one_facility() -> None:
    cinema = {
        "name": "109シネマズグランベリーパーク",
        "prefecture": "東京都",
        "address": "東京都町田市鶴間3-4-1 グランベリーパーク内",
    }
    jcsc = [
        {
            "name": "グランベリーパーク",
            "prefecture": "東京都",
            "lat": "35.51",
            "lon": "139.47",
            "coordinate_source": "manual:source_a",
        },
        {
            "name": "グランベリーパーク",
            "prefecture": "東京都",
            "lat": "35.51",
            "lon": "139.47",
            "coordinate_source": "manual:source_b",
        },
    ]
    assert match_jcsc(cinema, jcsc) is jcsc[0]


def test_review_priority_reason_selects_large_or_mall_cinema() -> None:
    assert (
        review_priority_reason({"screen_count": "9", "mall_name": "テストモール"})
        == "9スクリーン・大型商業施設併設候補"
    )
    assert review_priority_reason({"screen_count": "4", "mall_name": ""}) == ""
    assert review_priority_reason({"screen_count": "不明", "mall_name": "テストモール"}) == (
        "大型商業施設併設候補"
    )


def test_match_manual_uses_cinema_id_and_coordinates() -> None:
    cinema = {"cinema_id": "cinema:1"}
    manual = [
        {"cinema_id": "cinema:1", "lat": "35.0", "lon": "139.0"},
        {"cinema_id": "cinema:2", "lat": "36.0", "lon": "140.0"},
    ]
    assert match_manual(cinema, manual) is manual[0]
