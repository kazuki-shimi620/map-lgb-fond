# training.md

# 学習システム仕様

本ドキュメントは学習処理の詳細仕様を定義する。

対象は training ディレクトリ配下の実装である。

---

# 1. 目的

学習システムは以下を目的とする。

* 国交省データの取得
* 学習用データ生成
* 特徴量生成
* LightGBM学習
* モデル評価
* ONNX出力
* 実験管理

---

# 2. ディレクトリ構成

```text
training/

├── configs/
│   └── 地域別学習設定
│
├── browser/
│   └── 公式画面CSVダウンロード用Playwrightスクリプト
│
├── scripts/
│   └── 複数モデル学習や長時間更新のラッパー
│
├── src/
│
│   ├── collect/     外部データ取得・正規化
│   ├── preprocess/  不動産CSV/ZIPの前処理
│   ├── features/    FeatureProviderと外部特徴量結合
│   ├── train/       LightGBM学習とONNX出力
│   ├── evaluate/    バックテスト・比較・更新前後レポート
│   ├── export/      frontend/public向け静的成果物生成
│   └── experiment/  SQLite実験管理
│
├── outputs/
│   ├── models/
│   ├── comparisons/
│   └── reports/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── cache/
│
└── db/
```

`training/data`、`training/outputs`、`training/db` はローカル生成物を置く作業領域であり、原則Git管理しない。

ブラウザ実行に必要な最新成果物だけを `frontend/public` へexportする。

---

# 3. 実行フロー

```text
collect
  ↓
preprocess
  ↓
feature
  ↓
train
  ↓
evaluate
  ↓
export
```

## 学習と配布モデル

MVPでは、評価用モデルとブラウザ配布用モデルを分ける。

```text
評価:
2005〜2024年で学習
2025年で評価

配布:
評価完了後、2005〜2025年の全データで再学習
ONNX / pkl / metadata は配布用モデルから出力
```

評価指標はテスト年を含まない評価用モデルで算出し、配布モデルは同じパラメータを使って最新年までの全データで再学習する。

## ハイパーパラメータチューニング

LightGBM のパラメータ探索は Optuna で行う。

設定例:

```yaml
tuning:
  enabled: true
  n_trials: 30
  validation_year: 2024
  early_stopping_rounds: 100
  max_estimators: 1000
  num_leaves_max: 96
  size_penalty_per_iteration: 200
```

MVPの標準試行回数は30回とする。`enabled: false` の場合は固定パラメータで学習する。

チューニングでは `validation_year` を検証年として利用し、最終評価年 `test_year` は探索に使わない。

ブラウザ配布用のONNXモデルが大きくなりすぎることを避けるため、チューニング時は木の本数や葉数に上限を設ける。また、検証MAEが近い候補では軽いモデルを優先できるよう、木の本数に応じたペナルティを目的関数へ加える。

## 配布ポリシー

通常は評価MAEが過去ベストを更新した場合だけ、`frontend/public` のブラウザ配布用モデルを更新する。

モデルサイズや読み込み速度を優先して、評価MAEが過去ベストより少し悪い最新モデルを採用したい場合は、学習時に `PUBLISH_POLICY=latest` を指定する。

```bash
make train-all PUBLISH_POLICY=latest
```

---

# 4. collect

## 責務

* 国交省データ取得
* ファイル保存
* Shift_JIS変換

---

## 取得元

```text
https://www.reinfolib.mlit.go.jp/realEstatePrices/
```

CSV/ZIPは公式ダウンロード画面をPlaywrightで操作して取得する。内部APIを直接呼び出さず、
Chrome上で都道府県、期間、中古マンション等、取引価格情報、成約価格情報を選択して
ダウンロードボタンを実行する。

現行モデルは最寄駅名と駅徒歩分を特徴量と価格推移集計に使用する。XIT001などの不動産価格API
レスポンスだけではこの2項目が揃わないため、地区名などで代用せず、学習用の不動産取引データは
CSV/ZIPを主入力にする。

```bash
make setup-csv-download
make download-csv CSV_PREFECTURES=tokyo CSV_FROM_YEAR=2025 CSV_TO_YEAR=2025
make download-csv-all
```

全国取得ではアクセス回数を抑えるため、都道府県ごとに全期間を1回取得し、ローカルで年別ZIPへ
分割する。正常な既存ZIPは再取得しない。CSV取得状況を確認したい場合だけ、`make csv-checklist`
で `TODO.md` のチェックリストを明示的に再生成する。

---

## 入力

なし

---

## 出力

```text
data/raw/
```

---

## 保存形式

```text
json
```

例

```text
data/raw/tokyo_2025_xit001.json
```

