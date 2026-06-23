from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.mlit import collect_mlit_data, convert_shift_jis_to_utf8


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4])
    parser.add_argument("--city")
    parser.add_argument("--station")
    parser.add_argument("--api-key")
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--convert-source")
    parser.add_argument("--convert-output")
    args = parser.parse_args()

    if args.convert_source and args.convert_output:
        output = convert_shift_jis_to_utf8(args.convert_source, args.convert_output)
        print(f"converted csv: {output}")
        return 0

    output = collect_mlit_data(
        region=args.region,
        year=args.year,
        quarter=args.quarter,
        city=args.city,
        station=args.station,
        api_key=args.api_key,
        output_dir=args.output_dir,
    )
    if output:
        print(f"collected data: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
