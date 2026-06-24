# CI/CD運用

本ドキュメントは、フロントエンドを GitHub Pages に公開するための CI/CD フローを定義する。

---

# 1. 目的

以下を実現する。

* Pull Request 時にフロントエンドのビルドが通ることを確認する
* `main` に取り込まれた内容だけを GitHub Pages に公開する
* 学習環境や生データに依存せず、`frontend/` の静的成果物だけをデプロイする

---

# 2. 対象

CI/CD の対象はフロントエンドのみ。

```text
frontend/
```

GitHub Pages に公開する成果物は以下。

```text
frontend/dist
```

学習処理、データ収集、モデル再学習はこの CI/CD では実行しない。

---

# 3. ブランチ運用

基本方針:

```text
develop: 開発用ブランチ
main: 公開用ブランチ
```

開発フロー:

```text
develop で開発
↓
main 向け Pull Request を作成
↓
GitHub Actions で frontend build を確認
↓
Pull Request を main に merge
↓
GitHub Actions で GitHub Pages に deploy
```

---

# 4. GitHub Actions

workflow ファイル:

```text
.github/workflows/deploy-frontend.yml
```

実行タイミング:

* `main` への push
* `main` 向け Pull Request
* 手動実行

対象パス:

```text
frontend/**
.github/workflows/deploy-frontend.yml
```

---

# 5. Pull Request 時の動作

Pull Request ではビルド確認のみを行う。

実行される job:

```text
フロントエンドをビルド
```

実行されない job:

```text
GitHub Pagesへデプロイ
```

理由:

Pull Request の段階では、まだ公開対象として確定していないため。

---

# 6. main push / merge 時の動作

`main` に push または merge されると、以下を実行する。

```text
依存関係をインストール
↓
frontend をビルド
↓
frontend/dist を Pages artifact としてアップロード
↓
GitHub Pages に deploy
```

公開URL:

```text
https://kazuki-shimi620.github.io/map-lgb-fond/
```

---

# 7. ローカル確認

CI/CD に乗せる前に、必要に応じてローカルで確認する。

```bash
cd frontend
npm ci
npm run build
npm run preview
```

---

# 8. フロントエンド単体完結性

GitHub Pages ではバックエンドを使わない。

予測に必要な静的ファイルは `frontend/public` から `frontend/dist` にコピーされる。

```text
frontend/public/models
frontend/public/metadata
frontend/public/histories
frontend/public/stations
frontend/public/onnx
```

外部通信は以下に限定する。

* OpenStreetMap の地図タイル
* Nominatim の geocoding / reverse geocoding

---

# 9. 注意点

* `frontend/public/.nojekyll` を削除しない
* Vite の `base: "./"` を維持する
* `frontend/public/models` と `frontend/public/onnx` は Pages で配信される前提
* APIキーや `.env` は Pages に含めない
* 学習データ、生データZIP、`training/outputs` は deploy 対象にしない

---

# 10. トラブルシュート

## Pages に反映されない

確認箇所:

* Pull Request ではなく `main` に merge されているか
* GitHub Actions の `GitHub Pagesへデプロイ` job が成功しているか
* ブラウザキャッシュが残っていないか

## モデルや wasm が読めない

確認箇所:

* `frontend/dist/models/*.onnx` が生成されているか
* `frontend/dist/onnx/*.wasm` が生成されているか
* `frontend/public/.nojekyll` が `frontend/dist/.nojekyll` にコピーされているか
* ONNX Runtime の wasm が `application/wasm` として返っているか
