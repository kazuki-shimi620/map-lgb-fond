# commercial-facilities.md

# ショッピングセンター開業データ取得・特徴量化仕様

本ドキュメントは、日本ショッピングセンター協会（JCSC）が公開している「オープンSC一覧表」を取得し、学習用の商業施設特徴量へ変換するための仕様を定義する。

---

# 1. 目的

ショッピングセンターの開業情報を中古マンション価格予測の外部特徴量として利用できる形に整備する。

初期段階では、データ取得と正規化JSON生成を優先する。モデル投入時は特徴量候補を比較し、精度改善が確認できるものだけを採用する。

---

# 2. データソース

## 取得元

```text
https://www.jcsc.or.jp/sc_data/sc_open/sc_list
```

## 取得単位

年単位で取得する。

```text
target_year = 2026
```

最新年はベースURLで表示される。過去年はベースURL内の年別リンクからURLを解決する。

2026年7月10日時点でベースURLから解決できる過去年リンクは2015年以降である。
それ以前の年を利用する場合は、別アーカイブや追加データソースの有無を確認してから取得対象に含める。

## 利用制約

* 取得は `training` 側のスクリプトだけで行う。
* ブラウザからJCSCサイトへ直接アクセスしない。
* 取得済みHTMLと正規化JSONをローカルに保存し、再実行時に検証できるようにする。
* ページ構造変更や解析失敗は警告・エラーとして記録する。

---

# 3. 入力IF

## Python関数

```python
def fetch_sc_open_data(
    target_year: int,
    source: str = "jcsc",
    normalize: bool = True,
    include_raw: bool = True,
) -> dict:
    ...
```

## CLI

```bash
training/.venv/bin/python training/src/collect/jcsc_sc_open.py --year 2026
```

複数年取得:

```bash
training/.venv/bin/python training/src/collect/jcsc_sc_open.py --from-year 2005 --to-year 2026
```

## 引数

| name | type | required | description |
| --- | ---: | ---: | --- |
| `target_year` | int | yes | 取得対象年 |
| `source` | str | no | 初期値 `jcsc` |
| `normalize` | bool | no | 正規化するか |
| `include_raw` | bool | no | raw値をJSONに残すか |
| `cache` | bool | no | 正常な既存HTMLがある場合に再取得しない |

---

# 4. 保存先

JCSC由来のraw HTML、正規化JSON、エラーログはGit管理しない。

```text
training/data/raw/jcsc/jcsc_sc_open_2026_raw.html
training/data/processed/jcsc/jcsc_sc_open_2026.json
training/data/processed/jcsc/jcsc_sc_open_2026.csv
training/data/processed/jcsc/jcsc_sc_open.csv
training/data/cache/jcsc/jcsc_sc_open_2026_errors.json
```

`jcsc_sc_open_YYYY.csv` は年別CSV、`jcsc_sc_open.csv` は取得対象年を結合したCSVとする。

ブラウザ推論に必要な集計済み成果物を出す場合だけ `frontend/public` へ配置する。

```text
frontend/public/facilities/
```

---

# 5. JSON出力IF

## 全体構造

```json
{
  "meta": {
    "source": "jcsc",
    "target_year": 2026,
    "source_url": "https://www.jcsc.or.jp/sc_data/sc_open/sc_list",
    "fetched_at": "2026-07-09T23:00:00+09:00",
    "schema_version": "1.0.0",
    "definition_version": "2025_jcsc_standard"
  },
  "summary": {
    "monthly_open_count_raw": "2026年6月のオープンSC数：3SC",
    "yearly_open_count_raw": "2026年オープンSC総数：17SC",
    "yearly_open_count": 17
  },
  "items": [],
  "errors": []
}
```

## itemスキーマ

```json
{
  "no": 1,
  "open_date_raw": "1月（注1）",
  "open_year": 2026,
  "open_month": 1,
  "open_day": null,
  "open_date": null,
  "name": "フォレストスクエア仙川",
  "address_raw": "東京都調布市仙川町3-1-17",
  "prefecture": "東京都",
  "city": "調布市",
  "developer_raw": "㈱カワタケ、㈱三越伊勢丹（注2）",
  "developers": ["カワタケ", "三越伊勢丹"],
  "store_area_raw": "2879.45",
  "store_area_sqm": 2879.45,
  "store_area_type": "store_area",
  "key_tenants_raw": "–",
  "key_tenants": [],
  "tenant_count_raw": "18",
  "tenant_count": 18,
  "notes": ["注1", "注2"],
  "parse_status": "ok",
  "warnings": []
}
```

---

# 6. カラム対応

| 元カラム | JSON field |
| --- | --- |
| No | `no` |
| オープン日 | `open_date_raw` / `open_month` / `open_day` / `open_date` |
| SC名 | `name` |
| 所在地 | `address_raw` / `prefecture` / `city` |
| ディベロッパー | `developer_raw` / `developers` |
| 店舗面積(㎡) | `store_area_raw` / `store_area_sqm` / `store_area_type` |
| キーテナント名 | `key_tenants_raw` / `key_tenants` |
| テナント数(店) | `tenant_count_raw` / `tenant_count` |

---

# 7. URL解決

```python
BASE_URL = "https://www.jcsc.or.jp"
SC_OPEN_LIST_URL = f"{BASE_URL}/sc_data/sc_open/sc_list"
YEAR_LINK_PATTERN = r"(?P<year>20\d{2})年\s*\(一覧表\)"
```

最新年は `SC_OPEN_LIST_URL` を利用する。過去年はページ内リンクテキストから該当年のhrefを探索し、相対URLの場合は `BASE_URL` で絶対URL化する。

---

# 8. 正規化仕様

