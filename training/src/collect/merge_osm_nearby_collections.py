from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from collect.osm_nearby_facilities import (  # noqa: E402
    NEARBY_FACILITY_FIELDNAMES,
    PARK_AREA_FIELDNAMES,
    SCHEMA_VERSION,
    write_csv,
)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _deduplicate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return list({row["id"]: row for row in rows}.values())


def merge_collections(
    *,
    input_dirs: list[Path],
    error_source_dirs: list[Path],
    output_dir: Path,
    allow_errors: bool = False,
) -> dict[str, Any]:
    if not input_dirs:
        raise ValueError("at least one input directory is required")
    unknown_error_sources = set(error_source_dirs) - set(input_dirs)
    if unknown_error_sources:
        raise ValueError("error source directories must also be input directories")

    nearby_rows: list[dict[str, str]] = []
    park_area_rows: list[dict[str, str]] = []
    inputs = []
    active_errors = []
    superseded_errors = []
    categories: list[str] | None = None
    for input_dir in input_dirs:
        metadata = json.loads((input_dir / "metadata.json").read_text(encoding="utf-8"))
        input_categories = metadata.get("categories")
        if categories is None:
            categories = input_categories
        elif input_categories != categories:
            raise ValueError(f"category mismatch: {input_dir}")
        if not metadata.get("includeGeometry"):
            raise ValueError(f"geometry is required: {input_dir}")

        nearby_rows.extend(_read_rows(input_dir / "nearby_osm_facilities.csv"))
        park_area_rows.extend(_read_rows(input_dir / "park_areas.csv"))
        scoped_errors = [
            {"input": str(input_dir), **error} for error in metadata.get("errors", [])
        ]
        if input_dir in error_source_dirs:
            active_errors.extend(scoped_errors)
        else:
            superseded_errors.extend(scoped_errors)
        inputs.append(
            {
                "path": str(input_dir),
                "generatedAt": metadata.get("generatedAt"),
                "nearbyFacilityCount": metadata.get("nearbyFacilityCount"),
                "parkAreaCount": metadata.get("parkAreaCount"),
                "errorCount": metadata.get("errorCount", 0),
                "errorsAreActive": input_dir in error_source_dirs,
            }
        )

    nearby_rows = _deduplicate(nearby_rows)
    park_area_rows = _deduplicate(park_area_rows)
    if active_errors and not allow_errors:
        raise ValueError(
            f"cannot publish an incomplete merge: {len(active_errors)} active errors"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "nearby_osm_facilities.csv", nearby_rows, NEARBY_FACILITY_FIELDNAMES)
    write_csv(output_dir / "park_areas.csv", park_area_rows, PARK_AREA_FIELDNAMES)
    metadata = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "OpenStreetMap Overpass API",
        "license": "Open Database License (ODbL)",
        "categories": categories,
        "includeGeometry": True,
        "nearbyFacilityCount": len(nearby_rows),
        "parkAreaCount": len(park_area_rows),
        "inputs": inputs,
        "errorCount": len(active_errors),
        "errors": active_errors,
        "supersededErrorCount": len(superseded_errors),
        "supersededErrors": superseded_errors,
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge cached OSM nearby collections.")
    parser.add_argument("--input-dir", action="append", type=Path, required=True)
    parser.add_argument("--error-source-dir", action="append", type=Path, default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-errors", action="store_true")
    args = parser.parse_args()
    try:
        metadata = merge_collections(
            input_dirs=args.input_dir,
            error_source_dirs=args.error_source_dir,
            output_dir=args.output_dir,
            allow_errors=args.allow_errors,
        )
    except ValueError as error:
        print(f"OSM nearby merge failed: {error}", file=sys.stderr)
        return 1
    print(
        "merged OSM nearby collections: "
        f"nearby={metadata['nearbyFacilityCount']} "
        f"parkAreas={metadata['parkAreaCount']} errors={metadata['errorCount']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
