# hazard-maps.md

# ハザードマップ・災害リスク評価仕様

本ドキュメントは、不動産価格予測アプリで指定地点の災害リスクを表示・評価するための仕様を定義する。

価格予測とは独立した情報として災害リスクを提示し、ユーザーが価格、利便性、安全性を分けて比較できる状態を目指す。

---

# 1. 目的

指定地点について、洪水、土砂災害、津波、高潮などの公開ハザード情報を取得・正規化し、以下を表示する。

* ハザード区域に含まれるか
* 想定浸水深または警戒区域種別
* 災害リスク評価スコア
* 地図上のハザードレイヤー
* 出典と公的ハザードマップへの導線

初期段階では、災害リスクを価格予測モデルの補正値として直接利用しない。将来的に特徴量として利用する場合は、別候補モデルとしてバックテストする。

---

# 2. MVP対象

| ハザード種別 | ID | MVP | 評価内容 |
| --- | --- | ---: | --- |
| 洪水浸水想定 | `flood` | ○ | 浸水深 |
| 土砂災害 | `landslide` | ○ | 警戒区域・特別警戒区域 |
| 津波浸水想定 | `tsunami` | ○ | 浸水深 |
| 高潮浸水想定 | `storm_surge` | ○ | 浸水深 |
| 内水氾濫 | `inland_flood` | △ | 浸水深 |
| 家屋倒壊等氾濫想定 | `flood_collapse` | △ | 氾濫流・河岸侵食 |
| 浸水継続時間 | `flood_duration` | 将来 | 継続時間 |
| 指定緊急避難場所 | `shelter` | 将来 | 距離・対応災害 |
| 活断層 | `active_fault` | 将来 | 最寄り断層距離 |
| 地形分類 | `landform` | 将来 | 低地・盛土地等 |

`△` はデータ提供範囲と取得方法を確認してから有効化する。

---

# 3. データソース

## 3.1 重ねるハザードマップ

地図表示には、国土交通省・国土地理院の重ねるハザードマップのラスタタイルを利用する。

洪水タイル例:

```text
https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png
```

用途:

* Leafletでのハザードレイヤー表示
* ユーザーによる視覚的なリスク確認
* APIキーなしのMVP表示

制約:

* ラスタタイルだけでは指定地点の属性値を直接取得できない
* 浸水深、区域名、告示情報などの数値判定には別データが必要
* 出典表記を必ず表示する

## 3.2 不動産情報ライブラリAPI

地点判定や属性取得には、不動産情報ライブラリAPIまたは国土数値情報由来のGeoJSON/PBFを利用する。

APIキーはHTTPヘッダーで送信する。

```http
Ocp-Apim-Subscription-Key: {API_KEY}
```

ブラウザから直接呼び出さない。APIキー秘匿とCORS回避のため、MVPでAPI判定を行う場合は中継APIを利用する。

## 3.3 国土数値情報

完全静的構成や学習特徴量化では、国土数値情報のGISデータを事前処理して利用する。

用途:

* H3セル単位の事前集計
* ポイント・イン・ポリゴン判定
* GitHub Pages向け静的JSON生成
* 学習用ハザード特徴量生成

---

# 4. 推奨構成

## 4.1 MVP構成

```text
React
  -> Leaflet
  -> 重ねるハザードマップ ラスタタイル

React
  -> Hazard Proxy API
  -> Cache
  -> 不動産情報ライブラリAPI
```

価格予測は引き続きONNX Runtime Webでブラウザ内実行する。災害リスク判定は価格推論と並列に実行する。

中継API候補:

1. Cloudflare Workers
2. Google Apps Script
3. Vercel Functions
4. Netlify Functions
5. FastAPI

第一候補はCloudflare Workersとする。

## 4.2 完全静的構成

ランニングコストとAPI依存を減らす場合は、国土数値情報を事前処理して静的JSONとして配信する。

```text
国土数値情報 GeoJSON
  -> Python前処理
  -> ポリゴン正規化
  -> H3セル集計
  -> 都道府県・H3別JSON
  -> GitHub Pages
```

