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
LAND_PRICE_YEARS ?= 2024,2025
LAND_PRICE_AREA ?= capital
LAND_PRICE_ZOOM ?= 14
LAND_PRICE_USE_CATEGORY_CODES ?= 00,05
LAND_PRICE_REQUEST_INTERVAL_SECONDS ?= 1.0
LAND_PRICE_POINTS_CSV ?= data/processed/land_prices/land_price_points.csv
LAND_PRICE_CITY_SUMMARY_CSV ?= data/processed/land_prices/land_price_city_summary.csv
HAZARDS_CSV ?= data/processed/hazards/hazard_features.csv
HAZARD_INPUT ?=
HAZARD_URL ?=
FEATURE_ORDER_CONFIGS ?= configs/tokyo.yaml configs/kanagawa.yaml configs/saitama.yaml configs/chiba.yaml
FEATURE_ORDER_METADATA ?= ../$(FRONTEND_DIR)/public/metadata/tokyo_latest_metadata.json ../$(FRONTEND_DIR)/public/metadata/kanagawa_latest_metadata.json ../$(FRONTEND_DIR)/public/metadata/saitama_latest_metadata.json ../$(FRONTEND_DIR)/public/metadata/chiba_latest_metadata.json
MODEL_UPDATE_RUN_ID := $(or $(MODEL_UPDATE_RUN_ID),$(shell date +%Y%m%d_%H%M%S))
MODEL_UPDATE_LOG ?= training/outputs/comparisons/model_update_$(MODEL_UPDATE_RUN_ID).log
MODEL_UPDATE_PID ?= training/outputs/comparisons/model_update_$(MODEL_UPDATE_RUN_ID).pid
MODEL_UPDATE_LOCK_DIR ?= training/outputs/comparisons/model_update.lock
SNAPSHOT_OUTPUT ?= outputs/comparisons/model_metrics_snapshot.json
BEFORE_SNAPSHOT ?= outputs/comparisons/model_update_before.json
AFTER_SNAPSHOT ?= outputs/comparisons/model_update_after.json
REPORT_OUTPUT ?= outputs/comparisons/model_update_comparison.json
MARKDOWN_OUTPUT ?= outputs/comparisons/model_update_comparison.md
UV := $(shell command -v uv 2>/dev/null)

ifeq ($(UV),)
TRAINING_PYTHON := .venv/bin/python
else
TRAINING_PYTHON := $(UV) run python
endif

-include $(TRAINING_DIR)/.env
export REINFOLIB_API_KEY

.PHONY: help setup setup-frontend setup-training setup-csv-download dev build preview verify python-check init-db collect collect-all collect-legacy-api collect-legacy-api-all collect-property collect-property-all collect-sc collect-sc-all collect-station-passengers collect-station-passengers-national collect-land-prices collect-hazards collect-data download-csv download-csv-all csv-checklist preprocess preprocess-zip preprocess-capital-all-years preprocess-national train train-all train-regional-models train-production-models refresh-production-artifacts model-update-background model-update-log snapshot-model-metrics compare-model-metrics compare-models compare-national-models compare-commercial-features compare-station-passenger-features compare-land-price-features compare-external-features compare-train-start-years compare-outlier-filters summarize-edge-cases check-feature-order histories-national facilities stations stations-national

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
	@echo "  make collect            公式画面から中古マンションCSVを取得"
	@echo "  make collect-all        全国・2005〜2025年の中古マンションCSVを取得"
	@echo "  make collect-property   公式画面から不動産CSVを取得"
	@echo "  make collect-sc SC_YEAR=2026"
	@echo "                          JCSCオープンSC一覧を取得してJSON/CSV化"
	@echo "  make collect-station-passengers PASSENGER_AREA=capital"
	@echo "                          駅別乗降客数を取得してJSON/CSV化"
	@echo "  make collect-station-passengers-national"
	@echo "                          全国範囲の駅別乗降客数を取得してJSON/CSV化"
	@echo "  make collect-land-prices LAND_PRICE_YEARS=2024,2025"
	@echo "                          地価公示・地価調査ポイントを取得してCSV化"
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
	@echo "  make model-update-background"
	@echo "                          モデル更新をバックグラウンドで実行し、更新前後の指標差分を記録"
	@echo "  make model-update-log MODEL_UPDATE_LOG=path/to/log"
	@echo "                          バックグラウンド実行ログを追尾"
	@echo "  make snapshot-model-metrics SNAPSHOT_OUTPUT=path/to/json"
	@echo "                          public配下の現行モデル指標をスナップショット保存"
	@echo "  make compare-model-metrics BEFORE_SNAPSHOT=... AFTER_SNAPSHOT=..."
	@echo "                          モデル指標スナップショットを比較"
	@echo "  make compare-models     首都圏の共通・軽量モデルを現行4モデルと比較"
	@echo "  make compare-national-models"
	@echo "                          全国1モデル、8地方モデル、地域補正モデルを比較"
	@echo "  make compare-commercial-features"
	@echo "                          JCSC商業施設特徴量のバックテストを実行"
	@echo "  make compare-station-passenger-features"
	@echo "                          駅別乗降客数特徴量のバックテストを実行"
	@echo "  make compare-land-price-features"
	@echo "                          地価公示・基準地価特徴量のバックテストを実行"
	@echo "  make compare-external-features"
	@echo "                          商業施設、駅規模、ハザードの組み合わせバックテストを実行"
	@echo "  make compare-train-start-years"
	@echo "                          学習開始年を複数holdout年で比較"
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

