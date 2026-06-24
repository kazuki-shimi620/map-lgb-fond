# frontend.md

# フロントエンド仕様

本ドキュメントはフロントエンドの実装仕様を定義する。

対象は `frontend/` ディレクトリ配下の実装である。

---

# 1. 目的

フロントエンドは以下を目的とする。

* 物件情報入力
* 地図選択
* モデルロード
* 価格予測
* 価格推移表示

学習処理は行わない。

---

# 2. 技術スタック

```text
React
TypeScript
Vite
Leaflet
ONNX Runtime Web
Recharts
```

---

# 3. ディレクトリ構成

```text
frontend/

src/

├── features/
│
│   ├── map/
│   │
│   ├── prediction/
│   │
│   └── model/
│
├── components/
│
├── hooks/
│
├── services/
│
├── types/
│
└── utils/

public/

├── models/
├── metadata/
├── histories/
└── stations/
```

---

# 4. Feature構成

## map

責務

* 地図表示
* 地図クリック
* 地域取得

---

## prediction

責務

* フォーム表示
* リクエスト生成
* 結果表示

---

## model

責務

* モデルロード
* 推論実行
* カテゴリ辞書ロード
* 文字列入力からカテゴリIDへの変換

---

# 5. 画面構成

MVPでは単一画面とする。

---

## HomePage

表示内容

```text
地図

↓

物件入力フォーム

↓

予測ボタン

↓

予測結果

↓

価格推移グラフ
```

---

# 6. 画面レイアウト

```text
+----------------------+
|       地図           |
+----------------------+

+----------------------+
|     入力フォーム     |
+----------------------+

+----------------------+
|     予測ボタン       |
+----------------------+

+----------------------+
|     予測結果         |
+----------------------+

+----------------------+
|     価格推移         |
+----------------------+
```

---

# 7. 地図機能

## ライブラリ

```text
Leaflet
```

---

## 地図検索

地図パネルの中央上部に地名検索ボックスを表示する。

ユーザーが地名を入力して検索した場合、Nominatim の forward geocoding を利用して該当地点へ地図を移動する。

検索による地図移動だけでは物件位置を確定しない。物件位置、最寄駅、駅徒歩の更新は地図クリック時に行う。

---

## 取得情報

```typescript
prefecture
municipality
station

lat
lon
```

---

## 動作

```text
地図クリック

↓

位置取得

↓

逆ジオコーディングAPIで都道府県・市区町村取得

↓

駅マスタCSVとの距離計算

↓

最寄駅決定

↓

フォーム反映
```

MVPでは駅マスタの件数が限定的なため、最寄駅検索は全件総当たりで行う。

全国対応時はKDTree等の空間検索へ移行可能な構造にする。

---

# 8. 地域入力

地図入力後も編集可能とする。

---

## 入力項目

```text
都道府県

市区町村

最寄駅
```

---

## 最寄駅

検索可能なプルダウンを利用する。

例

```text
大

↓

大宮
大森
大塚
```

---

# 9. 物件入力フォーム

## 数値入力

```text
面積

築年数

駅徒歩

予測年
```

---

## 選択入力

```text
間取り

建物構造
```

---

# 10. PredictionRequest

推論用DTO。

---

## Interface

```typescript
export type PredictionRequest = {

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

---

# 11. PredictionResult

推論結果DTO。

---

## Interface

```typescript
export type PredictionResult = {

  predictedPrice: number;

  pricePerSquareMeter: number;

  lowerPrice: number;

  upperPrice: number;
};
```

---

# 12. ModelManager

モデル管理クラス。

---

## 責務

* モデルロード
* 推論
* 前処理
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

---

## 推論前変換

ONNX Runtime Webへ渡す前に、ModelManagerが文字列入力を数値特徴量へ変換する。

学習時に生成されたカテゴリ辞書JSONを読み込む。

例

```json
{
  "stations": {
    "大宮": 123,
    "新宿": 456
  }
}
```

変換対象

```text
prefecture
municipality
station
roomLayout
buildingType
```

---

# 13. モデルロード

都道府県ごとにロードする。

---

## 例

```text
東京都

↓

tokyo_latest.onnx

↓

ロード
```

---

## 保存先

```text
public/models/
```

関連メタデータは以下に配置する。

```text
public/metadata/
public/histories/
public/stations/
```

---

# 14. モデル未対応地域

モデル未配置地域は選択できない。

---

例

```text
北海道

↓

