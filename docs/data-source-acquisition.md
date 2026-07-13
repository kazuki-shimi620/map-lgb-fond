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

初期collector:

```text
training/src/collect/land_prices.py
```

出力:

```text
training/data/raw/land_prices/
training/data/processed/land_prices/land_price_points.csv
training/data/processed/land_prices/land_price_city_summary.csv
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

初期collector:

```text
training/src/collect/population_stats.py
```

出力:

```text
training/data/raw/population/
training/data/processed/population/municipality_population.csv
training/data/processed/population/population_mesh.csv
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
