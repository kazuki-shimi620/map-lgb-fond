# 外部データ取得・成果物更新ワークフロー

# 1. 目的

不動産価格予測モデルに使う外部データを取得し、前処理、学習、ブラウザ配信用成果物へ反映するまでの運用手順をまとめる。

この手順は、モデル更新を行う前の確認用チェックリストとして使う。ONNX、メタデータ、駅マスタなどの配布成果物更新は、精度・容量・ブラウザ速度を確認した後にまとめて実施する。

---

# 2. 対象データ

| データ | 取得コマンド | 主な出力 |
| --- | --- | --- |
| 不動産取引CSV | `make download-csv-all` | `training/data/raw/mlit_{prefecture}_{year}.zip` |
| JCSCオープンSC一覧 | `make collect-sc-all` | `training/data/processed/jcsc/jcsc_sc_open.csv` |
| 駅別乗降客数 | `make collect-station-passengers` | `training/data/processed/station_passengers/station_groups.csv` |
| ハザード情報 | `make collect-hazards HAZARD_INPUT=...` | `training/data/processed/hazards/hazard_features.csv` |
| 周辺施設候補 | 未実装 | `docs/surrounding-features.md` で候補管理 |
| 住みやすさ・将来性データ | 未実装 | `docs/data-source-acquisition.md` で取得設計を管理 |

ハザード情報は自治体APIやダウンロード済みJSON/CSVを入力にし、学習側で正規化する。ブラウザから外部APIを直接呼ばない。

## データソース別の扱い

| データ | 主入力 | 認証 | Git管理 | 備考 |
| --- | --- | --- | --- | --- |
| 不動産取引 | 公式画面CSV/ZIP | 不要 | raw/processedは管理しない | 最寄駅名と駅徒歩分を使うためAPIではなくCSV/ZIPを主入力にする |
| 駅別乗降客数 | XKT015 API | `REINFOLIB_API_KEY` | raw/processedは管理しない | 学習特徴量と駅マスタJSONの駅規模表示に利用する |
| JCSCオープンSC一覧 | JCSC公開ページ | 不要 | raw/processedは管理しない | `frontend/public/facilities` には市区町村/都道府県集計だけを配布する |
| ハザード | 入力JSON/CSVまたは公開データ | 入力元に依存 | raw/processedは管理しない | まずモデル特徴量CSVとして扱い、ブラウザから外部APIを直接呼ばない |

`training/data` と `training/outputs` は再生成可能な作業領域として扱う。Git管理するのは、ブラウザ実行に必要な `frontend/public` 配下の静的成果物だけに限定する。

---

# 3. 取得

外部特徴量をまとめて更新する場合は以下を実行する。

```bash
make collect-data
```

このターゲットは以下を順に実行する。

```text
不動産CSV取得
↓
2015年以降のJCSCオープンSC一覧取得
↓
駅別乗降客数取得
```

ハザード情報は対象地点や自治体APIの入力条件が案件ごとに変わるため、一括取得には含めない。入力ファイルまたはURLを指定して個別に実行する。

```bash
make collect-hazards HAZARD_INPUT=path/to/hazards.json
```

---

# 4. 前処理

首都圏4都県を更新する場合:

```bash
make preprocess-capital-all-years
```

全国比較用データを更新する場合:

```bash
make preprocess-national
```

2015年以降の学習に絞る場合は、モデル設定または学習スクリプト側で学習対象年を指定し、2005〜2025年学習とのバックテスト結果を比較する。

---

# 5. モデル比較

外部特徴量は、いきなり本番配布せず、以下の比較を先に行う。

```bash
make compare-commercial-features
make compare-station-passenger-features
```

比較では最低限以下を見る。

* MAE、RMSE、MAPE
* ONNXサイズ
* メタデータJSONサイズ
* `station` カテゴリあり・なしの精度差
* ブラウザ初回ロード時間
* 推論時間

商業施設、駅規模、ハザードを組み合わせる場合は、欠損フラグやデータ提供範囲が地域そのものの代理変数になりすぎていないか確認する。

---

# 6. 採用判断

ブラウザ推論ではモデルサイズと読み込み速度が制約になるため、精度改善が小さい特徴量は採用しない。

採用候補の優先順位:

1. 精度改善が安定している
2. 欠損時の挙動が明確
3. フロント推論時に同じ特徴量を再現できる
4. モデル・メタデータのサイズ増加が小さい
5. 将来のデータ更新が自動化しやすい

駅規模特徴量は、`station` カテゴリを削る軽量モデルとの相性も確認する。

大学、病院、大型公園、再開発エリアなどの周辺特徴量は、`docs/surrounding-features.md` の採用基準に沿って個別に比較する。

地価公示・基準地価、人口統計、用途地域、学区、保育園、路線利便性、犯罪・治安などは、`docs/data-source-acquisition.md` の難易度分類と実装単位に沿って、collector設計から着手する。

---

# 7. 成果物反映

採用モデルが決まったら、以下をまとめて更新する。

```bash
make train-all PUBLISH_POLICY=latest
make train-regional-models
make stations
make histories-national
```

チャットやターミナル接続が途中で切れる可能性がある場合は、更新前後の指標記録を含むバックグラウンド実行を使う。

```bash
make model-update-background
```

このコマンドは以下を順に実行する。

```text
更新前の frontend/public モデル指標を保存
↓
make refresh-production-artifacts ALLOW_MODEL_UPDATE=1
↓
更新後の frontend/public モデル指標を保存
↓
更新前後のMAE/RMSE/MAPE/ONNXサイズ差分をMarkdown/JSONで保存
```

出力例:

```text
training/outputs/comparisons/model_update_YYYYMMDD_HHMMSS/
├── before_model_metrics.json
├── after_model_metrics.json
├── model_update_comparison.json
└── model_update_comparison.md
```

ログを追う場合:

```bash
make model-update-log MODEL_UPDATE_LOG=training/outputs/comparisons/model_update_YYYYMMDD_HHMMSS.log
```

全国駅マスタを更新する場合:

```bash
make stations-national
```

反映対象:

```text
frontend/public/models/
frontend/public/metadata/
frontend/public/stations/
frontend/public/histories/
```

成果物反映後は `featureOrder` とフロントエンドの推論入力順が一致していることを確認する。

```bash
make check-feature-order
```

このコマンドは4都県の学習configと `frontend/public/metadata/*_latest_metadata.json` を確認する。ハザードなど、フロント推論入力に未対応の特徴量を追加した場合はここで検出する。`featureDefaults` は `featureOrder` に含まれる特徴量だけ許可し、余ったdefault値が残っている場合も失敗させる。

---

# 8. 検証

最低限以下を実行する。

```bash
training/.venv/bin/python -m compileall training/src
cd frontend
npm run build
npm run test:e2e
```

README画像を更新する場合:

```bash
cd frontend
npm run test:e2e:screenshots
```

スクリーンショットは `docs/images/` に出力し、差分を確認してからコミットする。
