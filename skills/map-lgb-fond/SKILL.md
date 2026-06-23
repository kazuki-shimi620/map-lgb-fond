---
name: map-lgb-fond
description: Project skill for the map-lgb-fond real estate price prediction app. Use when Codex works in this repository on frontend React/Vite/Leaflet/ONNX Runtime code, training Python/LightGBM/Optuna/SQLite pipelines, model export assets, project documentation, or implementation planning from docs/*.md.
---

# Map LGB Fond

## First Reads

Read these before making architectural or cross-cutting changes:

1. `docs/requirements.md`
2. `docs/implementation.md`
3. `docs/frontend.md` for React, map, model loading, and UI behavior
4. `docs/training.md` for Python pipeline, feature generation, and export
5. `docs/database.md` for SQLite experiment/model management

For quick orientation, read `references/project-map.md`.

## Working Rules

- Keep MVP scope first: browser inference, training/export separation, FeatureProvider extension, prefecture-level model management.
- Prefer existing structure over new abstractions.
- Keep generated browser assets under `frontend/public/{models,metadata,histories,stations}`.
- Keep training artifacts under `training/outputs/`; export copies latest frontend assets only when the model is accepted as latest.
- Treat external network steps, MLIT endpoint discovery, and real model/data acquisition as skippable unless the user explicitly asks to perform them.
- Use `uv` for Python dependency management. Do not reintroduce `requirements.txt` unless the user asks.
- Preserve Japanese UI labels and documentation language unless there is a reason to change them.

## Frontend Workflow

Use this when editing `frontend/`.

1. Confirm the change against `docs/frontend.md`.
2. Keep feature code under `src/features/{map,prediction,model}`.
3. Keep shared loading and distance helpers under `src/services` and `src/utils`.
4. Run `npm run build` after TypeScript or Vite changes.
5. If ONNX files are empty or missing, keep development fallback behavior working so UI flow remains testable.

## Training Workflow

Use this when editing `training/`.

1. Confirm the change against `docs/training.md` and `docs/database.md`.
2. Keep pipeline stages separated: collect, preprocess, features, train, evaluate, export, experiment.
3. Add new feature logic through FeatureProvider-style classes.
4. Export category dictionaries, model metadata, and price history JSON alongside model files.
5. Run `python3 -m compileall training/src` after Python changes.
6. If `uv` is available, prefer `cd training && uv run python ...` commands.

## Validation

Minimum checks:

```bash
cd frontend
npm run build
```

```bash
python3 -m compileall training/src
python3 training/src/experiment/init_db.py --db-path training/db/experiments.db
```

When real processed data exists:

```bash
cd training
uv run python src/train/train.py --config configs/tokyo.yaml --db-path db/experiments.db --export-onnx
```

## References

- `references/project-map.md`: repository layout, source-of-truth docs, and current implementation map.
- `references/workflows.md`: common task workflows for frontend, training, export, and docs.
