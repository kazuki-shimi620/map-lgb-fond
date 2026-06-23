# Project Map

## Purpose

`map-lgb-fond` is a portfolio-oriented real estate price prediction app for used apartments.

Core goals:

- Train LightGBM models from MLIT real estate transaction data.
- Export ONNX models for browser inference.
- Run prediction in a React/Vite frontend without a backend.
- Keep feature additions easy through FeatureProvider-style training code.
- Manage models by prefecture.

## Source Of Truth

- `docs/requirements.md`: product requirements and scope.
- `docs/implementation.md`: implementation-level structure and priorities.
- `docs/frontend.md`: frontend DTOs, ModelManager, map behavior, station lookup, chart behavior.
- `docs/training.md`: collect, preprocess, feature, train, evaluate, export responsibilities.
- `docs/database.md`: SQLite schema, constraints, latest model rule.
- `docs/architecture.md`: high-level component flow.

## Important Paths

- `frontend/src/App.tsx`: single-screen app composition.
- `frontend/src/features/model/ModelManager.ts`: model, metadata, category dictionary loading and prediction.
- `frontend/src/features/map/PropertyMap.tsx`: Leaflet map input.
- `frontend/public/metadata/`: category dictionaries and model metadata.
- `frontend/public/histories/`: station/year price history JSON.
- `frontend/public/stations/`: station master JSON.
- `training/src/train/train.py`: training pipeline entrypoint.
- `training/src/features/`: FeatureProvider-style feature logic and category dictionary generation.
- `training/src/export/artifacts.py`: model and JSON artifact writing plus frontend copy.
- `training/src/experiment/database.py`: SQLite schema and latest model management.

## Current Practical Constraints

- MLIT data acquisition uses the Real Estate Information Library API at `https://www.reinfolib.mlit.go.jp/realEstatePrices/`.
- API calls require `REINFOLIB_API_KEY`; collect safely skips when it is not set.
- Do not call the MLIT API from browser code.
- Placeholder ONNX files may be empty. Frontend metadata can enable development fallback for UI testing.
- Python dependency management should use `training/pyproject.toml` with `uv`.
- Frontend uses npm with `frontend/package-lock.json`.
