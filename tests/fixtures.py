"""
Test fixtures for integration testing.

This module provides mock fixtures and sample data for testing
Kafka, QRadar, and S3 integrations without requiring live services.
"""

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

# =============================================================================
# Sample Log Messages
# =============================================================================

SAMPLE_CRITICAL_LOG = {
    "timestamp": "2026-01-26T10:15:30.123Z",
    "source": "firewall-01",
    "message": "CRITICAL: Multiple failed login attempts from 192.168.1.100",
    "severity": "critical",
    "source_ip": "192.168.1.100",
}

SAMPLE_SUSPICIOUS_LOG = {
    "timestamp": "2026-01-26T10:15:31.456Z",
    "source": "ids-sensor",
    "message": "Unusual outbound connection to known C2 server",
    "severity": "high",
    "destination_ip": "10.0.0.55",
}

SAMPLE_ROUTINE_LOG = {
    "timestamp": "2026-01-26T10:15:32.789Z",
    "source": "app-server-01",
    "message": "User admin@example.com logged in successfully",
    "severity": "info",
    "user": "admin@example.com",
}

SAMPLE_NOISE_LOG = {
    "timestamp": "2026-01-26T10:15:33.000Z",
    "source": "load-balancer",
    "message": "Health check passed for backend server",
    "severity": "debug",
}

SAMPLE_COMPLIANCE_LOG = {
    "timestamp": "2026-01-26T10:15:34.111Z",
    "source": "pci-gateway",
    "message": "PCI-DSS: Card transaction processed",
    "severity": "info",
    "compliance_framework": "PCI-DSS",
}


# =============================================================================
# Kafka Mock Fixtures
# =============================================================================


class MockKafkaMessage:
    """Mock Kafka message for testing."""

    def __init__(
        self,
        value: dict[str, Any],
        topic: str = "raw-logs",
        partition: int = 0,
        offset: int = 0,
        key: bytes | None = None,
    ):
        self._value = value
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._key = key
        self._error = None

    def value(self) -> bytes:
        return json.dumps(self._value).encode("utf-8")

    def topic(self) -> str:
        return self._topic

    def partition(self) -> int:
        return self._partition

    def offset(self) -> int:
        return self._offset

    def key(self) -> bytes | None:
        return self._key

    def error(self):
        return self._error


