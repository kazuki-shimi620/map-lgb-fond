# 作業ワークフロー

## フロントエンド実装を続ける

1. `docs/frontend.md` を読む。
2. `frontend/src/App.tsx` と関連する `frontend/src/features/*` を確認する。
3. モデル成果物のパスは Vite public root からの相対パスを維持する。
   - `./models/{region}_latest.onnx`
   - `./metadata/{region}_latest_metadata.json`
   - `./metadata/{region}_latest_categories.json`
   - `./histories/{region}_latest_history.json`
   - `./stations/{region}_stations.json`
4. 地図の自動入力後もフォームを手入力で修正できる状態を維持する。
5. `cd frontend && npm run build` を実行する。

## 学習実装を続ける

1. `docs/training.md` と `docs/database.md` を読む。
2. パイプラインの責務を分けて保つ。
   - collect: MLIT 不動産情報ライブラリ API 取得
   - preprocess: 文字コード、型、欠損値、外れ値処理
   - features: FeatureProvider とカテゴリ辞書
   - train: LightGBM 学習
   - evaluate: MAE、RMSE、MAPE
   - export: pkl、ONNX、カテゴリJSON、メタデータJSON、価格推移JSON、frontend copy
   - experiment: SQLite 記録と latest model 管理
3. 設定は `training/configs/*.yaml` に寄せる。
4. `training/.venv/bin/python -m compileall training/src` を実行する。

収集コマンド:

```bash
cd training
REINFOLIB_API_KEY=... uv run python src/collect/collect.py --region tokyo --year 2025 --output-dir data/raw
```

前処理コマンド:

```bash
cd training
uv run python src/preprocess/preprocess.py --input data/raw/tokyo_2025_xit001.json --output data/processed/tokyo.parquet
```

複数ZIPを1つの地域データにまとめる例:

```bash
cd training
uv run python src/preprocess/preprocess.py \
  --input data/raw/mlit_tokyo_2020.zip data/raw/mlit_tokyo_2021.zip data/raw/mlit_tokyo_2022.zip data/raw/mlit_tokyo_2023.zip data/raw/mlit_tokyo_2024.zip data/raw/mlit_tokyo_2025.zip \
  --output data/processed/tokyo.parquet
```

## 駅マスタJSONを再生成する

駅マスタは `frontend/public/stations/{region}_stations.json` に置く。地図クリック時の最寄駅と駅徒歩の自動更新に使うため、空ファイルや少なすぎる駅数にしない。

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

更新後の確認:

```bash
node -e "for (const r of ['tokyo','saitama','chiba','kanagawa']) { const s=require('./frontend/public/stations/'+r+'_stations.json'); console.log(r, s.length); }"
```

期待値の目安:

- 東京: 数百駅
- 埼玉: 数百駅
- 千葉: 数百駅
- 神奈川: 数百駅

最後に `cd frontend && npm run build` を実行する。

## FeatureProvider を追加する

1. `training/src/features/providers.py` に provider class を追加する。大きくなる場合だけ専用モジュールに分ける。
2. パイプラインの factory または登録箇所に追加する。
3. config YAML と docs に feature 名を追加する。
4. カテゴリ変数の場合は `category_dictionary.py` の辞書化対象も確認する。
5. 実験DBへの feature 登録は config の feature 一覧と整合させる。

## 新しい地域を追加する

1. `training/configs/{region}.yaml` を追加する。
2. 学習と export を実行し、モデルとJSON成果物を生成する。
3. 最新成果物を次の場所に置く。
   - `frontend/public/models/{region}_latest.onnx`
   - `frontend/public/metadata/{region}_latest_metadata.json`
   - `frontend/public/metadata/{region}_latest_categories.json`
   - `frontend/public/histories/{region}_latest_history.json`
   - `frontend/public/stations/{region}_stations.json`
4. `frontend/src/utils/region.ts` の都道府県/region mapping を更新する。

## ドキュメント変更

1. プロダクト要件が変わる場合は `docs/requirements.md` を更新する。
2. 実装方針が変わる場合は `docs/implementation.md` を更新する。
3. フロントエンド、学習、DBなど個別領域の変更は対応する docs に反映する。
4. README はセットアップと実行手順を中心に保つ。
5. 原則として日本語で書く。

## Git運用

- コミットメッセージは原則日本語にする。
- 変更内容が分かる短い文にする。
- 例:
  - `最寄駅の自動更新を修正`
  - `駅マスタ生成手順を追加`
  - `学習データの前処理を調整`
