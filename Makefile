SHELL := /usr/bin/env bash

REGIONS ?= tokyo kanagawa saitama chiba
REGION ?= tokyo
YEAR ?= 2025
YEARS ?= 2005 2006 2007 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025
TRAINING_DIR := training
FRONTEND_DIR := frontend
DB_PATH := db/experiments.db
RAW_INPUT ?= data/raw/mlit_$(REGION)_$(YEAR).zip
RAW_INPUTS ?= data/raw/mlit_$(REGION)_*.zip
NATIONAL_RAW_INPUTS ?= data/raw/mlit_*.zip
PROCESSED_OUTPUT ?= data/processed/$(REGION).parquet
PUBLISH_POLICY ?= best
CSV_PREFECTURES ?= all
CSV_FROM_YEAR ?= 2005
CSV_TO_YEAR ?= 2025
CSV_DELAY_SECONDS ?= 15
CSV_CHUNK_YEARS ?= 0
CSV_DOWNLOAD_TIMEOUT_MS ?= 120000
SC_YEAR ?= 2026
SC_FROM_YEAR ?= 2015
SC_TO_YEAR ?= 2026
PASSENGER_AREA ?= capital
PASSENGER_ZOOM ?= 11
PASSENGER_NATIONAL_ZOOM ?= 11
PASSENGER_REQUEST_INTERVAL_SECONDS ?= 1.0
STATION_PASSENGERS_CSV ?= data/processed/station_passengers/station_groups.csv
HAZARD_INPUT ?=
HAZARD_URL ?=
FEATURE_ORDER_CONFIGS ?= configs/tokyo.yaml configs/kanagawa.yaml configs/saitama.yaml configs/chiba.yaml
FEATURE_ORDER_METADATA ?= ../$(FRONTEND_DIR)/public/metadata/tokyo_latest_metadata.json ../$(FRONTEND_DIR)/public/metadata/kanagawa_latest_metadata.json ../$(FRONTEND_DIR)/public/metadata/saitama_latest_metadata.json ../$(FRONTEND_DIR)/public/metadata/chiba_latest_metadata.json
UV := $(shell command -v uv 2>/dev/null)

ifeq ($(UV),)
TRAINING_PYTHON := .venv/bin/python
else
TRAINING_PYTHON := $(UV) run python
endif

-include $(TRAINING_DIR)/.env
export REINFOLIB_API_KEY

.PHONY: help setup setup-frontend setup-training setup-csv-download dev build preview verify python-check init-db collect collect-all collect-property collect-property-all collect-sc collect-sc-all collect-station-passengers collect-station-passengers-national collect-hazards collect-data download-csv download-csv-all csv-checklist preprocess preprocess-zip preprocess-capital-all-years preprocess-national train train-all train-regional-models train-production-models refresh-production-artifacts compare-models compare-national-models compare-commercial-features compare-station-passenger-features compare-external-features compare-outlier-filters summarize-edge-cases check-feature-order histories-national facilities stations stations-national

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
	@echo "  make collect-all        4地域・2005〜2025年をAPIから取得"
	@echo "  make collect-property   公式画面から不動産CSVを取得"
	@echo "  make collect-sc SC_YEAR=2026"
	@echo "                          JCSCオープンSC一覧を取得してJSON/CSV化"
	@echo "  make collect-station-passengers PASSENGER_AREA=capital"
	@echo "                          駅別乗降客数を取得してJSON/CSV化"
	@echo "  make collect-station-passengers-national"
	@echo "                          全国範囲の駅別乗降客数を取得してJSON/CSV化"
	@echo "  make collect-hazards HAZARD_INPUT=path/to/hazards.json"
	@echo "                          ハザード情報を正規化して学習用CSV化"
	@echo "  make collect-data       不動産CSV、2015年以降のJCSC、駅別乗降客数をまとめて取得"
	@echo "  make download-csv CSV_PREFECTURES=tokyo CSV_FROM_YEAR=2025 CSV_TO_YEAR=2025"
	@echo "                          公式画面から中古マンションCSVを取得"
	@echo "  make download-csv-all   全国・2005〜2025年のCSVを取得"
	@echo "  make csv-checklist      TODOのCSV取得状況を再集計"
	@echo "  make preprocess REGION=tokyo YEAR=2025"
	@echo "                          単一CSV/ZIPファイルを前処理"
	@echo "  make preprocess-zip REGION=tokyo"
	@echo "                          2005〜2025年のZIPをまとめて前処理"
	@echo "  make preprocess-capital-all-years"
	@echo "                          首都圏4都県の2005〜2025年ZIPを個別に前処理"
	@echo "  make preprocess-national 全国の2005〜2025年ZIPを比較用Parquetへ変換"
	@echo "  make train REGION=tokyo 指定地域のモデルを再学習"
	@echo "  make train-all          4地域のモデルを再学習"
	@echo "  make train-all PUBLISH_POLICY=latest"
	@echo "                          MAEベスト判定に関係なく最新学習モデルをpublicへ反映"
	@echo "  make train-regional-models"
	@echo "                          8地方160木モデルを生成してpublicへ反映"
	@echo "  make train-production-models"
	@echo "                          首都圏専用＋8地方モデルを本番用に一括生成"
	@echo "  make refresh-production-artifacts ALLOW_MODEL_UPDATE=1"
	@echo "                          データ取得から本番用モデル・静的成果物検証までを一括実行"
	@echo "  make compare-models     首都圏の共通・軽量モデルを現行4モデルと比較"
	@echo "  make compare-national-models"
	@echo "                          全国1モデル、8地方モデル、地域補正モデルを比較"
	@echo "  make compare-commercial-features"
	@echo "                          JCSC商業施設特徴量のバックテストを実行"
	@echo "  make compare-station-passenger-features"
	@echo "                          駅別乗降客数特徴量のバックテストを実行"
	@echo "  make compare-external-features"
	@echo "                          商業施設と駅規模の組み合わせバックテストを実行"
	@echo "  make compare-outlier-filters"
	@echo "                          外れ値処理候補のバックテストを実行"
	@echo "  make summarize-edge-cases REGION=tokyo"
	@echo "                          築古・駅遠・高額帯などの件数と分布を集計"
	@echo "  make check-feature-order"
	@echo "                          config/metadata の特徴量がフロント推論で扱えるか確認"
	@echo "  make histories-national 類似条件比較用の全国価格推移JSONとトレンドJSONを再生成"
	@echo "  make facilities         商業施設の配信用軽量JSONを再生成"
	@echo "  make stations           駅マスタJSONを再生成"
	@echo "  make stations-national  全国47都道府県の駅マスタJSONを再生成"
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

