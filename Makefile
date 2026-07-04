SHELL := /usr/bin/env bash

REGIONS ?= tokyo kanagawa saitama chiba
REGION ?= tokyo
YEAR ?= 2025
YEARS ?= 2020 2021 2022 2023 2024 2025
TRAINING_DIR := training
FRONTEND_DIR := frontend
DB_PATH := db/experiments.db
RAW_INPUT ?= data/raw/mlit_$(REGION)_$(YEAR).zip
RAW_INPUTS ?= data/raw/mlit_$(REGION)_2020.zip data/raw/mlit_$(REGION)_2021.zip data/raw/mlit_$(REGION)_2022.zip data/raw/mlit_$(REGION)_2023.zip data/raw/mlit_$(REGION)_2024.zip data/raw/mlit_$(REGION)_2025.zip
PROCESSED_OUTPUT ?= data/processed/$(REGION).parquet
PUBLISH_POLICY ?= best
CSV_PREFECTURES ?= all
CSV_FROM_YEAR ?= 2005
CSV_TO_YEAR ?= 2025
CSV_DELAY_SECONDS ?= 15
CSV_CHUNK_YEARS ?= 0
CSV_DOWNLOAD_TIMEOUT_MS ?= 120000
UV := $(shell command -v uv 2>/dev/null)

ifeq ($(UV),)
TRAINING_PYTHON := .venv/bin/python
else
TRAINING_PYTHON := $(UV) run python
endif

-include $(TRAINING_DIR)/.env
export REINFOLIB_API_KEY

.PHONY: help setup setup-frontend setup-training setup-csv-download dev build preview verify python-check init-db collect collect-all download-csv download-csv-all csv-checklist preprocess preprocess-zip train train-all stations

help:
	@echo "map-lgb-fond make targets"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              frontend / training の依存関係を準備"
	@echo "  make setup-frontend     frontend の npm 依存関係を準備"
	@echo "  make setup-training     training の uv 依存関係を準備"
	@echo "  make setup-csv-download CSVダウンロード用Playwrightを準備"
	@echo ""
	@echo "Frontend:"
	@echo "  make dev                Vite 開発サーバーを起動"
	@echo "  make build              frontend をビルド"
	@echo "  make preview            frontend の preview を起動"
	@echo ""
	@echo "Training:"
	@echo "  make init-db            実験管理DBを初期化"
	@echo "  make collect REGION=tokyo YEAR=2025"
	@echo "                          国交省APIからraw JSONを取得"
	@echo "  make collect-all        4地域・2020〜2025年をAPIから取得"
	@echo "  make download-csv CSV_PREFECTURES=tokyo CSV_FROM_YEAR=2025 CSV_TO_YEAR=2025"
	@echo "                          公式画面から中古マンションCSVを取得"
	@echo "  make download-csv-all   全国・2005〜2025年のCSVを取得"
	@echo "  make csv-checklist      TODOのCSV取得状況を再集計"
	@echo "  make preprocess REGION=tokyo YEAR=2025"
	@echo "                          単一CSV/ZIPファイルを前処理"
	@echo "  make preprocess-zip REGION=tokyo"
	@echo "                          2020〜2025年のZIPをまとめて前処理"
	@echo "  make train REGION=tokyo 指定地域のモデルを再学習"
	@echo "  make train-all          4地域のモデルを再学習"
	@echo "  make train-all PUBLISH_POLICY=latest"
	@echo "                          MAEベスト判定に関係なく最新学習モデルをpublicへ反映"
	@echo "  make stations           駅マスタJSONを再生成"
	@echo ""
	@echo "Verify:"
	@echo "  make verify             Python構文チェックとfrontend buildを実行"
	@echo "  make python-check       training/src の構文チェック"

setup: setup-training setup-frontend

setup-frontend:
	cd $(FRONTEND_DIR) && npm install

setup-training:
	cd $(TRAINING_DIR) && uv sync

setup-csv-download:
	cd $(TRAINING_DIR)/browser && npm ci

dev:
	cd $(FRONTEND_DIR) && npm run dev

build:
	cd $(FRONTEND_DIR) && npm run build

preview:
	cd $(FRONTEND_DIR) && npm run preview

verify: python-check build

python-check:
	$(TRAINING_DIR)/.venv/bin/python -m compileall $(TRAINING_DIR)/src

init-db:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/experiment/init_db.py --db-path $(DB_PATH)

collect:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/collect.py --region $(REGION) --year $(YEAR) --output-dir data/raw

collect-all:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/collect.py --region $(REGIONS) --year $(YEARS) --output-dir data/raw

download-csv:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/download_csv.py --prefectures $(CSV_PREFECTURES) --from-year $(CSV_FROM_YEAR) --to-year $(CSV_TO_YEAR) --delay-seconds $(CSV_DELAY_SECONDS) --chunk-years $(CSV_CHUNK_YEARS) --download-timeout-ms $(CSV_DOWNLOAD_TIMEOUT_MS)

download-csv-all:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/download_csv.py --prefectures all --from-year 2005 --to-year 2025 --delay-seconds $(CSV_DELAY_SECONDS) --chunk-years $(CSV_CHUNK_YEARS) --download-timeout-ms $(CSV_DOWNLOAD_TIMEOUT_MS) --continue-on-error

csv-checklist:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/download_csv.py --from-year 2005 --to-year 2025 --checklist-only

preprocess:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/preprocess/preprocess.py --input $(RAW_INPUT) --output $(PROCESSED_OUTPUT)

preprocess-zip:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/preprocess/preprocess.py --input $(RAW_INPUTS) --output $(PROCESSED_OUTPUT)

train:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/train/train.py --config configs/$(REGION).yaml --db-path $(DB_PATH) --export-onnx --publish-policy $(PUBLISH_POLICY)

train-all:
	PUBLISH_POLICY=$(PUBLISH_POLICY) $(TRAINING_DIR)/scripts/train_all_models.sh

stations:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --regions $(REGIONS)
