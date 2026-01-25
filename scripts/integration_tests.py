#!/usr/bin/env python3
"""
Integration Test Framework for AI Log Filter

Tests integration with external systems:
- Kafka (producer/consumer)
- QRadar (API client)
- S3 (cold storage)

Usage:
    python -m scripts.integration_tests --help
    python -m scripts.integration_tests --kafka --qradar --all
"""

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class IntegrationTestConfig:
    """Configuration for integration tests."""

    kafka_brokers: str = "localhost:9092"
    kafka_topic: str = "ai-log-filter-input"
    kafka_output_topic: str = "ai-log-filter-output"
    qradar_host: str = "qradar.example.com"
    qradar_token: str = ""
    qradar_verify_ssl: bool = True
    s3_bucket: str = ""
    s3_prefix: str = "ai-log-filter/"
    test_messages: int = 100
    timeout_seconds: int = 60


class KafkaIntegrationTests:
    """Integration tests for Kafka connectivity and functionality."""

    def __init__(self, config: IntegrationTestConfig):
        self.config = config
        self.passed = 0
        self.failed = 0
        self.errors = []

    async def test_connection(self) -> bool:
        """Test Kafka connection."""
        test_name = "Kafka Connection"
        logger.info(f"Running: {test_name}")

        try:
            # Try to import and create consumer
            from confluent_kafka import Consumer

            conf = {
                "bootstrap.servers": self.config.kafka_brokers,
                "group.id": "test-consumer",
                "auto.offset.reset": "earliest",
            }

            consumer = Consumer(conf)

            # List topics to verify connection
            metadata = consumer.list_topics(timeout=10)

            consumer.close()

            logger.info(f"✅ {test_name}: Connected to {self.config.kafka_brokers}")
            logger.info(f"   Available topics: {list(metadata.topics.keys())[:10]}...")
            self.passed += 1
            return True

        except ImportError:
            logger.warning(f"⚠️  {test_name}: confluent_kafka not installed - skipping")
            self.errors.append((test_name, "confluent_kafka not installed"))
            return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def test_producer(self) -> bool:
        """Test Kafka producer functionality."""
        test_name = "Kafka Producer"
        logger.info(f"Running: {test_name}")

        try:
            from confluent_kafka import Producer

            conf = {
                "bootstrap.servers": self.config.kafka_brokers,
                "acks": "all",
            }

            producer = Producer(conf)

            # Test message delivery
            test_message = {
                "id": "test-001",
                "timestamp": datetime.now(UTC).isoformat(),
                "source": "integration-test",
                "raw_message": "Test message for integration testing",
            }

            delivered = asyncio.Event()

            def delivery_callback(err, msg):
                if err:
                    logger.error(f"Delivery failed: {err}")
                else:
                    delivered.set()

            producer.produce(
                self.config.kafka_topic,
                key="test-001",
                value=json.dumps(test_message),
                callback=delivery_callback,
            )

            # Wait for delivery with timeout
            try:
                await asyncio.wait_for(delivered.wait(), timeout=10.0)
            except TimeoutError:
                raise Exception("Message delivery timed out")

            producer.flush(timeout=5)

            logger.info(f"✅ {test_name}: Message delivered successfully")
            self.passed += 1
            return True

        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def test_consumer(self) -> bool:
        """Test Kafka consumer functionality."""
        test_name = "Kafka Consumer"
        logger.info(f"Running: {test_name}")

        try:
            from confluent_kafka import Consumer, KafkaError

            conf = {
                "bootstrap.servers": self.config.kafka_brokers,
                "group.id": f"test-consumer-{int(time.time())}",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }

            consumer = Consumer(conf)
            consumer.subscribe([self.config.kafka_topic])

            # Poll for messages with timeout
            messages_received = 0
            start_time = time.time()

            while time.time() - start_time < 10:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise Exception(msg.error())
                messages_received += 1
                break  # Got at least one message

            consumer.close()

            if messages_received > 0:
                logger.info(f"✅ {test_name}: Received {messages_received} message(s)")
            else:
                logger.warning(f"⚠️  {test_name}: No messages available (may be OK)")

            self.passed += 1
            return True

        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def test_topic_creation(self) -> bool:
        """Test Kafka topic creation."""
        test_name = "Kafka Topic Creation"
        logger.info(f"Running: {test_name}")

        try:
            from confluent_kafka.admin import AdminClient, NewTopic

            admin = AdminClient({"bootstrap.servers": self.config.kafka_brokers})

            # Check if topic exists
            metadata = admin.list_topics(timeout=10)
            if self.config.kafka_topic in metadata.topics:
                logger.info(f"Topic {self.config.kafka_topic} already exists")
                self.passed += 1
                return True

            # Create topic
            new_topic = NewTopic(
                self.config.kafka_topic,
                num_partitions=3,
                replication_factor=1,
            )

            futures = admin.create_topics([new_topic])

            for topic, future in futures.items():
                try:
                    future.result(timeout=10)
                    logger.info(f"✅ {test_name}: Created topic '{topic}'")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"Topic {topic} already exists")
                    else:
                        raise

            self.passed += 1
            return True

        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def run_all(self) -> dict[str, Any]:
        """Run all Kafka integration tests."""
        logger.info("\n" + "=" * 60)
        logger.info("KAFKA INTEGRATION TESTS")
        logger.info("=" * 60)

        await self.test_connection()
        await self.test_topic_creation()
        await self.test_producer()
        await self.test_consumer()

        return {
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
        }


