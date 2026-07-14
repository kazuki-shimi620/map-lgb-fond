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
LAND_PRICE_TILE_Z ?= 14
LAND_PRICE_TILE_X ?= 14550
LAND_PRICE_TILE_Y ?= 6449
LAND_PRICE_USE_CATEGORY_CODES ?= 00,05
LAND_PRICE_REQUEST_INTERVAL_SECONDS ?= 1.0
LAND_PRICE_POINTS_CSV ?= data/processed/land_prices/land_price_points.csv
LAND_PRICE_CITY_SUMMARY_CSV ?= data/processed/land_prices/land_price_city_summary.csv
POPULATION_INPUT ?=
POPULATION_TEMPLATE ?= data/manual/population/municipality_population_template.csv
ESTAT_STATS_DATA_ID ?=
ESTAT_AREA_CODES ?=
ESTAT_TIME_CODES ?=
ESTAT_ITEMS ?=
POPULATION_STATS_CSV ?= data/processed/population/municipality_population.csv
RAIL_TERMINAL_STATIONS_CSV ?= data/manual/rail/terminal_stations.csv
RAIL_TRAVEL_TIMES_CSV ?= data/manual/rail/major_station_travel_times.csv
RAIL_ACCESS_CSV ?= data/processed/rail/rail_access.csv
NEARBY_FACILITIES_CSV ?= data/processed/facilities/nearby_facilities.csv
NEARBY_FACILITIES_JSON ?= ../$(FRONTEND_DIR)/public/facilities/nearby_facilities.json
NEARBY_FACILITIES_TEMPLATE ?= data/manual/facilities/nearby_facilities_template.csv
EDUCATION_APIS ?= XKT004,XKT005,XKT006,XKT007
EDUCATION_AREA ?= capital
EDUCATION_ZOOM ?= 13
EDUCATION_TILE_Z ?= 13
EDUCATION_TILE_X ?= 7269
EDUCATION_TILE_Y ?= 3235
EDUCATION_ADMINISTRATIVE_AREA_CODES ?=
URBAN_PLANNING_APIS ?= XKT001,XKT002,XKT003
URBAN_PLANNING_AREA ?= capital
URBAN_PLANNING_ZOOM ?= 13
URBAN_PLANNING_TILE_Z ?= 13
URBAN_PLANNING_TILE_X ?= 7269
URBAN_PLANNING_TILE_Y ?= 3235
CRIME_INPUT ?=
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

