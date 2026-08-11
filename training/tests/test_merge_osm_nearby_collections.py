from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from collect.merge_osm_nearby_collections import merge_collections


def _write_collection(path: Path, ids: list[str], *, errors: list[dict[str, str]]) -> None:
    path.mkdir()
    nearby_fields = [
        "id", "category_id", "name", "lat", "lon", "prefecture",
        "municipality", "address", "source", "updated_at",
    ]
    with (path / "nearby_osm_facilities.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=nearby_fields)
        writer.writeheader()
        for row_id in ids:
            writer.writerow({"id": row_id, "category_id": "park", "name": row_id})
    with (path / "park_areas.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id", "name", "lat", "lon", "area_sqm", "area_source", "source"],
        )
        writer.writeheader()
        for row_id in ids:
            writer.writerow({"id": row_id, "name": row_id, "area_sqm": "1000"})
    (path / "metadata.json").write_text(
        json.dumps(
            {
                "generatedAt": "2026-08-11T00:00:00+00:00",
                "categories": ["park"],
                "includeGeometry": True,
                "nearbyFacilityCount": len(ids),
                "parkAreaCount": len(ids),
                "errorCount": len(errors),
                "errors": errors,
            }
        ),
        encoding="utf-8",
    )


def test_merge_collections_deduplicates_and_tracks_active_errors(tmp_path) -> None:
    base = tmp_path / "base"
    replacement = tmp_path / "replacement"
    output = tmp_path / "output"
    _write_collection(base, ["park_1", "park_2"], errors=[{"cell": "r00_c01"}])
    _write_collection(
        replacement,
        ["park_2", "park_3"],
        errors=[{"cell": "r00_c00", "error": "HTTP 504"}],
    )

    metadata = merge_collections(
        input_dirs=[base, replacement],
        error_source_dirs=[replacement],
        output_dir=output,
        allow_errors=True,
    )

    assert metadata["nearbyFacilityCount"] == 3
    assert metadata["parkAreaCount"] == 3
    assert metadata["errorCount"] == 1
    assert metadata["supersededErrorCount"] == 1
    assert metadata["errors"][0]["input"] == str(replacement)


def test_merge_collections_rejects_active_errors_by_default(tmp_path) -> None:
    incomplete = tmp_path / "incomplete"
    output = tmp_path / "output"
    _write_collection(
        incomplete,
        ["park_1"],
        errors=[{"cell": "r00_c00", "error": "HTTP 504"}],
    )

    with pytest.raises(ValueError, match="1 active errors"):
        merge_collections(
            input_dirs=[incomplete],
            error_source_dirs=[incomplete],
            output_dir=output,
        )

    assert not output.exists()