class QRadarIntegrationTests:
    """Integration tests for QRadar API connectivity."""

    def __init__(self, config: IntegrationTestConfig):
        self.config = config
        self.passed = 0
        self.failed = 0
        self.errors = []

    async def test_connection(self) -> bool:
        """Test QRadar API connection."""
        test_name = "QRadar Connection"
        logger.info(f"Running: {test_name}")

        if not self.config.qradar_token:
            logger.warning(f"⚠️  {test_name}: QRadar token not configured - skipping")
            self.errors.append((test_name, "Token not configured"))
            return False

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{self.config.qradar_host}/api/system/info",
                    headers={"SEC": self.config.qradar_token},
                    verify=self.config.qradar_verify_ssl,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    info = response.json()
                    logger.info(
                        f"✅ {test_name}: Connected to QRadar {info.get('version')}"
                    )
                    logger.info(f"   Hostname: {info.get('hostname')}")
                    self.passed += 1
                    return True
                else:
                    raise Exception(
                        f"HTTP {response.status_code}: {response.text[:100]}"
                    )

        except ImportError:
            logger.warning(f"⚠️  {test_name}: httpx not installed - skipping")
            self.errors.append((test_name, "httpx not installed"))
            return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def test_event_submission(self) -> bool:
        """Test event submission to QRadar."""
        test_name = "QRadar Event Submission"
        logger.info(f"Running: {test_name}")

        if not self.config.qradar_token:
            logger.warning(f"⚠️  {test_name}: QRadar token not configured - skipping")
            return False

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                # Test event payload (LEEF format)
                test_event = {
                    "events": [
                        {
                            "device_time": datetime.utcnow().isoformat(),
                            "logsource_id": 116,  # Generic log source
                            "sourceip": "192.168.1.100",
                            "severity": 5,
                            "qid": 5013001,
                            "content": "LEEF:1.0|AI-Log-Filter|Test|1.0|5|src=192.168.1.100",
                        }
                    ]
                }

                response = await client.post(
                    f"https://{self.config.qradar_host}/api/siem/events",
                    headers={"SEC": self.config.qradar_token},
                    json=test_event,
                    verify=self.config.qradar_verify_ssl,
                    timeout=30.0,
                )

                if response.status_code in [200, 201, 202]:
                    logger.info(f"✅ {test_name}: Event submitted successfully")
                    self.passed += 1
                    return True
                else:
                    raise Exception(
                        f"HTTP {response.status_code}: {response.text[:100]}"
                    )

        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def test_offense_query(self) -> bool:
        """Test offense retrieval from QRadar."""
        test_name = "QRadar Offense Query"
        logger.info(f"Running: {test_name}")

        if not self.config.qradar_token:
            logger.warning(f"⚠️  {test_name}: QRadar token not configured - skipping")
            return False

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://{self.config.qradar_host}/api/siem/offenses?filter=status%20!=%27CLOSED%27&limit=10",
                    headers={"SEC": self.config.qradar_token},
                    verify=self.config.qradar_verify_ssl,
                    timeout=30.0,
                )

                if response.status_code == 200:
                    offenses = response.json()
                    logger.info(
                        f"✅ {test_name}: Retrieved {len(offenses)} open offenses"
                    )
                    self.passed += 1
                    return True
                else:
                    raise Exception(
                        f"HTTP {response.status_code}: {response.text[:100]}"
                    )

        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def run_all(self) -> dict[str, Any]:
        """Run all QRadar integration tests."""
        logger.info("\n" + "=" * 60)
        logger.info("QRADAR INTEGRATION TESTS")
        logger.info("=" * 60)

        await self.test_connection()
        await self.test_offense_query()
        await self.test_event_submission()

        return {
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
        }


