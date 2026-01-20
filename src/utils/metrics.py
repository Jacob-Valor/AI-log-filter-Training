"""
Prometheus Metrics

Defines application metrics for monitoring and observability.
"""


try:
    from prometheus_client import Counter, Gauge, Histogram, Info
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


class MetricsPlaceholder:
    """Placeholder metrics when prometheus_client is not available."""

    def __getattr__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        return self

    def labels(self, **kwargs):
        return self

    def inc(self, value=1):
        pass

    def dec(self, value=1):
        pass

    def set(self, value):
        pass

    def observe(self, value):
        pass


class ApplicationMetrics:
    """
    Application metrics for monitoring.

    Provides counters, histograms, and gauges for tracking
    application performance and behavior.
    """

    def __init__(self):
        if HAS_PROMETHEUS:
            self._init_prometheus_metrics()
        else:
            self._init_placeholder_metrics()

    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics."""

        # Counters
        self.logs_processed = Counter(
            "log_filter_logs_processed_total",
            "Total number of logs processed",
            ["source"]
        )

        self.logs_classified = Counter(
            "log_filter_logs_classified_total",
            "Total number of logs classified",
            ["category", "model"]
        )

        self.classification_distribution = Counter(
            "log_filter_classification_distribution",
            "Distribution of log classifications",
            ["category"]
        )

        self.kafka_errors = Counter(
            "log_filter_kafka_errors_total",
            "Total Kafka consumer errors"
        )

        self.kafka_messages_sent = Counter(
            "log_filter_kafka_messages_sent_total",
            "Total Kafka messages sent"
        )

        self.kafka_delivery_errors = Counter(
            "log_filter_kafka_delivery_errors_total",
            "Total Kafka delivery errors"
        )

        self.processing_errors = Counter(
            "log_filter_processing_errors_total",
            "Total processing errors"
        )

        self.routing_errors = Counter(
            "log_filter_routing_errors_total",
            "Total routing errors",
            ["destination"]
        )

        # Histograms
        self.classification_latency = Histogram(
            "log_filter_classification_latency_seconds",
            "Time to classify a log message",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
        )

        self.batch_processing_time = Histogram(
            "log_filter_batch_processing_seconds",
            "Time to process a batch of logs",
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
        )

        self.classification_confidence = Histogram(
            "log_filter_classification_confidence",
            "Confidence scores of classifications",
            buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
        )

        # Gauges
        self.active_connections = Gauge(
            "log_filter_active_connections",
            "Number of active connections",
            ["type"]
        )

        self.queue_size = Gauge(
            "log_filter_queue_size",
            "Current queue size",
            ["queue_name"]
        )

        self.model_loaded = Gauge(
            "log_filter_model_loaded",
            "Whether models are loaded",
            ["model_name"]
        )

        # Info
        self.app_info = Info(
            "log_filter_app",
            "Application information"
        )

    def _init_placeholder_metrics(self):
        """Initialize placeholder metrics when Prometheus is not available."""
        placeholder = MetricsPlaceholder()

        self.logs_processed = placeholder
        self.logs_classified = placeholder
        self.classification_distribution = placeholder
        self.kafka_errors = placeholder
        self.kafka_messages_sent = placeholder
        self.kafka_delivery_errors = placeholder
        self.processing_errors = placeholder
        self.routing_errors = placeholder
        self.classification_latency = placeholder
        self.batch_processing_time = placeholder
        self.classification_confidence = placeholder
        self.active_connections = placeholder
        self.queue_size = placeholder
        self.model_loaded = placeholder
        self.app_info = placeholder

    def set_app_info(self, version: str, environment: str):
        """Set application info metric."""
        if HAS_PROMETHEUS:
            self.app_info.info({
                "version": version,
                "environment": environment
            })


# Global metrics instance
METRICS = ApplicationMetrics()


def get_metrics() -> ApplicationMetrics:
    """Get the global metrics instance."""
    return METRICS