class MockKafkaProducer:
    """Mock Kafka producer for testing."""

    def __init__(self):
        self.messages: list[dict] = []
        self.flush_count = 0

    def produce(
        self,
        topic: str,
        value: bytes,
        key: bytes | None = None,
        callback: Any = None,
    ):
        self.messages.append(
            {
                "topic": topic,
                "value": value,
                "key": key,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        if callback:
            callback(None, MockKafkaMessage(json.loads(value), topic=topic))

    def flush(self, timeout: float = 10.0):
        self.flush_count += 1
        return 0

    def poll(self, timeout: float = 0):
        return 0


class MockKafkaConsumer:
    """Mock Kafka consumer for testing."""

    def __init__(self, messages: list[dict] | None = None):
        self._messages = messages or [
            SAMPLE_CRITICAL_LOG,
            SAMPLE_SUSPICIOUS_LOG,
            SAMPLE_ROUTINE_LOG,
            SAMPLE_NOISE_LOG,
        ]
        self._index = 0
        self._subscribed_topics: list[str] = []

    def subscribe(self, topics: list[str]):
        self._subscribed_topics = topics

    def poll(self, timeout: float = 1.0) -> MockKafkaMessage | None:
        if self._index < len(self._messages):
            msg = MockKafkaMessage(
                self._messages[self._index],
                offset=self._index,
            )
            self._index += 1
            return msg
        return None

    def commit(self, asynchronous: bool = True):
        pass

    def close(self):
        pass


# =============================================================================
# QRadar Mock Fixtures
# =============================================================================


class MockQRadarResponse:
    """Mock QRadar API response."""

    def __init__(
        self,
        status_code: int = 200,
        data: dict | list | None = None,
    ):
        self.status_code = status_code
        self._data = data or {}

    def json(self) -> dict | list:
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class MockQRadarClient:
    """Mock QRadar API client for testing."""

    def __init__(self):
        self.events_submitted: list[dict] = []
        self.offenses_created: list[dict] = []
        self._offense_id_counter = 1000

    async def submit_event(self, event: dict) -> dict:
        """Submit event to mock QRadar."""
        event_id = len(self.events_submitted) + 1
        self.events_submitted.append(
            {
                "event_id": event_id,
                "event": event,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        return {"event_id": event_id, "status": "accepted"}

    async def create_offense(
        self,
        name: str,
        description: str,
        severity: int,
    ) -> dict:
        """Create mock offense."""
        offense = {
            "id": self._offense_id_counter,
            "name": name,
            "description": description,
            "severity": severity,
            "status": "OPEN",
            "created_time": datetime.now(UTC).isoformat(),
        }
        self.offenses_created.append(offense)
        self._offense_id_counter += 1
        return offense

    async def get_offenses(self, status: str = "OPEN") -> list[dict]:
        """Get mock offenses."""
        return [o for o in self.offenses_created if o["status"] == status]

    async def health_check(self) -> dict:
        """Mock health check."""
        return {"status": "healthy", "version": "7.5.0"}


# =============================================================================
# S3 Mock Fixtures
# =============================================================================


class MockS3Client:
    """Mock S3 client for testing."""

    def __init__(self):
        self.buckets: dict[str, list[dict]] = {}
        self.uploaded_objects: list[dict] = []

    def put_object(
        self,
        Bucket: str,
        Key: str,
        Body: bytes,
        ContentType: str = "application/json",
    ) -> dict:
        """Upload object to mock S3."""
        if Bucket not in self.buckets:
            self.buckets[Bucket] = []

        obj = {
            "Key": Key,
            "Body": Body,
            "ContentType": ContentType,
            "LastModified": datetime.now(UTC).isoformat(),
            "Size": len(Body),
        }
        self.buckets[Bucket].append(obj)
        self.uploaded_objects.append({"Bucket": Bucket, **obj})
        return {"ETag": f'"{hash(Body)}"'}

    def get_object(self, Bucket: str, Key: str) -> dict:
        """Get object from mock S3."""
        if Bucket not in self.buckets:
            raise Exception(f"Bucket {Bucket} not found")

        for obj in self.buckets[Bucket]:
            if obj["Key"] == Key:
                # Capture obj in default argument to fix B023
                body = obj["Body"]
                return {
                    "Body": MagicMock(read=lambda b=body: b),
                    "ContentType": obj["ContentType"],
                    "LastModified": obj["LastModified"],
                }
        raise Exception(f"Key {Key} not found")

    def list_objects_v2(self, Bucket: str, Prefix: str = "") -> dict:
        """List objects in mock S3."""
        if Bucket not in self.buckets:
            return {"Contents": []}

        contents = [
            {"Key": obj["Key"], "Size": obj["Size"], "LastModified": obj["LastModified"]}
            for obj in self.buckets[Bucket]
            if obj["Key"].startswith(Prefix)
        ]
        return {"Contents": contents}


# =============================================================================
# Fixture Factory Functions
# =============================================================================


def create_kafka_producer_mock() -> MockKafkaProducer:
    """Create a mock Kafka producer."""
    return MockKafkaProducer()


def create_kafka_consumer_mock(
    messages: list[dict] | None = None,
) -> MockKafkaConsumer:
    """Create a mock Kafka consumer with optional custom messages."""
    return MockKafkaConsumer(messages)


def create_qradar_client_mock() -> MockQRadarClient:
    """Create a mock QRadar client."""
    return MockQRadarClient()


def create_s3_client_mock() -> MockS3Client:
    """Create a mock S3 client."""
    return MockS3Client()


def generate_batch_logs(
    count: int = 100,
    distribution: dict[str, float] | None = None,
) -> list[dict]:
    """
    Generate a batch of sample logs with specified distribution.

    Args:
        count: Number of logs to generate
        distribution: Dict with keys 'critical', 'suspicious', 'routine', 'noise'
                     and float values summing to 1.0

    Returns:
        List of log dictionaries
    """
    import random

    if distribution is None:
        distribution = {
            "critical": 0.05,
            "suspicious": 0.15,
            "routine": 0.30,
            "noise": 0.50,
        }

    templates = {
        "critical": SAMPLE_CRITICAL_LOG,
        "suspicious": SAMPLE_SUSPICIOUS_LOG,
        "routine": SAMPLE_ROUTINE_LOG,
        "noise": SAMPLE_NOISE_LOG,
    }

    logs = []
    for i in range(count):
        category = random.choices(
            list(distribution.keys()),
            weights=list(distribution.values()),
        )[0]
        log = templates[category].copy()
        log["id"] = f"log-{i:06d}"
        log["timestamp"] = datetime.now(UTC).isoformat()
        logs.append(log)

    return logs
