from datetime import UTC, datetime
from typing import Any

from src.monitoring.metrics import METRICS
from src.routing.destinations.base import BaseDestination
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ColdStorageDestination(BaseDestination):
    """Store logs in cold storage (S3, Azure Blob, etc.)."""

    def __init__(self, config: dict[str, Any]):
        super().__init__("cold_storage", config)
        self.storage_type = config.get("type", "local")
        self.bucket = config.get("bucket", "log-archive")
        self.partition_by = config.get("partition_by", ["date", "category"])
        self.compression = config.get("compression", "gzip")
        self.buffer: list[dict[str, Any]] = []
        self.buffer_size = config.get("batch_size", 10000)

    async def send(self, logs: list[dict[str, Any]]):
        """Buffer logs and flush when full."""
        self.buffer.extend(logs)

        if len(self.buffer) >= self.buffer_size:
            await self._flush()

    async def _flush(self):
        """Flush buffer to storage."""
        if not self.buffer:
            return

        try:
            # Generate partition path
            now = datetime.now(UTC)
            partition_path = f"year={now.year}/month={now.month:02d}/day={now.day:02d}"
            filename = f"logs_{now.strftime('%Y%m%d_%H%M%S')}.json.gz"

            # In production, this would write to S3/Azure/GCS
            logger.info("Flushing %s logs to %s/%s", len(self.buffer), partition_path, filename)

            # Clear buffer
            self.buffer = []

        except Exception as e:
            logger.error("Failed to flush to cold storage: %s", e)
            METRICS.routing_errors.labels(destination="cold_storage").inc()
            raise

    async def close(self):
        """Flush remaining logs and close."""
        await self._flush()
