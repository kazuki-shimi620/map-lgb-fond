from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from common.regions import CAPITAL_MODEL_BY_PREFECTURE, REGIONAL_CLUSTERS  # noqa: E402
from export.artifacts import build_input_baselines, build_input_ranges  # noqa: E402

RANGE_COLUMNS = [
    "area",
    "age",
    "station_distance",
    "transaction_year",
    "room_layout",
    "building_type",
]


def refresh_input_ranges(processed_dir: Path, public_dir: Path) -> list[Path]:
    import pandas as pd

    metadata_dir = public_dir / "metadata"
    updated: list[Path] = []

    for _prefecture, region in CAPITAL_MODEL_BY_PREFECTURE.items():
        metadata_path = metadata_dir / f"{region}_latest_metadata.json"
        parquet_path = processed_dir / f"{region}.parquet"
        if not metadata_path.exists() or not parquet_path.exists():
            continue
        dataframe = pd.read_parquet(parquet_path, columns=RANGE_COLUMNS)
        updated.append(_update_metadata(metadata_path, dataframe))

    national_path = processed_dir / "national.parquet"
    if national_path.exists():
        national = pd.read_parquet(national_path, columns=["prefecture", *RANGE_COLUMNS])
        for cluster, prefectures in REGIONAL_CLUSTERS.items():
            metadata_path = metadata_dir / f"regional_{cluster}_latest_metadata.json"
            if not metadata_path.exists():
                continue
            dataframe = national[national["prefecture"].isin(prefectures)]
            updated.append(_update_metadata(metadata_path, dataframe))

    return updated


def _update_metadata(path: Path, dataframe) -> Path:
    metadata = json.loads(path.read_text(encoding="utf-8"))
    deployment = metadata.get("deployment", {})
    start_year = deployment.get("trainStartYear")
    end_year = deployment.get("latestTrainingYear", metadata.get("latestTrainingYear"))
    target = dataframe
    if start_year is not None:
        target = target[target["transaction_year"] >= int(start_year)]
    if end_year is not None:
        target = target[target["transaction_year"] <= int(end_year)]
    metadata["inputRanges"] = build_input_ranges(target)
    metadata["inputBaselines"] = build_input_baselines(target)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh input ranges in public model metadata")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    args = parser.parse_args()
    updated = refresh_input_ranges(args.processed_dir, args.public_dir)
    print(f"updated input ranges: {len(updated)} metadata files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