初期H3解像度候補:

| 用途 | H3 Resolution | 粒度 |
| --- | ---: | --- |
| 大まかなリスク表示 | 8 | 数百m単位 |
| 不動産地点判定 | 9 | 約100〜200m単位 |
| 詳細地点判定 | 10 | 数十m単位 |

区域境界付近ではH3セルだけで断定せず、元ポリゴンでのポイント・イン・ポリゴン判定へフォールバックする。

---

# 5. 内部API

## 5.1 地点ハザード評価API

```http
GET /api/v1/hazards/assessment
```

Query:

| パラメータ | 型 | 必須 | 内容 |
| --- | --- | ---: | --- |
| `lat` | number | ○ | 緯度 |
| `lng` | number | ○ | 経度 |
| `radius` | number | - | 周辺検索半径m |
| `types` | string | - | カンマ区切りのハザード種別 |
| `detail` | boolean | - | 詳細情報を返すか |
| `version` | string | - | 評価ロジックバージョン |

Response概要:

```json
{
  "location": {
    "latitude": 35.681236,
    "longitude": 139.767125,
    "meshCode": "53394611",
    "h3Index": "892f5a37583ffff"
  },
  "assessment": {
    "score": 72,
    "grade": "B",
    "level": "moderate",
    "label": "一部の災害リスクに注意",
    "confidence": "medium",
    "evaluatedHazardCount": 4,
    "availableHazardCount": 4
  },
  "hazards": {},
  "metadata": {
    "scoringVersion": "1.0.0",
    "dataSource": ["MLIT_REAL_ESTATE_INFORMATION_LIBRARY", "GSI_HAZARD_MAP_PORTAL"],
    "evaluatedAt": "2026-07-10T02:00:00Z",
    "disclaimer": "本結果は公開データを機械的に整理した参考情報です。正式な判断には自治体等の最新ハザードマップをご確認ください。"
  }
}
```

## 5.2 地図レイヤー定義

レイヤーURLはコードへ分散して書かず、定義ファイルで一元管理する。

```json
{
  "layers": [
    {
      "id": "flood",
      "name": "洪水浸水想定区域",
      "type": "raster",
      "tileUrl": "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png",
      "minZoom": 2,
      "maxZoom": 17,
      "defaultOpacity": 0.65,
      "enabled": true,
      "attribution": "ハザードマップポータルサイト"
    }
  ]
}
```

静的配信する場合の配置候補:

```text
frontend/public/hazards/layers.json
```

---

# 6. フロントエンド型

```typescript
export type HazardType =
  | "flood"
  | "inland_flood"
  | "landslide"
  | "tsunami"
  | "storm_surge"
  | "flood_collapse"
  | "flood_duration"
  | "shelter";

export type HazardStatus =
  | "affected"
  | "not_affected"
  | "unknown"
  | "not_applicable";

export type RiskLevel = 0 | 1 | 2 | 3 | 4 | 5;

export interface HazardDetail {
  status: HazardStatus;
  riskLevel: RiskLevel | null;
  score: number | null;
  depth?: {
    min: number | null;
    max: number | null;
    unit: "m";
    category: string | null;
  } | null;
  zoneType?: string | null;
  scenario?: string | null;
  message: string;
  sourceAvailable: boolean;
}
```

---

# 7. 正規化

## 7.1 共通形式

```typescript
interface NormalizedHazardFeature {
  hazardType: HazardType;
  geometryType: "Point" | "LineString" | "Polygon" | "MultiPolygon";
  geometry: GeoJSON.Geometry | null;
  riskCategory: string | null;
  riskLevel: RiskLevel | null;
  depthMin: number | null;
  depthMax: number | null;
  durationMinHours: number | null;
  durationMaxHours: number | null;
  zoneType: string | null;
  scenario: string | null;
  authority: string | null;
  designatedDate: string | null;
  sourceDataset: string;
  sourceVersion: string | null;
  prefectureCode: string | null;
  municipalityCode: string | null;
}
```

