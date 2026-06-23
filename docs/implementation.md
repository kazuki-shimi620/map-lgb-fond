# implementation.md

# 不動産価格予測システム 実装仕様書

本ドキュメントは AI エージェント（Codex / Claude Code 等）による実装を前提とした実装仕様書である。

requirements.md の内容を実装レベルまで具体化する。

---

# 1. 設計原則

## MUST

* requirements.md を満たすこと
* MVPを優先すること
* 過剰設計を避けること
* FeatureProviderによる特徴量拡張を可能にすること
* サーバーレス推論を前提とすること
* 学習と推論を分離すること
* 都道府県単位でモデルを管理可能にすること

## SHOULD

* 新しい特徴量追加時に既存コード修正を最小限にする
* 新しいデータソース追加時に既存コード修正を最小限にする
* 全国対応を想定した構造にする

## MAY

* 商業施設特徴量追加
* 人口統計特徴量追加
* GeoJSON判定への移行
* モデル比較機能追加

---

# 2. リポジトリ構成

```text
repo/

├── frontend/
│
├── training/
│
├── docs/
│   ├── requirements.md
│   ├── implementation.md
│   ├── architecture.md
│   ├── frontend.md
│   ├── training.md
│   └── database.md
│
└── README.md
```

---

# 3. frontend構成

```text
frontend/

src/

├── features/
│   ├── map/
│   ├── prediction/
│   └── model/
│
├── components/
│
├── services/
│
├── types/
│
├── hooks/
│
└── utils/

public/

├── models/
│   ├── tokyo_latest.onnx
│   ├── saitama_latest.onnx
│   ├── chiba_latest.onnx
│   └── kanagawa_latest.onnx
│
├── metadata/
│
├── histories/
│
└── stations/
```

---

# 4. training構成

```text
training/

├── configs/
│   ├── tokyo.yaml
│   ├── saitama.yaml
│   ├── chiba.yaml
│   └── kanagawa.yaml
│
├── src/
│
│   ├── collect/
│   │
│   ├── preprocess/
│   │
│   ├── features/
│   │
│   ├── train/
│   │
│   ├── evaluate/
│   │
│   ├── export/
│   │
│   └── experiment/
│
├── outputs/
│
│   ├── models/
│   │
│   ├── reports/
│   │
│   └── datasets/
│
├── data/
│
│   ├── raw/
│   ├── processed/
│   └── cache/
│
└── db/
    └── experiments.db
```

---

# 5. 学習パイプライン

実行順序

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

---

## collect

責務

* 国交省データ取得
* Shift_JIS → UTF-8変換
* 生データ保存

取得元

```text
https://www.reinfolib.mlit.go.jp/realEstatePrices/
```

不動産情報ライブラリAPIを利用する。

APIキーは `REINFOLIB_API_KEY` 環境変数から読み込む。

ブラウザからAPIを直接呼ばない。

出力

```text
data/raw/
```

---

## preprocess

責務

* 欠損除去
* 型変換
* 外れ値除去(IQR)

出力

```text
data/processed/
```

Parquet形式で保存する。

---

## feature

責務

* FeatureProvider実行
* FeatureContext生成
* 学習用DataFrame生成

---

## train

責務

* LightGBM学習
* Optuna最適化

成果物

```text
model.pkl
```

---

## evaluate

責務

* MAE計算
* RMSE計算
* MAPE計算
* 時系列CV

---

## export

責務

* ONNX出力
* モデル世代管理
* latest更新
* カテゴリ辞書JSON出力
* モデルメタデータJSON出力
* 価格推移集計JSON出力
* frontend/public への配信用コピー

---

# 6. FeatureProvider

特徴量追加を容易にするためProviderパターンを採用する。

---

## IFeatureProvider

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

# 7. FeatureContext

Provider間で特徴量を受け渡すために利用する。

```python
context["area"]

context["station"]

context["building_type"]
```

FeatureProviderは直接依存してはならない。

FeaturePipelineが実行順序を管理する。

---

# 8. FeatureRegistry

Providerは明示登録とする。

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

自動探索は行わない。

---

# 9. FeatureMetadata

特徴量情報を保持する。

```python
{
    "feature_name": "area",
    "dtype": "float"
}
```

