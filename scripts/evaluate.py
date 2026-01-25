#!/usr/bin/env python3
"""
Model Evaluation Script

Evaluate trained models on test data.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.ensemble import EnsembleClassifier
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def evaluate_model(model_path: str, test_data_path: str):
    """Evaluate model on test data."""

    # Load model
    logger.info(f"Loading model from {model_path}")
    classifier = EnsembleClassifier(model_path=model_path, config={})
    await classifier.load()

    # Load test data
    logger.info(f"Loading test data from {test_data_path}")
    test_df = pd.read_csv(test_data_path)

    X_test = test_df["message"].tolist()
    y_test = test_df["category"].tolist()

    # Predict
    logger.info(f"Evaluating on {len(X_test)} samples...")
    predictions = await classifier.predict_batch(X_test)

    y_pred = [p.category for p in predictions]
    confidences = [p.confidence for p in predictions]

    # Calculate metrics
    logger.info("\n" + "=" * 60)
    logger.info("EVALUATION RESULTS")
    logger.info("=" * 60)

    # Overall accuracy
    accuracy = accuracy_score(y_test, y_pred)
    logger.info(f"\nOverall Accuracy: {accuracy:.4f}")

    # Classification report
    logger.info("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Confusion matrix
    labels = ["critical", "suspicious", "routine", "noise"]
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    logger.info("\nConfusion Matrix:")
    print(pd.DataFrame(cm, index=labels, columns=labels))

    # Per-class metrics
    precision, recall, f1, support = precision_recall_fscore_support(
        y_test, y_pred, labels=labels
    )

    logger.info("\nPer-Class Metrics:")
    for i, label in enumerate(labels):
        logger.info(
            f"  {label:12s}: P={precision[i]:.3f} R={recall[i]:.3f} "
            f"F1={f1[i]:.3f} Support={support[i]}"
        )

    # Confidence analysis
    logger.info("\nConfidence Statistics:")
    logger.info(f"  Mean: {np.mean(confidences):.3f}")
    logger.info(f"  Std:  {np.std(confidences):.3f}")
    logger.info(f"  Min:  {np.min(confidences):.3f}")
    logger.info(f"  Max:  {np.max(confidences):.3f}")

    # Analyze errors
    errors = [(x, yt, yp, c) for x, yt, yp, c in zip(X_test, y_test, y_pred, confidences, strict=False) if yt != yp]

    logger.info(f"\nTotal Errors: {len(errors)} / {len(X_test)} ({100*len(errors)/len(X_test):.2f}%)")

    if errors:
        logger.info("\nSample Errors (first 5):")
        for i, (msg, true_label, pred_label, conf) in enumerate(errors[:5]):
            logger.info(f"  [{i+1}] True: {true_label}, Pred: {pred_label} (conf={conf:.3f})")
            logger.info(f"      Message: {msg[:100]}...")

    return {
        "accuracy": accuracy,
        "precision": precision.tolist(),
        "recall": recall.tolist(),
        "f1": f1.tolist(),
        "confusion_matrix": cm.tolist(),
        "total_samples": len(X_test),
        "total_errors": len(errors)
    }


def main():
    """Main evaluation function."""
    parser = argparse.ArgumentParser(description="Evaluate log classification models")
    parser.add_argument(
        "--model",
        type=str,
        default="models/latest",
        help="Path to model directory"
    )
    parser.add_argument(
        "--test-data",
        type=str,
        default="data/labeled/test.csv",
        help="Path to test data CSV"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for results (JSON)"
    )

    args = parser.parse_args()

    setup_logging(level="INFO")

    import asyncio
    results = asyncio.run(evaluate_model(args.model, args.test_data))

    if args.output:
        import json
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        logger.info(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
