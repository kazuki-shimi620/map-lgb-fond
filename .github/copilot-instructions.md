# Copilot Instructions

このリポジトリは中古マンション価格予測アプリです。横断的な変更を行う前に、必ず `AGENTS.md` と `docs/` 配下の仕様を確認してください。

## 言語方針

- ユーザー向け説明、コメント、ドキュメント、実装メモは原則日本語で書く。
- コード識別子、ライブラリ名、API名、外部仕様名は英語のままでよい。
- コミットメッセージは日本語を基本にする。

## アーキテクチャ

- フロントエンド: React + TypeScript + Vite + Leaflet + ONNX Runtime Web + Recharts
- 学習側: collect、preprocess、features、train、evaluate、export、experiment に分けた Python パイプライン
- 推論はブラウザ側で行い、バックエンド推論は追加しない。
- モデルと関連JSONは都道府県単位で管理する。

## 主要ルール

- MVP範囲を優先する。
- ブラウザ推論用のカテゴリ辞書JSONを迂回しない。
- `training/outputs` の学習成果物と `frontend/public` の公開成果物を分けて扱う。
- 学習特徴量の追加は FeatureProvider 方式に寄せる。
- Python依存管理は `uv`、フロントエンド依存管理は npm を使う。
- 駅マスタJSONは `training/src/export/stations.py` で生成し、`frontend/public/stations` に置く。

## 検証

関連する変更では次を実行する。

```bash
cd frontend
npm run build
```

```bash
training/.venv/bin/python -m compileall training/src
```
