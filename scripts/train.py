#!/usr/bin/env python3
"""
Model Training Script

Train log classification models on labeled data.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.anomaly_detector import AnomalyDetector
from src.models.tfidf_classifier import TFIDFClassifier
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def load_config(config_path: str) -> dict:
    """Load training configuration."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_data(config: dict) -> tuple:
    """Load training data."""
    data_config = config.get("data", {})

    train_path = data_config.get("train_path", "data/labeled/train.csv")
    val_path = data_config.get("val_path", "data/labeled/val.csv")
    test_path = data_config.get("test_path", "data/labeled/test.csv")

    text_col = data_config.get("columns", {}).get("text", "message")
    label_col = data_config.get("columns", {}).get("label", "category")

    # Load datasets
    try:
        train_df = pd.read_csv(train_path)
        val_df = pd.read_csv(val_path)
        test_df = pd.read_csv(test_path)

        logger.info(f"Loaded {len(train_df)} training samples")
        logger.info(f"Loaded {len(val_df)} validation samples")
        logger.info(f"Loaded {len(test_df)} test samples")

        return (
            (train_df[text_col], train_df[label_col]),
            (val_df[text_col], val_df[label_col]),
            (test_df[text_col], test_df[label_col])
        )
    except FileNotFoundError as e:
        logger.warning(f"Data file not found: {e}")
        logger.info("Generating synthetic data for demonstration...")
        return generate_synthetic_data()


def generate_synthetic_data() -> tuple:
    """Generate synthetic data for testing."""
    np.random.seed(42)

    # Sample log patterns for each category
    patterns = {
        "critical": [
            "CRITICAL: Multiple failed authentication attempts detected from IP <IP>",
            "ALERT: Malware signature detected in file /usr/bin/suspicious",
            "SECURITY: Privilege escalation attempt by user admin",
            "CRITICAL: Data exfiltration detected - large upload to external IP",
            "ALERT: Known C2 beacon communication detected",
        ],
        "suspicious": [
            "WARNING: Failed login attempt for user admin from <IP>",
            "NOTICE: Unusual outbound connection to port 4444",
            "WARNING: Access denied for user guest to /etc/shadow",
            "NOTICE: Unusual process execution: powershell.exe -enc",
            "WARNING: Failed SSH authentication from new location",
        ],
        "routine": [
            "INFO: User admin logged in successfully",
            "INFO: Scheduled backup completed successfully",
            "INFO: Service nginx restarted",
            "INFO: Configuration file updated by admin",
            "INFO: Database connection established",
        ],
        "noise": [
            "DEBUG: Health check endpoint called",
            "TRACE: Heartbeat received from agent",
            "DEBUG: Cache hit for key user_session_123",
            "DEBUG: Metric collection completed",
            "TRACE: Keep-alive packet received",
        ],
    }

    # Generate samples
    data = []
    for category, templates in patterns.items():
        for _ in range(200):
            template = np.random.choice(templates)
            # Add some variation
            log = template.replace("<IP>", f"{np.random.randint(1,255)}.{np.random.randint(0,255)}.{np.random.randint(0,255)}.{np.random.randint(1,255)}")
            data.append({"message": log, "category": category})

    df = pd.DataFrame(data)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Split data
    train_df, temp_df = train_test_split(df, test_size=0.3, stratify=df["category"], random_state=42)
    val_df, test_df = train_test_split(temp_df, test_size=0.5, stratify=temp_df["category"], random_state=42)

    logger.info(f"Generated {len(train_df)} training, {len(val_df)} validation, {len(test_df)} test samples")

    return (
        (train_df["message"], train_df["category"]),
        (val_df["message"], val_df["category"]),
        (test_df["message"], test_df["category"])
    )


async def train_tfidf(config: dict, train_data: tuple, val_data: tuple, output_dir: Path):
    """Train TF-IDF + XGBoost classifier."""
    logger.info("Training TF-IDF + XGBoost classifier...")

    tfidf_config = config.get("models", {}).get("tfidf_xgboost", {})
    classifier = TFIDFClassifier(tfidf_config)

    await classifier.load()  # Initialize empty model

    X_train, y_train = train_data
    classifier.train(X_train.tolist(), y_train.tolist())

    # Save model
    model_path = output_dir / "tfidf_xgboost"
    classifier.save(str(model_path))

    # Evaluate
    predictions = await classifier.predict_batch(val_data[0].tolist())
    pred_labels = [p.category for p in predictions]

    logger.info("\nTF-IDF Classifier Validation Results:")
    print(classification_report(val_data[1], pred_labels))

    return classifier


async def train_anomaly(config: dict, train_data: tuple, output_dir: Path):
    """Train anomaly detector."""
    logger.info("Training Anomaly Detector...")

    anomaly_config = config.get("models", {}).get("anomaly", {})
    detector = AnomalyDetector(anomaly_config)

    await detector.load()  # Initialize empty model

    X_train, y_train = train_data

    # Train on normal logs (routine category)
    normal_logs = X_train[y_train == "routine"].tolist()
    detector.train(normal_logs)

    # Save model
    model_path = output_dir / "anomaly_detector"
    detector.save(str(model_path))

    logger.info("Anomaly detector training complete")

    return detector


def evaluate_models(classifiers: dict, test_data: tuple):
    """Evaluate all models on test data."""
    import asyncio

    X_test, y_test = test_data

    logger.info("\n" + "=" * 60)
    logger.info("FINAL EVALUATION ON TEST SET")
    logger.info("=" * 60)

    for name, classifier in classifiers.items():
        predictions = asyncio.run(classifier.predict_batch(X_test.tolist()))
        pred_labels = [p.category for p in predictions]

        logger.info(f"\n{name.upper()} Results:")
        print(classification_report(y_test, pred_labels))

        # Confusion matrix
        cm = confusion_matrix(y_test, pred_labels, labels=["critical", "suspicious", "routine", "noise"])
        logger.info(f"\nConfusion Matrix:\n{cm}")


def main():
    """Main training function."""
    parser = argparse.ArgumentParser(description="Train log classification models")
    parser.add_argument(
        "--config",
        type=str,
        default="configs/model_config.yaml",
        help="Path to model configuration file"
    )
    parser.add_argument(
        "--model-type",
        type=str,
        choices=["tfidf", "anomaly", "ensemble", "all"],
        default="all",
        help="Model type to train"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models",
        help="Output directory for trained models"
    )

    args = parser.parse_args()

    # Setup
    setup_logging(level="INFO")
    config = load_config(args.config)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Training run: {run_dir}")

    # Load data
    train_data, val_data, test_data = load_data(config)

    # Train models
    import asyncio
    classifiers = {}

    if args.model_type in ["tfidf", "all"]:
        classifier = asyncio.run(train_tfidf(config, train_data, val_data, run_dir))
        classifiers["tfidf"] = classifier

    if args.model_type in ["anomaly", "all"]:
        detector = asyncio.run(train_anomaly(config, train_data, run_dir))
        classifiers["anomaly"] = detector

    # Evaluate
    if classifiers:
        evaluate_models(classifiers, test_data)

    # Create symlink to latest
    latest_link = output_dir / "latest"
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(run_dir.name)

    logger.info(f"\nTraining complete! Models saved to: {run_dir}")
    logger.info(f"Latest symlink updated: {latest_link} -> {run_dir.name}")


if __name__ == "__main__":
    main()