collect: collect-property

collect-all: collect-property-all

collect-legacy-api:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/legacy/collect.py --region $(REGION) --year $(YEAR) --output-dir data/raw

collect-legacy-api-all:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/legacy/collect.py --region $(REGIONS) --year $(YEARS) --output-dir data/raw

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

collect-land-prices:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/land_prices.py --area $(LAND_PRICE_AREA) --zoom $(LAND_PRICE_ZOOM) --years "$(LAND_PRICE_YEARS)" --use-category-codes "$(LAND_PRICE_USE_CATEGORY_CODES)" --request-interval-seconds $(LAND_PRICE_REQUEST_INTERVAL_SECONDS) --cache

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
	TRAINING_PYTHON="$(TRAINING_PYTHON)" PUBLISH_POLICY=$(PUBLISH_POLICY) $(TRAINING_DIR)/scripts/train_all_models.sh

train-regional-models:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/train/train_regional_models.py --publish

train-production-models: preprocess-capital-all-years preprocess-national
	TRAINING_PYTHON="$(TRAINING_PYTHON)" PUBLISH_POLICY=latest $(TRAINING_DIR)/scripts/train_all_models.sh
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

model-update-background:
	@mkdir -p training/outputs/comparisons
	@if ! mkdir "$(MODEL_UPDATE_LOCK_DIR)" 2>/dev/null; then \
		echo "model update is already running or lock remains: $(MODEL_UPDATE_LOCK_DIR)"; \
		if [ -f "$(MODEL_UPDATE_LOCK_DIR)/run_id" ]; then echo "run_id=$$(cat "$(MODEL_UPDATE_LOCK_DIR)/run_id")"; fi; \
		if [ -f "$(MODEL_UPDATE_LOCK_DIR)/pid" ]; then echo "pid=$$(cat "$(MODEL_UPDATE_LOCK_DIR)/pid")"; fi; \
		if [ -f "$(MODEL_UPDATE_LOCK_DIR)/log" ]; then echo "log=$$(cat "$(MODEL_UPDATE_LOCK_DIR)/log")"; fi; \
		exit 1; \
	fi
	@printf '%s\n' "$(MODEL_UPDATE_RUN_ID)" > "$(MODEL_UPDATE_LOCK_DIR)/run_id"
	@printf '%s\n' "$(MODEL_UPDATE_LOG)" > "$(MODEL_UPDATE_LOCK_DIR)/log"
	@MODEL_UPDATE_RUN_ID=$(MODEL_UPDATE_RUN_ID) MODEL_UPDATE_LOCK_DIR="$(MODEL_UPDATE_LOCK_DIR)" PYTHONUNBUFFERED=1 nohup bash training/scripts/run_model_update_with_report.sh > "$(MODEL_UPDATE_LOG)" 2>&1 < /dev/null & \
		echo $$! > "$(MODEL_UPDATE_PID)"; \
		echo $$! > "$(MODEL_UPDATE_LOCK_DIR)/pid"; \
		echo "model update started"; \
		echo "run_id=$(MODEL_UPDATE_RUN_ID)"; \
		echo "pid=$$(cat "$(MODEL_UPDATE_PID)")"; \
		echo "log=$(MODEL_UPDATE_LOG)"; \
		echo "report=training/outputs/comparisons/model_update_$(MODEL_UPDATE_RUN_ID)/model_update_comparison.md"

model-update-log:
	tail -f "$(MODEL_UPDATE_LOG)"

snapshot-model-metrics:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/model_update_report.py snapshot --public-dir ../$(FRONTEND_DIR)/public --output "$(SNAPSHOT_OUTPUT)"

compare-model-metrics:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/model_update_report.py compare --before "$(BEFORE_SNAPSHOT)" --after "$(AFTER_SNAPSHOT)" --output "$(REPORT_OUTPUT)" --markdown-output "$(MARKDOWN_OUTPUT)"

compare-models:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_models.py

compare-national-models:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_national_models.py

compare-commercial-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_commercial_features.py

compare-station-passenger-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_station_passenger_features.py

compare-land-price-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_land_price_features.py --land-price-points-csv "$(LAND_PRICE_POINTS_CSV)" --land-price-city-summary-csv "$(LAND_PRICE_CITY_SUMMARY_CSV)"

compare-external-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_external_features.py --hazards-csv "$(HAZARDS_CSV)"

compare-train-start-years:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_train_start_years.py

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
