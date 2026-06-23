from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from preprocess.cleaning import preprocess_csv, preprocess_files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if len(args.input) == 1:
        output = preprocess_csv(args.input[0], args.output)
    else:
        output = preprocess_files(args.input, args.output)
    print(f"processed dataset: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
