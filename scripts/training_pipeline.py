#!/usr/bin/env python3
"""
Comprehensive Training Pipeline for AI Log Filter

This script provides end-to-end training capabilities:
1. Data loading and preprocessing
2. Label generation (semi-supervised if needed)
3. Model training (TF-IDF + XGBoost, Anomaly Detector)
4. Evaluation and validation
5. Model versioning and export

Usage:
    python scripts/training_pipeline.py --data data/labeled/train.csv --output models/v1
    python scripts/training_pipeline.py --hdfs HDFS_v3_TraceBench/ --auto-label --output models/v1
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class TrainingConfig:
    """Training configuration."""

    # Data settings
    test_size: float = 0.15
    val_size: float = 0.10
    random_state: int = 42

    # TF-IDF settings
    tfidf_max_features: int = 10000
    tfidf_ngram_range: tuple[int, int] = (1, 3)
    tfidf_min_df: int = 2
    tfidf_max_df: float = 0.95

    # XGBoost settings
    xgb_n_estimators: int = 200
    xgb_max_depth: int = 6
    xgb_learning_rate: float = 0.1
    xgb_early_stopping_rounds: int = 20

    # Anomaly detector settings
    anomaly_contamination: float = 0.1
    anomaly_n_estimators: int = 200

    # Validation settings
    min_critical_recall: float = 0.99
    cv_folds: int = 5


@dataclass
class TrainingResults:
    """Results from training run."""

    model_version: str
    timestamp: str
    accuracy: float
    per_class_metrics: dict[str, dict[str, float]]
    confusion_matrix: list[list[int]]
    cv_scores: list[float]
    training_samples: int
    test_samples: int
    passed_validation: bool
    validation_messages: list[str]


# =============================================================================
# Data Loading and Preprocessing
# =============================================================================


class DataLoader:
    """Load and preprocess training data from various sources."""

    CATEGORIES = ["critical", "suspicious", "routine", "noise"]

    # Patterns for auto-labeling (when labels not available)
    AUTO_LABEL_PATTERNS = {
        "critical": [
            r"(malware|virus|trojan|ransomware)",
            r"(brute.?force|credential.?stuff)",
            r"(privilege.?escalat|root.?access)",
            r"(data.?exfil|unauthorized.?transfer)",
            r"(sql.?injection|xss|rce)",
            r"(c2.?beacon|command.?control)",
        ],
        "suspicious": [
            r"(failed.?login|auth.?fail|invalid.?password)",
            r"(access.?denied|permission.?denied|forbidden)",
            r"(port.?scan|network.?probe)",
            r"(unusual.?activity|anomal)",
            r"(error|exception|fail)",
        ],
        "noise": [
            r"(health.?check|heartbeat|keep.?alive)",
            r"(debug|trace|verbose)",
            r"(metric|telemetry|prometheus)",
            r"(cron|scheduled.?task|timer)",
            r"(ping|status.?ok|alive)",
        ],
        "routine": [
            r"(success|completed|started|finished)",
            r"(info|notice|log)",
            r"(session.?created|user.?login)",
            r"(config.?change|update)",
        ],
    }

    def __init__(self, config: TrainingConfig):
        self.config = config

    def load_csv(self, filepath: str) -> pd.DataFrame:
        """Load labeled data from CSV."""
        logger.info(f"Loading data from {filepath}")
        df = pd.read_csv(filepath)

        # Validate required columns
        required = ["message", "category"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Validate categories
        invalid = df[~df["category"].isin(self.CATEGORIES)]["category"].unique()
        if len(invalid) > 0:
            logger.warning(f"Invalid categories found: {invalid}")
            df = df[df["category"].isin(self.CATEGORIES)]

        logger.info(f"Loaded {len(df)} samples")
        logger.info(f"Category distribution:\n{df['category'].value_counts()}")

        return df

    def load_hdfs_data(self, hdfs_path: str) -> pd.DataFrame:
        """Load HDFS TraceBench data."""
        logger.info(f"Loading HDFS data from {hdfs_path}")

        hdfs_dir = Path(hdfs_path)
        dfs = []

        # Try to load various file formats
        for pattern in ["*.csv", "*.log", "*.txt"]:
            for filepath in hdfs_dir.glob(f"**/{pattern}"):
                try:
                    if pattern == "*.csv":
                        df = pd.read_csv(filepath)
                        if "Content" in df.columns:
                            df = df.rename(columns={"Content": "message"})
                        elif "message" not in df.columns:
                            # Use first text column as message
                            text_cols = df.select_dtypes(include=["object"]).columns
                            if len(text_cols) > 0:
                                df["message"] = df[text_cols[0]]
                    else:
                        # Load as raw log file
                        with open(filepath, errors="ignore") as f:
                            lines = f.readlines()
                        df = pd.DataFrame({"message": lines})

                    if "message" in df.columns:
                        df["source_file"] = filepath.name
                        dfs.append(df)
                        logger.debug(f"Loaded {len(df)} lines from {filepath.name}")

                except Exception as e:
                    logger.warning(f"Failed to load {filepath}: {e}")

        if not dfs:
            raise ValueError(f"No valid data found in {hdfs_path}")

        combined = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(combined)} total samples from HDFS")

        return combined

    def auto_label(self, df: pd.DataFrame) -> pd.DataFrame:
        """Auto-label data using pattern matching."""
        import re

        logger.info("Auto-labeling data using pattern matching...")

        labels = []
        confidences = []

        for message in df["message"]:
            message_lower = str(message).lower()
            label = "routine"  # default
            confidence = 0.5

            # Check patterns in priority order
            for category in ["critical", "suspicious", "noise", "routine"]:
                for pattern in self.AUTO_LABEL_PATTERNS[category]:
                    if re.search(pattern, message_lower):
                        label = category
                        confidence = 0.8 if category in ["critical", "noise"] else 0.7
                        break
                if label != "routine" or category == "routine":
                    break

            labels.append(label)
            confidences.append(confidence)

        df["category"] = labels
        df["label_confidence"] = confidences

        logger.info(f"Auto-labeled distribution:\n{df['category'].value_counts()}")

        return df

    def preprocess_text(self, text: str) -> str:
        """Preprocess log message for training."""
        import re

        # Normalize IP addresses
        text = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", text)

        # Normalize timestamps
        text = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "<TIMESTAMP>", text)

        # Normalize hex values
        text = re.sub(r"0x[0-9a-fA-F]+", "<HEX>", text)

        # Normalize UUIDs
        text = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<UUID>",
            text,
            flags=re.IGNORECASE,
        )

        # Normalize paths
        text = re.sub(r"(/[\w\-./]+)+", "<PATH>", text)

        # Normalize large numbers
        text = re.sub(r"\b\d{5,}\b", "<LONGNUM>", text)

        # Lowercase and normalize whitespace
        text = text.lower()
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def prepare_data(
        self, df: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Prepare data for training with train/val/test split."""

        # Preprocess messages
        logger.info("Preprocessing messages...")
        df["processed"] = df["message"].apply(self.preprocess_text)

        # Remove empty messages
        df = df[df["processed"].str.len() > 0]

        X = df["processed"].values
        y = df["category"].values

        # First split: train+val vs test
        X_trainval, X_test, y_trainval, y_test = train_test_split(
            X, y, test_size=self.config.test_size, random_state=self.config.random_state, stratify=y
        )

        # Second split: train vs val
        val_ratio = self.config.val_size / (1 - self.config.test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_trainval,
            y_trainval,
            test_size=val_ratio,
            random_state=self.config.random_state,
            stratify=y_trainval,
        )

        logger.info(f"Data split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

        return X_train, X_val, X_test, y_train, y_val, y_test


# =============================================================================
# Model Training
# =============================================================================


class ModelTrainer:
    """Train classification and anomaly detection models."""

    CATEGORIES = ["critical", "suspicious", "routine", "noise"]

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.vectorizer = None
        self.classifier = None
        self.label_encoder = None
        self.anomaly_detector = None
        self.anomaly_scaler = None

    def train_tfidf_xgboost(
        self, X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray
    ) -> dict[str, Any]:
        """Train TF-IDF + XGBoost classifier."""
        from xgboost import XGBClassifier

        logger.info("Training TF-IDF + XGBoost classifier...")

        # Initialize vectorizer
        self.vectorizer = TfidfVectorizer(
            max_features=self.config.tfidf_max_features,
            ngram_range=self.config.tfidf_ngram_range,
            min_df=self.config.tfidf_min_df,
            max_df=self.config.tfidf_max_df,
            sublinear_tf=True,
        )

        # Fit vectorizer and transform
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_val_vec = self.vectorizer.transform(X_val)

        logger.info(f"Vocabulary size: {len(self.vectorizer.vocabulary_)}")

        # Encode labels
        self.label_encoder = LabelEncoder()
        self.label_encoder.fit(self.CATEGORIES)
        y_train_enc = self.label_encoder.transform(y_train)
        y_val_enc = self.label_encoder.transform(y_val)

        # Calculate class weights for imbalanced data
        from sklearn.utils.class_weight import compute_sample_weight

        sample_weights = compute_sample_weight("balanced", y_train_enc)

        # Initialize classifier
        self.classifier = XGBClassifier(
            n_estimators=self.config.xgb_n_estimators,
            max_depth=self.config.xgb_max_depth,
            learning_rate=self.config.xgb_learning_rate,
            objective="multi:softprob",
            eval_metric="mlogloss",
            use_label_encoder=False,
            n_jobs=-1,
            random_state=self.config.random_state,
            early_stopping_rounds=self.config.xgb_early_stopping_rounds,
        )

        # Train with early stopping
        self.classifier.fit(
            X_train_vec,
            y_train_enc,
            sample_weight=sample_weights,
            eval_set=[(X_val_vec, y_val_enc)],
            verbose=False,
        )

        # Get feature importance
        feature_names = self.vectorizer.get_feature_names_out()
        importances = self.classifier.feature_importances_
        top_features = sorted(
            zip(feature_names, importances, strict=False), key=lambda x: x[1], reverse=True
        )[:20]

        logger.info("Top 10 features:")
        for name, imp in top_features[:10]:
            logger.info(f"  {name}: {imp:.4f}")

        return {
            "vocabulary_size": len(self.vectorizer.vocabulary_),
            "n_estimators_used": self.classifier.best_iteration + 1,
            "top_features": dict(top_features),
        }

    def train_anomaly_detector(self, X_train: np.ndarray) -> dict[str, Any]:
        """Train anomaly detector on normal logs."""
        logger.info("Training anomaly detector...")

        # Extract numerical features
        features = self._extract_anomaly_features(X_train)

        # Scale features
        self.anomaly_scaler = StandardScaler()
        features_scaled = self.anomaly_scaler.fit_transform(features)

        # Train Isolation Forest
        self.anomaly_detector = IsolationForest(
            contamination=self.config.anomaly_contamination,
            n_estimators=self.config.anomaly_n_estimators,
            max_samples="auto",
            random_state=self.config.random_state,
            n_jobs=-1,
        )
        self.anomaly_detector.fit(features_scaled)

        # Get anomaly scores for training data
        scores = self.anomaly_detector.score_samples(features_scaled)

        return {
            "n_features": features.shape[1],
            "mean_score": float(np.mean(scores)),
            "std_score": float(np.std(scores)),
            "threshold": float(np.percentile(scores, 10)),
        }

    def _extract_anomaly_features(self, texts: np.ndarray) -> np.ndarray:
        """Extract numerical features for anomaly detection."""
        import re

        features = []
        for text in texts:
            text = str(text)

            # Basic text features
            msg_len = len(text)
            word_count = len(text.split())

            # Character ratios
            digit_count = sum(c.isdigit() for c in text)
            special_count = sum(not c.isalnum() and not c.isspace() for c in text)
            upper_count = sum(c.isupper() for c in text)

            digit_ratio = digit_count / max(msg_len, 1)
            special_ratio = special_count / max(msg_len, 1)
            upper_ratio = upper_count / max(msg_len, 1)

            # Keyword indicators
            has_error = 1 if re.search(r"\b(error|fail|exception)\b", text, re.I) else 0
            has_ip = 1 if re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text) else 0
            has_path = 1 if re.search(r"/\w+/", text) else 0

            features.append(
                [
                    msg_len,
                    word_count,
                    digit_ratio,
                    special_ratio,
                    upper_ratio,
                    has_error,
                    has_ip,
                    has_path,
                ]
            )

        return np.array(features)

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> TrainingResults:
        """Evaluate trained models."""
        logger.info("Evaluating models...")

        # Transform test data
        X_test_vec = self.vectorizer.transform(X_test)
        self.label_encoder.transform(y_test)

        # Predict
        y_pred_enc = self.classifier.predict(X_test_vec)
        y_pred = self.label_encoder.inverse_transform(y_pred_enc)
        self.classifier.predict_proba(X_test_vec)

        # Calculate metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision, recall, f1, support = precision_recall_fscore_support(
            y_test, y_pred, labels=self.CATEGORIES
        )
        cm = confusion_matrix(y_test, y_pred, labels=self.CATEGORIES)

        # Per-class metrics
        per_class = {}
        for i, cat in enumerate(self.CATEGORIES):
            per_class[cat] = {
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }

        # Cross-validation using a fresh classifier without early stopping
        # (early_stopping_rounds is incompatible with cross_val_score)
        logger.info("Running cross-validation...")
        try:
            from xgboost import XGBClassifier as XGBClassifierCV

            cv_classifier = XGBClassifierCV(
                n_estimators=min(50, self.config.xgb_n_estimators),
                max_depth=self.config.xgb_max_depth,
                learning_rate=self.config.xgb_learning_rate,
                objective="multi:softprob",
                eval_metric="mlogloss",
                n_jobs=-1,
                random_state=self.config.random_state,
                # No early_stopping_rounds for CV compatibility
            )
            X_all = self.vectorizer.transform(X_test)
            y_all = self.label_encoder.transform(y_test)
            cv_scores = cross_val_score(
                cv_classifier,
                X_all,
                y_all,
                cv=min(self.config.cv_folds, len(y_test) // 10),
                scoring="accuracy",
            )
        except Exception as e:
            logger.warning(f"Cross-validation failed: {e}")
            cv_scores = np.array([accuracy])  # Fall back to test accuracy

        # Validation checks
        validation_messages = []
        passed = True

        # Check critical recall
        critical_recall = per_class["critical"]["recall"]
        if critical_recall < self.config.min_critical_recall:
            passed = False
            validation_messages.append(
                f"FAIL: Critical recall {critical_recall:.3f} < {self.config.min_critical_recall}"
            )
        else:
            validation_messages.append(
                f"PASS: Critical recall {critical_recall:.3f} >= {self.config.min_critical_recall}"
            )

        # Check overall accuracy
        if accuracy < 0.90:
            validation_messages.append(f"WARNING: Accuracy {accuracy:.3f} < 0.90")

        # Print report
        logger.info("\n" + "=" * 60)
        logger.info("EVALUATION RESULTS")
        logger.info("=" * 60)
        logger.info(f"Overall Accuracy: {accuracy:.4f}")
        logger.info(f"CV Scores: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
        logger.info("\nClassification Report:")
        print(classification_report(y_test, y_pred, labels=self.CATEGORIES))
        logger.info("\nConfusion Matrix:")
        print(pd.DataFrame(cm, index=self.CATEGORIES, columns=self.CATEGORIES))
        logger.info("\nValidation:")
        for msg in validation_messages:
            logger.info(f"  {msg}")

        # Generate version hash
        version = datetime.now().strftime("%Y%m%d_%H%M%S")

        return TrainingResults(
            model_version=version,
            timestamp=datetime.now().isoformat(),
            accuracy=float(accuracy),
            per_class_metrics=per_class,
            confusion_matrix=cm.tolist(),
            cv_scores=cv_scores.tolist(),
            training_samples=len(X_test),  # Will be updated
            test_samples=len(X_test),
            passed_validation=passed,
            validation_messages=validation_messages,
        )

    def save(self, output_path: str, results: TrainingResults):
        """Save trained models and metadata."""
        output_dir = Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save TF-IDF + XGBoost
        tfidf_dir = output_dir / "tfidf_xgboost"
        tfidf_dir.mkdir(exist_ok=True)
        joblib.dump(
            {
                "vectorizer": self.vectorizer,
                "classifier": self.classifier,
                "label_encoder": self.label_encoder,
                "config": asdict(self.config),
            },
            tfidf_dir / "model.joblib",
        )
        logger.info(f"Saved TF-IDF model to {tfidf_dir}")

        # Save anomaly detector
        anomaly_dir = output_dir / "anomaly_detector"
        anomaly_dir.mkdir(exist_ok=True)
        joblib.dump(
            {
                "model": self.anomaly_detector,
                "scaler": self.anomaly_scaler,
                "config": asdict(self.config),
            },
            anomaly_dir / "model.joblib",
        )
        logger.info(f"Saved anomaly detector to {anomaly_dir}")

        # Save results and metadata
        with open(output_dir / "training_results.json", "w") as f:
            json.dump(asdict(results), f, indent=2)

        with open(output_dir / "model_info.json", "w") as f:
            json.dump(
                {
                    "version": results.model_version,
                    "timestamp": results.timestamp,
                    "accuracy": results.accuracy,
                    "critical_recall": results.per_class_metrics["critical"]["recall"],
                    "passed_validation": results.passed_validation,
                    "config": asdict(self.config),
                },
                f,
                indent=2,
            )

        # Create latest symlink
        latest_link = output_dir.parent / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(output_dir.name)

        logger.info(f"Model saved to {output_dir}")
        logger.info("Created 'latest' symlink")


# =============================================================================
# Main Pipeline
# =============================================================================


def run_pipeline(args):
    """Run the complete training pipeline."""
    setup_logging(level="INFO")

    logger.info("=" * 60)
    logger.info("AI Log Filter - Training Pipeline")
    logger.info("=" * 60)

    # Initialize config
    config = TrainingConfig()

    # Override config from args
    if args.min_recall:
        config.min_critical_recall = args.min_recall

    # Load data
    loader = DataLoader(config)

    if args.data:
        df = loader.load_csv(args.data)
    elif args.hdfs:
        df = loader.load_hdfs_data(args.hdfs)
        if args.auto_label or "category" not in df.columns:
            df = loader.auto_label(df)
    else:
        raise ValueError("Must specify --data or --hdfs")

    # Check minimum data requirements
    min_samples = 1000
    if len(df) < min_samples:
        logger.warning(f"Only {len(df)} samples available. Recommended: {min_samples}+")

    # Prepare data
    X_train, X_val, X_test, y_train, y_val, y_test = loader.prepare_data(df)

    # Train models
    trainer = ModelTrainer(config)

    tfidf_info = trainer.train_tfidf_xgboost(X_train, y_train, X_val, y_val)
    logger.info(f"TF-IDF training info: {tfidf_info}")

    # Train anomaly detector on "normal" logs (routine + noise)
    normal_mask = np.isin(y_train, ["routine", "noise"])
    if np.sum(normal_mask) > 100:
        anomaly_info = trainer.train_anomaly_detector(X_train[normal_mask])
        logger.info(f"Anomaly detector info: {anomaly_info}")
    else:
        logger.warning("Not enough normal samples for anomaly detector")

    # Evaluate
    results = trainer.evaluate(X_test, y_test)
    results.training_samples = len(X_train)

    # Save
    trainer.save(args.output, results)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Model version: {results.model_version}")
    logger.info(f"Accuracy: {results.accuracy:.4f}")
    logger.info(f"Critical recall: {results.per_class_metrics['critical']['recall']:.4f}")
    logger.info(f"Validation passed: {results.passed_validation}")
    logger.info(f"Output: {args.output}")

    if not results.passed_validation:
        logger.error("MODEL DID NOT PASS VALIDATION - Review before production use")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Train AI Log Filter models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Train from labeled CSV
  python scripts/training_pipeline.py --data data/labeled/train.csv --output models/v1

  # Train from HDFS data with auto-labeling
  python scripts/training_pipeline.py --hdfs HDFS_v3_TraceBench/ --auto-label --output models/v1

  # Train with custom recall threshold
  python scripts/training_pipeline.py --data data/train.csv --min-recall 0.995 --output models/v1
        """,
    )

    parser.add_argument(
        "--data",
        type=str,
        help="Path to labeled CSV file (must have 'message' and 'category' columns)",
    )
    parser.add_argument("--hdfs", type=str, help="Path to HDFS TraceBench directory")
    parser.add_argument(
        "--auto-label", action="store_true", help="Auto-label data using pattern matching"
    )
    parser.add_argument(
        "--output", type=str, default="models/v1", help="Output directory for trained models"
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.99,
        help="Minimum required critical recall (default: 0.99)",
    )

    args = parser.parse_args()

    if not args.data and not args.hdfs:
        parser.error("Must specify either --data or --hdfs")

    sys.exit(run_pipeline(args))


if __name__ == "__main__":
    main()
