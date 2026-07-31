# station-passengers.md

# 駅別乗降客数データ取得・正規化仕様

本ドキュメントは、国土交通省「不動産情報ライブラリ」が提供する国土数値情報（駅別乗降客数）APIから駅別乗降客数を取得し、学習・分析・ブラウザ推論で利用しやすい形式へ正規化するための仕様を定義する。

---

# 1. 目的

駅別乗降客数を駅規模特徴量として利用し、中古マンション価格予測モデルの精度・軽量化・汎化性能を比較できるようにする。

主な用途:

* LightGBMの駅規模特徴量
* 駅カテゴリを外した軽量モデルの補助特徴量
* 駅周辺利便性の評価
* ブラウザ推論時の駅特徴量参照

---

# 2. データソース

## API

```text
https://www.reinfolib.mlit.go.jp/ex-api/external/XKT015
```

| 項目 | 内容 |
| --- | --- |
| 提供元 | 国土交通省 不動産情報ライブラリ |
| API ID | `XKT015` |
| API名 | 国土数値情報（駅別乗降客数）API |
| HTTPメソッド | GET |
| 認証方式 | APIキー |
| レスポンス形式 | GeoJSON |
| データ取得単位 | XYZ方式の地図タイル |

APIキーは `REINFOLIB_API_KEY` から読み込む。ブラウザから直接APIを呼び出さない。

---

# 3. CLI

## 単一タイル取得

```bash
cd training
uv run python src/collect/station_passengers.py --tile 11 1818 807
```

## BoundingBox取得

```bash
cd training
uv run python src/collect/station_passengers.py \
  --north 36.2 --south 35.6 --east 140.2 --west 138.8 --zoom 11
```

## 地域取得

```bash
make collect-station-passengers PASSENGER_AREA=capital
```

対象地域:

* `capital`: 首都圏概算範囲
* `japan`: 全国概算範囲

全国取得はリクエスト数が多くなるため、初期検証では `capital` または `--tile` を優先する。

全国取得では全国矩形をそのまま列挙せず、`frontend/public/stations` の全国駅マスタに
含まれる座標から対象タイルを抽出する。z11では矩形方式18,477タイルに対し、
駅マスタ方式は1,056タイルとなる。2026-07-31時点のキャッシュを考慮したdry-runは
960リクエストで、既定の1秒間隔では最低約16分を見込む。

```bash
make collect-station-passengers-national-dry-run
make collect-station-passengers-national
```

駅マスタに存在しない駅を新たに発見する用途には使えないため、駅マスタ更新後は
必ずdry-run件数を再確認する。

---

# 4. 保存先

raw GeoJSON、正規化JSON、CSVはGit管理しない。

```text
training/data/raw/xkt015/{run_id}/z{zoom}/{x}/{y}.geojson
training/data/raw/xkt015/{run_id}/manifest.json
training/data/processed/station_passengers/station_lines.json
training/data/processed/station_passengers/station_groups.json
training/data/processed/station_passengers/station_groups.csv
training/data/processed/station_passengers/station_passenger_summary.json
training/data/cache/station_passengers/failed_tiles.json
training/data/cache/station_passengers/invalid_features.json
```

ブラウザ配信用に採用する場合は、必要最小限の項目だけを `frontend/public` へ配置する。

フロントエンドでは、価格モデルへの採用とは分けて、最寄駅の参考情報として駅規模カードを表示する。

表示項目:

```text
駅名
駅規模ランク
推定乗降客数
路線数
運営会社数
```

乗降客数は駅マスタに含めた `station_passenger_log` から参考値として復元する。厳密な最新乗降客数ではなく、駅の相対的な規模を説明するための表示とする。

---

# 5. 正規化モデル

## 路線駅単位

APIの1 Featureを `StationLineRecord` として保持する。

GeoJSONの `geometry.type` は `Point` または `LineString` を許容する。`LineString` の場合は全座標の平均を代表座標として利用する。

```json
{
  "stationCode": "004562",
  "groupCode": "004562",
  "stationName": "新子安",
  "normalizedStationName": "新子安",
  "operatorName": "東日本旅客鉄道",
  "normalizedOperatorName": "JR東日本",
  "lineName": "東海道線",
  "normalizedLineName": "東海道線",
  "railwayTypeCode": "11",
  "operatorTypeCode": "2",
  "location": {
    "latitude": 35.487654,
    "longitude": 139.654321
  },
  "passengerHistory": [],
  "latestPassengerCount": 40962,
  "latestPassengerYear": 2023
}
```

## 駅グループ単位

同一駅グループを集約して `StationGroup` として保持する。

集約IDの優先順位:

1. `groupCode`
2. `stationCode`
3. 駅名・座標から生成したハッシュ

初期集約ルール:

* 同一年度の有効乗降客数を集める
* 同じ値は重複排除する
* 値が1種類ならその値を採用する
* 複数値がある場合は過大加算を避けるため最大値を採用する

---

# 6. 年度別属性

2011年以降の年度別属性は次の規則で扱う。

```text
2011: S12_006 / S12_007 / S12_008 / S12_009
2012: S12_010 / S12_011 / S12_012 / S12_013
...
2023: S12_054 / S12_055 / S12_056 / S12_057
```

各年度は `duplicateCode`、`availabilityCode`、`note`、`passengerCount` に正規化する。

年度追加に備え、実装では年度と属性名の対応を関数で生成し、未知属性は保持しない。

---

# 7. 駅規模ランク

| ランク | 1日当たり乗降客数 |
| --- | ---: |
| S | 500,000人以上 |
| A | 100,000人以上 |
| B | 50,000人以上 |
| C | 20,000人以上 |
| D | 5,000人以上 |
| E | 5,000人未満 |
| null | データなし |

モデル入力用に `log1p(passengerCount)` も出力する。

---

# 8. 特徴量化方針

初期候補:

```text
station_passenger_count
station_passenger_log
station_passenger_year
station_passenger_age
station_rank
station_line_count
station_operator_count
effective_station_scale
has_station_passenger_data
```

`effective_station_scale` は以下で計算する。

```text
log1p(passengerCount) * exp(-stationDistanceMeters / 1000)
```

駅徒歩分しかない場合は、既存仕様と同じく60m=1分の徒歩距離へ換算する。

初期のLightGBM比較では、ブラウザ推論時の容量を抑えるため、以下の小さな特徴量セットを優先する。

```text
station_passenger_log
station_line_count
station_operator_count
effective_station_scale
has_station_passenger_data
```

`station_rank` はカテゴリ数が少ないため比較候補に含めるが、効果が薄い場合は外す。`station_passenger_count` は歪みが大きいため、原則として `station_passenger_log` を優先する。

最寄駅との結合は、まず駅名を正規化して一致させる。同名駅が複数あり、駅別乗降客数と物件データの両方に座標がある場合は、駅名一致候補の中から物件座標に最も近い駅グループを採用する。座標がない場合は、乗降客数が最大の駅グループを代表値にする。

バックテストは以下で実行する。

```bash
make compare-station-passenger-features
```

2026-07-10時点の首都圏バックテストでは、`station` カテゴリを残す場合は `station_scale_numeric` がベースラインよりMAEを約2.5万円改善した。`station` カテゴリを外す軽量案では、`station_scale_numeric_rank_no_station` が `baseline_no_station` よりMAEを約41.8万円改善した。駅乗降客数マッチ件数は477,133件中419,802件だった。ブラウザ配布サイズを優先する場合は、駅カテゴリ辞書を持たない軽量案を候補にする。

2026-07-11時点の全国駅マスタ生成では、首都圏4都県は1,566駅中1,474駅に乗降客数が付与できた。一方、首都圏以外は7,487駅中282駅のみで、欠損率は96.2%だった。現状の `station_passengers` 取得範囲は首都圏中心のため、地方モデルへ駅規模特徴量を入れる場合は、全国範囲の乗降客数を取得してから再評価する。

全国範囲の駅別乗降客数を取得する場合:

```bash
make collect-station-passengers-national-dry-run
make collect-station-passengers-national
```

XKT015はズーム値に制約があり、現時点では `z=11` を使用する。2026-07-14時点のdry-runでは全国範囲が18,477タイルになるため、API制限と実行時間を見ながら実行する。必要に応じて `PASSENGER_REQUEST_INTERVAL_SECONDS` を調整する。

4都県の個別モデル設定は、この軽量案に合わせて `station` カテゴリを外し、以下を利用する。

```text
station_passenger_log
station_line_count
station_operator_count
effective_station_scale
has_station_passenger_data
station_rank
```

出力:

```text
training/outputs/comparisons/station_passenger_feature_backtest.json
training/outputs/comparisons/station_passenger_feature_backtest.md
training/outputs/comparisons/station_passenger_feature_models/
```

---

# 9. 実装上の注意

* APIキーはURLに含めずHTTPヘッダーで送る
* APIキーをログに出さない
* rawと正規化データを分離する
* タイル単位でキャッシュし、再取得を抑える
* 空FeatureCollectionは正常系として扱う
* 同一駅の路線別値は即時加算しない
* 乗降客数は「乗車人員」と混同せず `passengerCount` として扱う