collect-property: download-csv

collect-property-all: download-csv-all

collect-sc:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/jcsc_sc_open.py --year $(SC_YEAR)

collect-sc-all:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/jcsc_sc_open.py --from-year $(SC_FROM_YEAR) --to-year $(SC_TO_YEAR) --cache

collect-station-passengers:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/station_passengers.py --area $(PASSENGER_AREA) --zoom $(PASSENGER_ZOOM) --request-interval-seconds $(PASSENGER_REQUEST_INTERVAL_SECONDS) --cache

collect-station-passengers-national:
	$(MAKE) collect-station-passengers PASSENGER_AREA=japan PASSENGER_ZOOM=$(PASSENGER_NATIONAL_ZOOM) PASSENGER_REQUEST_INTERVAL_SECONDS=$(PASSENGER_REQUEST_INTERVAL_SECONDS)

collect-hazards:
	cd $(TRAINING_DIR) && \
	if [ -n "$(HAZARD_INPUT)" ]; then \
		$(TRAINING_PYTHON) src/collect/hazards.py --input "$(HAZARD_INPUT)"; \
	elif [ -n "$(HAZARD_URL)" ]; then \
		$(TRAINING_PYTHON) src/collect/hazards.py --url "$(HAZARD_URL)"; \
	else \
		echo "HAZARD_INPUT or HAZARD_URL is required"; \
		exit 1; \
	fi

collect-data: collect-property collect-sc-all collect-station-passengers

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

preprocess-capital-all-years:
	$(MAKE) preprocess-zip REGION=tokyo
	$(MAKE) preprocess-zip REGION=kanagawa
	$(MAKE) preprocess-zip REGION=saitama
	$(MAKE) preprocess-zip REGION=chiba

preprocess-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/preprocess/preprocess.py --input $(NATIONAL_RAW_INPUTS) --output data/processed/national.parquet

train:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/train/train.py --config configs/$(REGION).yaml --db-path $(DB_PATH) --export-onnx --publish-policy $(PUBLISH_POLICY)

train-all:
	PUBLISH_POLICY=$(PUBLISH_POLICY) $(TRAINING_DIR)/scripts/train_all_models.sh

train-regional-models:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/train/train_regional_models.py --publish

train-production-models: preprocess-capital-all-years preprocess-national
	PUBLISH_POLICY=latest $(TRAINING_DIR)/scripts/train_all_models.sh
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/train/train_regional_models.py --publish

refresh-production-artifacts:
	@if [ "$(ALLOW_MODEL_UPDATE)" != "1" ]; then \
		echo "ALLOW_MODEL_UPDATE=1 is required because this target updates browser model artifacts."; \
		exit 1; \
	fi
	$(MAKE) collect-data
	$(MAKE) train-production-models
	$(MAKE) histories-national
	$(MAKE) facilities
	$(MAKE) stations-national
	$(MAKE) check-feature-order
	$(MAKE) build

compare-models:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_models.py

compare-national-models:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_national_models.py

compare-commercial-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_commercial_features.py

compare-station-passenger-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_station_passenger_features.py

compare-external-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_external_features.py

compare-outlier-filters:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_outlier_filters.py

summarize-edge-cases:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/dataset_edge_cases.py --input $(PROCESSED_OUTPUT) --region $(REGION)

check-feature-order:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.feature_order \
		--config $(FEATURE_ORDER_CONFIGS) \
		--metadata $(FEATURE_ORDER_METADATA)

histories-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.histories --public-dir ../$(FRONTEND_DIR)/public

facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.commercial_facilities --output ../$(FRONTEND_DIR)/public/facilities/commercial_facilities.json

stations:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --regions $(REGIONS) --station-passengers-csv $(STATION_PASSENGERS_CSV)

stations-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --station-passengers-csv $(STATION_PASSENGERS_CSV)
