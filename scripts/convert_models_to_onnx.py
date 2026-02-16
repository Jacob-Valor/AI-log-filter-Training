#!/usr/bin/env python3
"""Prepare and validate ONNX model artifacts for deployment."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any


REQUIRED_ARTIFACTS = [
    "tfidf_xgboost/model.onnx",
    "tfidf_xgboost/vectorizer.onnx",
    "anomaly_detector/model.onnx",
    "anomaly_detector/scaler.onnx",
]

OPTIONAL_ARTIFACTS = [
    "tfidf_xgboost/labels.json",
    "model_info.json",
    "training_results.json",
]


def _copy_artifacts(input_dir: Path, output_dir: Path) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    missing: list[str] = []

    for relative_path in REQUIRED_ARTIFACTS:
        source = input_dir / relative_path
        destination = output_dir / relative_path
        if not source.exists():
            missing.append(relative_path)
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(relative_path)

    for relative_path in OPTIONAL_ARTIFACTS:
        source = input_dir / relative_path
        destination = output_dir / relative_path
        if source.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(relative_path)

    return copied, missing


def _infer_feature_count(input_shape: list[Any] | tuple[Any, ...]) -> int:
    if len(input_shape) >= 2 and isinstance(input_shape[1], int) and input_shape[1] > 0:
        return int(input_shape[1])
    return 8


def _benchmark_onnx_model(model_path: Path, iterations: int = 100) -> dict[str, float]:
    import numpy as np
    from importlib import import_module

    ort = import_module("onnxruntime")

    session = ort.InferenceSession(str(model_path))
    input_meta = session.get_inputs()[0]
    input_name = input_meta.name

    if "string" in str(input_meta.type).lower():
        test_data = np.array(["sample log line" for _ in range(64)], dtype=object).reshape(-1, 1)
    else:
        feature_count = _infer_feature_count(input_meta.shape)
        rng = np.random.default_rng(42)
        test_data = rng.standard_normal((64, feature_count), dtype=np.float32)

    _ = session.run(None, {input_name: test_data})

    import time

    start = time.perf_counter()
    for _ in range(iterations):
        _ = session.run(None, {input_name: test_data})
    elapsed = time.perf_counter() - start

    return {
        "avg_ms_per_batch": elapsed * 1000 / iterations,
        "batches_per_sec": iterations / elapsed if elapsed > 0 else float("inf"),
    }


def _write_readme(output_dir: Path):
    content = """# ONNX Artifact Package

This directory contains deployable ONNX artifacts for AI Log Filter.

Artifacts are exported directly by:

```bash
python scripts/training_pipeline.py --data data/labeled/train.csv --output models/vX
```

Validation:

```bash
python scripts/validate_models.py
```
"""
    (output_dir / "MIGRATION_GUIDE.md").write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare ONNX artifacts for deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/convert_models_to_onnx.py --input models/v3 --output models/v3/onnx
  python scripts/convert_models_to_onnx.py --input models/v3 --output models/v3/onnx --benchmark
        """,
    )

    parser.add_argument("--input", "-i", required=True, help="Directory containing ONNX artifacts")
    parser.add_argument(
        "--output", "-o", required=True, help="Output directory for packaged artifacts"
    )
    parser.add_argument(
        "--benchmark", "-b", action="store_true", help="Benchmark copied ONNX models"
    )
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    print("=" * 60)
    print("ONNX ARTIFACT PREPARATION")
    print("=" * 60)
    print(f"Input:  {input_dir.resolve()}")
    print(f"Output: {output_dir.resolve()}")

    if not input_dir.exists():
        print(f"\nERROR: Input directory does not exist: {input_dir}")
        return 1

    copied, missing = _copy_artifacts(input_dir, output_dir)

    print("\nCopied Artifacts:")
    if copied:
        for item in copied:
            print(f"  ✓ {item}")
    else:
        print("  (none)")

    if missing:
        print("\nMissing Required Artifacts:")
        for item in missing:
            print(f"  ✗ {item}")
        print("\nRun training first to export ONNX artifacts.")
        return 1

    _write_readme(output_dir)

    if args.benchmark:
        print("\nBenchmark Results:")
        model_paths = [
            output_dir / "tfidf_xgboost/model.onnx",
            output_dir / "anomaly_detector/model.onnx",
            output_dir / "anomaly_detector/scaler.onnx",
        ]
        for model_path in model_paths:
            if model_path.exists():
                stats = _benchmark_onnx_model(model_path)
                print(
                    f"  {model_path.name}: "
                    f"{stats['avg_ms_per_batch']:.3f} ms/batch, "
                    f"{stats['batches_per_sec']:.1f} batches/sec"
                )

    print("\nDone. ONNX artifacts are ready for deployment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
