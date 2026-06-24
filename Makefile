SHELL := /usr/bin/env bash

REGIONS ?= tokyo kanagawa saitama chiba
REGION ?= tokyo
YEAR ?= 2025
TRAINING_DIR := training
FRONTEND_DIR := frontend
DB_PATH := db/experiments.db
RAW_INPUT ?= data/raw/$(REGION)_$(YEAR)_xit001.json
RAW_INPUTS ?= data/raw/mlit_$(REGION)_2020.zip data/raw/mlit_$(REGION)_2021.zip data/raw/mlit_$(REGION)_2022.zip data/raw/mlit_$(REGION)_2023.zip data/raw/mlit_$(REGION)_2024.zip data/raw/mlit_$(REGION)_2025.zip
PROCESSED_OUTPUT ?= data/processed/$(REGION).parquet
PUBLISH_POLICY ?= best

.PHONY: help setup setup-frontend setup-training dev build preview verify python-check init-db collect preprocess preprocess-zip train train-all stations

help:
	@echo "map-lgb-fond make targets"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              frontend / training の依存関係を準備"
	@echo "  make setup-frontend     frontend の npm 依存関係を準備"
	@echo "  make setup-training     training の uv 依存関係を準備"
	@echo ""
	@echo "Frontend:"
	@echo "  make dev                Vite 開発サーバーを起動"
	@echo "  make build              frontend をビルド"
	@echo "  make preview            frontend の preview を起動"
	@echo ""
	@echo "Training:"
	@echo "  make init-db            実験管理DBを初期化"
	@echo "  make collect REGION=tokyo YEAR=2025"
	@echo "                          国交省APIから学習元データを取得"
	@echo "  make preprocess REGION=tokyo"
	@echo "                          単一rawファイルを前処理"
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
	cd $(TRAINING_DIR) && uv run python src/experiment/init_db.py --db-path $(DB_PATH)

collect:
	cd $(TRAINING_DIR) && uv run python src/collect/collect.py --region $(REGION) --year $(YEAR) --output-dir data/raw

preprocess:
	cd $(TRAINING_DIR) && uv run python src/preprocess/preprocess.py --input $(RAW_INPUT) --output $(PROCESSED_OUTPUT)

preprocess-zip:
	cd $(TRAINING_DIR) && uv run python src/preprocess/preprocess.py --input $(RAW_INPUTS) --output $(PROCESSED_OUTPUT)

train:
	cd $(TRAINING_DIR) && uv run python src/train/train.py --config configs/$(REGION).yaml --db-path $(DB_PATH) --export-onnx --publish-policy $(PUBLISH_POLICY)

train-all:
	PUBLISH_POLICY=$(PUBLISH_POLICY) $(TRAINING_DIR)/scripts/train_all_models.sh

stations:
	cd $(TRAINING_DIR) && uv run python -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --regions $(REGIONS)
