from __future__ import annotations

import argparse
import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Snapshot and compare published model metrics.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--public-dir", type=Path, default=Path("../frontend/public"))
    snapshot_parser.add_argument("--output", type=Path, required=True)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--before", type=Path, required=True)
    compare_parser.add_argument("--after", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, required=True)
    compare_parser.add_argument("--markdown-output", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "snapshot":
        snapshot = build_model_metrics_snapshot(args.public_dir)
        _save_json(snapshot, args.output)
        print(f"model metrics snapshot: {args.output}")
        return 0

    comparison = compare_snapshots(
        json.loads(args.before.read_text(encoding="utf-8")),
        json.loads(args.after.read_text(encoding="utf-8")),
        before_path=args.before,
        after_path=args.after,
    )
    _save_json(comparison, args.output)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(comparison), encoding="utf-8")
    print(f"model update comparison: {args.markdown_output}")
    return 0


def build_model_metrics_snapshot(public_dir: Path) -> dict[str, Any]:
    metadata_dir = public_dir / "metadata"
    model_dir = public_dir / "models"
    regions = []
    for metadata_path in sorted(metadata_dir.glob("*_latest_metadata.json")):
        region = metadata_path.name.removesuffix("_latest_metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        model_path = model_dir / f"{region}_latest.onnx"
        categories_path = metadata_dir / f"{region}_latest_categories.json"
        evaluation = metadata.get("evaluation") or {}
        metrics = evaluation.get("metrics") or {}
        regions.append(
            {
                "region": region,
                "modelName": metadata.get("modelName"),
                "latestTrainingYear": metadata.get("latestTrainingYear"),
                "featureCount": len(metadata.get("featureOrder") or []),
                "features": metadata.get("featureOrder") or [],
                "evaluation": {
                    "split": evaluation.get("split"),
                    "trainStartYear": evaluation.get("trainStartYear"),
                    "testYear": evaluation.get("testYear"),
                    "trainCount": evaluation.get("trainCount"),
                    "testCount": evaluation.get("testCount"),
                    "metrics": {
                        "mae": _to_float(metrics.get("mae")),
                        "rmse": _to_float(metrics.get("rmse")),
                        "mape": _to_float(metrics.get("mape")),
                    },
                },
                "deployment": metadata.get("deployment") or {},
                "onnxBytes": _file_size(model_path),
                "onnxGzipBytes": _gzip_file_size(model_path),
                "metadataBytes": _file_size(metadata_path),
                "categoriesBytes": _file_size(categories_path),
                "categoriesGzipBytes": _gzip_file_size(categories_path),
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "publicDir": str(public_dir),
        "modelCount": len(regions),
        "aggregate": _aggregate_regions(regions),
        "regions": regions,
    }


def compare_snapshots(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    before_path: Path,
    after_path: Path,
) -> dict[str, Any]:
    before_regions = {row["region"]: row for row in before.get("regions", [])}
    after_regions = {row["region"]: row for row in after.get("regions", [])}
    regions = []
    for region in sorted(set(before_regions) | set(after_regions)):
        before_row = before_regions.get(region)
        after_row = after_regions.get(region)
        regions.append(
            {
                "region": region,
                "before": _compact_region(before_row),
                "after": _compact_region(after_row),
                "delta": _delta_region(before_row, after_row),
            }
        )

    return {
        "schemaVersion": 1,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
        "beforeSnapshot": str(before_path),
        "afterSnapshot": str(after_path),
        "beforeGeneratedAt": before.get("generatedAt"),
        "afterGeneratedAt": after.get("generatedAt"),
        "aggregate": {
            "before": before.get("aggregate"),
            "after": after.get("aggregate"),
            "delta": _delta_metrics(before.get("aggregate") or {}, after.get("aggregate") or {}),
        },
        "regions": regions,
    }


def render_markdown(comparison: dict[str, Any]) -> str:
    aggregate = comparison["aggregate"]
    lines = [
        "# モデル更新前後比較",
        "",
        f"* before: `{comparison['beforeSnapshot']}`",
        f"* after: `{comparison['afterSnapshot']}`",
        "",
        "## 全体",
        "",
        "| 指標 | 更新前 | 更新後 | 差分 |",
        "|---|---:|---:|---:|",
    ]
    for key, label in [
        ("mae", "MAE"),
        ("rmse", "RMSE"),
        ("mape", "MAPE"),
        ("onnxBytes", "ONNX bytes"),
        ("categoriesGzipBytes", "カテゴリ辞書 gzip bytes"),
    ]:
        lines.append(
            f"| {label} | {_format_number(aggregate['before'].get(key))} | "
            f"{_format_number(aggregate['after'].get(key))} | "
            f"{_format_signed(aggregate['delta'].get(key))} |"
        )

    lines.extend(
        [
            "",
            "## 地域別",
            "",
            "| 地域 | MAE before | MAE after | MAE差分 | RMSE差分 | MAPE差分 | ONNX差分 | 特徴量数 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparison["regions"]:
        before = row["before"] or {}
        after = row["after"] or {}
        delta = row["delta"] or {}
        lines.append(
            f"| {row['region']} | {_format_number(before.get('mae'))} | "
            f"{_format_number(after.get('mae'))} | {_format_signed(delta.get('mae'))} | "
            f"{_format_signed(delta.get('rmse'))} | {_format_signed(delta.get('mape'))} | "
            f"{_format_signed(delta.get('onnxBytes'))} | {_format_number(after.get('featureCount'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def _aggregate_regions(regions: list[dict[str, Any]]) -> dict[str, float | int | None]:
    test_count = sum(int((row["evaluation"].get("testCount") or 0)) for row in regions)
    if test_count == 0:
        mae = rmse = mape = None
    else:
        mae = sum(
            (row["evaluation"]["metrics"].get("mae") or 0.0) * int(row["evaluation"].get("testCount") or 0)
            for row in regions
        ) / test_count
        rmse = (
            sum(
                ((row["evaluation"]["metrics"].get("rmse") or 0.0) ** 2)
                * int(row["evaluation"].get("testCount") or 0)
                for row in regions
            )
            / test_count
        ) ** 0.5
        mape = sum(
            (row["evaluation"]["metrics"].get("mape") or 0.0) * int(row["evaluation"].get("testCount") or 0)
            for row in regions
        ) / test_count

    return {
        "modelCount": len(regions),
        "testCount": test_count,
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
        "onnxBytes": sum(row.get("onnxBytes") or 0 for row in regions),
        "onnxGzipBytes": sum(row.get("onnxGzipBytes") or 0 for row in regions),
        "metadataBytes": sum(row.get("metadataBytes") or 0 for row in regions),
        "categoriesBytes": sum(row.get("categoriesBytes") or 0 for row in regions),
        "categoriesGzipBytes": sum(row.get("categoriesGzipBytes") or 0 for row in regions),
    }


def _compact_region(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    metrics = row["evaluation"]["metrics"]
    return {
        "latestTrainingYear": row.get("latestTrainingYear"),
        "testYear": row["evaluation"].get("testYear"),
        "testCount": row["evaluation"].get("testCount"),
        "featureCount": row.get("featureCount"),
        "mae": metrics.get("mae"),
        "rmse": metrics.get("rmse"),
        "mape": metrics.get("mape"),
        "onnxBytes": row.get("onnxBytes"),
        "onnxGzipBytes": row.get("onnxGzipBytes"),
        "categoriesGzipBytes": row.get("categoriesGzipBytes"),
    }


def _delta_region(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, float | int | None] | None:
    if before is None or after is None:
        return None
    return _delta_metrics(_compact_region(before) or {}, _compact_region(after) or {})


def _delta_metrics(before: dict[str, Any], after: dict[str, Any]) -> dict[str, float | int | None]:
    keys = sorted(set(before) | set(after))
    return {key: _numeric_delta(before.get(key), after.get(key)) for key in keys}


def _numeric_delta(before: Any, after: Any) -> float | int | None:
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        return after - before
    return None


def _to_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _file_size(path: Path) -> int | None:
    return path.stat().st_size if path.exists() else None


def _gzip_file_size(path: Path) -> int | None:
    return len(gzip.compress(path.read_bytes(), mtime=0)) if path.exists() else None


def _save_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_number(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}"


def _format_signed(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    if isinstance(value, float):
        return f"{value:+,.2f}"
    return f"{value:+,}"


if __name__ == "__main__":
    raise SystemExit(main())
