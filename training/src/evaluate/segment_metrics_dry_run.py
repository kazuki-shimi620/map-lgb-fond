from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.config import load_config  # noqa: E402
from evaluate.metrics import (  # noqa: E402
    calculate_metrics,
    calculate_segment_metrics,
    compare_segment_intervals,
)
from export.artifacts import save_json  # noqa: E402
from features.category_dictionary import build_and_apply_category_dictionary  # noqa: E402
from features.providers import create_mvp_feature_pipeline  # noqa: E402
from train.model import train_model  # noqa: E402
from train.train import (  # noqa: E402
    _add_external_features_if_needed,
    _build_train_test_split,
    _resolve_data_path,
)


def run_dry_run(config_path: Path, metadata_path: Path, output_path: Path) -> dict[str, object]:
    import pandas as pd

    started = perf_counter()
    config = load_config(config_path)
    data_path = _resolve_data_path(config)
    if data_path is None:
        raise FileNotFoundError("processed dataset is not configured or does not exist")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    model_params = metadata.get("modelParams")
    if not isinstance(model_params, dict) or not model_params:
        raise ValueError("metadata does not contain modelParams")

    dataframe = pd.read_parquet(data_path)
    feature_df, _context = create_mvp_feature_pipeline().fit_transform(dataframe)
    feature_df = _add_external_features_if_needed(feature_df, config)
    encoding = build_and_apply_category_dictionary(feature_df, config.categorical_features)
    train_mask, test_mask, split_name = _build_train_test_split(encoding.dataframe, config)

    model = train_model(
        encoding.dataframe.loc[train_mask, config.features],
        encoding.dataframe.loc[train_mask, config.target],
        config.categorical_features,
        model_params,
    )
    predictions = model.predict(encoding.dataframe.loc[test_mask, config.features])
    evaluation_rows = feature_df.loc[test_mask]
    segments = calculate_segment_metrics(evaluation_rows, predictions)
    report = {
        "schemaVersion": 1,
        "kind": "segment_metrics_dry_run",
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "region": config.region,
        "split": split_name,
        "trainCount": int(train_mask.sum()),
        "testCount": int(test_mask.sum()),
        "modelParamsSource": str(metadata_path),
        "metrics": calculate_metrics(evaluation_rows[config.target], predictions),
        "segments": segments,
        "intervalComparison": compare_segment_intervals(
            evaluation_rows, predictions, segments
        ),
        "elapsedSeconds": perf_counter() - started,
    }
    save_json(report, output_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate segment metrics for one region without publishing model artifacts"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_dry_run(args.config, args.metadata, args.output)
    print(
        f"segment metrics dry-run: region={report['region']} "
        f"train={report['trainCount']} test={report['testCount']} "
        f"elapsed={report['elapsedSeconds']:.2f}s output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
