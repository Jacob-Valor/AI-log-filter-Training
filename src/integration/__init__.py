"""
Integration Module

Provides integrations with external systems:
- Kafka: Log ingestion and output routing
- QRadar: SIEM event forwarding
- Common: Shared utilities for all integrations
"""

from src.integration.common import (
    BaseIntegration,
    ConnectionState,
    HealthStatus,
    IntegrationConfig,
    retry_with_backoff,
)
from src.integration.kafka import (
    KafkaConfig,
    KafkaConsumerIntegration,
    KafkaProducerIntegration,
    create_kafka_topics,
)
from src.integration.qradar import (
    LEEFEvent,
    QRadarConfig,
    QRadarIntegration,
    create_qradar_event,
)

__all__ = [
    # Common
    "BaseIntegration",
    "IntegrationConfig",
    "ConnectionState",
    "HealthStatus",
    "retry_with_backoff",
    # Kafka
    "KafkaConfig",
    "KafkaProducerIntegration",
    "KafkaConsumerIntegration",
    "create_kafka_topics",
    # QRadar
    "QRadarConfig",
    "QRadarIntegration",
    "LEEFEvent",
    "create_qradar_event",
]
