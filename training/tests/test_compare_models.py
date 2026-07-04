import json

import pytest

from evaluate.compare_models import _published_baseline, render_markdown


def test_published_baseline_aggregates_metrics_and_sizes(tmp_path):
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
            json.dumps({"evaluation": evaluation}), encoding="utf-8"
        )
        (model_dir / f"{region}_latest.onnx").write_bytes(region.encode())

    baseline = _published_baseline(["tokyo", "chiba"], tmp_path)

    assert baseline["modelCount"] == 2
    assert baseline["onnxBytes"] == len(b"tokyochiba")
    assert baseline["metrics"]["mae"] == pytest.approx(15.0)
    assert baseline["metrics"]["rmse"] == pytest.approx((700.0) ** 0.5)
    assert baseline["metrics"]["mape"] == pytest.approx(6.0)


def test_render_markdown_includes_gzip_size():
    report = {
        "trainStartYear": 2020,
        "testYear": 2025,
        "trainCount": 10,
        "testCount": 2,
        "candidates": [
            {
                "name": "compact",
                "modelCount": 1,
                "onnxBytes": 1024 * 1024,
                "onnxGzipBytes": 512 * 1024,
                "trainingSeconds": 1.25,
                "metrics": {"mae": 1.0, "rmse": 2.0, "mape": 3.0},
            }
        ],
    }

    markdown = render_markdown(report)

    assert "1.00 MB" in markdown
    assert "0.50 MB" in markdown
