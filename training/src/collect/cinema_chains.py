from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
import unicodedata
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

SOURCES = {
    "aeon": ("イオンシネマ", "https://www.aeoncinema.com/theater/index.html"),
    "toho": ("TOHOシネマズ", "https://www.tohotheater.jp/theater/find.html"),
    "united": (
        "ローソン・ユナイテッドシネマ",
        "https://www.unitedcinemas.jp/about_company/uc_theater_list.html",
    ),
    "smt": (
        "松竹マルチプレックスシアターズ",
        "https://www.smt-cinema.com/assets/module/page_theater_list_partner.html",
    ),
    "tjoy": ("T・ジョイ", "https://tjoy.jp/mypagelist/"),
    "sunshine": ("シネマサンシャイン", "https://www.cinemasunshine.co.jp/areas/"),
    "109": (
        "109シネマズ",
        "https://109cinemas.net/service/theatrepromotion/mediaguide.pdf",
    ),
}
RAW_SUFFIXES = {"109": ".pdf"}
FIELDNAMES = [
    "cinema_id",
    "name",
    "operator",
    "prefecture",
    "municipality",
    "address",
    "mall_name",
    "screen_count",
    "seat_count",
    "lat",
    "lon",
    "coordinate_source",
    "source_url",
    "confirmed_at",
]


