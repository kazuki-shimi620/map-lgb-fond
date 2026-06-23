from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrainingConfig:
    region: str
    features: list[str]
    target: str = "price"
    latest_training_year: int = 2025
    train_start_year: int = 2020
    test_year: int = 2025
    raw_path: str | None = None
    processed_path: str | None = None
    output_dir: str = "outputs/models"
    frontend_public_dir: str = "../frontend/public"
    categorical_features: list[str] = field(
        default_factory=lambda: [
            "prefecture",
            "municipality",
            "station",
            "room_layout",
            "building_type",
        ]
    )


def load_config(path: str | Path) -> TrainingConfig:
    config_path = Path(path)
    data = _load_yaml_like(config_path)
    base_dir = _resolve_base_dir(config_path)
    return TrainingConfig(
        region=str(data["region"]),
        features=list(data["features"]),
        target=str(data.get("target", "price")),
        latest_training_year=int(data.get("latest_training_year", 2025)),
        train_start_year=int(data.get("train_start_year", 2020)),
        test_year=int(data.get("test_year", 2025)),
        raw_path=_resolve_optional_path(base_dir, data.get("raw_path")),
        processed_path=_resolve_optional_path(base_dir, data.get("processed_path")),
        output_dir=str(_resolve_path(base_dir, str(data.get("output_dir", "outputs/models")))),
        frontend_public_dir=str(
            _resolve_path(base_dir, str(data.get("frontend_public_dir", "../frontend/public")))
        ),
        categorical_features=list(data.get("categorical_features", []))
        or TrainingConfig(region="", features=[]).categorical_features,
    )


def _resolve_base_dir(config_path: Path) -> Path:
    if config_path.parent.name == "configs":
        return config_path.parent.parent
    return config_path.parent


def _resolve_optional_path(base_dir: Path, value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(_resolve_path(base_dir, str(value)))


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


def _load_yaml_like(path: Path) -> dict[str, Any]:
    try:
        import yaml

        with path.open("r", encoding="utf-8") as file:
            loaded = yaml.safe_load(file) or {}
        return dict(loaded)
    except ModuleNotFoundError:
        return _load_simple_yaml(path)


def _load_simple_yaml(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_list_key:
            result.setdefault(current_list_key, []).append(line[4:].strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                result[key] = _coerce_scalar(value)
                current_list_key = None
            else:
                result[key] = []
                current_list_key = key

    return result


def _coerce_scalar(value: str) -> str | int | float | bool:
    if value in {"true", "false"}:
        return value == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
