#!/usr/bin/env python3
"""
Shadow Mode Validation Script

Validates AI classifier accuracy by running on historical labeled data
without affecting production systems.

This script:
1. Loads the trained models
2. Runs classification on labeled historical data
3. Compares predictions with ground truth labels
4. Reports accuracy metrics (especially critical recall)
5. Identifies false negatives for review
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for shadow mode validation."""

    model_path: str = "models/v1"
    test_data_path: str = "data/labeled/test.csv"
    output_path: str = "reports/shadow_validation"
    min_samples: int = 1000
    target_recall: float = 0.995  # 99.5% critical recall required
    max_false_negatives: int = 5  # Maximum allowed critical FN per 1000 samples
    batch_size: int = 100


@dataclass
class ValidationResult:
    """Results from shadow mode validation."""

    total_samples: int = 0
    correct_predictions: int = 0
    incorrect_predictions: int = 0

    # By category
    critical_tp: int = 0
    critical_fp: int = 0
    critical_tn: int = 0
    critical_fn: int = 0

    suspicious_tp: int = 0
    suspicious_fp: int = 0
    suspicious_tn: int = 0
    suspicious_fn: int = 0

    routine_tp: int = 0
    routine_fp: int = 0
    routine_tn: int = 0
    routine_fn: int = 0

    noise_tp: int = 0
    noise_fp: int = 0
    noise_tn: int = 0
    noise_fn: int = 0

    # False negatives for review
    false_negatives: list[dict] = field(default_factory=list)

    # Metadata
    execution_time_seconds: float = 0.0
    timestamp: str = ""

    @property
    def accuracy(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return self.correct_predictions / self.total_samples

    @property
    def critical_recall(self) -> float:
        total_critical = self.critical_tp + self.critical_fn
        if total_critical == 0:
            return 1.0
        return self.critical_tp / total_critical

    @property
    def critical_precision(self) -> float:
        total_predicted_critical = self.critical_tp + self.critical_fp
        if total_predicted_critical == 0:
            return 1.0
        return self.critical_tp / total_predicted_critical

    @property
    def false_negative_rate(self) -> float:
        total_critical = self.critical_tp + self.critical_fn
        if total_critical == 0:
            return 0.0
        return self.critical_fn / total_critical

    @property
    def critical_fn_per_1000(self) -> float:
        if self.total_samples == 0:
            return 0.0
        return (self.critical_fn / self.total_samples) * 1000


class ShadowModeValidator:
    """
    Validates AI classifier in shadow mode using historical labeled data.
    """

    def __init__(self, config: ValidationConfig):
        self.config = config
        self.classifier = None
        self.results = ValidationResult()

    async def initialize(self):
        """Initialize the classifier with trained models."""
        logger.info("Loading classifier models...")

        try:
            from src.models.safe_ensemble import SafeEnsembleClassifier

            self.classifier = SafeEnsembleClassifier(model_path=self.config.model_path, config={})
            await self.classifier.load()

            logger.info("Classifier loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load classifier: {e}")

            # Try fallback to simpler classifier
            try:
                from src.models.ensemble import EnsembleClassifier

                logger.info("Trying fallback to EnsembleClassifier...")
                from src.utils.config import load_config

                config = load_config("configs/config.yaml")

                self.classifier = EnsembleClassifier(
                    model_path=self.config.model_path, config=config.get("model", {})
                )
                await self.classifier.load()

                logger.info("Fallback classifier loaded successfully")
                return True

            except Exception as e2:
                logger.error(f"Fallback classifier also failed: {e2}")
                return False

    async def classify_batch(self, logs: list[str]) -> list[tuple[str, float]]:
        """Classify a batch of logs."""
        # Convert strings to dictionaries for SafeEnsembleClassifier
        log_dicts = [{"message": log} for log in logs]

        if hasattr(self.classifier, "classify_batch"):
            raw_results = await self.classifier.classify_batch(log_dicts)
            # Extract category and confidence from ClassificationResult
            return [(r.prediction.category, r.prediction.confidence) for r in raw_results]
        else:
            # Fallback for simpler classifier
            results = []
            for log in logs:
                pred = await self.classifier.classify(log)
                results.append((pred.category, pred.confidence))
            return results

    def load_test_data(self) -> tuple[list[str], list[str]]:
        """Load labeled test data."""
        import pandas as pd

        data_path = Path(self.config.test_data_path)

        if not data_path.exists():
            logger.warning(f"Test data not found at {data_path}")
            logger.info("Generating synthetic test data for validation...")
            return self._generate_synthetic_test_data()

        logger.info(f"Loading test data from {data_path}")
        df = pd.read_csv(data_path)

        # Validate required columns
        required_cols = ["message", "category"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        # Sample if too large
        if len(df) > self.config.min_samples * 2:
            df = df.sample(n=self.config.min_samples * 2, random_state=42)

        messages = df["message"].tolist()
        labels = df["category"].tolist()

        logger.info(f"Loaded {len(messages)} test samples")
        return messages, labels

    def _generate_synthetic_test_data(self) -> tuple[list[str], list[str]]:
        """Generate synthetic test data for validation."""
        import pandas as pd

        # Load training data instead
        train_path = Path("data/labeled/train.csv")
        if train_path.exists():
            logger.info("Using training data for validation...")
            df = pd.read_csv(train_path)

            # Use last 20% as test data
            test_df = df.iloc[int(len(df) * 0.8) :]

            if len(test_df) >= self.config.min_samples:
                test_df = test_df.sample(n=self.config.min_samples, random_state=42)

            return test_df["message"].tolist(), test_df["category"].tolist()

        # Final fallback: generate synthetic data
        logger.warning("Generating synthetic test data...")

        messages = []
        labels = []

        # Critical patterns
        critical_patterns = [
            "Failed login attempt from 192.168.1.100",
            "SQL injection detected in request",
            "Unauthorized access attempt to admin panel",
            "Malware signature detected in file",
            "Brute force attack detected from suspicious IP",
            "Data exfiltration attempt blocked",
            "Privilege escalation detected",
            "Critical vulnerability exploit attempt",
            "Ransomware activity detected",
            "Unauthorized access to sensitive data",
        ]

        # Suspicious patterns
        suspicious_patterns = [
            "Multiple failed login attempts",
            "Unusual access time detected",
            "Configuration change detected",
            "Port scan detected",
            "Failed 2FA verification",
            "Unusual network traffic pattern",
            "Abnormal data access pattern",
            "Repeated password reset attempts",
        ]

        # Routine patterns
        routine_patterns = [
            "User login successful",
            "File accessed successfully",
            "Database query executed",
            "API request processed",
            "Cache hit recorded",
            "Backup completed successfully",
            "Data synchronization finished",
            "Scheduled task executed",
        ]

        # Noise patterns
        noise_patterns = [
            "Heartbeat check received",
            "Health check passed",
            "Keepalive packet received",
            "Metric collection completed",
            "Debug trace logged",
            "Verbose logging enabled",
            "Ping response received",
            "Liveness probe successful",
        ]

        # Generate samples
        np.random.seed(42)

        for _ in range(self.config.min_samples // 4):
            messages.append(np.random.choice(critical_patterns))
            labels.append("critical")

            messages.append(np.random.choice(suspicious_patterns))
            labels.append("suspicious")

            messages.append(np.random.choice(routine_patterns))
            labels.append("routine")

            messages.append(np.random.choice(noise_patterns))
            labels.append("noise")

        logger.info(f"Generated {len(messages)} synthetic test samples")
        return messages, labels

    async def run_validation(self) -> ValidationResult:
        """Run shadow mode validation."""
        start_time = datetime.now(UTC)

        # Load test data
        messages, true_labels = self.load_test_data()

        if len(messages) < self.config.min_samples:
            logger.warning(f"Insufficient test data: {len(messages)} < {self.config.min_samples}")

        # Run classification
        logger.info("Running classification on test data...")

        predictions = []
        batch_size = self.config.batch_size

        for i in range(0, len(messages), batch_size):
            batch = messages[i : i + batch_size]
            batch_preds = await self.classify_batch(batch)
            predictions.extend([p[0] for p in batch_preds])

            if (i + batch_size) % 1000 == 0:
                logger.info(
                    f"Processed {min(i + batch_size, len(messages))}/{len(messages)} samples"
                )

        # Calculate metrics
        self._calculate_metrics(predictions, true_labels)

        # Calculate execution time
        self.results.execution_time_seconds = (datetime.now(UTC) - start_time).total_seconds()
        self.results.timestamp = start_time.isoformat()

        return self.results

    def _calculate_metrics(self, predictions: list[str], true_labels: list[str]):
        """Calculate validation metrics."""
        self.results.total_samples = len(predictions)

        for pred, true_label in zip(predictions, true_labels, strict=False):
            # Normalize labels
            pred = pred.lower().strip()
            true_label = true_label.lower().strip()

            # Track by category
            if true_label == "critical":
                if pred == "critical":
                    self.results.critical_tp += 1
                    self.results.correct_predictions += 1
                else:
                    self.results.critical_fn += 1
                    self.results.incorrect_predictions += 1
                    self.results.false_negatives.append(
                        {
                            "message": "N/A",  # Would need original message
                            "true_label": true_label,
                            "predicted_label": pred,
                            "severity": "HIGH",
                        }
                    )
            elif true_label == "suspicious":
                if pred == "suspicious":
                    self.results.suspicious_tp += 1
                    self.results.correct_predictions += 1
                else:
                    self.results.suspicious_fn += 1
                    self.results.incorrect_predictions += 1
            elif true_label == "routine":
                if pred == "routine":
                    self.results.routine_tp += 1
                    self.results.correct_predictions += 1
                else:
                    self.results.routine_fn += 1
                    self.results.incorrect_predictions += 1
            elif true_label == "noise":
                if pred == "noise":
                    self.results.noise_tp += 1
                    self.results.correct_predictions += 1
                else:
                    self.results.noise_fn += 1
                    self.results.incorrect_predictions += 1

    def print_report(self):
        """Print validation report."""
        r = self.results

        print("\n" + "=" * 80)
        print("SHADOW MODE VALIDATION REPORT")
        print("=" * 80)
        print(f"\nTimestamp: {r.timestamp}")
        print(f"Execution Time: {r.execution_time_seconds:.2f} seconds")
        print(f"Total Samples: {r.total_samples:,}")
        print(f"Correct: {r.correct_predictions:,} ({r.accuracy * 100:.2f}%)")
        print(f"Incorrect: {r.incorrect_predictions:,} ({(1 - r.accuracy) * 100:.2f}%)")

        print("\n" + "-" * 80)
        print("CRITICAL CATEGORY METRICS (MOST IMPORTANT)")
        print("-" * 80)
        print(
            f"  Critical Recall:     {r.critical_recall * 100:.2f}%  (Target: {self.config.target_recall * 100}%)"
        )
        print(f"  Critical Precision:  {r.critical_precision * 100:.2f}%")
        print(f"  False Negatives:     {r.critical_fn}")
        print(f"  FN per 1000 samples: {r.critical_fn_per_1000:.2f}")

        print("\n" + "-" * 80)
        print("ALL CATEGORIES")
        print("-" * 80)
        print(f"{'Category':<15} {'Precision':<12} {'Recall':<12} {'F1':<12}")
        print("-" * 51)

        categories = ["critical", "suspicious", "routine", "noise"]
        for cat in categories:
            tp = getattr(r, f"{cat}_tp")
            fp = getattr(r, f"{cat}_fp")
            fn = getattr(r, f"{cat}_fn")
            getattr(r, f"{cat}_tn")

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            print(
                f"{cat.capitalize():<15} {precision * 100:>6.2f}%    {recall * 100:>6.2f}%    {f1 * 100:>6.2f}%"
            )

        print("\n" + "-" * 80)
        print("PASS/FAIL STATUS")
        print("-" * 80)

        # Critical recall check
        if r.critical_recall >= self.config.target_recall:
            print(
                f"✅ CRITICAL RECALL: PASS ({r.critical_recall * 100:.2f}% >= {self.config.target_recall * 100}%)"
            )
        else:
            print(
                f"❌ CRITICAL RECALL: FAIL ({r.critical_recall * 100:.2f}% < {self.config.target_recall * 100}%)"
            )

        # False negative check
        max_fn = self.config.max_false_negatives * (r.total_samples / 1000)
        if r.critical_fn <= max_fn:
            print(f"✅ FALSE NEGATIVES: PASS ({r.critical_fn} <= {max_fn:.0f} max)")
        else:
            print(f"❌ FALSE NEGATIVES: FAIL ({r.critical_fn} > {max_fn:.0f} max)")

        print("\n" + "=" * 80)

    def save_report(self):
        """Save validation report to file."""
        import pandas as pd

        # Create output directory
        output_dir = Path(self.config.output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        report_path = output_dir / f"validation_{timestamp}.json"
        csv_path = output_dir / f"false_negatives_{timestamp}.csv"

        # Save JSON report
        report_data = {
            "timestamp": self.results.timestamp,
            "execution_time_seconds": self.results.execution_time_seconds,
            "config": {
                "model_path": self.config.model_path,
                "test_data_path": self.config.test_data_path,
                "target_recall": self.config.target_recall,
                "max_false_negatives_per_1000": self.config.max_false_negatives,
            },
            "metrics": {
                "total_samples": self.results.total_samples,
                "accuracy": self.results.accuracy,
                "critical_recall": self.results.critical_recall,
                "critical_precision": self.results.critical_precision,
                "critical_fn": self.results.critical_fn,
                "critical_fn_per_1000": self.results.critical_fn_per_1000,
            },
            "pass_fail": {
                "critical_recall_pass": self.results.critical_recall >= self.config.target_recall,
                "false_negatives_pass": self.results.critical_fn
                <= self.config.max_false_negatives * (self.results.total_samples / 1000),
            },
        }

        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        logger.info(f"Report saved to {report_path}")

        # Save false negatives to CSV
        if self.results.false_negatives:
            fn_df = pd.DataFrame(self.results.false_negatives)
            fn_df.to_csv(csv_path, index=False)
            logger.info(f"False negatives saved to {csv_path}")

        return report_path

    def is_passed(self) -> bool:
        """Check if validation passed all criteria."""
        r = self.results
        max_fn = self.config.max_false_negatives * (r.total_samples / 1000)

        return r.critical_recall >= self.config.target_recall and r.critical_fn <= max_fn


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Shadow Mode Validation")
    parser.add_argument("--model-path", default="models/v1")
    parser.add_argument("--test-data", default="data/labeled/test.csv")
    parser.add_argument("--output", default="reports/shadow_validation")
    parser.add_argument("--target-recall", type=float, default=0.995)
    parser.add_argument("--min-samples", type=int, default=1000)

    args = parser.parse_args()

    config = ValidationConfig(
        model_path=args.model_path,
        test_data_path=args.test_data,
        output_path=args.output,
        target_recall=args.target_recall,
        min_samples=args.min_samples,
    )

    validator = ShadowModeValidator(config)

    # Initialize classifier
    if not await validator.initialize():
        logger.error("Failed to initialize classifier")
        sys.exit(1)

    # Run validation
    await validator.run_validation()

    # Print report
    validator.print_report()

    # Save report
    validator.save_report()

    # Exit with appropriate code
    if validator.is_passed():
        logger.info("✅ VALIDATION PASSED")
        sys.exit(0)
    else:
        logger.error("❌ VALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
