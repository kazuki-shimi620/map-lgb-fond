# AI Agent Guide

Use this file as the first stop for AI agents working on this repository.

## Project

This is a browser-based real estate price prediction app for used apartments.

The system has two major parts:

- `frontend/`: React, TypeScript, Vite, Leaflet, ONNX Runtime Web, Recharts.
- `training/`: Python training/export pipeline using LightGBM, SQLite experiment tracking, and frontend asset export.

## Source Of Truth

Read the docs before broad changes:

1. `docs/requirements.md`
2. `docs/implementation.md`
3. `docs/frontend.md`
4. `docs/training.md`
5. `docs/database.md`
6. `docs/architecture.md`

There is also a repo-local Codex skill at `skills/map-lgb-fond/SKILL.md`.

## Working Principles

- Preserve MVP scope unless the user explicitly expands it.
- Keep learning and inference separated.
- Keep browser inference serverless.
- Keep model management prefecture-based.
- Use FeatureProvider-style additions for training features.
- Treat network-dependent data acquisition and real model downloads as skippable unless requested.
- MLIT data comes from `https://www.reinfolib.mlit.go.jp/realEstatePrices/`.
- Use `REINFOLIB_API_KEY` only in training-side collect commands. Do not call the MLIT API from the browser.
- Use `uv` for Python dependency management.
- Use npm for the frontend.

## Commands

Frontend:

```bash
cd frontend
npm run build
```

Training:

```bash
python3 -m compileall training/src
python3 training/src/experiment/init_db.py --db-path training/db/experiments.db
```

When `uv` is installed:

```bash
cd training
uv sync
uv run python src/train/train.py --config configs/tokyo.yaml --db-path db/experiments.db --export-onnx
```

## Notes

- Placeholder ONNX files may be empty. The frontend has development fallback metadata for UI flow testing.
- `frontend/public/metadata`, `frontend/public/histories`, and `frontend/public/stations` are part of the app contract.
- `training/outputs` is for generated artifacts; latest accepted assets are copied to `frontend/public`.
