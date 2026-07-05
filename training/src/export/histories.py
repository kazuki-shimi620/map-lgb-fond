from __future__ import annotations

import argparse
from pathlib import Path

from ..common.regions import CAPITAL_MODEL_BY_PREFECTURE, PREFECTURE_TO_SLUG
from .artifacts import RECENT_HISTORY_START_YEAR, build_price_history, save_json


def export_histories(processed_dir: Path, public_dir: Path) -> list[Path]:
    import pandas as pd

    national = pd.read_parquet(processed_dir / "national.parquet")
    outputs = []
    for prefecture, slug in PREFECTURE_TO_SLUG.items():
        capital_path = processed_dir / f"{slug}.parquet"
        if prefecture in CAPITAL_MODEL_BY_PREFECTURE and capital_path.exists():
            data = pd.read_parquet(capital_path)
        else:
            data = national[national["prefecture"] == prefecture].copy()
        recent_output = public_dir / "histories" / f"{slug}_latest_history.json"
        archive_output = public_dir / "histories" / f"{slug}_archive_history.json"
        outputs.append(
            save_json(
                build_price_history(data, min_year=RECENT_HISTORY_START_YEAR),
                recent_output,
                compact=True,
            )
        )
        outputs.append(
            save_json(
                build_price_history(data, max_year=RECENT_HISTORY_START_YEAR - 1),
                archive_output,
                compact=True,
            )
        )
        print(
            f"{slug}: exported {len(data)} transactions to "
            f"{recent_output} and {archive_output}"
        )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Export comparable price histories")
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    args = parser.parse_args()
    export_histories(args.processed_dir, args.public_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
