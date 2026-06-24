# AIエージェント向けガイド

このリポジトリで作業するAIエージェントは、最初にこのファイルを読んでください。

## プロジェクト概要

`map-lgb-fond` は、中古マンションの価格をブラウザ上で予測するポートフォリオ向けアプリです。

主な構成は次の2つです。

- `frontend/`: React、TypeScript、Vite、Leaflet、ONNX Runtime Web、Recharts を使ったブラウザアプリ
- `training/`: LightGBM、SQLite実験管理、ONNX/JSON成果物出力を含む Python 学習パイプライン

## 言語方針

- ユーザー向けの説明、レビュー、実装メモ、ドキュメント更新は原則として日本語で書く。
- UI文言、README、`docs/`、`skills/` 配下のプロジェクト説明も日本語を優先する。
- コード中の識別子、ライブラリ名、API名、エラー文、外部仕様名は英語のままでよい。
- コミットメッセージは原則として日本語で、短く変更内容が分かる文にする。
  - 例: `最寄駅の自動更新を修正`
  - 例: `駅マスタ生成手順を追加`
  - 例: `ONNX Runtime の読み込み設定を調整`

## 仕様の参照順

大きめの変更を行う前に、次のドキュメントを確認してください。

1. `docs/requirements.md`
2. `docs/implementation.md`
3. `docs/frontend.md`
4. `docs/training.md`
5. `docs/database.md`
6. `docs/architecture.md`
7. `docs/cicd.md`

リポジトリ内 skill として `skills/map-lgb-fond/SKILL.md` も用意しています。

## 作業方針

- MVP範囲を優先し、ユーザーが明示しない限り過度にスコープを広げない。
- 学習処理とブラウザ推論処理を分離する。
- ブラウザ推論はサーバーレス構成を維持する。
- モデル管理は都道府県単位を基本とする。
- 学習特徴量の追加は FeatureProvider 方式に寄せる。
- ネットワーク依存のデータ取得、外部API呼び出し、モデル再生成は、必要なときだけ実行する。
- 不動産取引データは `https://www.reinfolib.mlit.go.jp/realEstatePrices/` を前提にする。
- `REINFOLIB_API_KEY` は学習側の収集処理だけで使う。ブラウザから MLIT API を呼ばない。
- Python の依存管理は `uv` を使う。`requirements.txt` は原則追加しない。
- フロントエンドは npm と `frontend/package-lock.json` を使う。

## 成果物の扱い

- `frontend/public/models`: ブラウザで読み込む最新ONNXモデル
- `frontend/public/metadata`: カテゴリ辞書とモデルメタデータ
- `frontend/public/histories`: 価格推移グラフ用の集計済みJSON
- `frontend/public/stations`: 地図クリック時に使う駅マスタJSON
- `training/outputs`: 学習・評価・エクスポートで生成される中間成果物

`training/outputs` や `training/data` の実データは Git 管理しない。ブラウザ実行に必要な最新成果物だけ `frontend/public` に置く。

## よく使うコマンド

フロントエンド:

```bash
cd frontend
npm run build
```

GitHub Pages:

```text
develop で開発し、main 向け Pull Request で build を確認する。
main に merge / push されたら GitHub Actions で frontend/dist を GitHub Pages に deploy する。
```

Python 構文チェック:

```bash
training/.venv/bin/python -m compileall training/src
```

DB初期化:

```bash
training/.venv/bin/python training/src/experiment/init_db.py --db-path training/db/experiments.db
```

`uv` が使える場合の学習:

```bash
cd training
uv sync
uv run python src/train/train.py --config configs/tokyo.yaml --db-path db/experiments.db --export-onnx
```

駅マスタ再生成:

```bash
cd training
uv run python -m src.export.stations --public-dir ../frontend/public --regions tokyo saitama chiba kanagawa
```

## 注意点

- ONNX Runtime Web の wasm 配置は壊れやすいため、変更後は必ずブラウザと `npm run build` で確認する。
- `frontend/public/onnx` はブラウザ実行に必要な静的ファイルとして扱う。
- 駅マスタは地図クリック時の最寄駅・駅徒歩更新に直結する。更新後は東京、埼玉、千葉、神奈川をまたいで確認する。
- 駅徒歩は距離kmではなく徒歩分で扱う。地図クリック時は 80m=1分、直線距離補正 1.25、切り上げで算出する。
- APIキー、`.env`、生データZIP、加工済みデータ、SQLite生成DBはコミットしない。
