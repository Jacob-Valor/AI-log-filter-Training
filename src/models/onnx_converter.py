"""Utilities for exporting in-memory estimators to ONNX."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def _write_onnx(onnx_model: Any, output_path: str) -> str:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "wb") as f:
        f.write(onnx_model.SerializeToString())
    logger.info("ONNX model saved", extra={"path": str(output_file)})
    return str(output_file)


def convert_sklearn_to_onnx(
    estimator: Any,
    output_path: str,
    feature_count: int,
    input_name: str = "float_input",
) -> str:
    """Convert a fitted scikit-learn estimator to ONNX."""
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
    except ImportError as exc:
        raise ImportError("skl2onnx is required. Install with: pip install skl2onnx") from exc

    initial_type = [(input_name, FloatTensorType([None, feature_count]))]
    onnx_model = convert_sklearn(
        estimator,
        initial_types=initial_type,
        target_opset={"": 17, "ai.onnx.ml": 3},
    )
    return _write_onnx(onnx_model, output_path)


def convert_text_vectorizer_to_onnx(
    vectorizer: Any,
    output_path: str,
    input_name: str = "text_input",
) -> str:
    """Convert a fitted text vectorizer (for example TfidfVectorizer) to ONNX."""
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import StringTensorType
    except ImportError as exc:
        raise ImportError("skl2onnx is required. Install with: pip install skl2onnx") from exc

    initial_type = [(input_name, StringTensorType([None, 1]))]
    onnx_model = convert_sklearn(
        vectorizer,
        initial_types=initial_type,
        target_opset={"": 17, "ai.onnx.ml": 3},
    )
    return _write_onnx(onnx_model, output_path)


def convert_xgboost_to_onnx(
    estimator: Any,
    output_path: str,
    feature_count: int,
    input_name: str = "float_input",
) -> str:
    """Convert a fitted XGBoost estimator (or Booster) to ONNX."""
    try:
        import xgboost as xgb
        from onnxmltools.convert import convert_xgboost
        from onnxmltools.convert.common.data_types import FloatTensorType
    except ImportError as exc:
        raise ImportError(
            "onnxmltools and xgboost are required. Install with: pip install onnxmltools xgboost"
        ) from exc

    if hasattr(estimator, "get_booster"):
        booster = estimator.get_booster()
    else:
        booster = estimator

    if not isinstance(booster, xgb.Booster):
        raise TypeError(f"Unsupported XGBoost model type: {type(estimator)}")

    initial_type = [(input_name, FloatTensorType([None, feature_count]))]
    onnx_model = convert_xgboost(booster, initial_types=initial_type)
    return _write_onnx(onnx_model, output_path)


def benchmark_models(
    onnx_path: str,
    baseline_predict: Callable[[np.ndarray], Any],
    test_data: np.ndarray,
    iterations: int = 1000,
) -> dict[str, Any]:
    """Benchmark ONNX inference against a provided baseline prediction function."""
    import time

    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError("onnxruntime is required. Install with: pip install onnxruntime") from exc

    session = ort.InferenceSession(onnx_path)
    input_name = session.get_inputs()[0].name
    test_data_float = test_data.astype(np.float32)

    _ = baseline_predict(test_data)
    _ = session.run(None, {input_name: test_data_float})

    start = time.perf_counter()
    for _ in range(iterations):
        _ = baseline_predict(test_data)
    baseline_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        _ = session.run(None, {input_name: test_data_float})
    onnx_time = time.perf_counter() - start

    return {
        "baseline_time_ms": baseline_time * 1000 / iterations,
        "onnx_time_ms": onnx_time * 1000 / iterations,
        "speedup": baseline_time / onnx_time if onnx_time > 0 else float("inf"),
        "iterations": iterations,
        "samples_per_iteration": len(test_data),
    }
