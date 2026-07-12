import hashlib
import json

import pandas as pd

from export.artifacts import (
    CAPITAL_REGION_PRIORITY,
    build_price_history,
    build_price_trend_summary,
    copy_for_frontend,
    update_model_manifest,
)


def test_update_model_manifest_records_hash_size_and_priority(tmp_path):
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    tokyo_model = b"tokyo-model"
    hokkaido_model = b"hokkaido-model"
    (model_dir / "tokyo_latest.onnx").write_bytes(tokyo_model)
    (model_dir / "hokkaido_latest.onnx").write_bytes(hokkaido_model)

    output = update_model_manifest(tmp_path)

    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["capitalRegionPriority"] == CAPITAL_REGION_PRIORITY
    assert list(manifest["models"]) == ["tokyo", "hokkaido"]
    assert manifest["models"]["tokyo"] == {
        "path": "models/tokyo_latest.onnx",
        "version": hashlib.sha256(tokyo_model).hexdigest(),
        "bytes": len(tokyo_model),
    }


def test_price_history_keeps_prefecture_for_regional_models():
    dataframe = pd.DataFrame(
        [
            {
                "prefecture": "大阪府",
                "station": "大阪",
                "transaction_year": 2025,
                "price": 10.0,
                "area": 50.0,
                "age": 15.0,
            },
            {
                "prefecture": "大阪府",
                "station": "大阪",
                "transaction_year": 2025,
                "price": 30.0,
                "area": 50.0,
                "age": 15.0,
            },
            {
                "prefecture": "兵庫県",
                "station": "大阪",
                "transaction_year": 2025,
                "price": 90.0,
                "area": 30.0,
                "age": 35.0,
            },
        ]
    )

    assert build_price_history(dataframe) == [
        {
            "prefecture": "兵庫県",
            "station": "大阪",
            "year": 2025,
            "avg_price": 90.0,
            "avg_unit_price": 3.0,
            "transaction_count": 1,
            "comparable_buckets": [[30, 35, 3.0, 1]],
        },
        {
            "prefecture": "大阪府",
            "station": "大阪",
            "year": 2025,
            "avg_price": 20.0,
            "avg_unit_price": 0.4,
            "transaction_count": 2,
            "comparable_buckets": [[50, 15, 0.4, 2]],
        },
    ]


def test_price_history_can_limit_transaction_years():
    dataframe = pd.DataFrame(
        [
            {
                "station": "東京",
                "transaction_year": year,
                "price": 50.0,
                "area": 50.0,
                "age": 10.0,
            }
            for year in (2019, 2020, 2025)
        ]
    )

    assert [point["year"] for point in build_price_history(dataframe, min_year=2020)] == [
        2020,
        2025,
    ]
    assert [point["year"] for point in build_price_history(dataframe, max_year=2019)] == [2019]


def test_price_trend_summary_builds_regional_and_station_trends():
    dataframe = pd.DataFrame(
        [
            {
                "station": "東京",
                "transaction_year": 2020,
                "price": 50.0,
                "area": 50.0,
            },
            {
                "station": "東京",
                "transaction_year": 2021,
                "price": 55.0,
                "area": 50.0,
            },
            {
                "station": "東京",
                "transaction_year": 2022,
                "price": 60.5,
                "area": 50.0,
            },
            {
                "station": "大手町",
                "transaction_year": 2022,
                "price": 30.0,
                "area": 30.0,
            },
        ]
    )

    summary = build_price_trend_summary(dataframe, region="tokyo", min_year=2020)

    assert summary["schemaVersion"] == 1
    assert summary["region"] == "tokyo"
    assert summary["latestTrainingYear"] == 2022
    assert summary["regionalTrend"]["sampleYears"] == 3
    assert round(summary["regionalTrend"]["annualizedRate"], 6) == 0.05119
    assert summary["stationTrends"]["東京"]["sampleYears"] == 3
    assert round(summary["stationTrends"]["東京"]["annualizedRate"], 6) == 0.1
    assert "大手町" not in summary["stationTrends"]


def test_copy_for_frontend_can_skip_combined_regional_history(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    paths = {}
    for key, suffix in {
        "onnx": ".onnx",
        "categories": "_categories.json",
        "metadata": "_metadata.json",
        "history": "_history.json",
    }.items():
        paths[key] = source_dir / f"model{suffix}"
        paths[key].write_text(key, encoding="utf-8")

    public_dir = tmp_path / "public"
    copy_for_frontend(paths, public_dir, "regional_kinki", include_history=False)

    assert (public_dir / "models" / "regional_kinki_latest.onnx").exists()
    assert not (public_dir / "histories" / "regional_kinki_latest_history.json").exists()
