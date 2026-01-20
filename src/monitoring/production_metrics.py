"""
Production Metrics

Comprehensive metrics for production monitoring of the AI log filter.
Includes EPS tracking, false negative detection, model drift, and SLA metrics.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, Optional

from prometheus_client import Counter, Gauge, Histogram, Info
from src.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# THROUGHPUT METRICS
# =============================================================================

# Events Per Second tracking
EPS_INGESTED = Gauge(
    'ai_filter_eps_ingested',
    'Events per second ingested from all sources',
    ['source_type']
)

EPS_TO_QRADAR = Gauge(
    'ai_filter_eps_to_qradar',
    'Events per second forwarded to QRadar',
    ['category']
)

EPS_FILTERED = Gauge(
    'ai_filter_eps_filtered',
    'Events per second filtered (not sent to QRadar)',
    ['category']
)

EPS_REDUCTION_RATIO = Gauge(
    'ai_filter_eps_reduction_ratio',
    'Ratio of logs filtered vs total (0-1)'
)

LOGS_PROCESSED_TOTAL = Counter(
    'ai_filter_logs_processed_total',
    'Total number of logs processed',
    ['source', 'category', 'model']
)

LOGS_FILTERED_TOTAL = Counter(
    'ai_filter_logs_filtered_total',
    'Total number of logs filtered from QRadar',
    ['category', 'reason']
)

# =============================================================================
# LATENCY METRICS
# =============================================================================

CLASSIFICATION_LATENCY = Histogram(
    'ai_filter_classification_latency_seconds',
    'Time to classify a batch of logs',
    ['model', 'batch_size_bucket'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5]
)

END_TO_END_LATENCY = Histogram(
    'ai_filter_end_to_end_latency_seconds',
    'Total time from log ingestion to routing decision',
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

ENRICHMENT_LATENCY = Histogram(
    'ai_filter_enrichment_latency_seconds',
    'Time spent on log enrichment',
    ['enrichment_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
)

# =============================================================================
# CLASSIFICATION QUALITY METRICS
# =============================================================================

CLASSIFICATION_CONFIDENCE = Histogram(
    'ai_filter_classification_confidence',
    'Distribution of classification confidence scores',
    ['category', 'model'],
    buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99]
)

# Critical for detection quality - tracks when we miss threats
FALSE_NEGATIVES_TOTAL = Counter(
    'ai_filter_false_negatives_total',
    'Logs filtered that later triggered QRadar offenses',
    ['original_category', 'offense_type', 'severity']
)

FALSE_POSITIVES_TOTAL = Counter(
    'ai_filter_false_positives_total',
    'Logs sent to QRadar that analysts marked as noise',
    ['predicted_category', 'source']
)

# Recall tracking for critical events
CRITICAL_RECALL = Gauge(
    'ai_filter_critical_recall',
    'Proportion of true critical events correctly identified (0-1)'
)

CRITICAL_PRECISION = Gauge(
    'ai_filter_critical_precision',
    'Proportion of predicted critical events that are true positives (0-1)'
)

# =============================================================================
# MODEL HEALTH METRICS
# =============================================================================

MODEL_PREDICTION_COUNT = Counter(
    'ai_filter_model_predictions_total',
    'Number of predictions by each model',
    ['model', 'category']
)

MODEL_LOAD_TIME = Gauge(
    'ai_filter_model_load_time_seconds',
    'Time taken to load the model',
    ['model']
)

MODEL_LAST_TRAINED = Gauge(
    'ai_filter_model_last_trained_timestamp',
    'Unix timestamp of when model was last trained',
    ['model']
)

MODEL_DRIFT_SCORE = Gauge(
    'ai_filter_model_drift_score',
    'Statistical drift from training distribution (0-1)',
    ['model', 'drift_type']
)

MODEL_VERSION = Info(
    'ai_filter_model_version',
    'Current model version information'
)

# =============================================================================
# CIRCUIT BREAKER METRICS
# =============================================================================

CIRCUIT_BREAKER_STATE = Gauge(
    'ai_filter_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    ['circuit_name']
)

CIRCUIT_BREAKER_FAILURES = Counter(
    'ai_filter_circuit_breaker_failures_total',
    'Total failures recorded by circuit breaker',
    ['circuit_name']
)

CIRCUIT_BREAKER_OPENS = Counter(
    'ai_filter_circuit_breaker_opens_total',
    'Number of times circuit breaker has opened',
    ['circuit_name']
)

FAIL_OPEN_EVENTS = Counter(
    'ai_filter_fail_open_events_total',
    'Number of logs forwarded due to fail-open mode',
    ['reason']
)

# =============================================================================
# COMPLIANCE METRICS
# =============================================================================

COMPLIANCE_BYPASSES = Counter(
    'ai_filter_compliance_bypasses_total',
    'Logs that bypassed filtering due to compliance rules',
    ['framework', 'rule']
)

COMPLIANCE_CHECK_LATENCY = Histogram(
    'ai_filter_compliance_check_latency_seconds',
    'Time to check compliance rules',
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01]
)

# =============================================================================
# ROUTING METRICS
# =============================================================================

ROUTING_DECISIONS = Counter(
    'ai_filter_routing_decisions_total',
    'Routing decisions by destination',
    ['category', 'destination']
)

ROUTING_QUEUE_SIZE = Gauge(
    'ai_filter_routing_queue_size',
    'Current size of routing queues',
    ['category']
)

ROUTING_ERRORS = Counter(
    'ai_filter_routing_errors_total',
    'Errors during log routing',
    ['destination', 'error_type']
)

# =============================================================================
# SYSTEM HEALTH METRICS
# =============================================================================

KAFKA_CONSUMER_LAG = Gauge(
    'ai_filter_kafka_consumer_lag',
    'Number of messages behind in Kafka consumption',
    ['topic', 'partition']
)

KAFKA_CONSUMER_OFFSET = Gauge(
    'ai_filter_kafka_consumer_offset',
    'Current consumer offset',
    ['topic', 'partition']
)

MEMORY_USAGE_BYTES = Gauge(
    'ai_filter_memory_usage_bytes',
    'Current memory usage in bytes',
    ['type']
)

BATCH_SIZE_ACTUAL = Histogram(
    'ai_filter_batch_size_actual',
    'Actual batch sizes processed',
    buckets=[1, 10, 50, 100, 256, 500, 1000, 2000]
)


# =============================================================================
# METRICS COLLECTOR CLASS
# =============================================================================

@dataclass
class EPSWindow:
    """Sliding window for EPS calculation."""
    window_size_seconds: int = 60
    samples: deque = field(default_factory=lambda: deque(maxlen=60))
    lock: Lock = field(default_factory=Lock)

    def add_sample(self, count: int, timestamp: Optional[float] = None):
        """Add a sample to the window."""
        ts = timestamp or time.time()
        with self.lock:
            self.samples.append((ts, count))

    def get_eps(self) -> float:
        """Calculate events per second from window."""
        with self.lock:
            if len(self.samples) < 2:
                return 0.0

            now = time.time()
            cutoff = now - self.window_size_seconds

            # Filter to window
            valid = [(ts, count) for ts, count in self.samples if ts >= cutoff]

            if len(valid) < 2:
                return 0.0

            total_events = sum(count for _, count in valid)
            time_span = valid[-1][0] - valid[0][0]

            if time_span <= 0:
                return 0.0

            return total_events / time_span


class ProductionMetricsCollector:
    """
    Centralized metrics collector for production monitoring.

    Provides high-level methods for recording metrics and
    calculating derived values like EPS and recall rates.
    """

    def __init__(self):
        self.eps_ingested = EPSWindow()
        self.eps_to_qradar = EPSWindow()
        self.eps_filtered = EPSWindow()

        # Tracking for recall calculation
        self.critical_true_positives = 0
        self.critical_false_negatives = 0
        self.critical_false_positives = 0

        self._lock = Lock()

        logger.info("Production metrics collector initialized")

    def record_log_processed(
        self,
        source: str,
        category: str,
        model: str,
        confidence: float,
        latency_seconds: float,
        forwarded_to_qradar: bool
    ):
        """Record a processed log with all relevant metrics."""
        # Throughput
        LOGS_PROCESSED_TOTAL.labels(
            source=source,
            category=category,
            model=model
        ).inc()

        # EPS tracking
        self.eps_ingested.add_sample(1)

        if forwarded_to_qradar:
            self.eps_to_qradar.add_sample(1)
            EPS_TO_QRADAR.labels(category=category).set(
                self.eps_to_qradar.get_eps()
            )
        else:
            self.eps_filtered.add_sample(1)
            LOGS_FILTERED_TOTAL.labels(
                category=category,
                reason="classification"
            ).inc()

        # Update EPS gauges
        EPS_INGESTED.labels(source_type=source).set(self.eps_ingested.get_eps())

        # Confidence distribution
        CLASSIFICATION_CONFIDENCE.labels(
            category=category,
            model=model
        ).observe(confidence)

        # Latency
        END_TO_END_LATENCY.observe(latency_seconds)

        # Model predictions
        MODEL_PREDICTION_COUNT.labels(
            model=model,
            category=category
        ).inc()

        # Update reduction ratio
        total_eps = self.eps_ingested.get_eps()
        if total_eps > 0:
            filtered_eps = self.eps_filtered.get_eps()
            EPS_REDUCTION_RATIO.set(filtered_eps / total_eps)

    def record_batch_processed(
        self,
        batch_size: int,
        model: str,
        latency_seconds: float
    ):
        """Record batch processing metrics."""
        # Determine batch size bucket for labeling
        if batch_size < 50:
            bucket = "small"
        elif batch_size < 200:
            bucket = "medium"
        else:
            bucket = "large"

        CLASSIFICATION_LATENCY.labels(
            model=model,
            batch_size_bucket=bucket
        ).observe(latency_seconds)

        BATCH_SIZE_ACTUAL.observe(batch_size)

    def record_false_negative(
        self,
        original_category: str,
        offense_type: str,
        severity: str
    ):
        """Record a false negative (missed detection)."""
        FALSE_NEGATIVES_TOTAL.labels(
            original_category=original_category,
            offense_type=offense_type,
            severity=severity
        ).inc()

        with self._lock:
            if original_category == "critical":
                self.critical_false_negatives += 1
                self._update_recall()

        logger.warning(
            f"False negative recorded: {offense_type}",
            extra={
                "original_category": original_category,
                "offense_type": offense_type,
                "severity": severity
            }
        )

    def record_true_positive(self, category: str):
        """Record a true positive detection."""
        with self._lock:
            if category == "critical":
                self.critical_true_positives += 1
                self._update_recall()

    def record_false_positive(self, predicted_category: str, source: str):
        """Record a false positive (noise sent to QRadar)."""
        FALSE_POSITIVES_TOTAL.labels(
            predicted_category=predicted_category,
            source=source
        ).inc()

        with self._lock:
            if predicted_category == "critical":
                self.critical_false_positives += 1
                self._update_precision()

    def _update_recall(self):
        """Update critical recall metric."""
        total = self.critical_true_positives + self.critical_false_negatives
        if total > 0:
            recall = self.critical_true_positives / total
            CRITICAL_RECALL.set(recall)

    def _update_precision(self):
        """Update critical precision metric."""
        total = self.critical_true_positives + self.critical_false_positives
        if total > 0:
            precision = self.critical_true_positives / total
            CRITICAL_PRECISION.set(precision)

    def record_circuit_breaker_state(
        self,
        circuit_name: str,
        state: str,
        failure_count: int = 0
    ):
        """Record circuit breaker state change."""
        state_map = {"closed": 0, "open": 1, "half_open": 2}
        CIRCUIT_BREAKER_STATE.labels(
            circuit_name=circuit_name
        ).set(state_map.get(state, 0))

        if state == "open":
            CIRCUIT_BREAKER_OPENS.labels(circuit_name=circuit_name).inc()

    def record_fail_open_event(self, reason: str, count: int = 1):
        """Record logs forwarded due to fail-open mode."""
        FAIL_OPEN_EVENTS.labels(reason=reason).inc(count)

    def record_compliance_bypass(self, framework: str, rule: str):
        """Record a compliance bypass event."""
        COMPLIANCE_BYPASSES.labels(framework=framework, rule=rule).inc()

    def record_model_drift(
        self,
        model: str,
        drift_type: str,
        score: float
    ):
        """Record model drift detection."""
        MODEL_DRIFT_SCORE.labels(
            model=model,
            drift_type=drift_type
        ).set(score)

        if score > 0.1:  # Threshold for warning
            logger.warning(
                "Model drift detected",
                extra={
                    "model": model,
                    "drift_type": drift_type,
                    "score": score
                }
            )

    def record_routing_decision(
        self,
        category: str,
        destination: str
    ):
        """Record a routing decision."""
        ROUTING_DECISIONS.labels(
            category=category,
            destination=destination
        ).inc()

    def record_routing_error(
        self,
        destination: str,
        error_type: str
    ):
        """Record a routing error."""
        ROUTING_ERRORS.labels(
            destination=destination,
            error_type=error_type
        ).inc()

    def update_kafka_lag(self, topic: str, partition: int, lag: int):
        """Update Kafka consumer lag metric."""
        KAFKA_CONSUMER_LAG.labels(
            topic=topic,
            partition=str(partition)
        ).set(lag)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics."""
        return {
            "eps": {
                "ingested": round(self.eps_ingested.get_eps(), 2),
                "to_qradar": round(self.eps_to_qradar.get_eps(), 2),
                "filtered": round(self.eps_filtered.get_eps(), 2),
            },
            "detection_quality": {
                "critical_true_positives": self.critical_true_positives,
                "critical_false_negatives": self.critical_false_negatives,
                "critical_false_positives": self.critical_false_positives,
            },
        }


# Global metrics collector instance
METRICS = ProductionMetricsCollector()


def get_metrics_collector() -> ProductionMetricsCollector:
    """Get the global metrics collector."""
    return METRICS
