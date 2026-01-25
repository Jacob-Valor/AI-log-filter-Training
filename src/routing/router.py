"""
Log Router

Routes classified logs to appropriate destinations based on category.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from src.utils.logging import get_logger
from src.utils.metrics import METRICS

logger = get_logger(__name__)


class BaseDestination(ABC):
    """Base class for log destinations."""

    def __init__(self, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config

    @abstractmethod
    async def send(self, logs: list[dict[str, Any]]):
        """Send logs to destination."""
        pass

    @abstractmethod
    async def close(self):
        """Close connection to destination."""
        pass


class QRadarDestination(BaseDestination):
    """Send logs to IBM QRadar SIEM."""

    def __init__(self, config: dict[str, Any]):
        super().__init__("qradar", config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 443)
        self.token = config.get("token")
        self.verify_ssl = config.get("verify_ssl", True)
        self.timeout = config.get("timeout", 30)
        self._client = None

    async def _get_client(self):
        """Get or create HTTP client."""
        if self._client is None:
            try:
                import httpx

                self._client = httpx.AsyncClient(
                    base_url=f"https://{self.host}:{self.port}",
                    verify=self.verify_ssl,
                    timeout=self.timeout,
                    headers={"SEC": self.token, "Content-Type": "application/json"},
                )
            except ImportError:
                logger.warning("httpx not available, QRadar destination disabled")
                self._client = None
        return self._client

    async def send(self, logs: list[dict[str, Any]]):
        """Send logs to QRadar."""
        client = await self._get_client()
        if client is None:
            logger.debug(f"QRadar client not available, skipping {len(logs)} logs")
            return

        try:
            # Convert logs to LEEF format or JSON
            for log in logs:
                leef_message = self._to_leef(log)
                await self._send_syslog(leef_message)

            logger.debug(f"Sent {len(logs)} logs to QRadar")

        except Exception as e:
            logger.error(f"Failed to send logs to QRadar: {e}")
            METRICS.routing_errors.labels(destination="qradar").inc(len(logs))
            raise

    def _to_leef(self, log: dict[str, Any]) -> str:
        """Convert log to LEEF format."""
        # LEEF format: LEEF:Version|Vendor|Product|Version|EventID|Attributes
        timestamp = datetime.utcnow().isoformat()

        attributes = [
            f"devTime={timestamp}",
            f"cat={log.get('category', 'unknown')}",
            f"sev={self._get_severity(log.get('category'))}",
            f"msg={log.get('message', '')}",
            f"confidence={log.get('confidence', 0)}",
        ]

        return (
            f"LEEF:2.0|AILogFilter|LogClassifier|1.0|"
            f"{log.get('category', 'unknown')}|"
            f"{' '.join(attributes)}"
        )

    def _get_severity(self, category: str) -> int:
        """Map category to QRadar severity."""
        severity_map = {"critical": 10, "suspicious": 7, "routine": 3, "noise": 1}
        return severity_map.get(category, 5)

    async def _send_syslog(self, message: str):
        """Send message via syslog."""
        # In production, this would use actual syslog
        logger.debug(f"LEEF: {message[:100]}...")

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


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
            now = datetime.utcnow()
            partition_path = f"year={now.year}/month={now.month:02d}/day={now.day:02d}"
            filename = f"logs_{now.strftime('%Y%m%d_%H%M%S')}.json.gz"

            # In production, this would write to S3/Azure/GCS
            logger.info(f"Flushing {len(self.buffer)} logs to {partition_path}/{filename}")

            # Clear buffer
            self.buffer = []

        except Exception as e:
            logger.error(f"Failed to flush to cold storage: {e}")
            METRICS.routing_errors.labels(destination="cold_storage").inc()
            raise

    async def close(self):
        """Flush remaining logs and close."""
        await self._flush()


class SummaryDestination(BaseDestination):
    """Aggregate and summarize noise logs."""

    def __init__(self, config: dict[str, Any]):
        super().__init__("summary", config)
        self.window_seconds = config.get("aggregation_window_seconds", 3600)
        self.summaries: dict[str, dict[str, Any]] = {}

    async def send(self, logs: list[dict[str, Any]]):
        """Aggregate logs into summaries."""
        for log in logs:
            # Create summary key from log template
            template = self._extract_template(log.get("message", ""))

            if template not in self.summaries:
                self.summaries[template] = {
                    "template": template,
                    "count": 0,
                    "first_seen": datetime.utcnow().isoformat(),
                    "last_seen": None,
                    "sample": log,
                }

            self.summaries[template]["count"] += 1
            self.summaries[template]["last_seen"] = datetime.utcnow().isoformat()

        logger.debug(f"Aggregated {len(logs)} logs into {len(self.summaries)} summaries")

    def _extract_template(self, message: str) -> str:
        """Extract template from message by replacing variables."""
        import re

        # Replace IPs
        template = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", message)
        # Replace numbers
        template = re.sub(r"\b\d+\b", "<NUM>", template)
        # Replace UUIDs
        template = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "<UUID>",
            template,
            flags=re.IGNORECASE,
        )

        return template[:200]  # Limit template length

    async def get_summaries(self) -> list[dict[str, Any]]:
        """Get current summaries."""
        return list(self.summaries.values())

    async def close(self):
        """Export final summaries."""
        if self.summaries:
            logger.info(f"Final summary: {len(self.summaries)} unique log patterns")


class LogRouter:
    """
    Routes classified logs to appropriate destinations.

    Supports multiple destinations with different routing strategies:
    - immediate: Send immediately (for critical logs)
    - queue: Buffer and send in batches
    - batch: Large batch processing (for routine logs)
    - aggregate: Summarize and discard (for noise logs)
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.destinations: dict[str, BaseDestination] = {}
        self.routing_rules: dict[str, dict[str, Any]] = config.get("rules", {})

        # Queues for different routing strategies
        self.queues: dict[str, asyncio.Queue] = {}
        self._workers: list[asyncio.Task] = []

    async def initialize(self):
        """Initialize routing destinations."""
        logger.info("Initializing log router...")

        # Initialize QRadar
        if "qradar" in self.config:
            self.destinations["qradar"] = QRadarDestination(self.config["qradar"])

        # Initialize cold storage
        if "cold_storage" in self.config:
            self.destinations["cold_storage"] = ColdStorageDestination(self.config["cold_storage"])

        # Initialize summary aggregator
        self.destinations["summary"] = SummaryDestination(self.config.get("summary", {}))

        # Initialize queues
        for category in ["critical", "suspicious", "routine", "noise"]:
            self.queues[category] = asyncio.Queue()

        # Start queue workers
        self._start_workers()

        logger.info(f"Router initialized with {len(self.destinations)} destinations")

    def _start_workers(self):
        """Start background workers for queue processing."""
        for category, queue in self.queues.items():
            worker = asyncio.create_task(self._process_queue(category, queue))
            self._workers.append(worker)

    async def _process_queue(self, category: str, queue: asyncio.Queue):
        """Process logs from a queue."""
        batch = []
        batch_size = self.routing_rules.get(category, {}).get("batch_size", 100)

        while True:
            try:
                # Wait for logs with timeout
                try:
                    log = await asyncio.wait_for(queue.get(), timeout=5.0)
                    batch.append(log)
                except TimeoutError:
                    pass

                # Process batch if full or timeout
                if len(batch) >= batch_size or (batch and queue.empty()):
                    await self._route_batch(category, batch)
                    batch = []

            except asyncio.CancelledError:
                # Process remaining logs
                while not queue.empty():
                    batch.append(await queue.get())
                if batch:
                    await self._route_batch(category, batch)
                break
            except Exception as e:
                logger.error(f"Error processing {category} queue: {e}")

    async def route(self, log: dict[str, Any]):
        """Route a single log to appropriate destinations."""
        category = log.get("category", "routine")

        rule = self.routing_rules.get(category, {})
        method = rule.get("method", "queue")

        if method == "immediate":
            await self._route_immediate(category, log)
        else:
            await self.queues.get(category, self.queues["routine"]).put(log)

    async def route_batch(self, logs: list[Any]):
        """Route a batch of classified logs."""
        for log in logs:
            # Convert ClassifiedLog to dict if needed
            if hasattr(log, "to_dict"):
                log_dict = log.to_dict()
            else:
                log_dict = log

            await self.route(log_dict)

    async def _route_immediate(self, category: str, log: dict[str, Any]):
        """Route log immediately without queuing."""
        rule = self.routing_rules.get(category, {})
        destinations = rule.get("destinations", ["qradar"])

        for dest_name in destinations:
            if dest_name in self.destinations:
                try:
                    await self.destinations[dest_name].send([log])
                except Exception as e:
                    logger.error(f"Failed to route to {dest_name}: {e}")

    async def _route_batch(self, category: str, batch: list[dict[str, Any]]):
        """Route a batch of logs."""
        if not batch:
            return

        rule = self.routing_rules.get(category, {})
        destinations = rule.get("destinations", ["cold_storage"])

        for dest_name in destinations:
            if dest_name in self.destinations:
                try:
                    await self.destinations[dest_name].send(batch)
                except Exception as e:
                    logger.error(f"Failed to route batch to {dest_name}: {e}")

    async def close(self):
        """Shutdown router and flush all queues."""
        logger.info("Shutting down router...")

        # Cancel workers
        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)

        # Close destinations
        for dest in self.destinations.values():
            await dest.close()

        logger.info("Router shutdown complete")
