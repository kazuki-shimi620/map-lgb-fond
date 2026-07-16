from __future__ import annotations

from collect.jcsc_sc_pdf import (
    PAGE_AUDIT_FIELDNAMES,
    OcrToken,
    SideState,
    diff_new_candidates,
    facility_match_key,
    infer_prefectures_from_municipality,
    load_municipality_prefecture_map,
    parse_page_tokens,
    parse_store_area_sqm,
)


def token(text: str, x: float, y: float, confidence: float = 1.0) -> OcrToken:
    return OcrToken(text=text, confidence=confidence, x=x, y=y, width=0.02, height=0.01)


def test_parse_page_tokens_extracts_left_and_right_rows() -> None:
    tokens = [
        token("北海道", 0.22, 0.84),
        token("札幌市", 0.09, 0.805),
        token("中央区", 0.09, 0.795),
        token("札幌PARCO", 0.14, 0.795),
        token("14,000", 0.36, 0.795),
        token("1975年8月", 0.43, 0.795),
        token("小樽市", 0.52, 0.846),
        token("長崎屋小樽店、ドン・キホーテ小樽店", 0.57, 0.846),
        token("12.150", 0.79, 0.846),
        token("1975年4月", 0.86, 0.846),
    ]

    rows, prefecture = parse_page_tokens(
        tokens=tokens,
        page=1,
        source_url="https://example.test/source.pdf",
        initial_prefecture="",
        states={"left": SideState(), "right": SideState()},
    )

    assert prefecture == "北海道"
    assert len(rows) == 2
    left = next(row for row in rows if row["name"] == "札幌PARCO")
    right = next(row for row in rows if row["name"] == "長崎屋小樽店、ドン・キホーテ小樽店")
    assert left["prefecture"] == "北海道"
    assert left["municipality"] == "札幌市"
    assert left["district"] == "中央区"
    assert left["name"] == "札幌PARCO"
    assert left["store_area_sqm"] == 14000.0
    assert left["open_year"] == 1975
    assert left["open_month"] == 8
    assert right["municipality"] == "小樽市"
    assert right["store_area_sqm"] == 12150.0


def test_parse_page_tokens_joins_wrapped_name() -> None:
    tokens = [
        token("ショッピングセンターア・モール", 0.57, 0.824),
        token("（豊岡ショッピングセンター）", 0.57, 0.812),
        token("15.857", 0.79, 0.812),
        token("1983年5月", 0.86, 0.812),
    ]

    rows, _prefecture = parse_page_tokens(
        tokens=tokens,
        page=1,
        source_url="https://example.test/source.pdf",
        initial_prefecture="北海道",
        states={"left": SideState(), "right": SideState(municipality="旭川市")},
    )

    assert len(rows) == 1
    assert rows[0]["name"] == "ショッピングセンターア・モール (豊岡ショッピングセンター)"
    assert rows[0]["municipality"] == "旭川市"
    assert rows[0]["store_area_sqm"] == 15857.0


def test_parse_page_tokens_splits_location_and_name_token() -> None:
    tokens = [
        token("新ひだか町イオン静内店", 0.52, 0.846),
        token("16,356", 0.79, 0.846),
        token("1978年11月", 0.86, 0.846),
    ]

    rows, _prefecture = parse_page_tokens(
        tokens=tokens,
        page=1,
        source_url="https://example.test/source.pdf",
        initial_prefecture="北海道",
        states={"left": SideState(), "right": SideState()},
    )

    assert len(rows) == 1
    assert rows[0]["municipality"] == "新ひだか町"
    assert rows[0]["name"] == "イオン静内店"
    assert rows[0]["parse_warnings"] == ""


def test_parse_page_tokens_keeps_row_when_area_is_missing() -> None:
    tokens = [
        token("平塚市", 0.09, 0.612),
        token("ラスカ平塚", 0.14, 0.612),
        token("1973年6月", 0.43, 0.612),
    ]

    rows, _prefecture = parse_page_tokens(
        tokens=tokens,
        page=10,
        source_url="https://example.test/source.pdf",
        initial_prefecture="神奈川県",
        states={"left": SideState(), "right": SideState()},
    )

    assert len(rows) == 1
    assert rows[0]["municipality"] == "平塚市"
    assert rows[0]["name"] == "ラスカ平塚"
    assert rows[0]["store_area_sqm"] == ""
    assert rows[0]["open_year"] == 1973
    assert rows[0]["open_month"] == 6
    assert rows[0]["parse_warnings"] == "area_missing"


