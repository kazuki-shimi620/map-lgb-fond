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
LAND_PRICE_PUBLIC_JSON ?= ../$(FRONTEND_DIR)/public/land-prices/municipality_land_prices.json
URBAN_PLANNING_PUBLIC_JSON ?= ../$(FRONTEND_DIR)/public/urban-planning/urban_planning_areas.json
ADDRESS_POINTS_INPUT ?=
ADDRESS_POINTS_SOURCE_URL ?= https://geolonia.github.io/japanese-addresses/latest.csv
ADDRESS_POINTS_CSV ?= data/processed/address_points/town_points.csv
COORDINATE_ENRICHED_DIR ?= data/processed/with_address_coordinates
COORDINATE_INCLUDE_MUNICIPALITY_FALLBACK ?= 0
SPATIAL_DRY_RUN_SAMPLE_SIZE ?= 200
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
MUSEUM_REGIONS ?= hokkaido tohoku kanto chubu kinki chugoku shikoku kyushu okinawa
MUSEUM_FACILITIES_INPUTS := $(foreach region,$(MUSEUM_REGIONS),data/processed/osm_nearby/museum_$(region)/nearby_osm_facilities.csv)
NEARBY_FACILITIES_INPUTS ?= data/processed/osm_nearby/cinema_japan/nearby_osm_facilities.csv $(MUSEUM_FACILITIES_INPUTS) data/processed/osm_nearby/hot_spring_public_bath_node_japan/nearby_osm_facilities.csv data/processed/osm_nearby/hot_spring_natural_japan/nearby_osm_facilities.csv data/processed/osm_nearby/hot_spring_spa_japan/nearby_osm_facilities.csv data/processed/osm_nearby/entertainment_capital/nearby_osm_facilities.csv
NEARBY_FACILITIES_JSON ?= ../$(FRONTEND_DIR)/public/facilities/nearby_facilities.json
NEARBY_FACILITIES_TEMPLATE ?= data/manual/facilities/nearby_facilities_template.csv
CINEMA_CHAINS_RAW_DIR ?= data/raw/cinemas
CINEMA_CHAINS_CSV ?= data/processed/cinemas/official_chain_cinemas.csv
CINEMA_OSM_CSV ?= data/processed/osm_nearby/cinema_japan/nearby_osm_facilities.csv
CINEMA_ENRICHED_CSV ?= data/processed/cinemas/official_chain_cinemas_enriched.csv
CINEMA_REVIEW_CSV ?= data/processed/cinemas/official_chain_cinemas_review.csv
CINEMA_PRIORITY_REVIEW_CSV ?= data/processed/cinemas/official_chain_cinemas_priority_review.csv
CINEMA_COORDINATES_CSV ?= data/processed/cinemas/official_chain_cinema_coordinates.csv
CINEMA_MANUAL_COORDINATES_CSV ?= data/manual/cinemas/cinema_coordinates.csv
CINEMA_COVERAGE_JSON ?= data/processed/cinemas/coverage.json
COMMERCIAL_FACILITIES_CSV ?= data/processed/jcsc/jcsc_sc_open.csv
COMMERCIAL_FACILITIES_COORDINATED_CSV ?= data/processed/jcsc/jcsc_sc_open_with_coordinates.csv
COMMERCIAL_FACILITIES_INPUTS ?= $(COMMERCIAL_FACILITIES_COORDINATED_CSV) $(JCSC_SC_PDF_COORDINATED_CSV)
COMMERCIAL_FACILITIES_MANUAL_COORDINATES_CSV ?= data/manual/facilities/commercial_facility_manual_coordinates.csv
COMMERCIAL_FACILITIES_MUNICIPALITY_ALIASES_CSV ?= data/manual/facilities/commercial_facility_municipality_aliases.csv
COMMERCIAL_FACILITIES_ROW_CORRECTIONS_CSV ?= data/manual/facilities/commercial_facility_row_corrections.csv
JCSC_SC_PDF ?=
JCSC_SC_PDF_OUTPUT_DIR ?= data/processed/jcsc_pdf
JCSC_SC_PDF_PAGE_LIMIT ?=
JCSC_SC_EXISTING_CSV ?= data/processed/jcsc/jcsc_sc_open.csv
JCSC_SC_MUNICIPALITY_PREFECTURE_CSV ?= data/processed/address_points/town_points.csv
JCSC_SC_PDF_CANDIDATES_CSV ?= data/processed/jcsc_pdf/jcsc_sc_pdf_new_candidates.csv
JCSC_SC_PDF_COORDINATED_CSV ?= data/processed/jcsc_pdf/jcsc_sc_pdf_new_candidates_with_coordinates.csv
JCSC_SC_PDF_FACILITIES_CSV ?= data/processed/jcsc_pdf/jcsc_sc_pdf_facilities.csv
JCSC_SC_PDF_COORDINATE_UNRESOLVED_CSV ?= data/manual/facilities/commercial_facility_low_confidence_geocode_review.csv
EDUCATION_APIS ?= XKT004,XKT005,XKT006,XKT007
EDUCATION_AREA ?= capital
EDUCATION_ZOOM ?= 13
EDUCATION_TILE_Z ?= 13
EDUCATION_TILE_X ?= 7269
EDUCATION_TILE_Y ?= 3235
EDUCATION_ADMINISTRATIVE_AREA_CODES ?=
EDUCATION_REQUEST_INTERVAL_SECONDS ?= 1.0
MEDICAL_AREA ?= capital
MEDICAL_ZOOM ?= 13
MEDICAL_TILE_Z ?= 13
MEDICAL_TILE_X ?= 7269
MEDICAL_TILE_Y ?= 3235
MEDICAL_REQUEST_INTERVAL_SECONDS ?= 1.0
OSM_NEARBY_AREA ?= capital
OSM_NEARBY_CATEGORIES ?= supermarket,convenience_store,park
OSM_NEARBY_TIMEOUT_SECONDS ?= 180
OSM_PARK_AREA ?= tokyo
OSM_PARK_BBOX ?=
OSM_PARK_RUN_ID ?= latest_park_$(OSM_PARK_AREA)_geometry
OSM_PARK_PROCESSED_DIR ?= data/processed/osm_nearby/park_$(OSM_PARK_AREA)_geometry
OSM_PARK_SPLIT_SIZE_DEGREES ?=
OSM_PARK_REQUEST_INTERVAL_SECONDS ?= 1.0
OSM_PARK_CONTINUE_ON_ERROR ?=
URBAN_PLANNING_APIS ?= XKT001,XKT002,XKT003
URBAN_PLANNING_AREA ?= capital
URBAN_PLANNING_ZOOM ?= 13
URBAN_PLANNING_TILE_Z ?= 13
URBAN_PLANNING_TILE_X ?= 7269
URBAN_PLANNING_TILE_Y ?= 3235
URBAN_PLANNING_REQUEST_INTERVAL_SECONDS ?= 1.0
URBAN_PLANNING_CSV ?= data/processed/urban_planning/urban_planning_areas.csv
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
TRAINING_OCR_PYTHON := .venv/bin/python
else
TRAINING_PYTHON := $(UV) run python
TRAINING_OCR_PYTHON := $(UV) run --extra ocr python
endif