.PHONY: help setup setup-frontend setup-training setup-csv-download dev build preview verify python-check init-db collect collect-all collect-legacy-api collect-legacy-api-all collect-property collect-property-all collect-sc collect-sc-all collect-station-passengers collect-station-passengers-dry-run collect-station-passengers-national collect-station-passengers-national-dry-run collect-land-prices collect-land-prices-dry-run collect-land-prices-tile collect-population-stats collect-population-stats-template collect-rail-access collect-education-facilities collect-education-facilities-dry-run collect-education-facilities-tile collect-urban-planning collect-urban-planning-dry-run collect-urban-planning-tile collect-crime-stats collect-hazards collect-data download-csv download-csv-all csv-checklist preprocess preprocess-zip preprocess-capital-all-years preprocess-national train train-all train-regional-models train-production-models refresh-production-artifacts model-update-background model-update-log snapshot-model-metrics compare-model-metrics compare-models compare-national-models compare-commercial-features compare-station-passenger-features compare-land-price-features compare-population-features compare-rail-access-features compare-external-features compare-train-start-years compare-outlier-filters summarize-edge-cases summarize-land-price-coverage summarize-population-coverage summarize-urban-planning-coverage summarize-education-coverage check-feature-order histories-national facilities nearby-facilities nearby-facilities-template stations stations-national

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
	@echo "  make collect-station-passengers-dry-run PASSENGER_AREA=capital"
	@echo "                          駅別乗降客数取得のリクエスト数を確認"
	@echo "  make collect-station-passengers-national"
	@echo "                          全国範囲の駅別乗降客数を取得してJSON/CSV化"
	@echo "  make collect-station-passengers-national-dry-run"
	@echo "                          全国範囲の駅別乗降客数取得リクエスト数を確認"
	@echo "  make collect-land-prices LAND_PRICE_YEARS=2024,2025"
	@echo "                          地価公示・地価調査ポイントを取得してCSV化"
	@echo "  make collect-land-prices-dry-run LAND_PRICE_ZOOM=14"
	@echo "                          地価ポイント取得のリクエスト数を確認"
	@echo "  make collect-land-prices-tile LAND_PRICE_TILE_Z=14 LAND_PRICE_TILE_X=14550 LAND_PRICE_TILE_Y=6449"
	@echo "                          地価ポイント取得を1タイルで疎通確認"
	@echo "  make collect-population-stats POPULATION_INPUT=path/to/population.csv"
	@echo "                          自治体人口統計CSVを正規化"
	@echo "  make collect-population-stats ESTAT_STATS_DATA_ID=... ESTAT_ITEMS='population_total=cat01:001 ...'"
	@echo "                          e-Stat APIから自治体人口統計CSVを生成"
	@echo "  make collect-population-stats-template"
	@echo "                          自治体人口統計CSVテンプレートを再生成"
	@echo "  make collect-rail-access"
	@echo "                          路線利便性の手動マスタから特徴量CSVを生成"
	@echo "  make collect-education-facilities"
	@echo "                          学校区・学校・保育園データを取得してCSV化"
	@echo "  make collect-education-facilities-dry-run"
	@echo "                          教育施設取得のリクエスト数を確認"
	@echo "  make collect-education-facilities-tile"
	@echo "                          教育施設取得を1タイルで疎通確認"
	@echo "  make collect-urban-planning"
	@echo "                          用途地域・都市計画データを取得してCSV化"
	@echo "  make collect-urban-planning-dry-run"
	@echo "                          用途地域・都市計画取得のリクエスト数を確認"
	@echo "  make collect-urban-planning-tile"
	@echo "                          用途地域・都市計画取得を1タイルで疎通確認"
	@echo "  make collect-crime-stats CRIME_INPUT=path/to/crime.csv"
	@echo "                          自治体単位の犯罪統計CSVを正規化"
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
	@echo "  make compare-population-features"
	@echo "                          人口統計特徴量のバックテストを実行"
	@echo "  make compare-rail-access-features"
	@echo "                          路線利便性特徴量のバックテストを実行"
	@echo "  make compare-external-features"
	@echo "                          商業施設、駅規模、ハザードの組み合わせバックテストを実行"
	@echo "  make compare-train-start-years"
	@echo "                          学習開始年を複数holdout年で比較"
	@echo "  make compare-outlier-filters"
	@echo "                          外れ値処理候補のバックテストを実行"
	@echo "  make summarize-edge-cases REGION=tokyo"
	@echo "                          築古・駅遠・高額帯などの件数と分布を集計"
	@echo "  make summarize-land-price-coverage"
	@echo "                          地価データのマッチ率、価格水準、変化率、配布サイズを集計"
	@echo "  make summarize-population-coverage"
	@echo "                          人口統計のマッチ率、人口密度、年齢構成、配布サイズを集計"
	@echo "  make summarize-urban-planning-coverage"
	@echo "                          用途地域・都市計画データのマッチ率と配布サイズを集計"
	@echo "  make summarize-education-coverage"
	@echo "                          教育施設データのマッチ率と配布サイズを集計"
	@echo "  make check-feature-order"
	@echo "                          config/metadata の特徴量がフロント推論で扱えるか確認"
	@echo "  make histories-national 類似条件比較用の全国価格推移JSONとトレンドJSONを再生成"
	@echo "  make facilities         商業施設の配信用軽量JSONを再生成"
	@echo "  make nearby-facilities  周辺施設マーカー用JSONを再生成"
	@echo "  make nearby-facilities-template"
	@echo "                          周辺施設CSVテンプレートを再生成"
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

collect-station-passengers-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/station_passengers.py --area $(PASSENGER_AREA) --zoom $(PASSENGER_ZOOM) --dry-run

collect-station-passengers-national:
	$(MAKE) collect-station-passengers PASSENGER_AREA=japan PASSENGER_ZOOM=$(PASSENGER_NATIONAL_ZOOM) PASSENGER_REQUEST_INTERVAL_SECONDS=$(PASSENGER_REQUEST_INTERVAL_SECONDS)

collect-station-passengers-national-dry-run:
	$(MAKE) collect-station-passengers-dry-run PASSENGER_AREA=japan PASSENGER_ZOOM=$(PASSENGER_NATIONAL_ZOOM)

collect-land-prices:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/land_prices.py --area $(LAND_PRICE_AREA) --zoom $(LAND_PRICE_ZOOM) --years "$(LAND_PRICE_YEARS)" --use-category-codes "$(LAND_PRICE_USE_CATEGORY_CODES)" --request-interval-seconds $(LAND_PRICE_REQUEST_INTERVAL_SECONDS) --cache

collect-land-prices-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/land_prices.py --area $(LAND_PRICE_AREA) --zoom $(LAND_PRICE_ZOOM) --years "$(LAND_PRICE_YEARS)" --use-category-codes "$(LAND_PRICE_USE_CATEGORY_CODES)" --dry-run

collect-land-prices-tile:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/land_prices.py --tile $(LAND_PRICE_TILE_Z) $(LAND_PRICE_TILE_X) $(LAND_PRICE_TILE_Y) --years "$(LAND_PRICE_YEARS)" --use-category-codes "$(LAND_PRICE_USE_CATEGORY_CODES)" --request-interval-seconds $(LAND_PRICE_REQUEST_INTERVAL_SECONDS) --cache