## 注記

```python
NOTE_PATTERN = r"（?注(?P<num>\d+)）?"
```

注記は `notes` に格納し、対象フィールドのraw値は保持する。

## オープン日

```python
FULL_DATE_PATTERN = r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日"
MONTH_ONLY_PATTERN = r"(?P<month>\d{1,2})月"
```

| raw | open_month | open_day | open_date |
| --- | ---: | ---: | --- |
| `3月7日` | 3 | 7 | `YYYY-03-07` |
| `1月` | 1 | null | null |
| `未定` | null | null | null |
| `春` | null | null | null |

## 店舗面積

```python
AREA_NUMBER_PATTERN = r"(?P<number>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)"
AREA_APPROX_PATTERN = r"約"
AREA_GLA_PATTERN = r"★"
AREA_LARGE_STORE_PATTERN = r"◇"
```

| 記号 | `store_area_type` |
| --- | --- |
| なし | `store_area` |
| `★` | `gross_leasable_area` |
| `◇` | `large_scale_retail_store_area` |

## テナント数

```python
TENANT_COUNT_PATTERN = r"\d+"
```

数値が取れない場合は `tenant_count = null` とし、必要に応じてwarningを付与する。

## 会社名

```python
CORP_MARK_PATTERN = r"㈱|（株）|\(株\)"
COMPANY_SPLIT_PATTERN = r"[、,，]"
```

法人格記号を除去し、読点・カンマで分割する。

## キーテナント

```python
TENANT_SPLIT_PATTERN = r"[、,，]"
EMPTY_VALUE_PATTERN = r"^[-–—ー]+$"
```

空値記号は空配列に変換する。

## 所在地

```python
PREFECTURE_PATTERN = r"^(東京都|北海道|大阪府|京都府|.{2,3}県)"
CITY_PATTERN = r"^(東京都|北海道|大阪府|京都府|.{2,3}県)(?P<city>.+?[市区町村])"
```

緯度経度は初期取得仕様では必須にしない。特徴量化に使う段階で、別途ジオコーディングまたは住所マスタ突合により付与する。

---

# 9. エラーIF

```json
{
  "row_index": 3,
  "raw_row": ["3", "3月7日", "..."],
  "parse_status": "warning",
  "warnings": [
    "column_count_mismatch",
    "store_area_parse_failed"
  ]
}
```

## warnings

| code | 内容 |
| --- | --- |
| `column_count_mismatch` | 期待カラム数と一致しない |
| `open_date_parse_failed` | オープン日の解析失敗 |
| `area_parse_failed` | 店舗面積の解析失敗 |
| `tenant_count_parse_failed` | テナント数の解析失敗 |
| `address_parse_failed` | 所在地の解析失敗 |
| `note_detected` | 注記あり |
| `multiline_cell_detected` | 改行セルあり |

---

# 10. 処理フロー

```text
1. target_yearを受け取る
2. JCSCのオープンSC一覧ページを取得
3. 年別URLを解決
4. HTMLを取得
5. テーブルを抽出
6. 行ごとにrawデータを保持
7. 注記・日付・面積・テナント数を抽出
8. 所在地から都道府県・市区町村を抽出
9. JSONスキーマに変換
10. warnings/errorsを付与
11. JSONとして保存または返却
```

---

# 11. 特徴量化方針

商業施設特徴量は、初期段階では市区町村・都道府県単位の集計特徴量として実装する。

JCSCデータは住所文字列を持つが、緯度経度は持たない。ジオコーディングを挟むと取得コスト、表記ゆれ、失敗時の欠損処理が増えるため、まずは住所から抽出できる市区町村単位の特徴量で効果を確認する。

初期候補:

```text
sc_city_open_count_cumulative
sc_city_open_count_last_3y
sc_city_store_area_sum_cumulative
sc_city_tenant_count_sum_cumulative
sc_prefecture_open_count_last_3y
has_sc_data_coverage
```

採用優先度:

1. 取引年以前に開業済みの市区町村内SC累計件数
2. 直近3年に開業した市区町村内SC件数
3. 市区町村内の店舗面積累計
4. 市区町村内のテナント数累計
5. 都道府県単位の直近開業トレンド
6. データ対象期間を示すcoverageフラグ

ディベロッパー、キーテナント、店舗面積種別は表記ゆれや欠損の影響を受けやすいため、初期モデルには入れず、分析用に保持する。

未来情報の混入を避けるため、取引年より後に開業したSCは当該取引レコードの特徴量に利用しない。

緯度経度が安定して付与できるようになった場合のみ、以下を追加候補にする。

```text
sc_count_within_1km
sc_count_within_3km
nearest_sc_distance_km
nearest_sc_opened_years
sc_store_area_sum_within_3km
sc_tenant_count_sum_within_3km
```

フロントエンドでの商業施設地図表示や `frontend/public/facilities/` へのGeoJSON配信は、価格モデル上の有効性を確認した後の拡張とする。初期MVPでは配信用JSON/GeoJSONを作らない。

---

# 12. モデル比較

商業施設特徴量は、既存モデルと同じ評価年・同じ分割条件で比較する。

採用条件:

* MAEまたはMAPEが改善する
* ONNXサイズと推論前処理が過度に増えない
* 欠損率が高すぎない
* ブラウザ推論時に同じ特徴量を再現できる

改善が小さい、地域により効果が不安定、重要度が低い、欠損が多い特徴量は採用しない。

---

# 13. 将来拡張

* 緯度経度付与
* 都道府県別集計
* ディベロッパー別集計
* 店舗面積レンジ分類
* SC名の表記ゆれ統合
* 大店立地法届出データとの突合
* 商業施設マップ表示用GeoJSON出力