-include $(TRAINING_DIR)/.env
export REINFOLIB_API_KEY

.PHONY: help setup setup-frontend setup-training setup-csv-download dev build preview verify python-check init-db collect collect-all collect-legacy-api collect-legacy-api-all collect-property collect-property-all collect-sc collect-sc-all collect-sc-pdf audit-sc-pdf-months collect-station-passengers collect-station-passengers-dry-run collect-station-passengers-national collect-station-passengers-national-dry-run collect-land-prices collect-land-prices-dry-run collect-land-prices-tile collect-address-points collect-population-stats collect-population-stats-template collect-rail-access collect-education-facilities collect-education-facilities-dry-run collect-education-facilities-tile collect-medical-facilities collect-medical-facilities-dry-run collect-medical-facilities-tile collect-osm-nearby-facilities collect-osm-nearby-facilities-dry-run collect-osm-park-areas collect-cinema-chains collect-cinema-osm-national collect-hot-springs-national collect-museums-national collect-cinema-coordinates collect-cinema-coordinates-dry-run enrich-cinemas collect-urban-planning collect-urban-planning-dry-run collect-urban-planning-tile collect-crime-stats collect-hazards collect-data download-csv download-csv-all csv-checklist preprocess preprocess-zip preprocess-capital-all-years preprocess-national enrich-coordinates enrich-commercial-facilities enrich-sc-pdf-candidates commercial-facility-manual-template train train-all train-regional-models train-production-models refresh-production-artifacts model-update-background model-update-log snapshot-model-metrics compare-model-metrics compare-models compare-national-models compare-commercial-features compare-station-passenger-features compare-land-price-features compare-urban-planning-features compare-location-features compare-population-features compare-rail-access-features compare-external-features compare-nearby-poi-features compare-train-start-years compare-outlier-filters summarize-edge-cases summarize-land-price-coverage summarize-coordinate-coverage summarize-population-coverage summarize-urban-planning-coverage summarize-education-coverage summarize-spatial-dry-run check-feature-order histories-national facilities land-prices urban-planning nearby-facilities nearby-facilities-template stations stations-national

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
	@echo "  make collect-address-points"
	@echo "                          町丁目代表点CSVを取得または正規化"
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
	@echo "  make collect-medical-facilities"
	@echo "                          医療機関データを取得してCSV化"
	@echo "  make collect-medical-facilities-dry-run"
	@echo "                          医療機関取得のリクエスト数を確認"
	@echo "  make collect-medical-facilities-tile"
	@echo "                          医療機関取得を1タイルで疎通確認"
	@echo "  make collect-osm-nearby-facilities"
	@echo "                          OSMからスーパー・コンビニ・公園を取得してCSV化"
	@echo "  make collect-osm-nearby-facilities-dry-run"
	@echo "                          OSM周辺施設取得クエリを確認"
	@echo "  make collect-cinema-chains"
	@echo "                          大手映画館7系列の公式一覧をキャッシュしてCSV化"
	@echo "  make collect-cinema-osm-national"
	@echo "                          全国のOSM映画館を1リクエストでキャッシュ"
	@echo "  make collect-hot-springs-national"
	@echo "                          全国の公衆浴場node・天然温泉・スパを分割取得"
	@echo "  make collect-museums-national"
	@echo "                          全国の美術館・博物館を地域グリッド分割でキャッシュ"
	@echo "  make enrich-cinemas     公式映画館をOSM・JCSCと照合してcoverageを出力"
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
	@echo "  make compare-nearby-poi-features"
	@echo "                          東京3万件で周辺施設POI特徴量を探索比較"
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
	@echo "  make enrich-coordinates  町丁目代表点で検証用lat/lon付きParquetを生成"
	@echo "  make enrich-commercial-facilities"
	@echo "                          JCSC商業施設CSVへ町丁目代表点のlat/lonを付与"
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
	@echo "  make compare-urban-planning-features"
	@echo "                          用途地域特徴量のバックテストを実行"
	@echo "  make compare-location-features"
	@echo "                          地価・用途地域の組み合わせバックテストを実行"
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
	@echo "  make summarize-coordinate-coverage"
	@echo "                          町丁目代表点による取引座標付与カバレッジを集計"
	@echo "  make summarize-population-coverage"
	@echo "                          人口統計のマッチ率、人口密度、年齢構成、配布サイズを集計"
	@echo "  make summarize-urban-planning-coverage"
	@echo "                          用途地域・都市計画データのマッチ率と配布サイズを集計"
	@echo "  make summarize-education-coverage"
	@echo "                          教育施設データのマッチ率と配布サイズを集計"
	@echo "  make summarize-spatial-dry-run"
	@echo "                          座標付き検証Parquetで空間特徴量をサンプル評価"
	@echo "  make check-feature-order"
	@echo "                          config/metadata の特徴量がフロント推論で扱えるか確認"
	@echo "  make histories-national 類似条件比較用の全国価格推移JSONとトレンドJSONを再生成"
	@echo "  make facilities         商業施設の配信用軽量JSONを再生成"
	@echo "  make land-prices        地価の市区町村別軽量JSONを再生成"
	@echo "  make urban-planning     用途地域の配信用軽量JSONを再生成"
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

