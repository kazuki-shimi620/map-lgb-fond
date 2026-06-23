# Workflows

## Continue Frontend Implementation

1. Read `docs/frontend.md`.
2. Inspect `frontend/src/App.tsx` and relevant `frontend/src/features/*` files.
3. Keep model asset paths relative to Vite public root:
   - `./models/{region}_latest.onnx`
   - `./metadata/{region}_latest_metadata.json`
   - `./metadata/{region}_latest_categories.json`
   - `./histories/{region}_latest_history.json`
   - `./stations/{region}_stations.json`
4. Keep form input editable after map autofill.
5. Run `npm run build`.

## Continue Training Implementation

1. Read `docs/training.md` and `docs/database.md`.
2. Keep stages isolated:
   - collect: MLIT Real Estate Information Library API download and Shift_JIS conversion
   - preprocess: UTF-8, types, missing values, IQR
   - features: FeatureProvider and category dictionary
   - train: LightGBM or fallback baseline only when dependencies are missing
   - evaluate: MAE, RMSE, MAPE
   - export: pkl, ONNX, category JSON, metadata JSON, history JSON, frontend copy
   - experiment: SQLite records and latest model rule
3. Use config files in `training/configs/*.yaml`.
4. Run `python3 -m compileall training/src`.

Collect command:

```bash
cd training
REINFOLIB_API_KEY=... uv run python src/collect/collect.py --region tokyo --year 2025 --output-dir data/raw
```

Preprocess command:

```bash
uv run python src/preprocess/preprocess.py --input data/raw/tokyo_2025_xit001.json --output data/processed/tokyo.parquet
```

Multiple ZIP files can be combined into one region dataset:

```bash
uv run python src/preprocess/preprocess.py \
  --input data/raw/mlit_tokyo_2020.zip data/raw/mlit_tokyo_2021.zip data/raw/mlit_tokyo_2022.zip data/raw/mlit_tokyo_2023.zip data/raw/mlit_tokyo_2024.zip data/raw/mlit_tokyo_2025.zip \
  --output data/processed/tokyo.parquet
```

## Add A New FeatureProvider

1. Add provider class in `training/src/features/providers.py` or a focused module if it becomes large.
2. Register it through the pipeline factory.
3. Add feature names to config YAML and docs.
4. If categorical, add dictionary mapping support in `category_dictionary.py`.
5. Update experiment feature registration implicitly through config features.

## Add A New Region

1. Add `training/configs/{region}.yaml`.
2. Generate model and JSON assets through training export.
3. Place latest assets in:
   - `frontend/public/models/{region}_latest.onnx`
   - `frontend/public/metadata/{region}_latest_metadata.json`
   - `frontend/public/metadata/{region}_latest_categories.json`
   - `frontend/public/histories/{region}_latest_history.json`
   - `frontend/public/stations/{region}_stations.json`
4. Add prefecture-to-region mapping in `frontend/src/utils/region.ts`.

## Documentation Changes

1. Update `docs/requirements.md` for product-level changes.
2. Update `docs/implementation.md` for implementation strategy changes.
3. Update component-specific docs when behavior changes.
4. Keep README focused on setup and execution.