def decode_html(payload: bytes) -> str:
    for encoding in ("utf-8", "cp932"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            pass
    return payload.decode("utf-8", errors="replace")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def strip_tags(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " ", value, flags=re.IGNORECASE)
    return clean_text(re.sub(r"<[^>]+>", "", value))


def municipality_from_address(address: str, prefecture: str) -> str:
    value = re.sub(r"^〒\d{3}-\d{4}\s*", "", address)
    if prefecture and value.startswith(prefecture):
        value = value[len(prefecture) :]
    match = re.match(r"(.+?[市区町村])", value)
    return match.group(1) if match else ""


def normalize_prefecture(value: str) -> str:
    value = value.strip()
    if value == "東京":
        return "東京都"
    if value in {"京都", "大阪"}:
        return f"{value}府"
    if value == "北海道" or value.endswith(("都", "府", "県")):
        return value
    return f"{value}県" if value else ""


def cinema_id(operator_key: str, value: str) -> str:
    normalized = re.sub(r"[^0-9a-z]+", "-", value.lower()).strip("-")
    return f"{operator_key}:{normalized}"


class _AeonParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.prefecture = ""
        self.capture_prefecture = False
        self.capture_name = False
        self.current: dict[str, str] | None = None
        self.rows: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "h2" and "c-area__name" in classes:
            self.prefecture = ""
            self.capture_prefecture = True
        if tag == "a" and values.get("data-theater-id"):
            self.current = {
                "id": values["data-theater-id"] or "",
                "slug": values.get("data-theater-name") or "",
                "prefecture": self.prefecture,
                "name": "",
            }
        if tag == "h3" and self.current is not None:
            self.capture_name = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self.capture_prefecture = False
        if tag == "h3" and self.current is not None:
            self.capture_name = False
            if self.current["name"]:
                self.rows.append(self.current)
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.capture_prefecture:
            self.prefecture += clean_text(data)
        if self.capture_name and self.current is not None:
            self.current["name"] += clean_text(data)


def parse_aeon(text: str, confirmed_at: str) -> list[dict[str, str]]:
    parser = _AeonParser()
    parser.feed(text)
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in parser.rows:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        rows.append(
            base_row(
                cinema_id=f"aeon:{item['id']}",
                name=f"イオンシネマ{item['name']}",
                operator=SOURCES["aeon"][0],
                prefecture=normalize_prefecture(item["prefecture"]),
                source_url=SOURCES["aeon"][1],
                confirmed_at=confirmed_at,
            )
        )
    return rows


def parse_toho(text: str, confirmed_at: str) -> list[dict[str, str]]:
    candidates: list[tuple[str, str, str, str]] = []
    sections = re.findall(
        r'<section class="theater-list-area">(.*?)</section>', text, re.DOTALL
    )
    for section in sections:
        pref_match = re.search(r'<h4[^>]*>(.*?)<br', section, re.DOTALL)
        prefecture = strip_tags(pref_match.group(1)) if pref_match else ""
        for match in re.finditer(
            r'<a href="([^"]*/net/schedule/(\d+)/[^"]*)"><span>(.*?)<br',
            section,
            re.DOTALL,
        ):
            href, theater_id, raw_name = match.groups()
            candidates.append(
                (theater_id, strip_tags(raw_name), prefecture, urljoin(SOURCES["toho"][1], href))
            )
    candidates = list(dict.fromkeys(candidates))
    id_counts: dict[str, int] = {}
    for theater_id, *_ in candidates:
        id_counts[theater_id] = id_counts.get(theater_id, 0) + 1
    rows: list[dict[str, str]] = []
    for theater_id, name, prefecture, source_url in candidates:
        suffix = ""
        if id_counts[theater_id] > 1:
            suffix = ":" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        rows.append(
            base_row(
                cinema_id=f"toho:{theater_id}{suffix}",
                name=name,
                operator=SOURCES["toho"][0],
                prefecture=prefecture,
                source_url=source_url,
                confirmed_at=confirmed_at,
            )
        )
    return rows


def parse_united(text: str, confirmed_at: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    blocks = re.findall(
        r'<div class="theaterBox"[^>]*>(.*?)</dl>\s*</div>', text, re.DOTALL
    )
    for block in blocks:
        if "閉館いたしました" in block:
            continue
        name_match = re.search(r"<h5>(.*?)</h5>", block, re.DOTALL)
        address_match = re.search(r"<dt>住所</dt>\s*<dd>(.*?)</dd>", block, re.DOTALL)
        screen_match = re.search(
            r"<dt>スクリーン数</dt>\s*<dd>\s*([\d,]+)", block, re.DOTALL
        )
        seat_match = re.search(
            r"<dt>総収容人数</dt>\s*<dd>\s*([\d,]+)", block, re.DOTALL
        )
        link_match = re.search(
            r'<a href="([^"]+)"[^>]*>劇場ホームページはこちら</a>', block
        )
        if not name_match:
            continue
        name = strip_tags(name_match.group(1))
        address_html = address_match.group(1) if address_match else ""
        address = strip_tags(address_html)
        pref_match = re.search(r"(北海道|東京都|大阪府|京都府|.{2,3}県)", address)
        prefecture = normalize_prefecture(pref_match.group(1) if pref_match else "")
        mall_parts = re.split(r"<br\s*/?>", address_html, flags=re.IGNORECASE)
        mall_match = re.search(r"(.+?)\s*内\s*$", strip_tags(mall_parts[-1]))
        mall_name = mall_match.group(1).strip() if len(mall_parts) > 1 and mall_match else ""
        detail_url = (
            urljoin(SOURCES["united"][1], link_match.group(1))
            if link_match
            else SOURCES["united"][1]
        )
        rows.append(
            base_row(
                cinema_id=cinema_id("united", detail_url.rstrip("/").split("/")[-1] or name),
                name=name,
                operator=SOURCES["united"][0],
                prefecture=prefecture,
                municipality=municipality_from_address(address, prefecture),
                address=address,
                mall_name=mall_name,
                screen_count=(screen_match.group(1).replace(",", "") if screen_match else ""),
                seat_count=(seat_match.group(1).replace(",", "") if seat_match else ""),
                source_url=detail_url,
                confirmed_at=confirmed_at,
            )
        )
    return rows


SMT_PREFECTURES = {
    "sendai": "宮城県",
    "marunouchi": "東京都",
    "shinjuku": "東京都",
    "togeki": "東京都",
    "tsukuba": "茨城県",
    "utsunomiya": "栃木県",
    "isesaki": "群馬県",
    "saitama": "埼玉県",
    "kawaguchi": "埼玉県",
    "kashiwanoha": "千葉県",
    "kameari": "東京都",
    "akishima": "東京都",
    "hashimoto": "神奈川県",
    "shimizu": "静岡県",
    "miyoshi": "愛知県",
    "yao": "大阪府",
    "amagasaki": "兵庫県",
    "kyoto": "京都府",
    "kurashiki": "岡山県",
    "hiezu": "鳥取県",
    "hiroshima": "広島県",
    "shunan": "山口県",
    "kumamoto": "熊本県",
}
SMT_PARTNER_PREFECTURES = {
    "osakastationcitycinema.com": "大阪府",
    "parkscinema.com": "大阪府",
}


def parse_smt(text: str, confirmed_at: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for match in re.finditer(
        r'<a href="([^"]+)"[^>]*>(.*?)</a>', text, flags=re.DOTALL | re.IGNORECASE
    ):
        href, raw_name = match.groups()
        name = strip_tags(raw_name)
        slug_match = re.search(r"/site/([^/]+)/", href)
        if slug_match:
            slug = slug_match.group(1)
            prefecture = SMT_PREFECTURES.get(slug, "")
        else:
            domain_match = re.search(r"https?://(?:www\.)?([^/]+)/", href)
            domain = domain_match.group(1) if domain_match else ""
            if domain not in SMT_PARTNER_PREFECTURES:
                continue
            slug = domain.split(".")[0]
            prefecture = SMT_PARTNER_PREFECTURES[domain]
        rows.append(
            base_row(
                cinema_id=f"smt:{slug}",
                name=name,
                operator=SOURCES["smt"][0],
                prefecture=prefecture,
                source_url=urljoin(SOURCES["smt"][1], href),
                confirmed_at=confirmed_at,
            )
        )
    return rows


def parse_tjoy(text: str, confirmed_at: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    prefecture = ""
    for block in re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.DOTALL | re.IGNORECASE):
        pref_match = re.search(r'<td[^>]*class="pref"[^>]*>(.*?)<span', block, re.DOTALL)
        if pref_match:
            prefecture = normalize_prefecture(strip_tags(pref_match.group(1)))
        theater_match = re.search(
            r'<a href="(https://tjoy\.jp/([^/]+)/mypage)"[^>]*>(.*?)<span',
            block,
            re.DOTALL,
        )
        if not theater_match:
            continue
        url, slug, raw_name = theater_match.groups()
        rows.append(
            base_row(
                cinema_id=f"tjoy:{slug}",
                name=strip_tags(raw_name),
                operator=SOURCES["tjoy"][0],
                prefecture=prefecture,
                source_url=url,
                confirmed_at=confirmed_at,
            )
        )
    return rows


SUNSHINE_PREFECTURES = {
    "gdcs": "東京都",
    "heiwajima": "東京都",
    "yukarigaoka": "千葉県",
    "misato": "埼玉県",
    "tsuchiura": "茨城県",
    "lalaportnumazu": "静岡県",
    "kahoku": "石川県",
    "yamatokoriyama": "奈良県",
    "shimonoseki": "山口県",
    "kinuyama": "愛媛県",
    "shigenobu": "愛媛県",
    "masaki": "愛媛県",
    "kitajima": "徳島県",
    "iizuka": "福岡県",
    "aira": "鹿児島県",
    "tomakomai": "北海道",
    "muroran": "北海道",
}


def parse_sunshine(text: str, confirmed_at: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for match in re.finditer(
        r'<a href="/theater/([^/]+)/"[^>]*>(.*?)</a>', text, re.DOTALL
    ):
        slug, raw_name = match.groups()
        name = strip_tags(raw_name)
        if not name.startswith(("グランドシネマサンシャイン", "ディノスシネマズ")):
            name = f"シネマサンシャイン{name}"
        rows.append(
            base_row(
                cinema_id=f"sunshine:{slug}",
                name=name,
                operator=SOURCES["sunshine"][0],
                prefecture=SUNSHINE_PREFECTURES.get(slug, ""),
                source_url=urljoin(SOURCES["sunshine"][1], f"/theater/{slug}/"),
                confirmed_at=confirmed_at,
            )
        )
    return rows


def parse_109_pdf(path: Path, confirmed_at: str) -> list[dict[str, str]]:
    import pdfplumber

    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if "１０９シネマズ所在地" in page_text:
                text = page_text
                break
    return parse_109_text(text, confirmed_at)


def parse_109_text(text: str, confirmed_at: str) -> list[dict[str, str]]:
    lines = [clean_text(line) for line in text.splitlines()]
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(?:(?:東北|関東|東海|関西|中国|九州)\s+)?"
        r"((?:１０９シネマズ|ムービル).+?)\s+(\d+)\s+([\d,]+)(?:\s+(.*))?$"
    )
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        name, screens, seats, trailing = match.groups()
        name = re.sub(r"\s*※.*$", "", name)
        address = trailing or ""
        if not re.search(r"(?:北海道|東京都|大阪府|京都府|.{2,3}県)", address):
            previous = lines[index - 1] if index > 0 else ""
            following = lines[index + 1] if index + 1 < len(lines) else ""
            address = next(
                (
                    value
                    for value in (previous, following)
                    if re.match(r"(?:北海道|東京都|大阪府|京都府|.{2,3}県)", value)
                ),
                address,
            )
            if address == previous and following and not pattern.match(following):
                address = f"{address} {following}"
        pref_match = re.search(r"(北海道|東京都|大阪府|京都府|.{2,3}県)", address)
        prefecture = pref_match.group(1) if pref_match else ""
        rows.append(
            base_row(
                cinema_id=f"109:{hashlib.sha1(name.encode('utf-8')).hexdigest()[:10]}",
                name=unicodedata.normalize("NFKC", name),
                operator=SOURCES["109"][0],
                prefecture=prefecture,
                municipality=municipality_from_address(address, prefecture),
                address=address,
                screen_count=screens,
                seat_count=seats.replace(",", ""),
                source_url=SOURCES["109"][1],
                confirmed_at=confirmed_at,
            )
        )
    return rows


def base_row(**values: str) -> dict[str, str]:
    return {field: values.get(field, "") for field in FIELDNAMES}


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "map-lgb-fond-cinema-collector/0.1"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def collect(raw_dir: Path, output: Path, *, force: bool = False) -> list[dict[str, str]]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    parsers = {
        "aeon": parse_aeon,
        "toho": parse_toho,
        "united": parse_united,
        "smt": parse_smt,
        "tjoy": parse_tjoy,
        "sunshine": parse_sunshine,
    }
    confirmed_at = date.today().isoformat()
    rows: list[dict[str, str]] = []
    for key, (_, url) in SOURCES.items():
        raw_path = raw_dir / f"{key}{RAW_SUFFIXES.get(key, '.html')}"
        if force or not raw_path.exists():
            raw_path.write_bytes(fetch(url))
        if key == "109":
            rows.extend(parse_109_pdf(raw_path, confirmed_at))
        else:
            rows.extend(parsers[key](decode_html(raw_path.read_bytes()), confirmed_at))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="大手映画館チェーンの公式一覧をCSV化")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/cinemas"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/cinemas/official_chain_cinemas.csv"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    rows = collect(args.raw_dir, args.output, force=args.force)
    counts = {
        operator: sum(row["operator"] == operator for row in rows)
        for operator, _ in SOURCES.values()
    }
    print(f"映画館公式一覧: {len(rows)}件 ({counts}) -> {args.output}")


if __name__ == "__main__":
    main()
