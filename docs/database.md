# database.md

# 実験管理データベース設計

本データベースは学習実験の再現性確保およびモデル管理を目的とする。

DBMS は SQLite を利用する。

---

# 1. 設計方針

## 目的

以下を実現する。

* 学習履歴管理
* モデル比較
* 特徴量比較
* 実験再現
* ベストモデル管理

---

## 管理対象

```text
datasets
features
models
experiments
```

---

# 2. datasets

利用したデータセットを管理する。

---

## テーブル

```text
datasets
```

---

## カラム

| カラム名         | 型        | 必須  | 説明      |
| ------------ | -------- | --- | ------- |
| id           | INTEGER  | YES | PK      |
| name         | TEXT     | YES | データセット名 |
| source_url   | TEXT     | YES | 取得元URL  |
| region       | TEXT     | YES | 対象地域    |
| record_count | INTEGER  | YES | レコード数   |
| created_at   | DATETIME | YES | 作成日時    |

---

## 制約

```text
PRIMARY KEY (id)
```

---

## サンプル

```text
id: 1

name:
mlit_tokyo_2025

region:
tokyo

record_count:
125000
```

---

# 3. features

利用可能な特徴量定義を管理する。

---

## テーブル

```text
features
```

---

## カラム

| カラム名         | 型        | 必須  | 説明   |
| ------------ | -------- | --- | ---- |
| id           | INTEGER  | YES | PK   |
| feature_name | TEXT     | YES | 特徴量名 |
| description  | TEXT     | YES | 説明   |
| created_at   | DATETIME | YES | 作成日時 |

---

## 制約

```text
PRIMARY KEY (id)
UNIQUE (feature_name)
```

---

## サンプル

```text
feature_name:
area

description:
専有面積
```

---

## MVP登録予定

```text
area

age

station

municipality

station_distance

room_layout

building_type

transaction_year
```

---

# 4. experiments

学習実験を管理する。

---

## テーブル

```text
experiments
```

---

## カラム

| カラム名               | 型        | 必須  | 説明                         |
| ------------------ | -------- | --- | -------------------------- |
| id                 | INTEGER  | YES | PK                         |
| experiment_name    | TEXT     | YES | 実験名                        |
| dataset_id         | INTEGER  | YES | datasets FK                |
| status             | TEXT     | YES | running / success / failed |
| mae                | REAL     | NO  | MAE                        |
| rmse               | REAL     | NO  | RMSE                       |
| mape               | REAL     | NO  | MAPE                       |
| train_time_seconds | REAL     | NO  | 学習時間                       |
| prediction_time_ms | REAL     | NO  | 推論時間                       |
| started_at         | DATETIME | YES | 開始日時                       |
| completed_at       | DATETIME | NO  | 終了日時                       |
| created_at         | DATETIME | YES | 作成日時                       |

---

## 制約

```text
PRIMARY KEY (id)
FOREIGN KEY (dataset_id) REFERENCES datasets(id)
CHECK (status IN ('running', 'success', 'failed'))
```

---

## ステータス

```text
running
success
failed
```

---

## サンプル

```text
experiment_name:
tokyo_lgbm_v1

status:
success

mae:
2540000
```

---

# 5. experiment_features

実験で使用した特徴量を管理する。

多対多テーブル。

---

## テーブル

```text
experiment_features
```

---

## カラム

| カラム名          | 型       | 必須  | 説明             |
| ------------- | ------- | --- | -------------- |
| experiment_id | INTEGER | YES | experiments FK |
| feature_id    | INTEGER | YES | features FK    |

---

## 制約

```text
PRIMARY KEY (experiment_id, feature_id)
FOREIGN KEY (experiment_id) REFERENCES experiments(id)
FOREIGN KEY (feature_id) REFERENCES features(id)
```

---

## サンプル

```text
experiment_id: 1
feature_id: 3
```

---

# 6. models

モデル管理テーブル。

---

## テーブル

```text
models
```

---

## カラム

| カラム名          | 型        | 必須  | 説明             |
| ------------- | -------- | --- | -------------- |
| id            | INTEGER  | YES | PK             |
| experiment_id | INTEGER  | YES | experiments FK |
| model_type    | TEXT     | YES | lightgbm       |
| region        | TEXT     | YES | 対象地域           |
| model_path    | TEXT     | YES | pkl保存先         |
| onnx_path     | TEXT     | NO  | onnx保存先        |
| is_latest     | INTEGER  | YES | 0/1            |
| created_at    | DATETIME | YES | 作成日時           |

---

## 制約

```text
PRIMARY KEY (id)
FOREIGN KEY (experiment_id) REFERENCES experiments(id)
CHECK (is_latest IN (0, 1))
```

regionごとのlatestは1件のみ許可する。

SQLiteでは以下の部分ユニークインデックスで実現する。

```sql
CREATE UNIQUE INDEX idx_models_latest_region
ON models(region)
WHERE is_latest = 1;
```

---

## サンプル

```text
model_type:
lightgbm

region:
tokyo

model_path:
outputs/models/tokyo_20260821.pkl

onnx_path:
outputs/models/tokyo_20260821.onnx

is_latest:
1
```

---

# 7. モデル更新ルール

## 学習成功時

models レコードを作成する。

---

## latest更新

以下の条件を満たす場合のみ更新する。

```text
新モデルMAE < 現latestモデルMAE
```

---

## 更新内容

旧latest

```text
is_latest = 0
```

新モデル

```text
is_latest = 1
```

---

# 8. 実験ライフサイクル

## 学習開始

experiments を作成する。

```text
status = running
```

---

## 学習成功

更新する。

```text
status = success
completed_at = now
```

---

## 学習失敗

更新する。

```text
status = failed
completed_at = now
```

---

失敗した実験も削除しない。

---

# 9. 将来拡張

将来的に以下のテーブル追加を想定する。

---

## feature_providers

```text
Provider定義管理
```

---

## datasets_versions

```text
データセット世代管理
```

---

## facility_features

```text
商業施設特徴量管理
```

---

## model_comparisons

```text
モデル比較結果管理
```

---

# 10. ER概要

```text
datasets
    |
    |
    +---- experiments
              |
              |
              +---- models
              |
              |
              +---- experiment_features
                          |
                          |
                          +---- features
```

---

# 11. MVP方針

MVPでは以下を優先する。

* 実験履歴を残せること
* ベストモデルを管理できること
* 特徴量比較ができること

SQLite単体で運用可能な構成とする。
