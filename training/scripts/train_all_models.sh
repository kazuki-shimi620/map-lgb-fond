#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

publish_policy="${PUBLISH_POLICY:-best}"

if [[ -n "${TRAINING_PYTHON:-}" ]]; then
  read -r -a python_command <<< "${TRAINING_PYTHON}"
elif command -v uv >/dev/null 2>&1; then
  python_command=(uv run python)
elif [[ -x .venv/bin/python ]]; then
  python_command=(.venv/bin/python)
else
  echo "training Python is not available; run 'make setup-training' first" >&2
  exit 1
fi

for region in tokyo kanagawa saitama chiba; do
  echo "train ${region}"
  "${python_command[@]}" src/train/train.py \
    --config "configs/${region}.yaml" \
    --db-path db/experiments.db \
    --export-onnx \
    --publish-policy "${publish_policy}"
done