collect-sc-pdf:
	@if [ -z "$(JCSC_SC_PDF)" ]; then \
		echo "JCSC_SC_PDF is required"; \
		exit 1; \
	fi
	cd $(TRAINING_DIR) && $(TRAINING_OCR_PYTHON) src/collect/jcsc_sc_pdf.py --pdf "$(JCSC_SC_PDF)" --output-dir "$(JCSC_SC_PDF_OUTPUT_DIR)" --existing-csv "$(JCSC_SC_EXISTING_CSV)" --municipality-prefecture-csv "$(JCSC_SC_MUNICIPALITY_PREFECTURE_CSV)" $(if $(strip $(JCSC_SC_PDF_PAGE_LIMIT)),--page-limit $(JCSC_SC_PDF_PAGE_LIMIT),)

audit-sc-pdf-months:
	@if [ -z "$(JCSC_SC_PDF)" ]; then \
		echo "JCSC_SC_PDF is required"; \
		exit 1; \
	fi
	cd $(TRAINING_DIR) && $(TRAINING_OCR_PYTHON) src/collect/jcsc_sc_pdf.py --audit-month-counts --pdf "$(JCSC_SC_PDF)" --output-dir "$(JCSC_SC_PDF_OUTPUT_DIR)" --facilities-csv "$(JCSC_SC_PDF_FACILITIES_CSV)" $(if $(strip $(JCSC_SC_PDF_PAGE_LIMIT)),--page-limit $(JCSC_SC_PDF_PAGE_LIMIT),)

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