---

# 5. preprocess

## 責務

* UTF-8統一
* 型変換
* 欠損除去
* 外れ値除去

---

## 欠損値処理

MVPでは削除する。

```python
df = df.dropna()
```

---

## 外れ値処理

IQRを利用する。

対象

```text
price
area
```

築古、駅遠、高額帯、極端な平米単価は、すぐに除外せずエッジケースとして分布を確認する。

```bash
make summarize-edge-cases REGION=tokyo
```

出力:

```text
training/outputs/reports/{region}_edge_cases.json
training/outputs/reports/{region}_edge_cases.md
```

このレポートで件数、中央値、平米単価、駅徒歩、築年数の分布を確認し、前処理で除外するか、特徴量として残してモデルに学習させるかを判断する。高級物件や駅遠物件を一律に削除すると、実運用で入力された条件への外挿が弱くなるため、除外ルールはバックテストで確認してから採用する。

外れ値処理候補の比較は、モデル成果物を更新せずに次のコマンドで実行する。

```bash
make compare-outlier-filters
```

出力:

```text
training/outputs/comparisons/outlier_filter_backtest.json
training/outputs/comparisons/outlier_filter_backtest.md
```

初期候補は、現行前処理、高平米単価除外、高額帯除外、面積端除外、駅遠・築古除外、厳しめの複合除外を比較する。MAEだけでなく、除外率とテスト年ごとの件数を見て、実運用で入力されやすい築古・駅遠・高額物件を削りすぎないか確認する。

---

## 出力

```text
data/processed/
```

---

## 保存形式

```text
parquet
```

---

# 6. 特徴量

## MVP特徴量

### 地域

```text
prefecture
municipality
station
```

---

### 物件

```text
area
age
station_distance
room_layout
building_type
```

---

### 時系列

```text
transaction_year
```

---

# 7. FeatureProvider

## 目的

特徴量追加容易性を確保する。

外部特徴量も同じFeatureProvider境界に寄せる。学習設定の `features` または `categorical_features` に外部特徴量が含まれる場合だけ、対応するProviderを実行する。

初期対象:

```text
StationPassengerProvider
CommercialFacilityProvider
HazardProvider
```

各Providerは以下を責務とする。

* 入力CSVの存在確認
* 正規化済みCSVの読み込み
* 学習データへの結合
* 欠損時の既定値付与
* 出力特徴量のcontext登録

モデル本体は外部データソースへ直接依存しない。外部データの取得・正規化は `training/src/collect`、特徴量結合は `training/src/features` に分ける。

---

## Interface

```python
class IFeatureProvider:

    def fit(
        self,
        df
    ):
        pass

    def transform(
        self,
        df,
        context
    ):
        pass
```

---

# 8. MVP Provider

## AreaProvider

出力

```text
area
```

---

## AgeProvider

出力

```text
age
```

---

## LocationProvider

出力

```text
prefecture

municipality

station

station_distance
```

---

## BuildingProvider

出力

```text
room_layout

building_type
```

---

## TransactionProvider

出力

```text
transaction_year
```

---

# 9. FeatureContext

## 目的

Provider間データ共有

---

## 例

```python
context["area"]

context["station"]

context["transaction_year"]
```

---

## 制約

Provider同士の直接依存は禁止。

---

# 10. FeatureRegistry

## 登録方法

```python
registry.register(
    AreaProvider()
)

registry.register(
    AgeProvider()
)

registry.register(
    LocationProvider()
)

registry.register(
    BuildingProvider()
)

registry.register(
    TransactionProvider()
)
```

---

# 11. カテゴリ変数

カテゴリ変数は学習時にカテゴリ辞書を生成し、IDへ変換する。

ONNXとは別にカテゴリ辞書JSONを出力し、フロントエンド推論時も同一辞書で変換する。

LightGBMでは変換後のカテゴリIDをカテゴリ特徴量として扱う。

---

## 対象

```text
prefecture

municipality

station

room_layout

building_type
```

---

## 非対象

OneHotEncoding

辞書を保存しない一時的なLabelEncoding

---

## カテゴリ辞書

出力例

```json
{
  "stations": {
    "大宮": 123,
    "新宿": 456
  }
}
```

未登録カテゴリの扱いはunknown IDへ変換する。

---

# 12. Config

## 例

```yaml
region: tokyo

features:
  - area
  - age
  - municipality
  - station_distance
  - room_layout
  - building_type
  - transaction_year
  - station_passenger_log
  - station_line_count
  - station_operator_count
  - effective_station_scale
  - has_station_passenger_data
  - station_rank

categorical_features:
  - prefecture
  - municipality
  - room_layout
  - building_type
  - station_rank
```

