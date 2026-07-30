from pathlib import Path

from src.collect.cinema_coordinates import (
    address_locality,
    build_url,
    cache_path,
    normalize_place_query,
    normalize_prefecture,
    place_name_from_address,
    select_candidate,
)


def test_select_candidate_requires_matching_prefecture() -> None:
    row = {"prefecture": " 埼玉県 ", "address": "埼玉県さいたま市浦和区東高砂町"}
    candidates = [
        {"display_name": "千葉県千葉市", "lat": "35.0", "lon": "140.0"},
        {"display_name": "埼玉県川越市", "lat": "35.9", "lon": "139.5"},
        {"display_name": "埼玉県さいたま市", "lat": "35.8", "lon": "139.6"},
    ]
    assert select_candidate(row, candidates) is candidates[2]


def test_url_and_cache_path_are_stable() -> None:
    assert "countrycodes=jp" in build_url("東京都千代田区")
    assert cache_path(Path("raw"), "cinema:1", "query") == cache_path(
        Path("raw"), "cinema:1", "query"
    )
    assert cache_path(Path("raw"), "cinema:1", "query") != cache_path(
        Path("raw"), "cinema:1", "other"
    )
    assert normalize_prefecture(" 神奈川県 ") == "神奈川県"
    assert address_locality("〒330-0055 埼玉県さいたま市浦和区東高砂町") == "さいたま市"
    assert address_locality("東京都練馬区練馬4-15-20") == "練馬区"
    assert address_locality("宮城県柴田郡大河原町字小島") == "大河原町"
    assert (
        place_name_from_address("大阪府吹田市千里万博公園2-1 EXPOCITY内")
        == "EXPOCITY"
    )
    assert (
        place_name_from_address("神奈川県藤沢市辻堂神台１-3-1 Terrace Mall湘南4F")
        == "Terrace Mall湘南"
    )
    assert normalize_place_query("Terrace Mall 湘南") == "テラスモール湘南"
    assert normalize_place_query("メッセ・アミューズ・モール") == "メッセアミューズモール"
