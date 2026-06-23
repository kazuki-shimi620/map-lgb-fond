from __future__ import annotations

import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path


def save_pickle(model, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as file:
        pickle.dump(model, file)
    return output


def save_json(data: object, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def build_artifact_paths(output_dir: str | Path, region: str) -> dict[str, Path]:
    date = datetime.now().strftime("%Y%m%d")
    base = Path(output_dir)
    return {
        "pkl": base / f"{region}_{date}.pkl",
        "onnx": base / f"{region}_{date}.onnx",
        "categories": base / f"{region}_{date}_categories.json",
        "metadata": base / f"{region}_{date}_metadata.json",
        "history": base / f"{region}_{date}_history.json",
    }


def copy_for_frontend(paths: dict[str, Path], frontend_public_dir: str | Path, region: str) -> None:
    public = Path(frontend_public_dir)
    destinations = {
        "onnx": public / "models" / f"{region}_latest.onnx",
        "categories": public / "metadata" / f"{region}_latest_categories.json",
        "metadata": public / "metadata" / f"{region}_latest_metadata.json",
        "history": public / "histories" / f"{region}_latest_history.json",
    }

    for key, destination in destinations.items():
        source = paths.get(key)
        if not source or not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def export_onnx_if_available(model, feature_count: int, path: str | Path) -> Path | None:
    try:
        from onnxmltools import convert_lightgbm
        from onnxmltools.convert.common.data_types import FloatTensorType
    except ModuleNotFoundError:
        print("skip onnx export: onnxmltools is not installed")
        return None

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    initial_types = [("input", FloatTensorType([None, feature_count]))]
    onnx_model = convert_lightgbm(model, initial_types=initial_types)
    output.write_bytes(onnx_model.SerializeToString())
    return output


def build_price_history(df) -> list[dict[str, object]]:
    grouped = (
        df.groupby(["station", "transaction_year"], as_index=False)["price"]
        .mean()
        .rename(columns={"transaction_year": "year", "price": "avg_price"})
    )
    return grouped.to_dict(orient="records")
