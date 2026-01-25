"""
Kafka Consumer for Log Ingestion

Handles consuming raw logs from Kafka topics and processing them
through the classification pipeline.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from confluent_kafka import Consumer, KafkaError

from src.models.base import BaseClassifier
from src.preprocessing.log_parser import LogParser
from src.routing.router import LogRouter
from src.utils.logging import get_logger
from src.utils.metrics import METRICS

logger = get_logger(__name__)


@dataclass
class RawLog:
    """Represents a raw log message from Kafka."""

    raw_message: str
    topic: str
    partition: int
    offset: int
    timestamp: datetime
    key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_message": self.raw_message,
            "topic": self.topic,
            "partition": self.partition,
            "offset": self.offset,
            "timestamp": self.timestamp.isoformat(),
            "key": self.key,
            "headers": self.headers
        }


@dataclass
class ClassifiedLog:
    """Represents a classified log with prediction."""

    raw_log: RawLog
    parsed_data: dict[str, Any]
    category: str
    confidence: float
    model_used: str
    explanation: dict[str, Any] | None = None
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_log": self.raw_log.to_dict(),
            "parsed_data": self.parsed_data,
            "category": self.category,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "explanation": self.explanation,
            "processing_time_ms": self.processing_time_ms
        }


class LogConsumer:
    """
    Kafka consumer for ingesting raw logs.

    Handles:
    - Consuming messages from Kafka
    - Parsing logs into structured format
    - Batch processing for efficiency
    - Error handling and retries
    """

    def __init__(
        self,
        config: dict[str, Any],
        classifier: BaseClassifier,
        router: LogRouter,
        batch_size: int = 256,
        max_wait_ms: int = 100
    ):
        self.config = config
        self.classifier = classifier
        self.router = router
        self.batch_size = batch_size
        self.max_wait_ms = max_wait_ms

        self.consumer: Consumer | None = None
        self.parser = LogParser()
        self.running = False
        self._processing_task: asyncio.Task | None = None

        # Kafka configuration
        self.kafka_config = {
            "bootstrap.servers": config["bootstrap_servers"],
            "group.id": config["consumer"]["group_id"],
            "auto.offset.reset": config["consumer"]["auto_offset_reset"],
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": config["consumer"].get("session_timeout_ms", 30000),
            "heartbeat.interval.ms": config["consumer"].get("heartbeat_interval_ms", 10000),
        }

        self.input_topic = config["topics"]["input"]

    def _create_consumer(self) -> Consumer:
        """Create Kafka consumer instance."""
        return Consumer(self.kafka_config)

    async def start(self):
        """Start consuming messages."""
        logger.info(f"Starting Kafka consumer for topic: {self.input_topic}")

        self.consumer = self._create_consumer()
        self.consumer.subscribe([self.input_topic])
        self.running = True

        # Start processing in background
        self._processing_task = asyncio.create_task(self._process_loop())

    async def stop(self):
        """Stop consuming messages."""
        logger.info("Stopping Kafka consumer...")
        self.running = False

        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        if self.consumer:
            self.consumer.close()

        logger.info("Kafka consumer stopped")

    async def _process_loop(self):
        """Main processing loop."""
        batch: list[RawLog] = []
        last_process_time = time.time()

        while self.running:
            try:
                # Poll for messages
                msg = self.consumer.poll(timeout=0.1)

                if msg is None:
                    # No message, check if we should process batch
                    if batch and (time.time() - last_process_time) * 1000 > self.max_wait_ms:
                        await self._process_batch(batch)
                        batch = []
                        last_process_time = time.time()
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        logger.error(f"Kafka error: {msg.error()}")
                        METRICS.kafka_errors.inc()
                        continue

                # Parse raw message
                raw_log = self._parse_kafka_message(msg)
                batch.append(raw_log)

                # Process batch if full
                if len(batch) >= self.batch_size:
                    await self._process_batch(batch)
                    batch = []
                    last_process_time = time.time()

            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                METRICS.processing_errors.inc()
                await asyncio.sleep(1)

        # Process remaining batch
        if batch:
            await self._process_batch(batch)

    def _parse_kafka_message(self, msg) -> RawLog:
        """Parse Kafka message into RawLog."""
        headers = {}
        if msg.headers():
            headers = {k: v.decode("utf-8") for k, v in msg.headers()}

        return RawLog(
            raw_message=msg.value().decode("utf-8"),
            topic=msg.topic(),
            partition=msg.partition(),
            offset=msg.offset(),
            timestamp=datetime.fromtimestamp(msg.timestamp()[1] / 1000),
            key=msg.key().decode("utf-8") if msg.key() else None,
            headers=headers
        )

    async def _process_batch(self, batch: list[RawLog]):
        """Process a batch of raw logs."""
        if not batch:
            return

        start_time = time.time()
        logger.debug(f"Processing batch of {len(batch)} logs")

        try:
            # Parse logs
            parsed_logs = [self.parser.parse(log.raw_message) for log in batch]

            # Extract messages for classification
            messages = [p.get("message", log.raw_message) for p, log in zip(parsed_logs, batch, strict=False)]

            # Classify batch
            predictions = await self.classifier.predict_batch(messages)

            # Create classified logs
            classified_logs = []
            for raw_log, parsed, pred in zip(batch, parsed_logs, predictions, strict=False):
                classified = ClassifiedLog(
                    raw_log=raw_log,
                    parsed_data=parsed,
                    category=pred["category"],
                    confidence=pred["confidence"],
                    model_used=pred.get("model", "ensemble"),
                    explanation=pred.get("explanation"),
                    processing_time_ms=(time.time() - start_time) * 1000 / len(batch)
                )
                classified_logs.append(classified)

            # Route classified logs
            await self.router.route_batch(classified_logs)

            # Commit offsets
            self.consumer.commit(asynchronous=False)

            # Update metrics
            processing_time = time.time() - start_time
            METRICS.logs_processed.inc(len(batch))
            METRICS.batch_processing_time.observe(processing_time)

            for log in classified_logs:
                METRICS.classification_distribution.labels(category=log.category).inc()

            logger.debug(
                f"Processed {len(batch)} logs in {processing_time*1000:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Error processing batch: {e}", exc_info=True)
            METRICS.processing_errors.inc(len(batch))
            raise


class LogProducer:
    """
    Kafka producer for sending classified logs to output topics.
    """

    def __init__(self, config: dict[str, Any]):
        from confluent_kafka import Producer

        self.config = config
        self.producer = Producer({
            "bootstrap.servers": config["bootstrap_servers"],
            "acks": config.get("producer", {}).get("acks", "all"),
            "retries": config.get("producer", {}).get("retries", 3),
            "batch.size": config.get("producer", {}).get("batch_size", 16384),
            "linger.ms": config.get("producer", {}).get("linger_ms", 10),
        })

    def send(self, topic: str, message: dict[str, Any], key: str | None = None):
        """Send message to Kafka topic."""
        try:
            self.producer.produce(
                topic=topic,
                key=key.encode("utf-8") if key else None,
                value=json.dumps(message).encode("utf-8"),
                callback=self._delivery_callback
            )
            self.producer.poll(0)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    def _delivery_callback(self, err, msg):
        """Callback for message delivery."""
        if err:
            logger.error(f"Message delivery failed: {err}")
            METRICS.kafka_delivery_errors.inc()
        else:
            METRICS.kafka_messages_sent.inc()

    def flush(self, timeout: float = 10.0):
        """Flush pending messages."""
        self.producer.flush(timeout)
