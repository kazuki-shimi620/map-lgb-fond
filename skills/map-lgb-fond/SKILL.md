---
name: map-lgb-fond
description: map-lgb-fond 不動産価格予測アプリ専用のプロジェクトskill。このリポジトリで、React/Vite/Leaflet/ONNX Runtime を使うフロントエンド、Python/LightGBM/SQLite の学習パイプライン、モデル成果物、駅マスタ、docs/*.md の仕様更新、実装計画を扱うときに使う。
---

# Map LGB Fond Skill

## 最初に読むもの

アーキテクチャや横断的な変更を行う前に、次の順で確認する。

1. `AGENTS.md`
2. `docs/requirements.md`
3. `docs/implementation.md`
4. `docs/frontend.md`
5. `docs/training.md`
6. `docs/database.md`
7. `docs/architecture.md`
8. `docs/cicd.md`

素早く全体像を掴む場合は `references/project-map.md` を読む。

## 言語方針

- ユーザー向け説明、レビュー、ドキュメント、実装メモは原則日本語で書く。
- UI文言、README、`docs/`、`skills/` 配下のプロジェクト説明も日本語を優先する。
- コード識別子、ライブラリ名、API名、外部仕様名、エラー文は英語のままでよい。
- コミットメッセージは原則日本語にする。
  - 例: `最寄駅の自動更新を修正`
  - 例: `駅マスタ生成手順を追加`

## 作業ルール

- MVPを優先する。ブラウザ推論、学習/推論分離、FeatureProvider 拡張、都道府県別モデル管理を崩さない。
- 新しい抽象化よりも、既存構成に沿った小さな変更を優先する。
- ブラウザ用生成物は `frontend/public/{models,metadata,histories,stations}` に置く。
- 学習成果物は `training/outputs/` に置き、最新採用分だけ `frontend/public` へコピーする。
- 外部ネットワーク、MLIT API、公開駅データ取得、モデル再生成は、必要な場合だけ実行する。
- Python の依存管理は `uv` を使う。ユーザーが求めない限り `requirements.txt` は追加しない。
- フロントエンドは npm を使う。

## フロントエンド作業

`frontend/` を編集するときの基本手順:

1. `docs/frontend.md` と対象ファイルを確認する。
2. 機能コードは `src/features/{map,prediction,model}` に寄せる。
3. 共通の読み込み処理や距離計算は `src/services` と `src/utils` に置く。
4. モデル・メタデータ・駅マスタのパスは Vite public root からの相対パスを維持する。
5. TypeScript/Vite 変更後は `npm run build` を実行する。
6. ONNX が壊れてもUI確認できるよう、開発用 fallback は維持する。

## GitHub Pages作業

- フロントエンドだけを `frontend/dist` にビルドして GitHub Pages にデプロイする。
- 詳細な運用ルールは `docs/cicd.md` を参照する。
- CI/CD は `.github/workflows/deploy-frontend.yml` で管理する。
- Pull Request では build だけを実行し、`main` への push / merge で deploy する。
- 開発は `develop` ブランチを基本にし、`main` へ取り込むタイミングを公開タイミングとする。
- Pages で動かすため、Vite の `base: "./"` と `frontend/public/.nojekyll` を維持する。

## 学習パイプライン作業

`training/` を編集するときの基本手順:

1. `docs/training.md` と `docs/database.md` を確認する。
2. collect、preprocess、features、train、evaluate、export、experiment の責務を混ぜない。
3. 特徴量追加は FeatureProvider 方式に寄せる。
4. モデルと一緒にカテゴリ辞書、メタデータ、価格推移JSONを出力する。
5. Python変更後は `training/.venv/bin/python -m compileall training/src` を実行する。
6. `uv` が使える環境では `cd training && uv run python ...` を優先する。

## 駅マスタ作業

駅マスタは地図クリック時の最寄駅・駅徒歩更新に直結するため、フロントエンドの一部として扱う。

基本コマンド:

```bash
cd training
uv run python -m src.export.stations --public-dir ../frontend/public --regions tokyo saitama chiba kanagawa
```

`uv` が使えない場合:

```bash
cd training
.venv/bin/python -m src.export.stations --public-dir ../frontend/public --regions tokyo saitama chiba kanagawa
```

更新後に確認すること:

- `frontend/public/stations/{region}_stations.json` の件数が空でないこと。
- 東京、埼玉、千葉、神奈川の県境をまたいでも最寄駅と駅徒歩が更新されること。
- 駅徒歩は距離kmではなく徒歩分で扱う。80m=1分、直線距離補正1.25、切り上げで算出する。
- `cd frontend && npm run build` が通ること。

## 検証

最低限の確認:

```bash
cd frontend
npm run build
```

```bash
training/.venv/bin/python -m compileall training/src
```

実データがある場合:

```bash
cd training
uv run python src/train/train.py --config configs/tokyo.yaml --db-path db/experiments.db --export-onnx
```

## 参照

- `references/project-map.md`: リポジトリ構成、仕様の参照先、主要ファイル
- `references/workflows.md`: フロントエンド、学習、駅マスタ、ドキュメント更新の作業手順
