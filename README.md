# 不動産価格予測システム

中古マンションの価格をブラウザ上で予測するWebアプリケーション。

将来予測は価格上昇率モデルではなく、transaction_year を特徴量として学習した結果を利用する。長期予測の精度は保証しない。

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

実モデルのONNXが未配置でも、開発用メタデータがある地域ではサンプル予測で画面フローを確認できる。

## 学習

```bash
cd training
uv sync
uv run python src/experiment/init_db.py --db-path db/experiments.db
REINFOLIB_API_KEY=... uv run python src/collect/collect.py --region tokyo --year 2025 --output-dir data/raw
uv run python src/preprocess/preprocess.py --input data/raw/tokyo_2025_xit001.json --output data/processed/tokyo.parquet
uv run python src/train/train.py --config configs/tokyo.yaml --db-path db/experiments.db --export-onnx
```

ZIPで取得した場合は、複数年をまとめて前処理できる。

```bash
uv run python src/preprocess/preprocess.py \
  --input \
    data/raw/mlit_tokyo_2020.zip \
    data/raw/mlit_tokyo_2021.zip \
    data/raw/mlit_tokyo_2022.zip \
    data/raw/mlit_tokyo_2023.zip \
    data/raw/mlit_tokyo_2024.zip \
    data/raw/mlit_tokyo_2025.zip \
  --output data/processed/tokyo.parquet
```

国交省データは不動産情報ライブラリから取得する。

```text
https://www.reinfolib.mlit.go.jp/realEstatePrices/
```

APIキーがない場合、collect処理は安全にスキップする。

APIキーは `training/.env.example` を参考に `REINFOLIB_API_KEY` として設定する。
