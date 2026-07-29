from src.preprocess.enrich_cinemas import (
    enrich,
    match_jcsc,
    match_osm,
    normalize_name,
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
