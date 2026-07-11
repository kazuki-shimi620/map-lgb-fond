# 将来価格シミュレーション方針

本ドキュメントは、現在の将来参考価格表示を、ユーザーが前提を変えられるシミュレーション機能へ拡張する方針を定義する。

## 目的

10年後などの長期価格を断定的に予測するのではなく、前提条件を変えた場合の参考レンジを表示する。

```text
現在の参考価格
↓
駅・地域の過去トレンド
↓
市場シナリオ
↓
将来参考レンジ
```

## 現行仕様との違い

現行の将来予測は、学習最終年のモデル予測値を基点に、駅別または地域別の価格推移トレンドで補正する。

シミュレーション機能では、ユーザーが次の前提を切り替えられるようにする。

* 標準
* 弱気
* 強気
* 横ばい

この切り替えは価格保証ではなく、過去トレンドを利用した参考表示として扱う。

## 入力

初期MVPでは、追加入力を最小限にする。

```text
target_year
scenario
```

将来拡張:

```text
annual_market_adjustment_rate
station_trend_weight
regional_trend_weight
renovation_assumption
```

## 出力

```typescript
type FuturePriceScenario = {
  scenario: "bear" | "flat" | "base" | "bull";
  targetYear: number;
  estimatedPrice: number;
  lowerPrice: number;
  upperPrice: number;
  annualizedChangeRate: number;
  basis: "station_trend" | "regional_trend" | "fallback";
};
```

## 計算方針

1. 学習最終年のモデル予測価格を基準価格にする
2. 駅別価格推移が十分にある場合は駅別トレンドを使う
3. 駅別価格推移が不足する場合は地域トレンドを使う
4. シナリオ係数を年率へ加減する
5. 上下レンジは過去トレンドのばらつきまたはモデル評価誤差から作る

例:

```text
base_rate = station_or_region_trend
bear = base_rate - scenario_width
flat = 0
base = base_rate
bull = base_rate + scenario_width
```

`scenario_width` は初期値として年率1.0〜1.5ポイント程度から比較し、表示が過度に派手にならないよう調整する。

## ブラウザ配布データ

追加で配布するデータは、駅別・地域別の年率トレンド集計に留める。

```text
frontend/public/histories/{region}_trend_summary.json
```

候補:

```json
{
  "region": "tokyo",
  "latestTrainingYear": 2025,
  "regionalTrend": {
    "annualizedRate": 0.018,
    "volatility": 0.045,
    "sampleYears": 6
  },
  "stationTrends": {
    "東京": {
      "annualizedRate": 0.022,
      "volatility": 0.052,
      "sampleYears": 6
    }
  }
}
```

生の取引データや詳細な駅別履歴を増やしすぎない。

## UI方針

初期UIは、予測年入力の近くにシナリオ切り替えを追加する。

```text
弱気 / 横ばい / 標準 / 強気
```

表示する文言は「将来参考レンジ」とし、「予測価格」や「保証」のような断定的な表現を避ける。

## 検証観点

* 10年後でも極端な価格になりすぎない
* 駅別トレンドが少数取引に引っ張られすぎない
* 地域トレンド fallback が自然に効く
* モバイルで操作が増えすぎない
* 追加JSONが軽量に収まる

## 非目標

初期段階では次を行わない。

* 金利、人口、再開発などを複雑に組み合わせたマクロ経済モデル
* 将来価格の保証表示
* 投資判断向けの利回り計算
* ユーザー入力シナリオの保存や共有