4都県の個別モデルは、ブラウザ配布サイズを抑えるため `station` カテゴリを外し、駅別乗降客数から作る軽量な駅規模特徴量を利用する。駅別乗降客数CSVは `station_passengers_csv` で指定する。

---

# 13. 学習

## モデル

```text
LightGBM
```

---

## 目的変数

```text
price
```

---

## ハイパーパラメータ探索

```text
Optuna
```

---

## 学習成果物

```text
pkl
```

---

## 付随成果物

```text
カテゴリ辞書JSON
モデルメタデータJSON
価格推移集計JSON
```

---

# 14. 評価

## 主指標

```text
MAE
```

---

## 補助指標

```text
RMSE

MAPE
```

---

# 15. 検証

## ホールドアウト

例

```text
2005-2024

↓

train

2025

↓

test
```

---

## 時系列CV

未来データが学習へ混入しないこと。

---

# 16. モデル採用基準

## latest更新条件

```text
新モデルMAE

<

現latestモデルMAE
```

---

更新されない場合もモデルは保存する。

---

# 17. モデル出力

## pkl

保存する。

用途

```text
再学習

分析

デバッグ
```

---

## ONNX

オプション指定時のみ出力。

---

### 実行例

```bash
python train.py \
  --config configs/tokyo.yaml \
  --export-onnx
```

---

## カテゴリ辞書JSON

学習時に生成し、ONNXとは別ファイルとして出力する。

フロントエンドのModelManagerが読み込み、文字列入力からカテゴリIDへ変換する。

---

## モデルメタデータJSON

評価時に算出したMAEを含める。

MVPでは参考価格帯を以下で表示するために利用する。これは統計的な信頼区間ではなく、検証データの平均絶対誤差を使った目安である。

```text
予測価格 ± MAE
```

---

## 価格推移集計JSON

学習データを最寄駅単位・年単位で集計して出力する。

学習データ全件はブラウザへ配布しない。

将来価格シミュレーション用の駅別・地域別トレンド集計も同じ履歴エクスポートで生成する。

```bash
make histories-national
```

出力:

```text
frontend/public/histories/{region}_trend_summary.json
```

このJSONは年別平均平米単価から年率トレンドと変動幅を集約したもので、生の取引明細は含めない。

例

```json
{
  "station": "大宮",
  "year": 2024,
  "avg_price": 42000000
}
```

---

# 18. モデル保存

## 保存先

```text
outputs/models/
```

---

## 例

```text
tokyo_20260821.pkl

tokyo_20260821.onnx

tokyo_20260821_categories.json

tokyo_20260821_metadata.json

tokyo_20260821_history.json

tokyo_latest.onnx
```

---

## 配信用コピー

export処理は成果物をfrontend配信用ディレクトリへ自動コピーする。

```text
training/outputs/models/

↓

frontend/public/models/
frontend/public/metadata/
frontend/public/histories/
frontend/public/model-manifest.json
```

手動コピー運用は行わない。

モデルを配信用ディレクトリへコピーした後、配置済みONNXのSHA-256と容量を`model-manifest.json`へ自動出力する。新しい地域モデルはマニフェストへ自動追加され、フロントエンドの優先ダウンロードとバージョン別キャッシュの対象になる。

## モデル容量比較

現行の都県別モデルと首都圏共通モデルの精度、ONNX容量、gzip後容量、学習時間を同じ2025年ホールドアウトで比較する。

```bash
make compare-models
```

比較用ONNX、カテゴリ辞書、JSON、Markdownレポートは`training/outputs/comparisons/`へ出力する。比較モデルは`frontend/public`へ自動配置しない。

全国1モデルと8地方クラスタモデルを比較する場合は、全国CSVを比較用Parquetへ変換してから比較する。

```bash
make preprocess-national
make compare-national-models
```

全国比較では、北海道、東北、関東、中部、近畿、中国、四国、九州・沖縄の8クラスタを使用する。合計ONNX容量に加えて、ユーザーが地域選択時に取得する最大1モデル容量も記録する。

## モデル説明

モデル全体の特徴量重要度は、学習時にメタデータへ出力する。

個別予測の説明にSHAPを使う場合は、ブラウザ上では計算せず、学習側で集計JSONを生成する方式を優先する。詳細は `docs/model-explainability.md` に記載する。

## 推奨構成の本番生成

首都圏4都県の専用モデルと8地方160木モデルを、前処理から配信用コピーまで一括生成する。

```bash
make train-production-models
```

このコマンドは次を順に実行する。

