#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

for region in tokyo kanagawa saitama chiba; do
  echo "train ${region}"
  uv run python src/train/train.py \
    --config "configs/${region}.yaml" \
    --db-path db/experiments.db \
    --export-onnx
done
