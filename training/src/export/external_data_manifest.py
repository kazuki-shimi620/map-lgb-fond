from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ARTIFACTS = {
    "commercialFacilities": ("facilities/commercial_facilities.json", "make facilities"),
    "nearbyFacilities": ("facilities/nearby_facilities.json", "make nearby-facilities"),
    "landPrices": ("land-prices/municipality_land_prices.json", "make land-prices"),
    "urbanPlanning": ("urban-planning/urban_planning_areas.json", "make urban-planning"),
    "hazardLayers": ("hazards/layers.json", "設定ファイルをレビューして更新"),
}


def build_external_data_manifest(public_dir: Path) -> dict[str, object]:
    artifacts = {}
    for artifact_id, (relative_path, command) in ARTIFACTS.items():
        path = public_dir / relative_path
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        artifacts[artifact_id] = {
            "path": relative_path,
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
            "source": payload.get("source"),
            "sourceLabel": payload.get("sourceLabel") or _source_name(payload.get("source")),
            "dataTimestamp": payload.get("generatedAt") or payload.get("updatedAt"),
            "coverage": _coverage_summary(artifact_id, payload),
            "generationCommand": command,
        }
    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "artifacts": artifacts,
    }


def write_external_data_manifest(public_dir: Path) -> Path:
    output = public_dir / "external-data-manifest.json"
    output.write_text(
        json.dumps(build_external_data_manifest(public_dir), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def _source_name(source: object) -> str | None:
    return str(source.get("name")) if isinstance(source, dict) and source.get("name") else None


def _coverage_summary(artifact_id: str, payload: dict[str, object]) -> object:
    if artifact_id == "commercialFacilities":
        return payload.get("coverage")
    if artifact_id == "nearbyFacilities":
        return {
            "facilityCount": len(payload.get("facilities") or []),
            "categories": [
                {
                    "id": category.get("id"),
                    "coverageArea": category.get("coverageArea"),
                    "sourceUrl": category.get("sourceUrl"),
                    "licenseLabel": category.get("licenseLabel"),
                }
                for category in payload.get("categories") or []
            ],
        }
    if artifact_id == "landPrices":
        return {
            "latestYear": payload.get("latestYear"),
            "cityCount": len(payload.get("cities") or {}),
        }
    if artifact_id == "urbanPlanning":
        return {"areaCount": payload.get("areaCount")}
    if artifact_id == "hazardLayers":
        return {"layerCount": len(payload.get("layers") or [])}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate external data artifact manifest")
    parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    args = parser.parse_args()
    print(write_external_data_manifest(args.public_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
