# 不動産価格予測システム

中古マンションの価格をブラウザ上で予測するWebアプリケーション。

地図上で場所を選択すると、最寄駅・駅徒歩・地域情報を自動補完し、物件条件から参考価格と価格推移グラフを表示する。

将来予測は学習最終年のモデル予測値を基点に、駅別または地域別の価格推移トレンドで補正する参考値として扱う。長期予測の精度は保証しない。

## できること

- 地図クリックまたは駅名・住所検索から物件位置を指定
- 最寄駅と駅徒歩を駅マスタから自動算出
- 面積、築年数、間取り、建物構造、予測年をもとに中古マンション価格を推定
- 予測価格、平米単価、信頼区間、価格推移グラフをブラウザだけで表示
- 東京都、神奈川県、埼玉県、千葉県の都県別モデルを切り替えて推論

## 構成

```text
frontend/  React + TypeScript + Vite
training/  データ取得、前処理、学習、評価、export
docs/      要件定義と実装仕様
```

## 推論アーキテクチャ

```text
React
↓
ONNX Runtime Web
↓
LightGBM(ONNX)
```

学習は Python / LightGBM で行い、ブラウザ配布用に ONNX へ変換する。推論APIサーバーを持たず、GitHub Pages 上の静的ファイルだけで価格予測を実行する。

サーバーレス推論にした理由:

- サーバー不要で公開できる
- 運用コストを抑えられる
- 推論がブラウザ内で完結する
- GitHub Pages だけでポートフォリオとして共有できる

## AI向け入口

AIエージェントはまず `AGENTS.md` を読む。

Codexで再利用する場合は、リポジトリ内skillとして `skills/map-lgb-fond/SKILL.md` も参照する。

GitHub Copilot系の補助には `.github/copilot-instructions.md` を用意している。

## フロントエンド

```bash
cd frontend
npm install
npm run dev
```

Makefile を使う場合:

```bash
make setup
make dev
```

実モデルのONNXが未配置でも、開発用メタデータがある地域ではサンプル予測で画面フローを確認できる。

## GitHub Pages

フロントエンドは `frontend/` だけをビルドし、GitHub Pages に静的サイトとしてデプロイする。

公開URL:

```text
https://kazuki-shimi620.github.io/map-lgb-fond/
```

CI/CD は `.github/workflows/deploy-frontend.yml` で管理する。

詳細は `docs/cicd.md` を参照する。

運用イメージ:

```text
develop で開発
↓
main 向け Pull Request を作成
↓
Pull Request では frontend build を確認
↓
main に merge / push
↓
GitHub Actions が frontend/dist を GitHub Pages に deploy
```

ローカル確認:

```bash
cd frontend
npm ci
npm run build
npm run preview
```

## 学習

```bash
make setup-training
make init-db
REINFOLIB_API_KEY=... make collect REGION=tokyo YEAR=2025
make preprocess REGION=tokyo YEAR=2025
make train REGION=tokyo
```

ZIPで取得した場合は、複数年をまとめて前処理できる。

```bash
make preprocess-zip REGION=tokyo
```

評価MAEが過去ベストより少し悪くても、軽量化した最新モデルをブラウザ配布用に反映したい場合は `PUBLISH_POLICY=latest` を指定する。

```bash
make train-all PUBLISH_POLICY=latest
```

国交省データは不動産情報ライブラリから取得する。

```text
https://www.reinfolib.mlit.go.jp/realEstatePrices/
```

APIキーがない場合、collect処理は安全にスキップする。

APIキーは `training/.env.example` を参考に `REINFOLIB_API_KEY` として設定する。

利用できるコマンドは以下で確認できる。

```bash
make help
```

## 実装で工夫した点

### 学習時と推論時の特徴量整合

LightGBMでは駅名、自治体、間取り、建物構造などのカテゴリ変数を利用して学習している。ブラウザ推論時にも同じ変換を再現する必要があるため、学習時にカテゴリ辞書とメタデータをJSONとして出力し、フロントエンドの `ModelManager` が同じ順序・同じIDで特徴量を組み立てる。

### ブラウザ推論化

FastAPI構成も検討したが、運用コスト削減と静的ホスティングを優先して ONNX Runtime Web を採用した。LightGBMモデルをONNXへ変換し、ブラウザ内で推論できる形にしている。

### 地図と不動産データの紐付け

地図クリック位置から緯度経度を取得し、逆ジオコーディングと駅マスタの距離計算を組み合わせて、予測に必要な都道府県、市区町村、最寄駅、駅徒歩へ変換している。

### データクレンジング

国交省データの文字コード、欠損値、数値表記、外れ値に対応する前処理を `training/src/preprocess` に分離した。複数年ZIPをまとめて処理し、地域別の parquet を生成できる。

### GitHub Pages対応

ローカル環境と公開環境で静的ファイル参照の基準パスが異なるため、ONNXモデル、wasm、メタデータ、価格推移JSONの配置を `frontend/public` に統一し、Vite の Pages 向け設定と合わせて読み込めるようにした。
