# プロジェクトマップ

## 目的

`map-lgb-fond` は、中古マンション価格を予測するポートフォリオ向けアプリです。

主な目的:

- MLIT 不動産取引データから LightGBM モデルを学習する。
- 学習済みモデルを ONNX に変換し、ブラウザで推論する。
- React/Vite フロントエンドをバックエンドなしで動かす。
- FeatureProvider 方式で特徴量を追加しやすくする。
- モデルと成果物を都道府県単位で管理する。

## 仕様の参照先

- `docs/requirements.md`: プロダクト要件とスコープ
- `docs/implementation.md`: 実装方針、構成、優先順位
- `docs/frontend.md`: DTO、ModelManager、地図操作、駅探索、グラフ挙動
- `docs/training.md`: collect、preprocess、features、train、evaluate、export の責務
- `docs/database.md`: SQLite schema、制約、latest model 管理
- `docs/architecture.md`: 全体アーキテクチャと処理フロー

## 主要パス

- `AGENTS.md`: AIエージェント向けの作業ルール
- `frontend/src/App.tsx`: 単一画面アプリの構成
- `frontend/src/features/model/ModelManager.ts`: モデル、メタデータ、カテゴリ辞書読み込みと推論
- `frontend/src/features/map/PropertyMap.tsx`: Leaflet の地図入力
- `frontend/public/models/`: ブラウザ用ONNXモデル
- `frontend/public/metadata/`: カテゴリ辞書とモデルメタデータ
- `frontend/public/histories/`: 駅別・年別の価格推移JSON
- `frontend/public/stations/`: 駅マスタJSON
- `training/src/train/train.py`: 学習パイプライン入口
- `training/src/features/`: FeatureProvider とカテゴリ辞書生成
- `training/src/export/artifacts.py`: モデル成果物とJSON出力、frontend copy
- `training/src/export/stations.py`: 公開駅データから駅マスタJSONを生成
- `training/src/experiment/database.py`: SQLite schema と latest model 管理

## 実務上の制約

- MLIT データ取得は `https://www.reinfolib.mlit.go.jp/realEstatePrices/` を前提にする。
- API 呼び出しには `REINFOLIB_API_KEY` が必要。未設定の場合は収集処理を安全にスキップする。
- ブラウザコードから MLIT API を呼ばない。
- Python 依存管理は `training/pyproject.toml` と `uv` を使う。
- フロントエンドは npm と `frontend/package-lock.json` を使う。
- `.env`、生データ、加工済みデータ、SQLite生成DB、`training/outputs` の実成果物は Git 管理しない。

## 言語とコミット

- ドキュメント、ユーザー向け説明、実装メモは日本語を基本にする。
- コミットメッセージも日本語を基本にする。
- 英語の識別子、外部API名、ライブラリ名は無理に翻訳しない。
