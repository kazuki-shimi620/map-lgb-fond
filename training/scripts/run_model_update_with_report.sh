#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${MODEL_UPDATE_RUN_ID:-$(date +%Y%m%d_%H%M%S)}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/training/outputs/comparisons/model_update_${RUN_ID}"

mkdir -p "${OUTPUT_DIR}"
cd "${ROOT_DIR}"

echo "[model-update] run_id=${RUN_ID}"
echo "[model-update] output_dir=${OUTPUT_DIR}"

make snapshot-model-metrics SNAPSHOT_OUTPUT="${OUTPUT_DIR}/before_model_metrics.json"
make refresh-production-artifacts ALLOW_MODEL_UPDATE=1
make snapshot-model-metrics SNAPSHOT_OUTPUT="${OUTPUT_DIR}/after_model_metrics.json"
make compare-model-metrics \
  BEFORE_SNAPSHOT="${OUTPUT_DIR}/before_model_metrics.json" \
  AFTER_SNAPSHOT="${OUTPUT_DIR}/after_model_metrics.json" \
  REPORT_OUTPUT="${OUTPUT_DIR}/model_update_comparison.json" \
  MARKDOWN_OUTPUT="${OUTPUT_DIR}/model_update_comparison.md"

echo "[model-update] done"
echo "[model-update] comparison=${OUTPUT_DIR}/model_update_comparison.md"
