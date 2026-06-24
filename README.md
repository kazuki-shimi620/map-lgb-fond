# 不動産価格予測システム

中古マンションの価格をブラウザ上で予測するWebアプリケーション。

将来予測は学習最終年のモデル予測値を基点に、駅別または地域別の価格推移トレンドで補正する参考値として扱う。長期予測の精度は保証しない。

## 構成

```text
frontend/  React + TypeScript + Vite
training/  データ取得、前処理、学習、評価、export
docs/      要件定義と実装仕様
```

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