1. 全国2005〜2025年CSVを`national.parquet`へ変換
2. 首都圏4都県も2005〜2025年CSVから個別Parquetを再生成
3. 東京、神奈川、埼玉、千葉の専用モデルを再学習して公開
4. 8地方モデルを2025年ホールドアウトで評価
5. 2025年を含む全件で8地方モデルを再学習
6. ONNX、カテゴリ辞書、メタデータ、価格推移を`frontend/public`へ配置
7. `model-manifest.json`のハッシュと容量を更新

首都圏モデルを再学習せず、全国Parquetから地方モデルだけを更新する場合は次を使う。

```bash
make train-regional-models
```

## 本番成果物更新ワークフロー

データ取得、前処理、本番用モデル生成、価格推移、駅マスタ、特徴量順序チェック、フロントエンドビルドまでをローカルでまとめて実行する場合は次を使う。

```bash
make refresh-production-artifacts ALLOW_MODEL_UPDATE=1
```

このコマンドはブラウザ配信用のONNX、メタデータ、価格推移、駅マスタを更新するため、誤実行を避ける目的で `ALLOW_MODEL_UPDATE=1` を必須にする。

実行前に手順だけ確認する場合は、Makeのドライランを使う。

```bash
make -n refresh-production-artifacts ALLOW_MODEL_UPDATE=1
```

ハザード特徴量や全国範囲の駅別乗降客数を本番モデルへ採用する場合は、先に対応する取得・比較TODOを完了し、設定ファイルの特徴量を確定してからこのワークフローへ組み込む。

全国47都道府県の駅マスタを再生成する場合は、外部駅APIへ接続できる環境で次を実行する。

```bash
make stations-national
```

---

# 19. 実験管理

## 学習開始時

experiments

```text
status=running
```

---

## 成功

```text
status=success
```

---

## 失敗

```text
status=failed
```

---

失敗した実験も保存する。

---

# 20. データセットキャッシュ

## 保存先

```text
data/cache/
```

---

## 保存形式

```text
parquet
```

---

## 目的

* 再実行高速化
* 開発効率向上

---

# 21. 将来追加予定

## CommercialFacilityProvider

例

```text
sc_count_within_1km
sc_count_within_3km
nearest_sc_distance_km
nearest_sc_opened_years
sc_store_area_sum_within_3km
sc_tenant_count_sum_within_3km
```

データソースは日本ショッピングセンター協会（JCSC）のオープンSC一覧表を利用する。

取得・正規化仕様は `docs/commercial-facilities.md` に記載する。

初期モデル投入時は、取引年以前に開業済みのSCだけを集計し、未来情報の混入を避ける。

店舗面積、テナント数、ディベロッパー、キーテナントは分析用に保持し、欠損率・重要度・評価指標を確認して採否を判断する。

---

## PopulationProvider

例

```text
人口

人口密度
```

---

## RailwayProvider

例

```text
路線数

乗換数

station_passenger_count

station_passenger_log

station_line_count
```

駅別乗降客数は不動産情報ライブラリの国土数値情報（駅別乗降客数）API `XKT015` から取得する。

取得・正規化仕様は `docs/station-passengers.md` に記載する。

初期比較では `station_passenger_log`、`station_line_count`、`station_operator_count`、`effective_station_scale`、`has_station_passenger_data` を優先し、`station_rank` は小さなカテゴリ特徴量として比較候補に含める。

バックテストは以下で実行する。

```bash
make compare-station-passenger-features
```

首都圏の初期比較では、既存の `station` カテゴリを残すなら数値の駅規模特徴量は小さな改善に留まる。一方で `station` カテゴリを外す軽量モデルでは駅規模特徴量の効果が大きく、ブラウザ配布サイズを抑える候補として有望。

ブラウザ推論ではAPIを呼ばず、学習側で生成した軽量JSONまたはモデル入力済み特徴量を利用する。

## SurroundingFacilityProvider

候補:

```text
nearest_large_park_distance_km
large_park_count_within_3km
nearest_hospital_distance_km
hospital_count_within_3km
nearest_university_distance_km
university_count_within_3km
redevelopment_project_count_last_5y
```

周辺特徴量の追加方針は `docs/surrounding-features.md` に記載する。

初期実装では、施設名を大量のカテゴリ特徴量にせず、距離、件数、面積合計、データ有無に絞って比較する。

---

# 22. 非目標

現時点では実施しない。

```text
MLFlow

Feature Store

分散学習

AutoML

GPU学習
```

---

# 23. 完了条件

以下を満たしたら学習基盤完成とする。

* データ取得できる
* 学習できる
* MAE算出できる
* ONNX出力できる
* 実験履歴保存できる
* latest管理できる
