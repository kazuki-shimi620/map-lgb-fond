from __future__ import annotations

from pathlib import Path

import pytest

from export.feature_order import validate_frontend_artifact_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
METADATA_DIR = REPO_ROOT / "frontend" / "public" / "metadata"
MODEL_DIR = REPO_ROOT / "frontend" / "public" / "models"


@pytest.mark.parametrize("metadata_path", sorted(METADATA_DIR.glob("*_latest_metadata.json")))
def test_frontend_model_artifact_contract(metadata_path: Path) -> None:
    region = metadata_path.name.removesuffix("_latest_metadata.json")
    categories_path = METADATA_DIR / f"{region}_latest_categories.json"
    model_path = MODEL_DIR / f"{region}_latest.onnx"

    errors = validate_frontend_artifact_contract(metadata_path, categories_path, model_path)

    assert errors == []


def test_frontend_model_artifacts_are_present() -> None:
    metadata_paths = sorted(METADATA_DIR.glob("*_latest_metadata.json"))

    assert len(metadata_paths) == 12
    for metadata_path in metadata_paths:
        region = metadata_path.name.removesuffix("_latest_metadata.json")
        assert (METADATA_DIR / f"{region}_latest_categories.json").exists()
        assert (MODEL_DIR / f"{region}_latest.onnx").exists()
