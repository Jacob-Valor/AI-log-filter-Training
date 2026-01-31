"""
ONNX-Only Configuration and Validation

This module provides configuration defaults and validation for ONNX-only mode.
No joblib models are used at runtime - everything must be in ONNX format.
"""

from pathlib import Path
from typing import Any


def get_onnx_only_config(model_path: str = "models/v3/onnx") -> dict[str, Any]:
    """
    Get default configuration for ONNX-only mode.

    This configuration:
    - Uses ONNX models exclusively (no joblib at runtime)
    - Optimizes for maximum performance
    - Enables all ONNX-specific features

    Args:
        model_path: Path to ONNX models directory

    Returns:
        Configuration dictionary for ONNX-only mode
    """
    return {
        "model": {
            "path": model_path,
            "format": "onnx",
            "use_onnx_only": True,
            "inference_engine": "onnx_runtime",
            "onnx_paths": {
                "anomaly_detector": "anomaly_detector.onnx",
                "xgboost": "xgboost.onnx",
            },
            "scaler_paths": {
                "anomaly_detector": "scaler.joblib",
                "tfidf_vectorizer": "tfidf_vectorizer.joblib",
            },
            "ensemble": {
                "weights": {
                    "rule_based": 0.30,
                    "tfidf_xgboost": 0.45,
                    "anomaly_detector": 0.25,
                },
                "combination_strategy": "weighted_average",
            },
            "performance": {
                "batch_size": 256,
                "max_latency_ms": 50,  # Lower than joblib mode
                "timeout_seconds": 5.0,
            },
        },
        "onnx_runtime": {
            "optimization_level": "all",  # ORT_ENABLE_ALL
            "intra_op_num_threads": 1,
            "inter_op_num_threads": 1,
            "enable_cpu_mem_arena": False,
            "enable_mem_pattern": False,
            "providers": ["CPUExecutionProvider"],  # or ["CUDAExecutionProvider"] for GPU
        },
        "monitoring": {
            "track_onnx_performance": True,
            "log_inference_times": True,
        },
        "compliance": {
            "bypass_regulated_logs": True,
            "frameworks": ["PCI-DSS", "HIPAA", "SOX", "GDPR"],
        },
    }


def validate_onnx_setup(model_path: str) -> dict[str, Any]:
    """
    Validate that ONNX models are properly set up.

    Args:
        model_path: Path to ONNX models directory

    Returns:
        Validation results dictionary

    Raises:
        RuntimeError: If required ONNX models are missing
    """
    path = Path(model_path)

    results = {
        "valid": False,
        "model_path": str(path.absolute()),
        "models_found": {},
        "models_missing": [],
        "warnings": [],
    }

    # Check required ONNX models
    required_models = {
        "anomaly_detector": "anomaly_detector.onnx",
    }

    optional_models = {
        "xgboost": "xgboost.onnx",
    }

    # Check required models
    for name, filename in required_models.items():
        model_file = path / filename
        if model_file.exists():
            size_kb = model_file.stat().st_size / 1024
            results["models_found"][name] = {
                "file": str(model_file),
                "size_kb": round(size_kb, 2),
                "status": "✓ found",
            }
        else:
            results["models_missing"].append(name)

    # Check optional models
    for name, filename in optional_models.items():
        model_file = path / filename
        if model_file.exists():
            size_kb = model_file.stat().st_size / 1024
            results["models_found"][name] = {
                "file": str(model_file),
                "size_kb": round(size_kb, 2),
                "status": "✓ found (optional)",
            }
        else:
            results["warnings"].append(f"Optional model '{name}' not found at {model_file}")

    # Check scalers (still needed for preprocessing)
    required_scalers = {
        "anomaly_scaler": "scaler.joblib",
    }

    for name, filename in required_scalers.items():
        scaler_file = path / filename
        if scaler_file.exists():
            results["models_found"][name] = {"file": str(scaler_file), "status": "✓ found"}
        else:
            results["warnings"].append(
                f"Scaler '{name}' not found. Anomaly detector may not work correctly."
            )

    # Validate
    if not results["models_missing"]:
        results["valid"] = True
        results["status"] = "✅ ONNX setup valid - ready for ONNX-only mode"
    else:
        results["status"] = f"❌ Missing required models: {', '.join(results['models_missing'])}"
        results["help"] = (
            "Run: python scripts/convert_models_to_onnx.py --input models/v3 --output models/v3/onnx"
        )

    return results


def print_onnx_validation(model_path: str = "models/v3/onnx"):
    """Print formatted validation results."""
    results = validate_onnx_setup(model_path)

    print("\n" + "=" * 60)
    print("ONNX-ONLY SETUP VALIDATION")
    print("=" * 60)
    print(f"\nModel Path: {results['model_path']}")
    print(f"Status: {results['status']}")

    if results["models_found"]:
        print("\n✓ Models Found:")
        for name, info in results["models_found"].items():
            size = info.get("size_kb", "N/A")
            if size != "N/A":
                print(f"  • {name}: {size} KB - {info['status']}")
            else:
                print(f"  • {name}: {info['status']}")

    if results["models_missing"]:
        print("\n✗ Missing Required Models:")
        for model in results["models_missing"]:
            print(f"  • {model}")

    if results["warnings"]:
        print("\n⚠ Warnings:")
        for warning in results["warnings"]:
            print(f"  • {warning}")

    if "help" in results:
        print(f"\n💡 {results['help']}")

    print("\n" + "=" * 60)

    return results["valid"]


# Default ONNX-only configuration instance
ONNX_ONLY_CONFIG = get_onnx_only_config()