実験管理で利用する。

---

# 10. Config

例

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

# 11. モデル管理

保存先

```text
outputs/models/
```

保存形式

```text
tokyo_20260821.onnx

tokyo_20260821_categories.json

tokyo_20260821_metadata.json

tokyo_20260821_history.json

tokyo_latest.onnx
```

---

## latest更新条件

ベストMAE更新時のみ。

---

# 12. ONNX出力

学習時に常時出力しない。

例

```bash
python train.py \
  --config tokyo.yaml \
  --export-onnx
```

---

# 13. PredictionRequest

フロントから推論に渡す入力。

```typescript
type PredictionRequest = {
  prefecture: string;
  municipality: string;
  station: string;

  area: number;
  age: number;
  stationDistance: number;

  roomLayout: string;
  buildingType: string;

  predictionYear: number;
};
```

名称ベースで管理する。

IDベース管理は行わない。

---

# 14. ModelManager

責務

* モデルロード
* 推論実行
* 推論前変換
* カテゴリ辞書ロード
* モデルメタデータロード

---

## Interface

```typescript
class ModelManager {

  loadMetadata()

  loadModel()

  loadCategoryDictionary()

  predict()
}
```

推論前変換では、カテゴリ辞書JSONを利用して文字列入力をカテゴリIDへ変換する。

---

# 15. React状態管理

状態管理ライブラリは利用しない。

利用

```typescript
useState
useMemo
useEffect
```

---

# 16. 地図機能

ライブラリ

```text
Leaflet
```

---

取得項目

```text
prefecture
municipality
station

lat
lon
```

地図クリック時は緯度経度と駅マスタCSVの距離計算により最寄駅を決定する。

MVPでは総当たり探索を利用する。

全国対応時はKDTree等へ移行可能な構造とする。

---

地図クリック後も編集可能とする。

---

# 17. 駅マスタ

CSV管理とする。

保持項目

```text
station_id
station_name
prefecture
line_name
lat
lon
```

---

# 18. 価格推移

過去価格推移

```text
年単位
```

---

データソース

```text
学習時に生成した集計済みJSON
```

学習データ全件はブラウザへ配布しない。

MVPでは最寄駅単位・年単位で集計する。

---

# 19. 将来予測

入力

```text
predictionYear
```

のみ。

月単位は扱わない。

学習データ範囲外の年も入力可能とする。

MVPでは、学習データ範囲外の将来年を LightGBM の transaction_year 特徴量だけに任せない。

将来年の予測は以下の流れで算出する。

```text
学習最終年のモデル予測値
+
駅別価格推移トレンド × 経過年数
```

駅別トレンドが算出できない場合は、地域全体の価格推移トレンドを利用する。

価格推移グラフに表示する中間年も直線補間ではなく、各年の将来補正値を表示する。

学習データの最新年から10年を超える場合は警告を表示する。

---

# 20. 信頼区間

表示形式

```text
4,700万円 ～ 5,300万円
```

MVPでは評価時に算出したMAEを利用し、以下で算出する。

```text
予測価格 ± MAE
```

MAEはモデルメタデータJSONから読み込む。

---

# 21. 商業施設特徴量

MVP対象外。

追加時はFeatureProviderとして実装する。

想定特徴量

```text
コンビニ件数
スーパー件数

最寄コンビニ距離
最寄スーパー距離
```

データソースはCSVを利用する。

必要に応じてSQLiteへ移行する。

---

# 22. 実験管理

学習開始時にレコード作成。

学習終了時に更新。

失敗時も記録する。

---

管理対象

```text
datasets
features
models
experiments
```

詳細定義は database.md に記載する。

---

# 23. ログ

標準 logging を利用する。

外部ライブラリは導入しない。

---

# 24. README構成

```text
1. プロジェクト目的

2. システム構成

3. 学習構成

4. 画面イメージ

5. 実行方法
```

---

# 25. 実装優先順位

Phase 1

* データ取得
* 前処理
* LightGBM学習
* ONNX出力

Phase 2

* React UI
* 地図入力
* 推論画面

Phase 3

* 実験管理
* モデル管理
* ドキュメント整備

Phase 4

* 商業施設特徴量
* 全国対応
* GeoJSON対応
