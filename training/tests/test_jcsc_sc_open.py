from __future__ import annotations

import csv

from collect.jcsc_sc_open import (
    SC_OPEN_LIST_URL,
    fetch_sc_open_data,
    parse_store_area,
    resolve_year_url,
    write_combined_csv,
)

SAMPLE_HTML = """
<html>
  <body>
    <p>2026年6月のオープンSC数：3SC</p>
    <p>2026年オープンSC総数：17SC</p>
    <a href="/sc_data/sc_open/sc_list2025">2025年(一覧表)</a>
    <table>
      <tr>
        <th>No</th>
        <th>オープン日</th>
        <th>SC名</th>
        <th>所在地</th>
        <th>ディベロッパー</th>
        <th>店舗面積(㎡)</th>
        <th>キーテナント名</th>
        <th>テナント数(店)</th>
      </tr>
      <tr>
        <td>1</td>
        <td>1月（注1）</td>
        <td>フォレストスクエア仙川</td>
        <td>東京都調布市仙川町3-1-17</td>
        <td>㈱カワタケ、㈱三越伊勢丹（注2）</td>
        <td>約2,879.45</td>
        <td>–</td>
        <td>18</td>
      </tr>
      <tr>
        <td>2</td>
        <td>3月7日</td>
        <td>テストSC</td>
        <td>大阪府大阪市北区梅田1-1-1</td>
        <td>三井不動産㈱</td>
        <td>約53,960 ★</td>
        <td>ゆめマート、無印良品</td>
        <td>10（注6）</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_fetch_sc_open_data_normalizes_rows() -> None:
    payload = fetch_sc_open_data(
        target_year=2026,
        source_url=SC_OPEN_LIST_URL,
        html=SAMPLE_HTML,
    )

    assert payload["summary"]["yearly_open_count"] == 17
    assert len(payload["items"]) == 2
    first = payload["items"][0]
    assert first["open_month"] == 1
    assert first["open_day"] is None
    assert first["open_date"] is None
    assert first["prefecture"] == "東京都"
    assert first["city"] == "調布市"
    assert first["developers"] == ["カワタケ", "三越伊勢丹"]
    assert first["store_area_sqm"] == 2879.45
    assert first["key_tenants"] == []
    assert first["tenant_count"] == 18
    assert first["notes"] == ["注1", "注2"]
    assert "note_detected" in first["warnings"]

    second = payload["items"][1]
    assert second["open_date"] == "2026-03-07"
    assert second["city"] == "大阪市"
    assert second["store_area_sqm"] == 53960.0
    assert second["store_area_type"] == "gross_leasable_area"
    assert second["key_tenants"] == ["ゆめマート", "無印良品"]
    assert second["tenant_count"] == 10


def test_resolve_year_url_uses_link_or_current_page() -> None:
    assert (
        resolve_year_url(2025, SAMPLE_HTML)
        == "https://www.jcsc.or.jp/sc_data/sc_open/sc_list2025"
    )
    assert resolve_year_url(2026, SAMPLE_HTML) == SC_OPEN_LIST_URL


def test_parse_store_area_detects_area_type() -> None:
    assert parse_store_area("約20,550") == (20550.0, "store_area")
    assert parse_store_area("約53,960 ★") == (53960.0, "gross_leasable_area")
    assert parse_store_area("6,024.4 ◇") == (6024.4, "large_scale_retail_store_area")


def test_write_combined_csv_flattens_items(tmp_path) -> None:
    payload = fetch_sc_open_data(
        target_year=2026,
        source_url=SC_OPEN_LIST_URL,
        html=SAMPLE_HTML,
    )
    output = write_combined_csv([payload], tmp_path / "jcsc_sc_open.csv")

    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 2
    assert rows[0]["source"] == "jcsc"
    assert rows[0]["target_year"] == "2026"
    assert rows[0]["name"] == "フォレストスクエア仙川"
    assert rows[0]["developers"] == "カワタケ|三越伊勢丹"
    assert rows[0]["notes"] == "注1|注2"
    assert rows[1]["key_tenants"] == "ゆめマート|無印良品"