選択不可
```

---

# 15. 推論フロー

```text
フォーム入力

↓

PredictionRequest生成

↓

ModelManagerでカテゴリ変換

↓

ModelManager.predict()

↓

PredictionResult

↓

画面表示
```

---

# 16. 推論シーケンス

```mermaid
sequenceDiagram

    actor User

    User->>Form:
    入力

    Form->>PredictionRequest:
    作成

    PredictionRequest->>ModelManager:
    predict()

    ModelManager->>ModelManager:
    category id conversion

    ModelManager->>ONNXRuntime:
    execute

    ONNXRuntime-->>ModelManager:
    result

    ModelManager-->>Form:
    PredictionResult

    Form-->>User:
    表示
```

---

# 17. 予測結果表示

表示内容

```text
予測価格

平米単価

信頼区間
```

---

## 表示例

```text
予測価格

5,234万円

平米単価

87万円/㎡

信頼区間

4,900万円
～
5,600万円
```

---

# 18. 価格推移

## ライブラリ

```text
Recharts
```

---

## 表示内容

```text
過去価格推移

現在価格

将来予測
```

過去価格推移は学習データ全件ではなく、学習時に生成した集計済みJSONを読み込む。

MVPでは最寄駅単位・年単位で集計する。

学習データ範囲外の将来年を表示する場合、グラフの中間年は単なる直線補間にしない。

学習最終年のモデル予測値を基点に、駅別または地域別の価格推移トレンドを各年に適用した予測点を表示する。

---

## グラフ

同一グラフに表示する。

---

## イメージ

```text
過去

|

|

現在

|

|

将来
```

---

# 19. グラフデータ

## Interface

```typescript
type PriceHistoryPoint = {

  year: number;

  price: number;
};
```

集計済みJSONの例

```json
{
  "station": "大宮",
  "year": 2024,
  "avg_price": 42000000
}
```

学習データ全件をブラウザへ配布しない。

---

# 20. React状態管理

状態管理ライブラリは利用しない。

---

利用可能

```typescript
useState

useMemo

useEffect
```

---

利用しない

```text
Redux

Zustand

MobX
```

---

# 21. エラーハンドリング

## モデルロード失敗

表示

```text
モデルの読み込みに失敗しました
```

---

## 推論失敗

表示

```text
価格予測に失敗しました
```

---

## 必須入力不足

表示

```text
入力内容を確認してください
```

---

## 長期将来予測

学習データの最新年から10年を超える予測年が入力された場合は警告を表示する。

将来年の予測は、LightGBM の transaction_year 特徴量だけでは外挿できないため、学習最終年のモデル予測値に価格推移トレンドを加えて算出する。

駅別価格推移が2点以上ある場合は駅別トレンドを利用し、不足する場合は地域全体の年別平均価格トレンドを利用する。

表示

```text
長期予測のため精度は保証できません
```

---

# 22. 駅マスタ

CSV管理とする。

---

## 駅徒歩計算

地図クリック時の最寄駅探索では、駅マスタとの直線距離を Haversine で算出する。

フォームに反映する駅徒歩は距離kmをそのまま使わず、以下で徒歩分に変換する。

```text
徒歩分 = ceil(直線距離km × 1000 × 1.25 / 80)
```

80mを徒歩1分とし、直線距離から実移動距離への補正として 1.25 を掛ける。

最低値は1分とする。

---

## 項目

```text
station_id

station_name

prefecture

line_name

lat

lon
```

---

## 最寄駅取得

地図クリック時の緯度経度と駅マスタCSVの緯度経度から距離を計算し、最寄駅を決定する。

MVPでは総当たり探索を利用する。

---

# 23. 信頼区間

MVPでは評価時に算出したMAEを利用し、以下の方式で表示する。

```text
予測価格 ± MAE
```

MAEはモデルメタデータJSONから読み込む。

---

# 24. 将来対応

## GeoJSON

外部APIを利用しない地域判定。

---

## 全国対応

モデル追加のみで対応可能な構造とする。

---

## 商業施設表示

将来的な追加候補。

---

# 25. 非目標

MVPでは実施しない。

```text
ユーザー管理

ログイン

会員登録

お気に入り

予測履歴保存

アクセス解析

SNS機能
```

---

# 26. 完了条件

以下を満たしたらフロントエンド完成とする。

* 地図が表示できる
* 地域取得できる
* 入力できる
* モデルロードできる
* 推論できる
* 価格表示できる
* グラフ表示できる
* GitHub Pagesで動作する
