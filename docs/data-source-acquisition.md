# データソース取得設計

本ドキュメントは、不動産価格予測アプリに「住みやすさ」「将来性」を加えるための外部データ取得方針を整理する。

モデル採用前に、取得、正規化、特徴量化、フロント再現性、利用規約を個別に確認する。ブラウザからAPIキー付きAPIを直接呼ばず、学習側のcollect処理でraw/processedを生成する。

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

初期collector:

```text
training/src/collect/urban_planning.py
```

出力:

```text
training/data/raw/urban_planning/
training/data/processed/urban_planning/zoning_features.csv
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

ポリゴン属性を取引地点へ付与する必要があるため、地価ポイント取得の後に実装する。

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

collectorは、上記CSVを `municipality_population.csv` へ正規化する。e-Stat API実装後も同じ正規化スキーマへ落とす。

CSV持ち込み:

```bash
make collect-population-stats POPULATION_INPUT=path/to/population.csv
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

`XKT013` は将来推計人口250mメッシュとして扱う。初期のモデル比較では自治体単位の人口統計を優先し、メッシュは以下の条件がそろった後に追加する。

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

初期collector:

```text
training/src/collect/education_facilities.py
```

出力:

```text
training/data/raw/education/
training/data/processed/education/education_facilities.csv
training/data/processed/education/school_districts.csv
training/data/processed/education/education_features.csv
```

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

初期collector:

```text
training/src/collect/crime_stats.py
```

出力:

```text
training/data/raw/crime/
training/data/processed/crime/crime_municipality.csv
```

特徴量候補:

```text
crime_count_per_1000_population
crime_year
crime_area_unit
has_crime_data
```

難易度: 高。

全国統一APIがないため、最初からモデル特徴量にはしない。表示する場合も星評価を避け、出典、年度、集計単位を必ず併記する。

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
