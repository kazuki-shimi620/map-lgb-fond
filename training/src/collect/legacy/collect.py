from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.legacy.mlit import (  # noqa: E402
    PREFECTURE_CODES,
    ReinfolibApiError,
    collect_mlit_data,
    convert_shift_jis_to_utf8,
)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", nargs="+", choices=sorted(PREFECTURE_CODES), required=True)
    parser.add_argument("--year", nargs="+", type=int, required=True)
    parser.add_argument("--quarter", type=int, choices=[1, 2, 3, 4])
    parser.add_argument("--city")
    parser.add_argument("--station")
    parser.add_argument("--output-dir", default="data/raw")
    parser.add_argument("--convert-source")
    parser.add_argument("--convert-output")
    args = parser.parse_args()

    load_env_file(Path(__file__).resolve().parents[3] / ".env")

    if args.convert_source and args.convert_output:
        output = convert_shift_jis_to_utf8(args.convert_source, args.convert_output)
        print(f"converted csv: {output}")
        return 0

    try:
        for region in args.region:
            for year in args.year:
                output = collect_mlit_data(
                    region=region,
                    year=year,
                    quarter=args.quarter,
                    city=args.city,
                    station=args.station,
                    output_dir=args.output_dir,
                )
                payload = json.loads(output.read_text(encoding="utf-8"))
                print(f"collected data: {output} ({len(payload['data'])} records)")
    except (ReinfolibApiError, ValueError) as error:
        print(f"collect failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
