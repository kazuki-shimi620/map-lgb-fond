from src.collect.cinema_chains import (
    parse_109_text,
    parse_aeon,
    parse_smt,
    parse_sunshine,
    parse_tjoy,
    parse_toho,
    parse_united,
)


def test_parse_aeon_deduplicates_theater_id() -> None:
    html = """
    <h2 class="c-area__name">北海道</h2>
    <a class="c-area__theater" data-theater-id="81005" data-theater-name="ebetsu">
      <h3>江別</h3>
    </a>
    <a data-theater-id="81005" data-theater-name="ebetsu"><h3>江別</h3></a>
    <h2 class="c-area__name">青森県</h2>
    <a data-theater-id="82001" data-theater-name="hirosaki"><h3>弘前</h3></a>
    """
    rows = parse_aeon(html, "2026-07-28")
    assert len(rows) == 2
    assert rows[0]["cinema_id"] == "aeon:81005"
    assert rows[0]["name"] == "イオンシネマ江別"
    assert rows[0]["prefecture"] == "北海道"
    assert rows[1]["prefecture"] == "青森県"


def test_parse_toho_uses_prefecture_and_detail_url() -> None:
    html = """
    <section class="theater-list-area">
      <h4 class="h4">北海道<br><span>HOKKAIDO</span></h4>
      <a href="/net/schedule/089/TNPI2000J01.do"><span>
        TOHOシネマズ すすきの<br><span>TOHO CINEMAS SUSUKINO</span>
      </span></a>
    </section>
    """
    rows = parse_toho(html, "2026-07-28")
    assert rows[0]["cinema_id"] == "toho:089"
    assert rows[0]["name"] == "TOHOシネマズ すすきの"
    assert rows[0]["prefecture"] == "北海道"
    assert "/net/schedule/089/" in rows[0]["source_url"]


def test_parse_united_extracts_facility_details() -> None:
    html = """
    <div class="theaterBox">
      <h5>ローソン・ユナイテッドシネマ札幌</h5>
      <dl class="info">
        <dt>住所</dt><dd>〒060-0031 北海道札幌市中央区北1条東4丁目1-1<br>
        サッポロファクトリー1条館 内</dd>
        <dt>スクリーン数</dt><dd>11</dd>
        <dt>総収容人数</dt><dd>2,356</dd>
        <dt><a href="/sapporo/">劇場ホームページはこちら</a></dt>
      </dl>
    </div>
    """
    rows = parse_united(html, "2026-07-28")
    assert rows[0]["prefecture"] == "北海道"
    assert rows[0]["municipality"] == "札幌市"
    assert rows[0]["mall_name"] == "サッポロファクトリー1条館"
    assert rows[0]["screen_count"] == "11"
    assert rows[0]["seat_count"] == "2356"


def test_parse_united_excludes_closed_theater() -> None:
    html = """
    <div class="theaterBox"><h5>閉館館</h5><dl class="info">
      <p>2026年5月31日に閉館いたしました。</p>
    </dl></div>
    """
    assert parse_united(html, "2026-07-28") == []


def test_parse_smt_includes_operated_and_partner_theaters() -> None:
    html = """
    <li id="theaterCode_1017"><a href="/site/sendai/">MOVIX仙台</a></li>
    <li><a href="http://www.parkscinema.com/" target="_blank">
      なんばパークスシネマ
    </a></li>
    """
    rows = parse_smt(html, "2026-07-28")
    assert [(row["name"], row["prefecture"]) for row in rows] == [
        ("MOVIX仙台", "宮城県"),
        ("なんばパークスシネマ", "大阪府"),
    ]


def test_parse_tjoy_carries_rowspan_prefecture() -> None:
    html = """
    <tr><td rowspan="2" class="pref">新潟<span>Niigata</span></td>
    <td><a href="https://tjoy.jp/t-joy_niigatabandai/mypage">
    T・ジョイ新潟万代<span>English</span></a></td></tr>
    <tr><td><a href="https://tjoy.jp/t-joy_nagaoka/mypage">
    T・ジョイ長岡<span>English</span></a></td></tr>
    """
    rows = parse_tjoy(html, "2026-07-28")
    assert len(rows) == 2
    assert {row["prefecture"] for row in rows} == {"新潟県"}


def test_parse_sunshine_adds_chain_name() -> None:
    html = """
    <a href="/theater/heiwajima/" class="link button">平和島</a>
    <a href="/theater/tomakomai/" class="link button">
    ディノスシネマズ 苫小牧</a>
    """
    rows = parse_sunshine(html, "2026-07-28")
    assert rows[0]["name"] == "シネマサンシャイン平和島"
    assert rows[0]["prefecture"] == "東京都"
    assert rows[1]["name"] == "ディノスシネマズ 苫小牧"


def test_parse_109_text_extracts_large_theater_details() -> None:
    text = """
    １０９シネマズ所在地
    地区 劇場名 SC数 座席数 導入設備 住所
    東北 １０９シネマズ富谷 10 1,793 宮城県富谷市大清水1-33-1 イオンモール富谷別棟
    東京都世田谷区玉川1-14-1
    １０９シネマズ二子玉川 10 1,665
    二子玉川ライズ・ショッピングセンター・テラスマーケット内
    """
    rows = parse_109_text(text, "2026-07-28")
    assert len(rows) == 2
    assert rows[0]["screen_count"] == "10"
    assert rows[0]["seat_count"] == "1793"
    assert rows[1]["prefecture"] == "東京都"
    assert "テラスマーケット内" in rows[1]["address"]