def test_parse_page_tokens_splits_area_attached_to_name() -> None:
    tokens = [
        token("矢巾町", 0.52, 0.767),
        token("矢巾ショッピングセンター・ショッピングモールアルコ 12,272", 0.57, 0.767),
        token("1997年3月", 0.86, 0.767),
    ]

    rows, _prefecture = parse_page_tokens(
        tokens=tokens,
        page=2,
        source_url="https://example.test/source.pdf",
        initial_prefecture="岩手県",
        states={"left": SideState(), "right": SideState()},
    )

    assert len(rows) == 1
    assert rows[0]["municipality"] == "矢巾町"
    assert rows[0]["name"] == "矢巾ショッピングセンター・ショッピングモールアルコ"
    assert rows[0]["store_area_sqm"] == 12272.0
    assert rows[0]["parse_warnings"] == ""


def test_parse_page_tokens_missing_area_row_does_not_pollute_wrapped_name() -> None:
    tokens = [
        token("リヴィンよこすか", 0.14, 0.667),
        token("2000年9月", 0.43, 0.667),
        token("ショッピングセンターア・モール", 0.14, 0.656),
        token("（豊岡ショッピングセンター）", 0.14, 0.645),
        token("15.857", 0.36, 0.645),
        token("1983年5月", 0.43, 0.645),
    ]

    rows, _prefecture = parse_page_tokens(
        tokens=tokens,
        page=10,
        source_url="https://example.test/source.pdf",
        initial_prefecture="神奈川県",
        states={"left": SideState(municipality="横須賀市"), "right": SideState()},
    )

    assert len(rows) == 2
    names = [row["name"] for row in rows]
    assert names == [
        "ショッピングセンターア・モール (豊岡ショッピングセンター)",
        "リヴィンよこすか",
    ]
    assert rows[0]["store_area_sqm"] == 15857.0
    assert rows[1]["store_area_sqm"] == ""


def test_parse_store_area_sqm_handles_ocr_decimal_separator() -> None:
    assert parse_store_area_sqm("15.947") == 15947.0
    assert parse_store_area_sqm("15,947") == 15947.0
    assert parse_store_area_sqm("2879.45") == 2879.45


def test_facility_match_key_normalizes_name() -> None:
    assert (
        facility_match_key(prefecture="東京都", name="（仮称）テスト・モール")
        == "東京都|仮称テストモール"
    )


def test_diff_new_candidates_uses_existing_facility_keys(tmp_path) -> None:
    existing_csv = tmp_path / "existing.csv"
    existing_csv.write_text(
        "prefecture,name\n東京都,テストモール\n",
        encoding="utf-8",
    )
    rows = [
        {"prefecture": "東京都", "name": "テスト・モール"},
        {"prefecture": "東京都", "name": "新規SC"},
    ]

    candidates = diff_new_candidates(rows, existing_csv)

    assert candidates == [{"prefecture": "東京都", "name": "新規SC", "match_key": "東京都|新規sc"}]


def test_infer_prefectures_from_municipality_adds_review_warning(tmp_path) -> None:
    address_csv = tmp_path / "town_points.csv"
    address_csv.write_text(
        "prefecture,municipality,district_name,sub_district_name,lat,lon,source\n"
        "埼玉県,さいたま市大宮区,大門町一丁目,,35.906,139.624,test\n",
        encoding="utf-8",
    )
    mapping = load_municipality_prefecture_map(address_csv)
    rows = [
        {
            "prefecture": "栃木県",
            "municipality": "さいたま市",
            "district": "大宮区",
            "parse_warnings": "",
        }
    ]

    inferred = infer_prefectures_from_municipality(rows, mapping)

    assert inferred[0]["prefecture"] == "埼玉県"
    assert inferred[0]["parse_warnings"] == "prefecture_inferred_from_municipality"


def test_page_audit_fieldnames_include_comparison_columns() -> None:
    assert PAGE_AUDIT_FIELDNAMES == [
        "page",
        "extracted_rows",
        "open_date_rows",
        "ocr_year_char_count",
        "ocr_month_char_count",
        "ocr_open_date_like_count",
        "row_minus_year_chars",
        "row_minus_month_chars",
        "row_minus_open_date_like",
        "audit_warning",
    ]
