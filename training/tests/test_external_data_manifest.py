from __future__ import annotations

import json

from export.external_data_manifest import build_external_data_manifest


def test_build_external_data_manifest_records_provenance_and_coverage(tmp_path) -> None:
    facilities = tmp_path / "facilities"
    facilities.mkdir()
    payload = {
        "source": "fixture",
        "sourceLabel": "テストデータ",
        "generatedAt": "2026-08-09T00:00:00+00:00",
        "coverage": {"area": "全国", "facilityCount": 2},
    }
    path = facilities / "commercial_facilities.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = build_external_data_manifest(tmp_path)

    artifact = manifest["artifacts"]["commercialFacilities"]
    assert artifact["sourceLabel"] == "テストデータ"
    assert artifact["dataTimestamp"] == "2026-08-09T00:00:00+00:00"
    assert artifact["coverage"]["facilityCount"] == 2
    assert artifact["generationCommand"] == "make facilities"
    assert len(artifact["sha256"]) == 64