class S3IntegrationTests:
    """Integration tests for S3 cold storage."""

    def __init__(self, config: IntegrationTestConfig):
        self.config = config
        self.passed = 0
        self.failed = 0
        self.errors = []

    async def test_connection(self) -> bool:
        """Test S3 connection."""
        test_name = "S3 Connection"
        logger.info(f"Running: {test_name}")

        if not self.config.s3_bucket:
            logger.warning(f"⚠️  {test_name}: S3 bucket not configured - skipping")
            self.errors.append((test_name, "Bucket not configured"))
            return False

        try:
            import boto3

            s3 = boto3.client("s3")

            # List buckets to verify connection
            response = s3.list_buckets()

            bucket_names = [b["Name"] for b in response["Buckets"]]

            if self.config.s3_bucket in bucket_names:
                logger.info(
                    f"✅ {test_name}: Connected to S3, bucket '{self.config.s3_bucket}' exists"
                )
            else:
                logger.warning(
                    f"⚠️  {test_name}: Bucket '{self.config.s3_bucket}' not found in account"
                )

            self.passed += 1
            return True

        except ImportError:
            logger.warning(f"⚠️  {test_name}: boto3 not installed - skipping")
            self.errors.append((test_name, "boto3 not installed"))
            return False
        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def test_put_object(self) -> bool:
        """Test S3 put object."""
        test_name = "S3 Put Object"
        logger.info(f"Running: {test_name}")

        if not self.config.s3_bucket:
            logger.warning(f"⚠️  {test_name}: S3 bucket not configured - skipping")
            return False

        try:
            import boto3

            s3 = boto3.client("s3")

            test_key = f"{self.config.s3_prefix}test/test_{int(time.time())}.json"
            test_data = {
                "test": True,
                "timestamp": datetime.now(UTC).isoformat(),
                "message": "Integration test data",
            }

            s3.put_object(
                Bucket=self.config.s3_bucket,
                Key=test_key,
                Body=json.dumps(test_data),
                ContentType="application/json",
            )

            logger.info(
                f"✅ {test_name}: Object uploaded to s3://{self.config.s3_bucket}/{test_key}"
            )
            self.passed += 1

            # Cleanup
            s3.delete_object(Bucket=self.config.s3_bucket, Key=test_key)

            return True

        except Exception as e:
            logger.error(f"❌ {test_name}: {e}")
            self.failed += 1
            self.errors.append((test_name, str(e)))
            return False

    async def run_all(self) -> dict[str, Any]:
        """Run all S3 integration tests."""
        logger.info("\n" + "=" * 60)
        logger.info("S3 INTEGRATION TESTS")
        logger.info("=" * 60)

        await self.test_connection()
        await self.test_put_object()

        return {
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
        }


