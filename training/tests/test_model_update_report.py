from __future__ import annotations

import json

import pytest

from evaluate.model_update_report import (
    build_model_metrics_snapshot,
    compare_snapshots,
    render_markdown,
)


def test_build_model_metrics_snapshot_aggregates_public_metadata(tmp_path) -> None:
    metadata_dir = tmp_path / "metadata"
    model_dir = tmp_path / "models"
    metadata_dir.mkdir()
    model_dir.mkdir()

    fixtures = {
        "tokyo": {"testCount": 3, "metrics": {"mae": 10.0, "rmse": 20.0, "mape": 5.0}},
        "chiba": {"testCount": 1, "metrics": {"mae": 30.0, "rmse": 40.0, "mape": 9.0}},
    }
    for region, evaluation in fixtures.items():
        (metadata_dir / f"{region}_latest_metadata.json").write_text(
            json.dumps(
                {
                    "modelName": f"{region}_latest",
                    "latestTrainingYear": 2025,
                    "featureOrder": ["area", "age"],
                    "evaluation": evaluation,
                    "deployment": {"trainCount": 10},
                }
            ),
            encoding="utf-8",
        )
        (metadata_dir / f"{region}_latest_categories.json").write_text("{}", encoding="utf-8")
        (model_dir / f"{region}_latest.onnx").write_bytes(region.encode())

    snapshot = build_model_metrics_snapshot(tmp_path)

    assert snapshot["modelCount"] == 2
    assert snapshot["aggregate"]["testCount"] == 4
    assert snapshot["aggregate"]["mae"] == pytest.approx(15.0)
    assert snapshot["aggregate"]["rmse"] == pytest.approx((700.0) ** 0.5)
    assert snapshot["aggregate"]["mape"] == pytest.approx(6.0)
    assert snapshot["aggregate"]["onnxBytes"] == len(b"tokyochiba")


def test_compare_snapshots_and_render_markdown(tmp_path) -> None:
    before = {
        "generatedAt": "before",
        "aggregate": {"mae": 20.0, "rmse": 30.0, "mape": 4.0, "onnxBytes": 100},
        "regions": [
            {
                "region": "tokyo",
                "latestTrainingYear": 2024,
                "featureCount": 2,
                "evaluation": {
                    "testYear": 2024,
                    "testCount": 2,
                    "metrics": {"mae": 20.0, "rmse": 30.0, "mape": 4.0},
                },
                "onnxBytes": 100,
                "onnxGzipBytes": 80,
                "categoriesGzipBytes": 10,
            }
        ],
    }
    after = {
        "generatedAt": "after",
        "aggregate": {"mae": 18.0, "rmse": 28.0, "mape": 3.5, "onnxBytes": 120},
        "regions": [
            {
                "region": "tokyo",
                "latestTrainingYear": 2025,
                "featureCount": 3,
                "evaluation": {
                    "testYear": 2025,
                    "testCount": 2,
                    "metrics": {"mae": 18.0, "rmse": 28.0, "mape": 3.5},
                },
                "onnxBytes": 120,
                "onnxGzipBytes": 90,
                "categoriesGzipBytes": 11,
            }
        ],
    }

    comparison = compare_snapshots(
        before,
        after,
        before_path=tmp_path / "before.json",
        after_path=tmp_path / "after.json",
    )
    markdown = render_markdown(comparison)

    assert comparison["aggregate"]["delta"]["mae"] == pytest.approx(-2.0)
    assert comparison["regions"][0]["delta"]["featureCount"] == 1
    assert "# モデル更新前後比較" in markdown
    assert "| MAE | 20.00 | 18.00 | -2.00 |" in markdown