collect-address-points:
	cd $(TRAINING_DIR) && \
	if [ -n "$(ADDRESS_POINTS_INPUT)" ]; then \
		$(TRAINING_PYTHON) src/collect/address_points.py --input "$(ADDRESS_POINTS_INPUT)"; \
	else \
		$(TRAINING_PYTHON) src/collect/address_points.py --source-url "$(ADDRESS_POINTS_SOURCE_URL)"; \
	fi

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
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/education_facilities.py --apis "$(EDUCATION_APIS)" --area $(EDUCATION_AREA) --zoom $(EDUCATION_ZOOM) --administrative-area-codes "$(EDUCATION_ADMINISTRATIVE_AREA_CODES)" --request-interval-seconds $(EDUCATION_REQUEST_INTERVAL_SECONDS) --cache

collect-education-facilities-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/education_facilities.py --apis "$(EDUCATION_APIS)" --area $(EDUCATION_AREA) --zoom $(EDUCATION_ZOOM) --administrative-area-codes "$(EDUCATION_ADMINISTRATIVE_AREA_CODES)" --dry-run

collect-education-facilities-tile:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/education_facilities.py --apis "$(EDUCATION_APIS)" --tile $(EDUCATION_TILE_Z) $(EDUCATION_TILE_X) $(EDUCATION_TILE_Y) --administrative-area-codes "$(EDUCATION_ADMINISTRATIVE_AREA_CODES)" --request-interval-seconds $(EDUCATION_REQUEST_INTERVAL_SECONDS) --cache

collect-medical-facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/medical_facilities.py --area $(MEDICAL_AREA) --zoom $(MEDICAL_ZOOM) --request-interval-seconds $(MEDICAL_REQUEST_INTERVAL_SECONDS) --cache

collect-medical-facilities-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/medical_facilities.py --area $(MEDICAL_AREA) --zoom $(MEDICAL_ZOOM) --dry-run

collect-medical-facilities-tile:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/medical_facilities.py --tile $(MEDICAL_TILE_Z) $(MEDICAL_TILE_X) $(MEDICAL_TILE_Y) --request-interval-seconds $(MEDICAL_REQUEST_INTERVAL_SECONDS) --cache

collect-osm-nearby-facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --area $(OSM_NEARBY_AREA) --categories "$(OSM_NEARBY_CATEGORIES)" --timeout-seconds $(OSM_NEARBY_TIMEOUT_SECONDS) --cache

collect-osm-nearby-facilities-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --area $(OSM_NEARBY_AREA) --categories "$(OSM_NEARBY_CATEGORIES)" --timeout-seconds $(OSM_NEARBY_TIMEOUT_SECONDS) --dry-run

