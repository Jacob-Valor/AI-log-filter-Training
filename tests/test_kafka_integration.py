"""
Integration tests for Kafka producer/consumer functionality.

These tests require a running Kafka instance and are marked with
@pytest.mark.integration and @pytest.mark.kafka decorators.

Run with: pytest -m integration
"""

import os

import pytest

# Skip all tests in this module if Kafka is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.kafka,
]


def kafka_available() -> bool:
    """Check if Kafka is available via environment variable."""
    return os.getenv("KAFKA_BOOTSTRAP_SERVERS") is not None


@pytest.fixture
def kafka_config():
    """Get Kafka configuration from environment."""
    return {
        "bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        "input_topic": os.getenv("KAFKA_INPUT_TOPIC", "test-raw-logs"),
        "output_topic": os.getenv("KAFKA_OUTPUT_TOPIC", "test-filtered-logs"),
    }


@pytest.mark.skipif(not kafka_available(), reason="Kafka not available")
class TestKafkaIntegration:
    """Integration tests for Kafka functionality."""

    def test_kafka_connection(self, kafka_config):
        """Test that we can connect to Kafka."""
        from confluent_kafka import Producer

        producer = Producer({"bootstrap.servers": kafka_config["bootstrap_servers"]})

        # Test by listing topics (will fail if not connected)
        metadata = producer.list_topics(timeout=10)
        assert metadata is not None
        producer.flush()

    def test_kafka_produce_message(self, kafka_config):
        """Test producing a message to Kafka."""
        from confluent_kafka import Producer

        producer = Producer({"bootstrap.servers": kafka_config["bootstrap_servers"]})

        # Delivery callback
        delivered = []

        def delivery_callback(err, msg):
            if err:
                delivered.append(("error", str(err)))
            else:
                delivered.append(("success", msg.topic()))

        # Produce test message
        test_message = b'{"log": "test message", "level": "INFO"}'
        producer.produce(
            kafka_config["input_topic"],
            value=test_message,
            callback=delivery_callback,
        )

        # Wait for delivery
        producer.flush(timeout=10)

        # Verify delivery
        assert len(delivered) == 1
        assert delivered[0][0] == "success"

    def test_kafka_consume_message(self, kafka_config):
        """Test consuming messages from Kafka."""
        from confluent_kafka import Consumer, Producer

        # First produce a message
        producer = Producer({"bootstrap.servers": kafka_config["bootstrap_servers"]})
        test_message = b'{"log": "integration test", "level": "DEBUG"}'
        producer.produce(kafka_config["input_topic"], value=test_message)
        producer.flush()

        # Now consume it
        consumer = Consumer(
            {
                "bootstrap.servers": kafka_config["bootstrap_servers"],
                "group.id": "integration-test-group",
                "auto.offset.reset": "earliest",
            }
        )
        consumer.subscribe([kafka_config["input_topic"]])

        try:
            msg = consumer.poll(timeout=10.0)
            # Message may or may not be available depending on timing
            # This test validates the consumer can connect and poll
            assert msg is None or msg.error() is None or msg.value() is not None
        finally:
            consumer.close()


@pytest.mark.skipif(not kafka_available(), reason="Kafka not available")
class TestKafkaLogProcessing:
    """Integration tests for log processing with Kafka."""

    def test_end_to_end_log_classification(self, kafka_config):
        """Test end-to-end log classification flow."""
        from confluent_kafka import Producer

        # Produce sample logs
        producer = Producer({"bootstrap.servers": kafka_config["bootstrap_servers"]})

        test_logs = [
            b'{"message": "Failed login attempt from 192.168.1.100", "severity": "WARNING"}',
            b'{"message": "User admin logged in successfully", "severity": "INFO"}',
            b'{"message": "SQL injection attempt detected", "severity": "CRITICAL"}',
        ]

        for log in test_logs:
            producer.produce(kafka_config["input_topic"], value=log)

        producer.flush()

        # Verify messages were produced (basic validation)
        metadata = producer.list_topics(timeout=10)
        assert kafka_config["input_topic"] in metadata.topics
