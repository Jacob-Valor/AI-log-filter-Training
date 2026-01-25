#!/usr/bin/env python3
"""
Model Artifact Validator

Validates that all required model artifacts are present and properly configured.
"""

import json
from pathlib import Path
from typing import Any

MODELS_DIR = Path("/home/jacob/Projects/tester/models")
MODEL_VERSION = "v1"


def validate_models() -> dict[str, Any]:
    """Validate model artifacts for production deployment."""

    results = {
        "valid": True,
        "model_version": MODEL_VERSION,
        "checks": [],
        "missing": [],
        "warnings": [],
    }

    model_path = MODELS_DIR / MODEL_VERSION

    # Required files
    required_files = [
        "model_info.json",
        "training_results.json",
        "model_registry.json",
        "ensemble_config.json",
        "tfidf_xgboost/model.joblib",
        "anomaly_detector/model.joblib",
        "rule_based/rules.yaml",
    ]

    # Check required files
    for file_path in required_files:
        full_path = model_path / file_path
        if full_path.exists():
            results["checks"].append(
                {"file": file_path, "status": "OK", "size": full_path.stat().st_size}
            )
        else:
            results["valid"] = False
            results["missing"].append(file_path)
            results["checks"].append({"file": file_path, "status": "MISSING"})

    # Validate model_info.json
    try:
        with open(model_path / "model_info.json") as f:
            info = json.load(f)
            if info.get("passed_validation"):
                results["checks"].append(
                    {
                        "check": "model_info validation",
                        "status": "OK",
                        "accuracy": info.get("accuracy"),
                        "critical_recall": info.get("critical_recall"),
                    }
                )
            else:
                results["valid"] = False
                results["warnings"].append("Model validation failed")
    except Exception as e:
        results["valid"] = False
        results["warnings"].append(f"Cannot read model_info.json: {e}")

    # Validate training_results.json
    try:
        with open(model_path / "training_results.json") as f:
            results_data = json.load(f)
            if results_data.get("passed_validation"):
                results["checks"].append(
                    {
                        "check": "training_results validation",
                        "status": "OK",
                        "accuracy": results_data.get("accuracy"),
                        "training_samples": results_data.get("training_samples"),
                    }
                )
    except Exception as e:
        results["warnings"].append(f"Cannot read training_results.json: {e}")

    # Check model file sizes
    model_files = ["tfidf_xgboost/model.joblib", "anomaly_detector/model.joblib"]

    for model_file in model_files:
        full_path = model_path / model_file
        if full_path.exists():
            size_mb = full_path.stat().st_size / (1024 * 1024)
            results["checks"].append(
                {
                    "check": f"{model_file} size",
                    "status": "OK" if size_mb > 0 else "WARNING",
                    "size_mb": round(size_mb, 2),
                }
            )

    # Summary
    results["summary"] = {
        "total_checks": len(results["checks"]),
        "passed": sum(1 for c in results["checks"] if c.get("status") == "OK"),
        "missing_count": len(results["missing"]),
        "warning_count": len(results["warnings"]),
    }

    return results


def print_results(results: dict[str, Any]):
    """Print validation results."""

    print("\n" + "=" * 70)
    print("MODEL ARTIFACT VALIDATION REPORT")
    print("=" * 70)
    print(f"\nModel Version: {results['model_version']}")
    print(f"Overall Status: {'✅ VALID' if results['valid'] else '❌ INVALID'}")

    print("\n📋 Checks:")
    for check in results["checks"]:
        if check.get("status") == "OK":
            status_icon = "✅"
        elif check.get("status") == "MISSING":
            status_icon = "❌"
        else:
            status_icon = "⚠️"
        print(f"  {status_icon} {check.get('file', check.get('check'))}")

    if results["missing"]:
        print("\n❌ Missing Files:")
        for missing in results["missing"]:
            print(f"   - {missing}")

    if results["warnings"]:
        print("\n⚠️ Warnings:")
        for warning in results["warnings"]:
            print(f"   - {warning}")

    summary = results["summary"]
    print("\n📊 Summary:")
    print(f"   Total Checks: {summary['total_checks']}")
    print(f"   Passed: {summary['passed']}")
    print(f"   Missing: {summary['missing_count']}")
    print(f"   Warnings: {summary['warning_count']}")

    print("\n" + "=" * 70)

    return results["valid"]


if __name__ == "__main__":
    results = validate_models()
    is_valid = print_results(results)
    exit(0 if is_valid else 1)