collect-osm-park-areas:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py $(if $(strip $(OSM_PARK_BBOX)),--bbox $(OSM_PARK_BBOX),--area $(OSM_PARK_AREA)) --categories park --timeout-seconds $(OSM_NEARBY_TIMEOUT_SECONDS) --run-id "$(OSM_PARK_RUN_ID)" --processed-dir "$(OSM_PARK_PROCESSED_DIR)" --include-geometry --request-interval-seconds $(OSM_PARK_REQUEST_INTERVAL_SECONDS) $(if $(strip $(OSM_PARK_SPLIT_SIZE_DEGREES)),--split-size-degrees $(OSM_PARK_SPLIT_SIZE_DEGREES),) $(if $(strip $(OSM_PARK_CONTINUE_ON_ERROR)),--continue-on-error,) --cache

collect-cinema-chains:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/cinema_chains.py --raw-dir "$(CINEMA_CHAINS_RAW_DIR)" --output "$(CINEMA_CHAINS_CSV)"

collect-cinema-osm-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --area japan --categories cinema --timeout-seconds 300 --cache --run-id latest_cinema_japan --processed-dir data/processed/osm_nearby/cinema_japan

collect-hot-springs-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --area japan --categories hot_spring_public_bath_node --timeout-seconds 300 --cache --run-id latest_hot_spring_public_bath_node_japan --processed-dir data/processed/osm_nearby/hot_spring_public_bath_node_japan
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --area japan --categories hot_spring_natural --timeout-seconds 300 --cache --run-id latest_hot_spring_natural_japan --processed-dir data/processed/osm_nearby/hot_spring_natural_japan
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --area japan --categories hot_spring_spa --timeout-seconds 300 --cache --run-id latest_hot_spring_spa_japan --processed-dir data/processed/osm_nearby/hot_spring_spa_japan

collect-museums-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 41.3 139.3 45.7 145.9 --categories museum --split-size-degrees 1 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_hokkaido --processed-dir data/processed/osm_nearby/museum_hokkaido
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 36.8 139.4 41.6 142.2 --categories museum --split-size-degrees 1 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_tohoku --processed-dir data/processed/osm_nearby/museum_tohoku
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 34.8 138.4 37.2 141.1 --categories museum --split-size-degrees 0.5 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_kanto --processed-dir data/processed/osm_nearby/museum_kanto
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 34.2 136.0 38.0 139.9 --categories museum --split-size-degrees 0.75 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_chubu --processed-dir data/processed/osm_nearby/museum_chubu
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 33.4 134.8 35.8 136.9 --categories museum --split-size-degrees 0.75 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_kinki --processed-dir data/processed/osm_nearby/museum_kinki
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 33.7 130.7 35.6 135.6 --categories museum --split-size-degrees 1 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_chugoku --processed-dir data/processed/osm_nearby/museum_chugoku
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 32.7 132.0 34.6 134.8 --categories museum --split-size-degrees 1 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_shikoku --processed-dir data/processed/osm_nearby/museum_shikoku
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 30.9 129.3 34.0 132.1 --categories museum --split-size-degrees 0.75 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_kyushu --processed-dir data/processed/osm_nearby/museum_kyushu
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/osm_nearby_facilities.py --bbox 24.0 122.9 27.1 131.4 --categories museum --split-size-degrees 1 --timeout-seconds 120 --request-interval-seconds 1 --continue-on-error --cache --run-id latest_museum_okinawa --processed-dir data/processed/osm_nearby/museum_okinawa

enrich-cinemas:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/preprocess/enrich_cinemas.py --cinemas "$(CINEMA_CHAINS_CSV)" --osm "$(CINEMA_OSM_CSV)" --jcsc "$(COMMERCIAL_FACILITIES_COORDINATED_CSV)" --jcsc "$(JCSC_SC_PDF_COORDINATED_CSV)" --manual-coordinates "$(CINEMA_COORDINATES_CSV)" --manual-coordinates "$(CINEMA_MANUAL_COORDINATES_CSV)" --output "$(CINEMA_ENRICHED_CSV)" --review-output "$(CINEMA_REVIEW_CSV)" --priority-review-output "$(CINEMA_PRIORITY_REVIEW_CSV)" --report-output "$(CINEMA_COVERAGE_JSON)"

