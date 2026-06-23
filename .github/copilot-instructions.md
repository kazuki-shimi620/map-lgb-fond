# Copilot Instructions

This repository is a real estate price prediction app. Follow the project docs under `docs/` before making cross-cutting changes.

## Architecture

- Frontend: React + TypeScript + Vite + Leaflet + ONNX Runtime Web + Recharts.
- Training: Python pipeline for collect, preprocess, features, train, evaluate, export, experiment.
- Inference is browser-side and serverless.
- Models and related JSON assets are managed by prefecture.

## Main Rules

- Keep MVP scope focused.
- Do not add backend inference.
- Do not bypass category dictionary JSON for browser inference.
- Keep training artifacts and frontend public assets separate.
- Use FeatureProvider-style changes for new training features.
- Use `uv` for Python dependencies and npm for frontend dependencies.

## Validation

Run these when relevant:

```bash
cd frontend
npm run build
```

```bash
python3 -m compileall training/src
```