## 7.2 浸水深

浸水深は表示文字列ではなく、可能な限り数値範囲へ変換する。

| 区分 | depthMin | depthMax | riskLevel |
| --- | ---: | ---: | ---: |
| `0.5m未満` | 0 | 0.5 | 1 |
| `0.5m以上3.0m未満` | 0.5 | 3.0 | 3 |
| `3.0m以上5.0m未満` | 3.0 | 5.0 | 4 |
| `5.0m以上10.0m未満` | 5.0 | 10.0 | 5 |
| `10.0m以上20.0m未満` | 10.0 | 20.0 | 5 |
| `20.0m以上` | 20.0 | null | 5 |

文字列解析では `m以上m未満`、`m未満`、`m以上` の表記ゆれへ対応する。

## 7.3 土砂災害

| 区域 | riskLevel | score |
| --- | ---: | ---: |
| 区域外 | 0 | 100 |
| 土砂災害警戒区域 | 4 | 30 |
| 土砂災害特別警戒区域 | 5 | 0 |
| データなし | null | null |

同一地点が複数区域に含まれる場合は、最も高いリスクを代表値とし、明細には全該当情報を保持する。

---

# 8. 地点包含判定

GeoJSONの座標順序は `[longitude, latitude]` とする。

```text
Point(latitude, longitude)
  -> 候補ポリゴンのBounding Box判定
  -> Point in Polygon判定
  -> 該当Featureの属性取得
```

使用ライブラリ候補:

```text
@turf/boolean-point-in-polygon
@turf/helpers
```

---

# 9. 災害リスクスコア

スコア方向:

```text
100 = 相対的にリスクが低い
0 = 非常に高いリスク情報が存在する
null = 評価不能
```

「安全」「危険」と断定せず、正式名称は「災害リスク評価スコア」とする。

## 9.1 洪水・高潮

| 想定浸水深 | Risk Level | Score |
| --- | ---: | ---: |
| 区域外 | 0 | 100 |
| 0〜0.5m未満 | 1 | 90 |
| 0.5〜1.0m未満 | 2 | 75 |
| 1.0〜3.0m未満 | 3 | 55 |
| 3.0〜5.0m未満 | 4 | 25 |
| 5.0m以上 | 5 | 0 |
| データなし | null | null |

## 9.2 津波

| 想定浸水深 | Risk Level | Score |
| --- | ---: | ---: |
| 区域外 | 0 | 100 |
| 0〜0.3m未満 | 1 | 90 |
| 0.3〜1.0m未満 | 2 | 70 |
| 1.0〜2.0m未満 | 3 | 45 |
| 2.0〜5.0m未満 | 4 | 20 |
| 5.0m以上 | 5 | 0 |
| データなし | null | null |

## 9.3 総合スコア

単純平均ではなく、最低スコアを強く反映する。

```text
総合スコア = 最低スコア * 0.6 + 加重平均スコア * 0.4
```

初期重み:

| ハザード | Weight |
| --- | ---: |
| 洪水 | 0.35 |
| 土砂災害 | 0.30 |
| 津波 | 0.20 |
| 高潮 | 0.15 |

---

# 10. UI方針

* 価格予測カードと災害リスクカードは分離する
* ハザード表示はレイヤートグルで切り替える
* 断定表現を避け、「公開データ上の参考情報」として表示する
* データなしと区域外を区別する
* 出典、評価日時、評価ロジックバージョンを表示する
* 正式判断は自治体等の最新ハザードマップ確認を促す

---

# 11. 将来の特徴量候補

価格モデル投入は初期MVPでは行わない。候補特徴量として比較する場合は以下を想定する。

```text
hazard_overall_score
hazard_available_count
hazard_flood_risk_level
hazard_flood_depth_max
hazard_landslide_risk_level
hazard_landslide_special_warning
hazard_tsunami_risk_level
hazard_tsunami_depth_max
hazard_storm_surge_risk_level
hazard_storm_surge_depth_max
```

商業施設・駅規模特徴量との組み合わせは、別候補としてバックテストする。