collect-cinema-coordinates-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/cinema_coordinates.py --review-csv "$(CINEMA_PRIORITY_REVIEW_CSV)" --output-csv "$(CINEMA_COORDINATES_CSV)" --dry-run

collect-cinema-coordinates:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/cinema_coordinates.py --review-csv "$(CINEMA_PRIORITY_REVIEW_CSV)" --output-csv "$(CINEMA_COORDINATES_CSV)"

collect-urban-planning:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/urban_planning.py --apis "$(URBAN_PLANNING_APIS)" --area $(URBAN_PLANNING_AREA) --zoom $(URBAN_PLANNING_ZOOM) --request-interval-seconds $(URBAN_PLANNING_REQUEST_INTERVAL_SECONDS) --cache

collect-urban-planning-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/urban_planning.py --apis "$(URBAN_PLANNING_APIS)" --area $(URBAN_PLANNING_AREA) --zoom $(URBAN_PLANNING_ZOOM) --dry-run

collect-urban-planning-tile:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/collect/urban_planning.py --apis "$(URBAN_PLANNING_APIS)" --tile $(URBAN_PLANNING_TILE_Z) $(URBAN_PLANNING_TILE_X) $(URBAN_PLANNING_TILE_Y) --request-interval-seconds $(URBAN_PLANNING_REQUEST_INTERVAL_SECONDS) --cache

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

enrich-coordinates:
	cd $(TRAINING_DIR) && \
	if [ "$(COORDINATE_INCLUDE_MUNICIPALITY_FALLBACK)" = "1" ]; then \
		$(TRAINING_PYTHON) src/preprocess/enrich_coordinates.py --regions $(REGIONS) --address-points-csv "$(ADDRESS_POINTS_CSV)" --output-dir "$(COORDINATE_ENRICHED_DIR)" --include-municipality-fallback; \
	else \
		$(TRAINING_PYTHON) src/preprocess/enrich_coordinates.py --regions $(REGIONS) --address-points-csv "$(ADDRESS_POINTS_CSV)" --output-dir "$(COORDINATE_ENRICHED_DIR)"; \
	fi

enrich-commercial-facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/preprocess/enrich_commercial_facilities.py --input-csv "$(COMMERCIAL_FACILITIES_CSV)" --address-points-csv "$(ADDRESS_POINTS_CSV)" --output-csv "$(COMMERCIAL_FACILITIES_COORDINATED_CSV)" --manual-coordinates-csv "$(COMMERCIAL_FACILITIES_MANUAL_COORDINATES_CSV)" --municipality-aliases-csv "$(COMMERCIAL_FACILITIES_MUNICIPALITY_ALIASES_CSV)" --row-corrections-csv "$(COMMERCIAL_FACILITIES_ROW_CORRECTIONS_CSV)"

enrich-sc-pdf-candidates:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/preprocess/enrich_commercial_facilities.py --input-csv "$(JCSC_SC_PDF_CANDIDATES_CSV)" --address-points-csv "$(ADDRESS_POINTS_CSV)" --output-csv "$(JCSC_SC_PDF_COORDINATED_CSV)" --manual-coordinates-csv "$(COMMERCIAL_FACILITIES_MANUAL_COORDINATES_CSV)" --municipality-aliases-csv "$(COMMERCIAL_FACILITIES_MUNICIPALITY_ALIASES_CSV)" --row-corrections-csv "$(COMMERCIAL_FACILITIES_ROW_CORRECTIONS_CSV)" --coordinate-unresolved-csv "$(JCSC_SC_PDF_COORDINATE_UNRESOLVED_CSV)" --allow-municipality-fallback

commercial-facility-manual-template:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/preprocess/enrich_commercial_facilities.py --write-manual-template "$(COMMERCIAL_FACILITIES_MANUAL_COORDINATES_CSV)"

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
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_commercial_features.py --facilities-csv $(COMMERCIAL_FACILITIES_INPUTS)

compare-station-passenger-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_station_passenger_features.py

compare-land-price-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_land_price_features.py --land-price-points-csv "$(LAND_PRICE_POINTS_CSV)" --land-price-city-summary-csv "$(LAND_PRICE_CITY_SUMMARY_CSV)"

