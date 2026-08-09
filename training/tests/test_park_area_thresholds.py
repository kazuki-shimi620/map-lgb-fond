from __future__ import annotations

from pathlib import Path

from evaluate.park_area_thresholds import summarize_park_areas


def test_summarize_park_areas_counts_thresholds_and_sources(tmp_path: Path) -> None:
    source = tmp_path / "park_areas.csv"
    source.write_text(
        "id,area_sqm,area_source\n"
        "park_1,5000,geometry\n"
        "park_2,20000,geometry\n"
        "park_3,50000,bounds\n",
        encoding="utf-8",
    )

    summary = summarize_park_areas(source)

    assert summary["rowCount"] == 3
    assert summary["areaSourceCounts"] == {"geometry": 2, "bounds": 1}
    assert summary["thresholdsSqm"]["20000"] == {"count": 2, "rate": 0.6667}
    assert summary["thresholdsSqm"]["100000"] == {"count": 0, "rate": 0.0}