async def run_integration_tests(
    test_kafka: bool = True,
    test_qradar: bool = True,
    test_s3: bool = True,
    config: IntegrationTestConfig | None = None,
) -> dict[str, Any]:
    """Run all integration tests."""

    if config is None:
        config = IntegrationTestConfig()

    results = {
        "kafka": None,
        "qradar": None,
        "s3": None,
        "summary": {
            "total_passed": 0,
            "total_failed": 0,
            "total_errors": 0,
        },
    }

    logger.info("\n" + "=" * 80)
    logger.info("AI LOG FILTER - INTEGRATION TESTS")
    logger.info("=" * 80)
    logger.info(f"Timestamp: {datetime.now(UTC).isoformat()}")
    logger.info("=" * 80)

    if test_kafka:
        kafka_tests = KafkaIntegrationTests(config)
        results["kafka"] = await kafka_tests.run_all()
        results["summary"]["total_passed"] += results["kafka"]["passed"]
        results["summary"]["total_failed"] += results["kafka"]["failed"]
        results["summary"]["total_errors"] += len(results["kafka"]["errors"])

    if test_qradar:
        qradar_tests = QRadarIntegrationTests(config)
        results["qradar"] = await qradar_tests.run_all()
        results["summary"]["total_passed"] += results["qradar"]["passed"]
        results["summary"]["total_failed"] += results["qradar"]["failed"]
        results["summary"]["total_errors"] += len(results["qradar"]["errors"])

    if test_s3:
        s3_tests = S3IntegrationTests(config)
        results["s3"] = await s3_tests.run_all()
        results["summary"]["total_passed"] += results["s3"]["passed"]
        results["summary"]["total_failed"] += results["s3"]["failed"]
        results["summary"]["total_errors"] += len(results["s3"]["errors"])

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("INTEGRATION TEST SUMMARY")
    logger.info("=" * 80)

    total = results["summary"]["total_passed"] + results["summary"]["total_failed"]

    logger.info(f"\nTotal Tests: {total}")
    logger.info(f"Passed: {results['summary']['total_passed']} ✅")
    logger.info(f"Failed: {results['summary']['total_failed']} ❌")
    logger.info(f"Errors/Skipped: {results['summary']['total_errors']} ⚠️")

    if results["summary"]["total_failed"] == 0:
        logger.info("\n🎉 All integration tests passed!")
    else:
        logger.info("\n⚠️  Some integration tests failed. Check the errors above.")

    logger.info("=" * 80)

    return results


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Integration Tests")
    parser.add_argument("--kafka", action="store_true", default=True)
    parser.add_argument("--no-kafka", action="store_false", dest="kafka")
    parser.add_argument("--qradar", action="store_true", default=True)
    parser.add_argument("--no-qradar", action="store_false", dest="qradar")
    parser.add_argument("--s3", action="store_true", default=True)
    parser.add_argument("--no-s3", action="store_false", dest="s3")
    parser.add_argument("--kafka-brokers", default="localhost:9092")
    parser.add_argument("--qradar-host", default="qradar.example.com")
    parser.add_argument("--qradar-token", default="")
    parser.add_argument("--s3-bucket", default="")

    args = parser.parse_args()

    config = IntegrationTestConfig(
        kafka_brokers=args.kafka_brokers,
        qradar_host=args.qradar_host,
        qradar_token=args.qradar_token,
        s3_bucket=args.s3_bucket,
    )

    results = await run_integration_tests(
        test_kafka=args.kafka,
        test_qradar=args.qradar,
        test_s3=args.s3,
        config=config,
    )

    # Exit with appropriate code
    if results["summary"]["total_failed"] == 0:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