compare-urban-planning-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_urban_planning_features.py

compare-location-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_location_features.py --land-price-points-csv "$(LAND_PRICE_POINTS_CSV)" --land-price-city-summary-csv "$(LAND_PRICE_CITY_SUMMARY_CSV)"

compare-population-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_population_features.py --population-stats-csv "$(POPULATION_STATS_CSV)"

compare-rail-access-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_rail_access_features.py --rail-access-csv "$(RAIL_ACCESS_CSV)"

compare-external-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_external_features.py --hazards-csv "$(HAZARDS_CSV)"

compare-nearby-poi-features:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_nearby_poi_features.py

compare-train-start-years:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_train_start_years.py

compare-outlier-filters:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/compare_outlier_filters.py

summarize-edge-cases:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/dataset_edge_cases.py --input $(PROCESSED_OUTPUT) --region $(REGION)

summarize-land-price-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/land_price_coverage.py --regions $(REGIONS) --land-price-points-csv "$(LAND_PRICE_POINTS_CSV)" --land-price-city-summary-csv "$(LAND_PRICE_CITY_SUMMARY_CSV)"

summarize-coordinate-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/address_coordinate_coverage.py --regions $(REGIONS) --address-points-csv "$(ADDRESS_POINTS_CSV)"

summarize-population-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/population_coverage.py --regions $(REGIONS) --population-stats-csv "$(POPULATION_STATS_CSV)"

summarize-urban-planning-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/urban_planning_coverage.py --regions $(REGIONS)

summarize-education-coverage:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/education_coverage.py --regions $(REGIONS)

summarize-spatial-dry-run:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/land_price_coverage.py --regions $(REGIONS) --processed-dir "$(COORDINATE_ENRICHED_DIR)" --land-price-points-csv "$(LAND_PRICE_POINTS_CSV)" --land-price-city-summary-csv "$(LAND_PRICE_CITY_SUMMARY_CSV)" --output-dir outputs/reports/spatial_dry_run/land_prices --sample-size $(SPATIAL_DRY_RUN_SAMPLE_SIZE)
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/urban_planning_coverage.py --regions $(REGIONS) --processed-dir "$(COORDINATE_ENRICHED_DIR)" --output-dir outputs/reports/spatial_dry_run/urban_planning --sample-size $(SPATIAL_DRY_RUN_SAMPLE_SIZE)
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) src/evaluate/education_coverage.py --regions $(REGIONS) --processed-dir "$(COORDINATE_ENRICHED_DIR)" --output-dir outputs/reports/spatial_dry_run/education --sample-size $(SPATIAL_DRY_RUN_SAMPLE_SIZE)

check-feature-order:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.feature_order \
		--config $(FEATURE_ORDER_CONFIGS) \
		--metadata $(FEATURE_ORDER_METADATA)

histories-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.histories --public-dir ../$(FRONTEND_DIR)/public

facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.commercial_facilities --input $(COMMERCIAL_FACILITIES_INPUTS) --output ../$(FRONTEND_DIR)/public/facilities/commercial_facilities.json

land-prices:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.land_prices --input "$(LAND_PRICE_CITY_SUMMARY_CSV)" --output "$(LAND_PRICE_PUBLIC_JSON)"

urban-planning:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.urban_planning --input "$(URBAN_PLANNING_CSV)" --output "$(URBAN_PLANNING_PUBLIC_JSON)"

nearby-facilities:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.nearby_facilities $(if $(strip $(NEARBY_FACILITIES_INPUTS)),--input-csv $(NEARBY_FACILITIES_INPUTS),) --commercial-facilities-csv $(COMMERCIAL_FACILITIES_INPUTS) --output "$(NEARBY_FACILITIES_JSON)"

nearby-facilities-template:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.nearby_facilities --write-template "$(NEARBY_FACILITIES_TEMPLATE)"

stations:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --regions $(REGIONS) --station-passengers-csv $(STATION_PASSENGERS_CSV)

stations-national:
	cd $(TRAINING_DIR) && $(TRAINING_PYTHON) -m src.export.stations --public-dir ../$(FRONTEND_DIR)/public --station-passengers-csv $(STATION_PASSENGERS_CSV)
