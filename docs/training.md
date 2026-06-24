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
2020〜2024年で学習
2025年で評価

配布:
評価完了後、2020〜2025年の全データで再学習
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

MVPでは価格情報区分を不動産取引価格情報のみにする。

```text
priceClassification=01
```

APIはブラウザから直接呼び出さず、training側のcollect処理で利用する。

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
2020-2024

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
```

手動コピー運用は行わない。

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
コンビニ件数

スーパー件数

最寄施設距離
```

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
```

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
