# データソース取得設計

本ドキュメントは、不動産価格予測アプリに「住みやすさ」「将来性」を加えるための外部データ取得方針を整理する。

モデル採用前に、取得、正規化、特徴量化、フロント再現性、利用規約を個別に確認する。ブラウザからAPIキー付きAPIを直接呼ばず、学習側のcollect処理でraw/processedを生成する。

本アプリでは有料API、有料契約前提、料金不明、またはキャッシュ・再配布条件が曖昧な外部サービスを初期実装で使わない。無料の公式APIとオープンデータを優先し、無料APIでもAPIキーは学習側collectorだけで扱う。

## 参照元

* [国土交通省 不動産情報ライブラリ API操作説明](https://www.reinfolib.mlit.go.jp/help/apiManual/)
* [e-Stat API機能](https://www.e-stat.go.jp/api/)
* [国土数値情報ダウンロードサービス 利用約款](https://nlftp.mlit.go.jp/ksj/other/agreement_02.html)

不動産情報ライブラリAPIは、API利用申請後に発行されるAPIキーをHTTPヘッダーへ設定して利用する。公式説明では、CORSエラー防止の観点からブラウザからAPIリクエストを送信しない注意があるため、本アプリでは既存の駅別乗降客数取得と同じく学習側へ閉じ込める。

## 難易度分類

| 難易度 | 定義 | 例 |
| --- | --- | --- |
| 低 | 既存の不動産情報ライブラリAPI取得パターンを流用でき、タイルGeoJSONを正規化すればよい | 地価公示・基準地価、用途地域、学校、保育園、医療機関、図書館 |
| 中 | APIはあるが、統計表ID、地域コード、年度差分、人口あたり指標などの設計が必要 | e-Stat人口・世帯・年齢構成、将来推計人口メッシュ |
| 中 | APIよりも事前計算JSONや手動マスタが向く | 路線利便性、ターミナル駅フラグ、主要駅所要時間 |
| 高 | 全国で粒度・形式が揃わず、利用条件と表示表現の注意が大きい | 犯罪・治安 |
| 高 | ポリゴン判定、区域外とデータなしの分離、災害種別ごとの意味づけが必要 | ハザード詳細特徴量 |

## 実装単位

各データソースは、以下の4段階で実装する。

```text
collector
  API/CSV/JSONを取得し raw と normalized を保存する
↓
feature builder
  取引データや自治体単位へ結合できるCSVを生成する
↓
FeatureProvider
  training/src/features/providers.py から学習特徴量として使えるようにする
↓
comparison
  単独投入、既存外部特徴量との組み合わせ、ブラウザ配布サイズを比較する
```

フロント表示を伴う場合は、FeatureProviderとは別に `frontend/public` 用の軽量JSONを設計する。モデルに入れない参考情報でも、表示価値が高ければ先にカード化してよい。

## 取引データの緯度経度付与方針

2026-07-15時点の公式CSV/ZIP由来の取引Parquetには `lat` / `lon` が無い。地価ポイントの近傍特徴量、用途地域、教育施設、ハザード詳細、周辺施設距離は物件座標が必要なため、座標なしでは比較しない。

初期方針:

* 最寄駅座標を物件座標として代用しない。駅徒歩や駅名の特徴量と強く重なり、用途地域やハザードの点-in-ポリゴン判定では誤差が大きい
* 有料ジオコーディングAPIや利用条件が曖昧な住所変換サービスは使わない
* 公式CSVの `地区名` は `district_name` として前処理後Parquetに保持する。将来、無料で再配布条件が明確な住所・町丁目代表点データを使える場合に、市区町村 + 地区名で代表座標を付与する
* `lat` / `lon` を持つ入力データが得られた場合は任意列として保持する。ただし既存の必須特徴量にはしない
* 座標精度が町丁目代表点や地区代表点に留まる場合は、近傍施設距離や用途地域判定の精度を別途レポートし、モデル採用前に表示用・参考用・学習用を分けて判断する

短期的には、市区町村単位で再現できる特徴量を優先する。地価は市区町村集計で改善が出たため本番モデルへ採用済み。用途地域、教育施設、ハザード詳細、地価近傍特徴量は、取引データの座標付与後に比較する。

初期の代表点データソースは Geolonia 住所データを使う。ライセンスは CC BY 4.0 とし、取得URLは `https://geolonia.github.io/japanese-addresses/latest.csv`。2026-07-15の実取得では277,189町丁目代表点、正規化CSV 25.3MBだった。

```bash
make collect-address-points
make summarize-coordinate-coverage
```

`district_name` を保持する形で首都圏4県を再前処理した結果、町丁目完全一致は19.33%、地区名prefixで町丁目代表点を平均する方式は80.25%、市区町村代表点フォールバックは0.17%だった。市区町村代表点は粗すぎるため、用途地域やハザード判定、近傍施設距離の学習特徴量には使わない。

町丁目/地区prefix代表点だけを付与した検証用Parquetは `make enrich-coordinates` で生成する。2026-07-15の首都圏4県では685,769件中682,846件、99.57%に座標を付与できた。内訳は町丁目完全一致132,546件、地区prefix代表点550,300件、未付与2,923件だった。次はこの検証用Parquetを使い、用途地域・地価近傍・教育施設の空間特徴量をdry-run比較する。

座標付き検証用Parquetで空間特徴量をサンプル確認する場合は `make summarize-spatial-dry-run` を使う。2026-07-15の200件サンプルでは、地価近傍は39件・19.50%、用途地域zoningは195件・97.50%にマッチした。教育施設CSVは実データ未取得のため0件・0.00%だった。

地価近傍特徴量はBallTreeで全件評価できる。座標付き検証用Parquetで2026-07-15に全件カバレッジとバックテストを再実行した結果、685,769件中123,690件・18.04%に地価特徴量が入り、stationありでMAE 5,447,875円から5,407,593円、stationなしで6,128,259円から6,011,686円へ改善した。

用途地域判定はポリゴンbboxのグリッド索引とユニーク座標単位の判定で全件評価できる。座標付き検証用Parquetで2026-07-15に再実行した結果、685,769件中656,910件・95.79%にzoningがマッチした。都市計画区域と立地適正化区域は未取得のためunknownのまま。

同じ座標付き検証用Parquetで用途地域特徴量のバックテストを実行した結果、stationありはMAE 5,447,875円から5,434,029円、stationなしは6,128,259円から5,964,895円へ改善した。zoning_typeはstationなし候補で上位特徴量に入った。

## 取得候補

### 地価公示・基準地価

目的:

* 周辺地価水準の表示
* 地価上昇率、下落率の表示
* モデル特徴量

主データ:

* 不動産情報ライブラリ `XPT002`: 地価公示・地価調査のポイント API
* 不動産情報ライブラリ `XCT001`: 鑑定評価書情報 API

公式仕様確認日: 2026-07-13。

`XPT002` はXYZタイルを指定して地価公示・地価調査のポイントデータを取得するAPIとして扱う。初期実装では `XPT002` を主経路にし、`XCT001` は鑑定評価書の詳細確認や補助データとして後段で扱う。

`XPT002` の取得パラメータ:

| パラメータ | 必須 | 初期方針 |
| --- | ---: | --- |
| `response_format` | ○ | `geojson` 固定。PBFは使わない |
| `z` | ○ | 初期は `14`。必要に応じて `13` から `15` の範囲で調整 |
| `x` | ○ | 首都圏4県のbboxからXYZタイルを列挙 |
| `y` | ○ | 首都圏4県のbboxからXYZタイルを列挙 |
| `year` | ○ | まず `2024` と `2025` を対象にし、前年比特徴量はAPIの `year_on_year_change_rate` を優先 |
| `priceClassification` |  | 未指定で地価公示・地価調査の両方を取得。比較時に `0` / `1` の分離も試す |
| `useCategoryCode` |  | 初期は住宅地 `00` と商業地 `05` を優先。全用途取得は件数・サイズ確認後 |

`XPT002` で正規化対象にする主な出力:

```text
point_id
target_year_name_ja
land_price_type
prefecture_code
prefecture_name_ja
city_code
city_county_name_ja
ward_town_village_name_ja
use_category_name_ja
standard_lot_number_ja
u_current_years_price_ja
last_years_price
year_on_year_change_rate
u_cadastral_ja
nearest_station_name_ja
u_road_distance_to_nearest_station_name_ja
area_division_name_ja
regulations_use_category_name_ja
u_regulations_building_coverage_ratio_ja
u_regulations_floor_area_ratio_ja
geometry.coordinates
```

`XCT001` の取得パラメータ:

| パラメータ | 必須 | 初期方針 |
| --- | ---: | --- |
| `year` | ○ | 直近5年分のみ。初期は最新年を指定 |
| `area` | ○ | 都道府県コード。首都圏4県をカンマ区切りまたは県別に取得 |
| `division` | ○ | 住宅地 `00` と商業地 `05` を優先 |

`XCT001` はgzipで返る場合がある。既存の駅別乗降客数collectorと同じくgzip展開、raw保存、リトライ、キャッシュを共通実装に寄せる。

初期collector:

```text
training/src/collect/land_prices.py
```

出力:

```text
training/data/raw/land_prices/
training/data/cache/land_prices/
training/data/processed/land_prices/land_price_points.csv
training/data/processed/land_prices/land_price_city_summary.csv
training/data/processed/land_prices/metadata.json
```

実行前の確認:

```bash
make collect-land-prices-dry-run LAND_PRICE_YEARS=2025 LAND_PRICE_ZOOM=14
make collect-land-prices-tile LAND_PRICE_YEARS=2025 LAND_PRICE_REQUEST_INTERVAL_SECONDS=0
```

2026-07-14時点の実測では、首都圏4県・`z=14`・2024/2025年は 8,480タイル x 2年 = 16,960リクエストになる。API応答時間を考えると長時間ジョブになるため、本番CSV生成前に `collect-land-prices-dry-run` で件数を確認し、必要に応じて `LAND_PRICE_ZOOM=12` / `13` や1年分で段階実行する。

疎通確認:

* `LAND_PRICE_TILE_Z=14 LAND_PRICE_TILE_X=14550 LAND_PRICE_TILE_Y=6449 LAND_PRICE_YEARS=2025 LAND_PRICE_REQUEST_INTERVAL_SECONDS=0` で1タイル取得を確認済み。
* 結果は26ポイント、5自治体集計、失敗0件。
* サンドボックスやCIではDNS制限で失敗する場合があるため、実取得はネットワーク許可済みのローカル環境または手動workflowで実行する。

collector設計:

```text
首都圏4県bbox
↓
z=14 のXYZタイルを列挙
↓
XPT002?response_format=geojson&z=...&x=...&y=...&year=...
↓
raw GeoJSONをタイル単位で保存
↓
features[].properties と geometry.coordinates を正規化
↓
point_id + year + land_price_type で重複排除
↓
land_price_points.csv と land_price_city_summary.csv を生成
```

正規化CSVスキーマ:

```text
source_api
point_id
year
land_price_type
prefecture
prefecture_code
municipality
city_code
use_category
standard_lot_number
lat
lon
current_price_yen_per_sqm
last_year_price_yen_per_sqm
year_on_year_change_rate
land_area_sqm
nearest_station
station_distance_m
area_division
zoning
building_coverage_ratio
floor_area_ratio
source_url
```

市区町村集計CSVスキーマ:

```text
year
prefecture
municipality
city_code
use_category
point_count
avg_price_yen_per_sqm
median_price_yen_per_sqm
avg_yoy_rate
```

特徴量候補:

```text
nearest_land_price_yen_per_sqm
nearest_land_price_distance_km
land_price_city_avg_yen_per_sqm
land_price_city_yoy_rate
land_price_points_within_2km
has_land_price_data
```

難易度: 低。

最初に着手する。価格予測モデルとの意味が近く、住環境表示にも使える。

### 用途地域・都市計画

目的:

* 住環境表示
* 開発余地、将来性の補助説明
* モデル特徴量

主データ:

* 不動産情報ライブラリ `XKT001`: 都市計画区域/区域区分
* 不動産情報ライブラリ `XKT002`: 用途地域
* 不動産情報ライブラリ `XKT003`: 立地適正化計画

公式仕様確認日: 2026-07-14。

API仕様:

| API | 種別 | パラメータ | ズーム | 主な属性 | 初期用途 |
| --- | --- | --- | --- | --- | --- |
| `XKT001` | 都市計画区域/区域区分 | `response_format`, `z`, `x`, `y` | 11-15 | `prefecture`, `city_code`, `city_name`, `kubun_id`, `area_classification_ja` | 市街化区域/市街化調整区域などの区域区分 |
| `XKT002` | 用途地域 | `response_format`, `z`, `x`, `y` | 11-15 | `youto_id`, `prefecture`, `city_code`, `city_name`, `use_area_ja`, `u_floor_area_ratio_ja`, `u_building_coverage_ratio_ja` | 用途地域、容積率、建ぺい率 |
| `XKT003` | 立地適正化計画 | `response_format`, `z`, `x`, `y` | 11-15 | `prefecture`, `city_code`, `city_name`, `kubun_id`, `kubun_name_ja`, `area_classification_ja` | 居住誘導区域/都市機能誘導区域などの将来性説明 |

取得方針:

```text
首都圏4県bbox
↓
XKT001 / XKT002 / XKT003 を z=13 から開始してXYZタイル取得
↓
raw GeoJSONをAPI・タイル単位で保存
↓
都市計画ポリゴンを normalized CSV へ保存
↓
取引地点または選択地点とポリゴンを結合し、用途地域特徴量を生成
```

初期collector:

```text
training/src/collect/urban_planning.py
```

実行前の確認:

```bash
make collect-urban-planning-dry-run URBAN_PLANNING_ZOOM=13
```

2026-07-14時点のdry-runでは、首都圏4県・`z=13`・`XKT001,XKT002,XKT003` で 2,160タイル x 3 API = 6,480リクエストになる。地価と同様に長時間ジョブとして扱い、まず `XKT002` 単独や低zoomでの段階取得を検討する。

出力:

```text
training/data/raw/urban_planning/
training/data/processed/urban_planning/urban_planning_areas.csv
training/data/processed/urban_planning/zoning_features.csv
training/data/processed/urban_planning/metadata.json
```

`urban_planning_areas.csv`:

```text
source_api
area_type
prefecture
city_code
city_name
area_code
area_name
zoning_type
floor_area_ratio
building_coverage_ratio
decision_date
decision_classification
decision_maker
geometry_type
geometry_json
source_url
```

`zoning_features.csv`:

```text
prefecture
municipality
lat
lon
city_planning_area_type
zoning_type
is_commercial_zone
is_residential_zone
floor_area_ratio
building_coverage_ratio
location_optimization_area
has_zoning_data
```

特徴量候補:

```text
zoning_type
is_commercial_zone
is_residential_zone
floor_area_ratio
building_coverage_ratio
has_zoning_data
```

難易度: 低から中。

ポリゴン属性を取引地点へ付与する必要があるため、collectorとFeatureBuilderを分ける。初期は価格モデル特徴量としても参考表示としても価値が高い `XKT002` の用途地域、容積率、建ぺい率を優先し、`XKT001` と `XKT003` は表示・将来性説明の補助として扱う。

### 人口・世帯数・年齢構成

目的:

* 自治体比較
* 人口密度、高齢化率、生産年齢人口比率の表示
* 将来人口による将来性説明

主データ:

* e-Stat API: 国勢調査、住民基本台帳、人口推計
* 不動産情報ライブラリ `XKT013`: 将来推計人口250mメッシュ

公式仕様確認日: 2026-07-13。

e-Stat APIはユーザー登録後に取得するアプリケーションIDを使う。現行のAPI仕様はバージョン3.0で、JSON、CSV、XML形式に対応する。HTTPSとgzipレスポンスに対応している。collectorでは `getStatsData` のJSONレスポンスを `training/data/raw/population/` に保存し、同じ正規化CSVへ落とす。

初期実装では、自治体単位CSVを正規化できる経路と、e-Stat APIレスポンスを正規化する経路を同じcollectorに持たせる。e-Statの統計表ID、地域コード、年齢階級、時点は統計ごとに異なるため、統計表IDをコードへ固定せず、項目マッピングを引数で渡す。

初期入力CSVスキーマ:

```text
year
prefecture
municipality
city_code
population_total
households_total
population_density_per_km2
population_under_15
population_15_to_64
population_65_plus
area_km2
source
source_url
```

テンプレート:

```text
training/data/manual/population/municipality_population_template.csv
```

collectorは、上記CSVを `municipality_population.csv` へ正規化する。e-Stat API実装後も同じ正規化スキーマへ落とす。

CSV持ち込み:

```bash
make collect-population-stats POPULATION_INPUT=path/to/population.csv
```

テンプレート再生成:

```bash
make collect-population-stats-template
```

e-Stat API直結:

```bash
ESTAT_APP_ID=... make collect-population-stats \
  ESTAT_STATS_DATA_ID=0000000000 \
  ESTAT_AREA_CODES="13101 13102" \
  ESTAT_TIME_CODES="2020000000 2025000000" \
  ESTAT_ITEMS="population_total=cat01:001 households_total=cat01:002 population_under_15=cat01:003 population_15_to_64=cat01:004 population_65_plus=cat01:005"
```

`ESTAT_ITEMS` は `正規化列=次元:コード` の形式で指定する。統計表によって年齢階級や男女区分の次元が変わる場合は、`population_total=cat01:001,cat02:000` のように複数条件を指定する。

初期取得仕様:

| 項目 | 初期方針 |
| --- | --- |
| 統計表ID | コードへハードコードしない。`getStatsList` と `getMetaInfo` で確認したIDを `ESTAT_STATS_DATA_ID` として指定する |
| 優先統計 | まず国勢調査の市区町村別人口・世帯・年齢階級。住民基本台帳や人口推計は比較候補に留める |
| 地域コード | 取引データと結合しやすいJIS市区町村コード5桁を `cdArea` に指定する |
| 年度 | 2015年、2020年を初期対象にし、2025年は利用可能になった時点で追加する |
| 粒度 | MVPでは市区町村単位。町丁目、小地域、メッシュは表示価値と配布サイズを確認してから追加する |
| 性別 | 初期は総数のみ。男女別は説明価値が出る場合だけ後続候補にする |
| 年齢階級 | `0-14`、`15-64`、`65+` に集約し、`under_15_rate`、`working_age_rate`、`aging_rate` を生成する |
| APIキー | `ESTAT_APP_ID` から読み、保存する `source_url` では `appId` をマスクする |

e-Stat API実装時の候補:

| 段階 | 方針 |
| --- | --- |
| 統計表検索 | `getStatsList` で国勢調査、住民基本台帳、人口推計の候補を調査 |
| メタ情報取得 | `getMetaInfo` で地域階層、年齢階級、男女、時点を固定 |
| 統計データ取得 | `getStatsData` で市区町村単位、必要項目だけ取得 |
| raw保存 | APIレスポンスJSON/CSVを `training/data/raw/population/` へ保存 |
| 正規化 | 統計表ごとの階級名をアプリ共通列へマッピング |

アプリケーションID:

```text
ESTAT_APP_ID
```

環境変数または `training/.env` から読み込む。ブラウザへは置かない。

`XKT013` は将来推計人口250mメッシュとして扱う。公式APIでは `response_format`、`z`、`x`、`y` を指定してGeoJSON/PBFを取得し、ズームは `11` から `15` を指定できる。データは国土数値情報「250mメッシュ別将来推計人口データ（R6国政局推計）」で、令和2年国勢調査に基づく。

主な属性:

```text
MESH_ID
SHICODE
PT00_20XX  男女計総数人口
PTA_20XX   0-14歳人口
PTB_20XX   15-64歳人口
PTC_20XX   65歳以上人口
RTA_20XX   0-14歳人口比率
RTB_20XX   15-64歳人口比率
RTC_20XX   65歳以上人口比率
```

採用方針:

| 用途 | 判断 |
| --- | --- |
| モデル特徴量 | 初期は見送る。将来年次の推計値は、学習時点から見て未来情報の扱いが難しく、取引地点の緯度経度がない行では250mメッシュ結合も安定しない |
| 参考表示 | 候補に残す。選択地点の緯度経度がある場合、周辺メッシュの将来人口変化を「将来性の参考情報」として出す価値は高い |
| 自治体集計 | 候補に残す。`SHICODE` 単位に集計すれば既存の自治体人口統計と接続できるが、250mメッシュの強みは薄まる |
| 配布サイズ | 要検証。首都圏だけでもメッシュ件数が多いため、フロント配信用には自治体集計または選択地点周辺の軽量化が必要 |

結論として、価格モデルの比較はまずe-Stat/CSV由来の自治体人口統計を優先する。`XKT013` は、緯度経度付きの表示機能または自治体集計のサイズ検証ができてから接続する。

初期のモデル比較では自治体単位の人口統計を優先し、メッシュは以下の条件がそろった後に追加する。

* 取引データまたは推論地点に緯度経度がある
* メッシュ集計の配布サイズが現実的
* 将来人口を価格予測に入れても未来情報リークにならない年度設計ができる

初期collector:

```text
training/src/collect/population_stats.py
```

出力:

```text
training/data/raw/population/
training/data/cache/population/
training/data/processed/population/municipality_population.csv
training/data/processed/population/population_mesh.csv
training/data/processed/population/metadata.json
```

正規化CSVスキーマ:

```text
year
prefecture
municipality
city_code
population_total
households_total
population_density_per_km2
aging_rate
working_age_rate
under_15_rate
population_change_5y_rate
household_persons_avg
area_km2
source
source_url
```

collector設計:

```text
入力CSVまたはe-Stat APIレスポンス
↓
year / city_code / municipality を標準化
↓
年齢階級を 0-14 / 15-64 / 65+ に集約
↓
population_density_per_km2 がなければ population_total / area_km2 で算出
↓
aging_rate / working_age_rate / under_15_rate を算出
↓
city_code単位で5年前人口を結合し population_change_5y_rate を算出
↓
municipality_population.csv と metadata.json を生成
```

特徴量候補:

```text
municipality_population
municipality_households
municipality_population_density
municipality_aging_rate
municipality_working_age_rate
population_change_5y_rate
future_population_change_rate
has_population_data
```

難易度: 中。

e-Statは統計表IDと地域コードの固定が先に必要。初期は自治体単位に絞り、メッシュは将来比較に回す。

### 学区・学校・保育園

目的:

* ファミリー向け説明
* 小学校、中学校、保育園、幼稚園の距離・件数表示
* モデル特徴量候補

主データ:

* 不動産情報ライブラリ `XKT004`: 小学校区
* 不動産情報ライブラリ `XKT005`: 中学校区
* 不動産情報ライブラリ `XKT006`: 学校
* 不動産情報ライブラリ `XKT007`: 保育園・幼稚園等

公式仕様確認日: 2026-07-13。

API仕様:

| API | 種別 | パラメータ | ズーム | 主な属性 | 初期用途 |
| --- | --- | --- | --- | --- | --- |
| `XKT004` | 小学校区 | `response_format`, `z`, `x`, `y`, `administrativeAreaCode` | 11-15 | `A27_001` 行政区域コード、`A27_003` 学校コード、`A27_004_ja` 名称、`A27_005` 所在地 | 学区ポリゴン、選択地点の小学校区名 |
| `XKT005` | 中学校区 | `response_format`, `z`, `x`, `y`, `administrativeAreaCode` | 11-15 | `A32_001` 行政区域コード、`A32_003` 学校コード、`A32_004_ja` 名称、`A32_005` 所在地 | 学区ポリゴン、選択地点の中学校区名 |
| `XKT006` | 学校 | `response_format`, `z`, `x`, `y` | 13-15 | `P29_001` 行政区域コード、`P29_002` 学校コード、`P29_003_name_ja` 学校分類名、`P29_004_ja` 名称、`P29_005_ja` 所在地 | 小学校・中学校の最寄距離 |
| `XKT007` | 保育園・幼稚園等 | `response_format`, `z`, `x`, `y` | 13-15 | 幼稚園/こども園は `preSchoolName_ja`, `schoolClassCode_name_ja`, `location_ja`、保育園は `preSchoolName_ja`, 福祉施設分類コード, `location_ja` | 保育園/幼稚園の半径件数 |

取得方針:

```text
首都圏4県bbox
↓
XKT004 / XKT005 は z=12 または z=13 で学校区ポリゴンを取得
↓
XKT006 / XKT007 は z=13 または z=14 で施設ポイントを取得
↓
raw GeoJSONをAPI・タイル単位で保存
↓
学校区ポリゴンと施設ポイントを別CSVへ正規化
↓
選択地点または取引地点に対して、最寄距離・半径件数・学区名を生成
```

注意点:

* 学校区は年度や自治体の指定校変更で変わるため、価格モデル特徴量に入れる前に年度差と表示上の注記が必要。
* 学区ポリゴンは「その学校に必ず通える」保証ではなく、自治体の例外運用や選択制があり得る。
* 保育園・幼稚園は定員、空き、認可区分、入園条件を表さないため、件数表示に留める。
* 初期は価格モデルに入れず、周辺情報カードとして「小学校までの距離」「中学校までの距離」「保育園/幼稚園件数」を出す。
* 有料APIや民間施設DBは使わず、不動産情報ライブラリAPI由来の無料データだけを対象にする。

初期collector:

```text
training/src/collect/education_facilities.py
```

実行前の確認:

```bash
make collect-education-facilities-dry-run EDUCATION_ZOOM=13
```

2026-07-14時点のdry-runでは、首都圏4県・`z=13`・`XKT004,XKT005,XKT006,XKT007` で 2,160タイル x 4 API = 8,640リクエストになる。学校区と施設ポイントは利用目的が異なるため、本番取得時は学区APIと施設APIを分けて段階実行する。

出力:

```text
training/data/raw/education/
training/data/processed/education/education_facilities.csv
training/data/processed/education/school_districts.csv
training/data/processed/education/education_features.csv
```

`school_districts.csv`:

```text
source_api
district_type
administrative_area_code
school_code
school_name
operator_name
address
geometry_type
geometry_json
source_url
```

`education_facilities.csv`:

```text
source_api
facility_type
administrative_area_code
facility_code
facility_name
facility_class_code
facility_class_name
administrator_code
closed_code
lat
lon
address
source_url
```

`education_features.csv`:

```text
prefecture
municipality
lat
lon
elementary_school_district_name
junior_high_school_district_name
nearest_elementary_school_distance_km
nearest_junior_high_school_distance_km
nursery_count_within_500m
nursery_count_within_1km
kindergarten_count_within_1km
has_education_data
```

collector実装では、`school_districts.csv` と `education_facilities.csv` の生成を先に行う。`education_features.csv` は取引地点または選択地点との空間結合が必要なため、FeatureBuilderで別段階に分ける。

特徴量候補:

```text
nearest_elementary_school_distance_km
nearest_junior_high_school_distance_km
nursery_count_within_500m
nursery_count_within_1km
kindergarten_count_within_1km
has_education_data
```

難易度: 低から中。

表示価値が高い一方、価格モデルでは地域差の代理になりやすい。最初は参考情報カードとして実装し、モデル採用は比較後に判断する。

### 路線利便性・ターミナル駅フラグ

目的:

* 駅利便性の説明
* 主要駅までの所要時間
* ターミナル駅、乗換拠点の評価

主データ:

* 自前JSON
* 必要時のみ Google Routes API、駅すぱあとAPI、NAVITIME APIなどで事前計算

初期collector:

```text
training/src/collect/rail_access.py
```

初期マスタ:

```text
training/data/manual/rail/terminal_stations.csv
training/data/manual/rail/major_station_travel_times.csv
```

`terminal_stations.csv`:

```text
station_name
station_aliases
is_terminal
terminal_group
source
source_year
```

`major_station_travel_times.csv`:

```text
origin_station
destination_station
travel_time_minutes
transfer_count
is_direct
source
source_year
```

collector出力:

```text
training/data/processed/rail/rail_access.csv
training/data/processed/rail/metadata.json
```

`rail_access.csv` は駅名正規化後に1駅1行へ集約し、東京、新宿、渋谷、横浜までの所要時間、乗換回数、最短主要ターミナル、ターミナル駅フラグを持つ。未収録駅はFeatureProvider側で `has_rail_access_data=0` とし、所要時間は `999` 分の番兵値を入れる。

特徴量候補:

```text
nearest_station_is_terminal
nearest_station_time_to_tokyo
nearest_station_time_to_shinjuku
nearest_station_time_to_shibuya
nearest_station_time_to_yokohama
major_terminal_min_time
has_rail_access_data
```

難易度: 中。

リアルタイムAPIは使わず、主要駅への所要時間を事前計算して固定JSONにする。API利用料と経路変化の追従があるため、自前マスタから始める。

外部API利用条件メモ（公式確認日: 2026-07-13）:

| API | 初期判断 | 料金・制約 | キャッシュ/再配布方針 |
| --- | --- | --- | --- |
| Google Routes API | MVPでは採用しない。検証用の一時取得候補 | Billing有効化とAPIキー/OAuthが必要。Compute Routesはリクエスト単位、Compute Route Matrixは origin × destination の要素単位で課金。Routes APIはSKUと利用機能で課金区分が変わる | Google Maps PlatformのService Specific Termsではキャッシュ可能なGoogle Maps Contentが項目・期間ごとに制限されるため、事前計算値を永続配布する用途には原則使わない |
| 駅すぱあと API | 高精度な候補だが契約前提。ポートフォリオMVPでは採用しない | 公開ページが取得制限されるため、料金、商用利用、保存可否は契約前に個別確認する | 契約条件で保存・再配布可否を確認できるまで、生成済みJSONの元データには使わない |
| NAVITIME API | 法人向け候補。必要になった場合だけ問い合わせ | 公式サイトではAPI/SDK、資料請求、問い合わせ、90日無料試用の導線がある。公開ページ上で料金表は確認できなかった | 契約条件で保存・再配布可否を確認できるまで、生成済みJSONの元データには使わない |

結論として、初期実装は手動CSVを正とする。外部APIは、主要駅所要時間の初期値を作るための調査・一時検証に限定し、APIレスポンスをそのまま配布成果物へ混ぜない。

### 犯罪・治安

目的:

* 治安比較
* 人口あたり刑法犯認知件数などの参考表示

主データ:

* 都道府県警、市区町村オープンデータ
* e-Statの一部統計

公式・公的データ候補の初期判断:

| 候補 | 初期判断 | 注意点 |
| --- | --- | --- |
| 都道府県警の犯罪統計 | 優先候補。無料公開が多いが、CSV/Excel/PDFなど形式が都道府県で異なる | 市区町村、警察署、町丁目など粒度が揃わない。罪種分類も地域で差が出る |
| 市区町村オープンデータ | 補助候補。自治体によって町丁目単位など細かい場合がある | 全国統一には向かない。更新停止や年度欠落に注意 |
| e-Stat | 補助候補。統計表IDが固定できる範囲で確認する | 市区町村単位で必要な罪種・年度が揃うとは限らない |
| 民間治安スコア/有料API | 採用しない | 有料、算出根拠不明、再配布条件不明のものは後回し |

初期collector:

```text
training/src/collect/crime_stats.py
```

入力形式:

* `.csv` / `.txt`: UTF-8 BOM付きCSVを含むカンマ区切り
* `.tsv`: タブ区切り
* `.xlsx`: 先頭シートの単純な表形式。標準ライブラリだけで読むため、結合セル、複数ヘッダー、注釈行がある公開Excelは事前に整形する

2026-07-14時点で、CSV/TSV/XLSXのfixtureから `crime_municipality.csv` を生成できることを確認済み。全国統一の特徴量化は急がず、自治体ごとに無料公開データの粒度と列名を確認してから取り込む。

出力:

```text
training/data/raw/crime/
training/data/processed/crime/crime_municipality.csv
training/data/processed/crime/metadata.json
```

正規化CSVスキーマ:

```text
year
prefecture
municipality
city_code
area_unit
crime_type
crime_count
population_total
crime_count_per_1000_population
source
source_url
notes
```

特徴量候補:

```text
crime_count_per_1000_population
crime_count
crime_year
crime_area_unit
has_crime_data
```

難易度: 高。

全国統一APIがないため、最初からモデル特徴量にはしない。表示する場合も星評価を避け、出典、年度、集計単位を必ず併記する。

表示方針:

* 星評価、治安偏差値、安全/危険の断定表現は使わない。
* 初期表示は「人口1000人あたり刑法犯認知件数」「件数」「年度」「集計単位」「出典」に限定する。
* 罪種を分ける場合は、総数、窃盗、侵入窃盗、自転車盗など自治体で比較的公開されやすい分類から始める。
* 人口あたり件数は都市規模や昼夜間人口の影響を受けるため、ランキングや優劣判断には使わない。
* モデル特徴量に入れる場合は、人口統計データと結合して `crime_count_per_1000_population` を算出し、欠損時は `has_crime_data=0` を明示する。

## 実装優先順位

| 順位 | データ | 理由 | 初期成果物 |
| ---: | --- | --- | --- |
| 1 | 地価公示・基準地価 | 価格モデルとの関連が強く、API導線も明確 | collector + 市区町村/近傍特徴量 |
| 2 | 用途地域 | 表示価値とモデル特徴量価値が高い | collector + ポリゴン属性付与 |
| 3 | 人口・世帯数 | 住みやすさ、将来性の基本指標 | e-Stat設計 + 自治体CSV |
| 4 | 学校・保育園 | UI価値が高い | 参考情報JSON + 距離/件数特徴量 |
| 5 | ハザード詳細 | 既存カードと比較候補はあるため、データ整備を進める | 災害種別ごとのcollector |
| 6 | 路線利便性 | 自前マスタ設計が必要 | terminal/travel time JSON |
| 7 | 犯罪・治安 | 粒度と表示リスクが大きい | 出典調査 + 一部地域fixture |

## 共通実装要件

* APIキーは `.env` または環境変数から読み、`frontend/` へ置かない
* rawレスポンスは `training/data/raw/<source>/` に保存する
* 正規化済みCSVは `training/data/processed/<source>/` に保存する
* 取得ログ、失敗タイル、パース不能レコードを保存する
* APIリクエストには間隔、リトライ、キャッシュを入れる
* 出典、年度、schemaVersion、generatedAtを成果物に含める
* 「データなし」と「対象外」は別の状態として保持する
* モデル投入前に `compare_*` スクリプトで単独効果と組み合わせ効果を確認する

## TODOへの分割方針

1データソースにつき、以下のTODO粒度に分ける。

```text
取得仕様確認
collector設計
collector実装
正規化CSV生成
FeatureProvider実装
比較スクリプト実装
UI参考表示または配信用JSON実装
モデル採用判断
```

この粒度にすると、データ取得だけ先に進め、モデル成果物反映はP2として後からまとめられる。
