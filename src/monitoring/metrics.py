"""
Metrics Server

Exposes Prometheus metrics for monitoring.
"""

import asyncio

from src.utils.logging import get_logger

logger = get_logger(__name__)


class MetricsServer:
    """
    HTTP server for exposing Prometheus metrics.
    """

    def __init__(self, port: int = 9090, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self._server = None
        self._app = None

    async def start(self):
        """Start the metrics server."""
        try:
            from prometheus_client import start_http_server

            # Start prometheus HTTP server in a thread
            start_http_server(self.port, addr=self.host)
            logger.info(f"Metrics server started on {self.host}:{self.port}")

        except ImportError:
            logger.warning("prometheus_client not available, metrics server disabled")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    async def stop(self):
        """Stop the metrics server."""
        logger.info("Metrics server stopped")


class HealthChecker:
    """
    Health check service for monitoring application health.
    """

    def __init__(self):
        self.checks = {}

    def register_check(self, name: str, check_func):
        """Register a health check function."""
        self.checks[name] = check_func

    async def check_health(self) -> dict:
        """Run all health checks and return status."""
        results = {"status": "healthy", "checks": {}}

        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()

                results["checks"][name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result,
                }

                if not result:
                    results["status"] = "unhealthy"

            except Exception as e:
                results["checks"][name] = {"status": "unhealthy", "error": str(e)}
                results["status"] = "unhealthy"

        return results

    def is_healthy(self) -> bool:
        """Quick health check."""
        return all(
            check() if not asyncio.iscoroutinefunction(check) else True
            for check in self.checks.values()
        )


# Global health checker instance
health_checker = HealthChecker()
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
            "log_filter_logs_processed_total", "Total number of logs processed", ["source"]
        )

        self.logs_classified = Counter(
            "log_filter_logs_classified_total",
            "Total number of logs classified",
            ["category", "model"],
        )

        self.classification_distribution = Counter(
            "log_filter_classification_distribution",
            "Distribution of log classifications",
            ["category"],
        )

        self.kafka_errors = Counter("log_filter_kafka_errors_total", "Total Kafka consumer errors")

        self.kafka_messages_sent = Counter(
            "log_filter_kafka_messages_sent_total", "Total Kafka messages sent"
        )

        self.kafka_delivery_errors = Counter(
            "log_filter_kafka_delivery_errors_total", "Total Kafka delivery errors"
        )

        self.processing_errors = Counter(
            "log_filter_processing_errors_total", "Total processing errors"
        )

        self.routing_errors = Counter(
            "log_filter_routing_errors_total", "Total routing errors", ["destination"]
        )

        # Histograms
        self.classification_latency = Histogram(
            "log_filter_classification_latency_seconds",
            "Time to classify a log message",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        self.batch_processing_time = Histogram(
            "log_filter_batch_processing_seconds",
            "Time to process a batch of logs",
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

        self.classification_confidence = Histogram(
            "log_filter_classification_confidence",
            "Confidence scores of classifications",
            buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99],
        )

        # Gauges
        self.active_connections = Gauge(
            "log_filter_active_connections", "Number of active connections", ["type"]
        )

        self.queue_size = Gauge("log_filter_queue_size", "Current queue size", ["queue_name"])

        self.model_loaded = Gauge(
            "log_filter_model_loaded", "Whether models are loaded", ["model_name"]
        )

        # Info
        self.app_info = Info("log_filter_app", "Application information")

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
            self.app_info.info({"version": version, "environment": environment})


# Global metrics instance
METRICS = ApplicationMetrics()


def get_metrics() -> ApplicationMetrics:
    """Get the global metrics instance."""
    return METRICS
