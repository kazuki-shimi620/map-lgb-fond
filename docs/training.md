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
│
├── src/
│
│   ├── collect/
│   ├── preprocess/
│   ├── features/
│   ├── train/
│   ├── evaluate/
│   ├── export/
│   └── experiment/
│
├── outputs/
│
├── data/
│
└── db/
```

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

不動産情報ライブラリの不動産価格（取引価格・成約価格）情報取得APIを利用する。

APIキーは環境変数で管理する。

```text
REINFOLIB_API_KEY
```

ローカルでは `training/.env.example` を `training/.env` にコピーして設定する。`training/.env` は
Git管理しない。collect CLIはこのファイルを自動で読み込むため、APIキーをコマンドライン引数へ
直接記載しない。

MVPでは価格情報区分を不動産取引価格情報のみにする。

```text
priceClassification=01
```

APIはブラウザから直接呼び出さず、training側のcollect処理で利用する。

単一地域・単一年の取得:

```bash
make collect REGION=tokyo YEAR=2025
```

対象4地域・2005〜2025年の一括取得:

```bash
make collect-all
```

APIキー未設定、HTTPエラー、不正なJSON、`status != OK` はエラー終了とする。

XIT001のJSONには最寄駅名と駅徒歩分が含まれない。現行モデルは両項目を特徴量と価格推移の集計に
使用しているため、同等情報を持つCSV/ZIP経路は削除しない。APIレスポンスの `DistrictName` を
駅名として代用せず、APIデータだけで前処理条件を満たせない場合は明示的にエラー終了する。
したがって現時点のAPI取得はraw JSONの保存とAPI連携確認までを責務とし、現行モデルの再学習には
最寄駅名・駅徒歩分を含むCSV/ZIPを使用する。

CSV/ZIPは公式ダウンロード画面をPlaywrightで操作して取得する。内部APIを直接呼び出さず、
Chrome上で都道府県、期間、中古マンション等、取引価格情報、成約価格情報を選択して
ダウンロードボタンを実行する。

```bash
make setup-csv-download
make download-csv CSV_PREFECTURES=tokyo CSV_FROM_YEAR=2025 CSV_TO_YEAR=2025
make download-csv-all
```

全国取得ではアクセス回数を抑えるため、都道府県ごとに全期間を1回取得し、ローカルで年別ZIPへ
分割する。正常な既存ZIPは再取得せず、各ファイルの完了状況を `TODO.md` に同期する。

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
  - station
  - municipality
  - station_distance
  - room_layout
  - building_type
  - transaction_year
```

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

MVPでは信頼区間を以下で表示するために利用する。

```text
予測価格 ± MAE
```

---

## 価格推移集計JSON

学習データを最寄駅単位・年単位で集計して出力する。

学習データ全件はブラウザへ配布しない。

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
