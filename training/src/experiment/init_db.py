from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from experiment.database import initialize_database


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="db/experiments.db")
    args = parser.parse_args()

    initialize_database(args.db_path)
    print(f"initialized database: {args.db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
