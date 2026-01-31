"""
Statistical Process Control (SPC) Anomaly Detection

Production-ready SPC implementation for real-time log metrics monitoring.
Complements ML-based detection with statistical quality control.

Advantages:
- Zero training required
- O(1) operations - extremely fast
- Highly interpretable (3-sigma rule)
- Self-adapting to normal patterns
- Industry-proven (100+ years in manufacturing)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

import numpy as np
from prometheus_client import Counter, Gauge, Histogram

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Prometheus metrics
spc_anomaly_total = Counter(
    "ai_filter_spc_anomaly_total",
    "Total SPC anomalies detected",
    ["metric_name", "direction"],  # direction: upper/lower
)

spc_z_score = Histogram(
    "ai_filter_spc_z_score",
    "Distribution of z-scores",
    ["metric_name"],
    buckets=[-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
)

spc_control_limit = Gauge(
    "ai_filter_spc_control_limit",
    "Current control limits",
    ["metric_name", "limit_type"],  # limit_type: upper/lower/mean
)


@dataclass
class SPCResult:
    """Result from SPC anomaly check."""

    is_anomaly: bool
    z_score: float
    value: float
    mean: float
    std: float
    upper_limit: float
    lower_limit: float
    direction: str | None  # "upper", "lower", or None
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_anomaly": self.is_anomaly,
            "z_score": round(self.z_score, 3),
            "value": round(self.value, 3),
            "mean": round(self.mean, 3),
            "std": round(self.std, 3),
            "upper_limit": round(self.upper_limit, 3),
            "lower_limit": round(self.lower_limit, 3),
            "direction": self.direction,
            "explanation": self.explanation,
        }


class SPCDetector:
    """
    Statistical Process Control detector using Shewhart control charts.

    Detects anomalies based on statistical deviation from normal behavior.
    Uses the 3-sigma rule (99.7% of normal data within ±3 standard deviations).

    Example:
        >>> detector = SPCDetector("error_rate", window_size=60, sigma=3.0)
        >>> for _ in range(100):
        ...     result = detector.update(current_error_rate)
        ...     if result.is_anomaly:
        ...         logger.warning(f"Anomaly detected: {result.explanation}")
    """

    def __init__(
        self,
        name: str,
        window_size: int = 100,
        sigma_threshold: float = 3.0,
        min_samples: int = 30,
        warmup_samples: int = 10,
    ):
        """
        Initialize SPC detector.

        Args:
            name: Metric name (for logging and metrics)
            window_size: Number of samples in rolling window
            sigma_threshold: Number of standard deviations for anomaly threshold
            min_samples: Minimum samples before detecting anomalies
            warmup_samples: Samples to collect before calculating statistics
        """
        self.name = name
        self.window_size = window_size
        self.sigma_threshold = sigma_threshold
        self.min_samples = min_samples
        self.warmup_samples = warmup_samples

        # Rolling window of values
        self.values = deque(maxlen=window_size)

        # Statistics
        self.mean = 0.0
        self.std = 0.0
        self.is_warmed_up = False

        # Performance tracking
        self.anomaly_count = 0
        self.total_checks = 0

        logger.info(
            f"SPC detector '{name}' initialized (window={window_size}, sigma={sigma_threshold})"
        )

    def update(self, value: float) -> SPCResult:
        """
        Update detector with new value and check for anomaly.

        Args:
            value: New metric value

        Returns:
            SPCResult with anomaly detection results
        """
        self.total_checks += 1

        # Add to window
        self.values.append(value)

        # Check if warmed up
        if len(self.values) < self.warmup_samples:
            return SPCResult(
                is_anomaly=False,
                z_score=0.0,
                value=value,
                mean=0.0,
                std=0.0,
                upper_limit=float("inf"),
                lower_limit=float("-inf"),
                direction=None,
                explanation=f"Warming up ({len(self.values)}/{self.warmup_samples} samples)",
            )

        self.is_warmed_up = True

        # Calculate statistics
        values_array = np.array(self.values)
        self.mean = np.mean(values_array)
        self.std = np.std(values_array)

        # Avoid division by zero
        if self.std == 0:
            self.std = 1e-10

        # Calculate control limits
        upper_limit = self.mean + (self.sigma_threshold * self.std)
        lower_limit = self.mean - (self.sigma_threshold * self.std)

        # Update Prometheus metrics
        spc_control_limit.labels(metric_name=self.name, limit_type="upper").set(upper_limit)
        spc_control_limit.labels(metric_name=self.name, limit_type="lower").set(lower_limit)
        spc_control_limit.labels(metric_name=self.name, limit_type="mean").set(self.mean)

        # Check if we have enough samples for reliable detection
        if len(self.values) < self.min_samples:
            return SPCResult(
                is_anomaly=False,
                z_score=0.0,
                value=value,
                mean=self.mean,
                std=self.std,
                upper_limit=upper_limit,
                lower_limit=lower_limit,
                direction=None,
                explanation=f"Collecting baseline ({len(self.values)}/{self.min_samples} samples)",
            )

        # Calculate z-score
        z_score = (value - self.mean) / self.std
        spc_z_score.labels(metric_name=self.name).observe(z_score)

        # Check for anomaly
        is_anomaly = False
        direction = None
        explanation = f"Normal (z={z_score:.2f}, mean={self.mean:.2f})"

        if value > upper_limit:
            is_anomaly = True
            direction = "upper"
            self.anomaly_count += 1
            explanation = (
                f"Anomaly: Value {value:.3f} exceeds upper limit {upper_limit:.3f} "
                f"(z-score: {z_score:.2f}, {self.sigma_threshold}σ)"
            )
            spc_anomaly_total.labels(metric_name=self.name, direction="upper").inc()

        elif value < lower_limit:
            is_anomaly = True
            direction = "lower"
            self.anomaly_count += 1
            explanation = (
                f"Anomaly: Value {value:.3f} below lower limit {lower_limit:.3f} "
                f"(z-score: {z_score:.2f}, -{self.sigma_threshold}σ)"
            )
            spc_anomaly_total.labels(metric_name=self.name, direction="lower").inc()

        return SPCResult(
            is_anomaly=is_anomaly,
            z_score=z_score,
            value=value,
            mean=self.mean,
            std=self.std,
            upper_limit=upper_limit,
            lower_limit=lower_limit,
            direction=direction,
            explanation=explanation,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        return {
            "name": self.name,
            "window_size": self.window_size,
            "current_samples": len(self.values),
            "sigma_threshold": self.sigma_threshold,
            "is_warmed_up": self.is_warmed_up,
            "mean": round(self.mean, 4) if self.is_warmed_up else None,
            "std": round(self.std, 4) if self.is_warmed_up else None,
            "anomaly_count": self.anomaly_count,
            "total_checks": self.total_checks,
            "anomaly_rate": round(self.anomaly_count / max(self.total_checks, 1), 4),
        }

    def reset(self):
        """Reset detector (clear all history)."""
        self.values.clear()
        self.mean = 0.0
        self.std = 0.0
        self.is_warmed_up = False
        self.anomaly_count = 0
        self.total_checks = 0
        logger.info(f"SPC detector '{self.name}' reset")


class SPCManager:
    """
    Manages multiple SPC detectors for different metrics.

    Example:
        >>> manager = SPCManager()
        >>> manager.add_detector("error_rate", window_size=60, sigma=3.0)
        >>> manager.add_detector("eps", window_size=30, sigma=2.5)
        >>>
        >>> # In your processing loop:
        >>> result = manager.check("error_rate", current_error_rate)
        >>> if result.is_anomaly:
        ...     alert(f"Error rate anomaly: {result.explanation}")
    """

    def __init__(self):
        self.detectors: dict[str, SPCDetector] = {}

    def add_detector(
        self,
        name: str,
        window_size: int = 100,
        sigma_threshold: float = 3.0,
        min_samples: int = 30,
    ) -> SPCDetector:
        """
        Add a new SPC detector.

        Args:
            name: Unique detector name
            window_size: Rolling window size
            sigma_threshold: Sigma threshold for anomaly detection
            min_samples: Minimum samples before detection

        Returns:
            Created SPCDetector instance
        """
        if name in self.detectors:
            logger.warning(f"Detector '{name}' already exists, returning existing")
            return self.detectors[name]

        detector = SPCDetector(
            name=name,
            window_size=window_size,
            sigma_threshold=sigma_threshold,
            min_samples=min_samples,
        )
        self.detectors[name] = detector
        logger.info(f"Added SPC detector: {name}")
        return detector

    def check(self, name: str, value: float) -> SPCResult:
        """
        Check value against named detector.

        Args:
            name: Detector name
            value: Value to check

        Returns:
            SPCResult

        Raises:
            KeyError: If detector doesn't exist
        """
        if name not in self.detectors:
            raise KeyError(
                f"SPC detector '{name}' not found. Available: {list(self.detectors.keys())}"
            )

        return self.detectors[name].update(value)

    def get_detector(self, name: str) -> SPCDetector | None:
        """Get detector by name."""
        return self.detectors.get(name)

    def get_all_stats(self) -> dict[str, Any]:
        """Get stats for all detectors."""
        return {name: detector.get_stats() for name, detector in self.detectors.items()}

    def reset_all(self):
        """Reset all detectors."""
        for detector in self.detectors.values():
            detector.reset()


# Pre-configured detectors for common SIEM metrics
def create_siem_spc_detectors() -> SPCManager:
    """
    Create SPC detectors pre-configured for SIEM monitoring.

    Returns:
        SPCManager with common SIEM metric detectors
    """
    manager = SPCManager()

    # Error rate detector (1-hour window, 3-sigma)
    manager.add_detector(
        name="error_rate",
        window_size=60,  # 60 samples = 1 hour at 1-min intervals
        sigma_threshold=3.0,
        min_samples=30,
    )

    # EPS (Events Per Second) detector (5-min window, 2.5-sigma)
    manager.add_detector(
        name="eps",
        window_size=300,  # 300 samples at 1-sec intervals
        sigma_threshold=2.5,  # Tighter threshold for EPS
        min_samples=60,
    )

    # Failed login rate detector (30-min window, 3-sigma)
    manager.add_detector(
        name="failed_login_rate",
        window_size=30,  # 30 samples = 30 minutes at 1-min intervals
        sigma_threshold=3.0,
        min_samples=15,
    )

    # Processing latency detector (5-min window, 2-sigma)
    manager.add_detector(
        name="processing_latency_ms",
        window_size=300,
        sigma_threshold=2.0,  # Very sensitive to latency spikes
        min_samples=60,
    )

    # Unique IPs per minute (10-min window, 3-sigma)
    manager.add_detector(
        name="unique_ips_per_minute",
        window_size=10,
        sigma_threshold=3.0,
        min_samples=5,
    )

    logger.info("Created SIEM SPC detectors with default configuration")
    return manager


# Example usage
if __name__ == "__main__":
    # Demo
    detector = SPCDetector("demo_metric", window_size=50, sigma_threshold=3.0)

    print("SPC Detector Demo")
    print("=" * 50)

    # Simulate normal data (mean=100, std=10)
    np.random.seed(42)
    normal_data = np.random.normal(100, 10, 60)

    # Add an anomaly
    anomaly_data = np.append(normal_data, 150)  # 5-sigma outlier

    for i, value in enumerate(anomaly_data):
        result = detector.update(value)

        if result.is_anomaly:
            print(f"Sample {i}: ANOMALY DETECTED!")
            print(f"  Value: {result.value:.2f}")
            print(f"  Z-score: {result.z_score:.2f}")
            print(f"  Explanation: {result.explanation}")
        elif i % 10 == 0:
            print(f"Sample {i}: Normal (mean={result.mean:.2f}, z={result.z_score:.2f})")

    print("\nFinal Stats:")
    print(detector.get_stats())
