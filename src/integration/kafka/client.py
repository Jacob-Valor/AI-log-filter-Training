"""
Kafka Integration Module

Provides Kafka producer and consumer implementations for log ingestion
and output routing.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from confluent_kafka import Consumer, KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from src.integration.common.base import BaseIntegration, HealthStatus, IntegrationConfig

logger = logging.getLogger(__name__)


@dataclass
class KafkaConfig(IntegrationConfig):
    """Kafka-specific configuration."""

    bootstrap_servers: str = "localhost:9092"
    group_id: str = "ai-log-filter"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 10000
    max_poll_records: int = 500
    topics: dict[str, str] = field(default_factory=dict)

    # Producer config
    acks: str = "all"
    retries: int = 5
    batch_size: int = 16384
    linger_ms: int = 5
    enable_idempotence: bool = True


@dataclass
class LogMessage:
    """Log message structure for Kafka."""

    id: str
    timestamp: str
    source: str
    raw_message: str
    parsed_fields: dict[str, Any] = field(default_factory=dict)
    category: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class KafkaProducerIntegration(BaseIntegration):
    """
    Kafka producer for sending classified logs to downstream systems.
    """

    def __init__(self, config: KafkaConfig):
        super().__init__("kafka-producer", config)
        self.config = config
        self._producer: Producer | None = None
        self._pending_messages: dict[str, asyncio.Future] = {}

    def _create_producer(self) -> Producer:
        """Create Kafka producer instance."""
        conf = {
            "bootstrap.servers": self.config.bootstrap_servers,
            "acks": self.config.acks,
            "retries": self.config.retries,
            "batch.size": self.config.batch_size,
            "linger.ms": self.config.linger_ms,
            "enable.idempotence": self.config.enable_idempotence,
            "compression.type": "gzip",
        }
        return Producer(conf)

    async def connect(self) -> bool:
        """Establish Kafka producer connection."""
        try:
            self._producer = self._create_producer()
            # Test connection by getting metadata
            metadata = self._producer.list_topics(timeout=10)
            logger.info(
                f"Kafka producer connected to {self.config.bootstrap_servers}",
                extra={"topics": list(metadata.topics.keys())},
            )
            return True
        except KafkaException as e:
            logger.error(f"Kafka producer connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Close Kafka producer."""
        if self._producer:
            # Flush pending messages
            self._producer.flush(timeout=30)
            logger.info("Kafka producer disconnected")

    def _delivery_callback(self, err: KafkaError | None, msg) -> None:
        """Callback for message delivery confirmation."""
        message_id = msg.headers().get("message_id", b"unknown") if msg.headers() else b"unknown"
        message_id = message_id.decode() if isinstance(message_id, bytes) else str(message_id)

        if err:
            logger.error(f"Message delivery failed: {err}")
            if message_id in self._pending_messages:
                self._pending_messages[message_id].set_exception(KafkaException(err))
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")
            if message_id in self._pending_messages:
                self._pending_messages[message_id].set_result(msg)

    async def send_message(
        self,
        topic: str,
        message: LogMessage | dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Send a message to Kafka."""
        if not self._producer:
            raise RuntimeError("Producer not connected")

        # Convert message to dict
        if isinstance(message, LogMessage):
            message_data = {
                "id": message.id,
                "timestamp": message.timestamp,
                "source": message.source,
                "raw_message": message.raw_message,
                "parsed_fields": message.parsed_fields,
                "category": message.category,
                "confidence": message.confidence,
                "metadata": message.metadata,
            }
        else:
            message_data = message

        # Create delivery future
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        message_id = message_data.get("id", str(datetime.utcnow().timestamp()))
        self._pending_messages[message_id] = future

        # Prepare headers
        kafka_headers = []
        if headers:
            kafka_headers.extend([(k, v.encode()) for k, v in headers.items()])
        kafka_headers.append(("message_id", message_id.encode()))
        kafka_headers.append(("timestamp", datetime.utcnow().isoformat().encode()))

        try:
            self._producer.produce(
                topic=topic,
                key=key.encode() if key else None,
                value=json.dumps(message_data).encode(),
                headers=kafka_headers,
                callback=self._delivery_callback,
            )

            # Trigger delivery reports
            self._producer.poll(0)

            # Wait for delivery
            await asyncio.wait_for(future, timeout=30.0)
            return True

        except TimeoutError:
            logger.error(f"Message delivery timeout: {message_id}")
            return False
        except Exception as e:
            logger.error(f"Message send error: {e}")
            return False
        finally:
            self._pending_messages.pop(message_id, None)

    async def send_batch(
        self, topic: str, messages: list[LogMessage | dict[str, Any]], key_field: str | None = None
    ) -> dict[str, int]:
        """Send multiple messages to Kafka."""
        results = {"success": 0, "failed": 0}

        for message in messages:
            key = None
            if isinstance(message, dict) and key_field:
                key = str(message.get(key_field, ""))

            success = await self.send_message(topic, message, key=key)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1

        return results

    async def health_check(self) -> HealthStatus:
        """Check Kafka producer health."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Try to list topics
            metadata = self._producer.list_topics(timeout=10)
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            return HealthStatus(
                healthy=True,
                latency_ms=latency_ms,
                message=f"Connected to {self.config.bootstrap_servers}",
                details={
                    "available_topics": len(metadata.topics),
                    "brokers": [b.host for b in metadata.brokers.values()],
                },
            )
        except KafkaException as e:
            return HealthStatus(
                healthy=False,
                latency_ms=0,
                message=f"Kafka health check failed: {e}",
                details={"error": str(e)},
            )

    async def is_healthy(self) -> bool:
        """Quick health check."""
        try:
            self._producer.list_topics(timeout=5)
            return True
        except KafkaException:
            return False


class KafkaConsumerIntegration(BaseIntegration):
    """
    Kafka consumer for ingesting logs from upstream systems.
    """

    def __init__(self, config: KafkaConfig):
        super().__init__("kafka-consumer", config)
        self.config = config
        self._consumer: Consumer | None = None
        self._running = False
        self._message_handlers: list[Callable] = []

    def _create_consumer(self) -> Consumer:
        """Create Kafka consumer instance."""
        conf = {
            "bootstrap.servers": self.config.bootstrap_servers,
            "group.id": self.config.group_id,
            "auto.offset.reset": self.config.auto_offset_reset,
            "enable.auto.commit": self.config.enable_auto_commit,
            "session.timeout.ms": self.config.session_timeout_ms,
            "heartbeat.interval.ms": self.config.heartbeat_interval_ms,
            "max.poll.records": self.config.max_poll_records,
        }
        return Consumer(conf)

    async def connect(self) -> bool:
        """Establish Kafka consumer connection."""
        try:
            self._consumer = self._create_consumer()

            # Subscribe to topics
            topics = list(self.config.topics.values()) if self.config.topics else []
            if topics:
                self._consumer.subscribe(topics)

            logger.info(
                f"Kafka consumer connected to {self.config.bootstrap_servers}",
                extra={"topics": topics, "group_id": self.config.group_id},
            )
            return True
        except KafkaException as e:
            logger.error(f"Kafka consumer connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Close Kafka consumer."""
        self._running = False
        if self._consumer:
            self._consumer.close()
            logger.info("Kafka consumer disconnected")

    def add_message_handler(self, handler: Callable[[LogMessage], None]) -> None:
        """Add message handler."""
        self._message_handlers.append(handler)

    async def consume_loop(self) -> None:
        """Main consumption loop."""
        self._running = True

        while self._running:
            try:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        raise KafkaException(msg.error())

                # Parse message
                try:
                    value = json.loads(msg.value().decode())
                    log_message = LogMessage(
                        id=value.get(
                            "id",
                            msg.headers().get("message_id", "unknown")
                            if msg.headers()
                            else "unknown",
                        ),
                        timestamp=value.get(
                            "timestamp",
                            msg.timestamp()[1].isoformat()
                            if msg.timestamp()[1]
                            else datetime.utcnow().isoformat(),
                        ),
                        source=value.get("source", msg.topic()),
                        raw_message=value.get("raw_message", msg.value().decode()),
                        parsed_fields=value.get("parsed_fields", {}),
                    )

                    # Call handlers
                    for handler in self._message_handlers:
                        try:
                            handler(log_message)
                        except Exception as e:
                            logger.error(f"Handler error: {e}")

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in message: {msg.value()[:100]}")

            except KafkaException as e:
                logger.error(f"Consume loop error: {e}")
                await asyncio.sleep(1)

    async def health_check(self) -> HealthStatus:
        """Check Kafka consumer health."""
        start_time = asyncio.get_event_loop().time()

        try:
            self._consumer.list_topics(timeout=10)
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            return HealthStatus(
                healthy=True,
                latency_ms=latency_ms,
                message=f"Consumer subscribed to {len(self._consumer.subscription())} topics",
                details={
                    "subscribed_topics": list(self._consumer.subscription()),
                    "assigned_partitions": [
                        {"topic": p.topic, "partition": p.partition}
                        for p in self._consumer.assignment()
                    ]
                    if self._consumer.assignment()
                    else [],
                },
            )
        except KafkaException as e:
            return HealthStatus(
                healthy=False,
                latency_ms=0,
                message=f"Kafka health check failed: {e}",
                details={"error": str(e)},
            )

    async def is_healthy(self) -> bool:
        """Quick health check."""
        try:
            self._consumer.list_topics(timeout=5)
            return True
        except KafkaException:
            return False

    def get_assignment(self) -> list[dict[str, int]]:
        """Get current topic assignments."""
        if not self._consumer:
            return []
        return [{"topic": p.topic, "partition": p.partition} for p in self._consumer.assignment()]


async def create_kafka_topics(
    bootstrap_servers: str, topics: list[str], num_partitions: int = 3, replication_factor: int = 1
) -> bool:
    """Create Kafka topics if they don't exist."""
    admin = AdminClient({"bootstrap.servers": bootstrap_servers})

    try:
        # Check existing topics
        metadata = admin.list_topics(timeout=10)
        existing_topics = {t.topic for t in metadata.topics.values()}

        # Create new topics
        new_topics = [
            NewTopic(
                topic=topic, num_partitions=num_partitions, replication_factor=replication_factor
            )
            for topic in topics
            if topic not in existing_topics
        ]

        if new_topics:
            futures = admin.create_topics(new_topics)
            for topic, future in futures.items():
                try:
                    future.result(timeout=10)
                    logger.info(f"Created topic: {topic}")
                except Exception as e:
                    logger.warning(f"Failed to create topic {topic}: {e}")

        return True

    except KafkaException as e:
        logger.error(f"Failed to create topics: {e}")
        return False
