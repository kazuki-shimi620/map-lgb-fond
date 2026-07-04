import hashlib
import json

from export.artifacts import CAPITAL_REGION_PRIORITY, update_model_manifest


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