collect-population-stats:
	cd $(TRAINING_DIR) && \
	if [ -n "$(POPULATION_INPUT)" ]; then \
		$(TRAINING_PYTHON) src/collect/population_stats.py --input "$(POPULATION_INPUT)"; \
	elif [ -n "$(ESTAT_STATS_DATA_ID)" ]; then \
		$(TRAINING_PYTHON) src/collect/population_stats.py \
			--estat-stats-data-id "$(ESTAT_STATS_DATA_ID)" \
			--estat-area-codes $(ESTAT_AREA_CODES) \
			--estat-time-codes $(ESTAT_TIME_CODES) \
			$(foreach item,$(ESTAT_ITEMS),--estat-item "$(item)"); \
	else \
		echo "POPULATION_INPUT or ESTAT_STATS_DATA_ID is required"; \
		exit 1; \
	fi

collect-population-stats-template:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/population_stats.py --write-template "$(POPULATION_TEMPLATE)"

collect-rail-access:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/rail_access.py --terminal-stations-csv "$(RAIL_TERMINAL_STATIONS_CSV)" --travel-times-csv "$(RAIL_TRAVEL_TIMES_CSV)"

collect-education-facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/education_facilities.py --apis "$(EDUCATION_APIS)" --area $(EDUCATION_AREA) --zoom $(EDUCATION_ZOOM) --administrative-area-codes "$(EDUCATION_ADMINISTRATIVE_AREA_CODES)" --cache

collect-education-facilities-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/education_facilities.py --apis "$(EDUCATION_APIS)" --area $(EDUCATION_AREA) --zoom $(EDUCATION_ZOOM) --administrative-area-codes "$(EDUCATION_ADMINISTRATIVE_AREA_CODES)" --dry-run

collect-education-facilities-tile:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/education_facilities.py --apis "$(EDUCATION_APIS)" --tile $(EDUCATION_TILE_Z) $(EDUCATION_TILE_X) $(EDUCATION_TILE_Y) --administrative-area-codes "$(EDUCATION_ADMINISTRATIVE_AREA_CODES)" --cache

collect-urban-planning:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/urban_planning.py --apis "$(URBAN_PLANNING_APIS)" --area $(URBAN_PLANNING_AREA) --zoom $(URBAN_PLANNING_ZOOM) --cache

collect-urban-planning-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/urban_planning.py --apis "$(URBAN_PLANNING_APIS)" --area $(URBAN_PLANNING_AREA) --zoom $(URBAN_PLANNING_ZOOM) --dry-run

collect-urban-planning-tile:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/urban_planning.py --apis "$(URBAN_PLANNING_APIS)" --tile $(URBAN_PLANNING_TILE_Z) $(URBAN_PLANNING_TILE_X) $(URBAN_PLANNING_TILE_Y) --cache

collect-crime-stats:
	cd $(TRAINING_DIR) && \
	if [ -n "$(CRIME_INPUT)" ]; then \
		$(TRAINING_PYTHON) src/collect/crime_stats.py --input "$(CRIME_INPUT)"; \
	else \
		echo "CRIME_INPUT is required"; \
		exit 1; \
	fi

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

compare-population-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_population_features.py --population-stats-csv "$(POPULATION_STATS_CSV)"

compare-rail-access-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_rail_access_features.py --rail-access-csv "$(RAIL_ACCESS_CSV)"

compare-external-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_external_features.py --hazards-csv "$(HAZARDS_CSV)"

compare-train-start-years:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_train_start_years.py

compare-outlier-filters:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_outlier_filters.py

summarize-edge-cases:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/dataset_edge_cases.py --input $(PROCESSED_OUTPUT) --region $(REGION)

summarize-land-price-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/land_price_coverage.py --regions $(REGIONS) --land-price-points-csv "$(LAND_PRICE_POINTS_CSV)" --land-price-city-summary-csv "$(LAND_PRICE_CITY_SUMMARY_CSV)"

summarize-population-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/population_coverage.py --regions $(REGIONS) --population-stats-csv "$(POPULATION_STATS_CSV)"

summarize-urban-planning-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/urban_planning_coverage.py --regions $(REGIONS)

summarize-education-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/education_coverage.py --regions $(REGIONS)

check-feature-order:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.feature_order \
		--config $(FEATURE_ORDER_CONFIGS) \
		--metadata $(FEATURE_ORDER_METADATA)

histories-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.histories --public-dir ../$(FRONTEND_DIR)/public

facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.commercial_facilities --output ../$(FRONTEND_DIR)/public/facilities/commercial_facilities.json

nearby-facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.nearby_facilities --input-csv "$(NEARBY_FACILITIES_CSV)" --output "$(NEARBY_FACILITIES_JSON)"

nearby-facilities-template:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.nearby_facilities --write-template "$(NEARBY_FACILITIES_TEMPLATE)"

stations:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --regions $(REGIONS) --station-passengers-csv $(STATION_PASSENGERS_CSV)

stations-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --station-passengers-csv $(STATION_PASSENGERS_CSV)
