from __future__ import annotations

import csv
import json

from collect.hazards import collect_hazards, normalize_hazard_records


def test_normalize_hazard_records_parses_depth_and_landslide() -> None:
    records = normalize_hazard_records(
        [
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "year": 2024,
                "hazard_type": "flood",
                "depth_label": "0.5m以上3.0m未満",
                "source_available": True,
            },
            {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "year": 2024,
                "hazard_type": "landslide",
                "zone_type": "土砂災害特別警戒区域",
                "source_available": True,
            },
        ],
        source_url="sample.json",
    )

    assert records[0]["risk_level"] == 3
    assert records[0]["depth_min"] == 0.5
    assert records[0]["depth_max"] == 3.0
    assert records[0]["score"] == 55.0
    assert records[1]["risk_level"] == 5
    assert records[1]["score"] == 0.0
    assert records[1]["special_warning"] == 1.0


def test_collect_hazards_writes_normalized_and_feature_csv(tmp_path) -> None:
    input_path = tmp_path / "hazards.json"
    input_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "prefecture": "東京都",
                        "municipality": "千代田区",
                        "year": 2024,
                        "hazard_type": "flood",
                        "depth_label": "0.5m以上3.0m未満",
                        "source_available": True,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outputs = collect_hazards(
        input_path=input_path,
        url=None,
        output_dir=tmp_path / "processed",
        raw_dir=tmp_path / "raw",
    )

    assert outputs["normalized_json"].exists()
    assert outputs["long_csv"].exists()
    assert outputs["wide_csv"].exists()

    with outputs["wide_csv"].open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert rows[0]["prefecture"] == "東京都"
    assert rows[0]["municipality"] == "千代田区"
    assert rows[0]["feature_year"] == "2024"
    assert float(rows[0]["hazard_flood_risk_level"]) == 3.0
